from netmiko import ConnectHandler
from hashlib import sha256
from pathlib import Path
from ..settings import settings


class NonRetryableBackupError(Exception):
    """A backup failure that retrying won't fix (e.g. the device rejected the
    command itself) - as opposed to transient issues like a timeout or a busy
    device. Callers should fail fast on this instead of retrying, both because
    it wastes time on a guaranteed-repeat failure and because hammering a
    device with repeated login/command attempts can trip its own lockout
    policy, breaking even manual troubleshooting logins right after."""
    pass

# device_type hanya untuk SSH
VENDOR_MAP = {
    "Cisco (IOS Router/Switch)": "cisco_ios",
    "Cisco (ASA Firewall)": "cisco_asa",
    "Cisco (NXOS Data Center)": "cisco_nxos",
    "Cisco (WLC Controller)": "cisco_wlc_ssh",
    "Allied Telesis (AWPlus)": "cisco_ios",
    "Aruba (AOS-CX Switch)": "aruba_aoscx",
    "Aruba (AOS AP/Controller)": "aruba_os",
    "MikroTik (RouterOS)": "mikrotik_routeros",
    "MikroTik (SwitchOS)": "mikrotik_switchos",
    "Huawei (Switch/AP)": "huawei",
    "Huawei (OLT)": "huawei_olt",
    "Huawei (SmartAX)": "huawei_smartax",
    "Fortinet (FortiGate)": "fortinet",
    "Juniper (JunOS)": "juniper",
    # legacy
    "Cisco": "cisco_ios",
    "Juniper": "juniper",
    "Mikrotik": "mikrotik_routeros",
    "Fortinet": "fortinet",
}

def _device_type_ssh(vendor: str) -> str:
    return VENDOR_MAP.get(vendor, "cisco_ios")


# Known CLI "invalid/unrecognized command" error signatures across vendors.
# A device that doesn't understand the config-fetch command (wrong device_type,
# wrong privilege level, unsupported syntax on that firmware, etc.) replies with
# one of these instead of real config text - that reply must NOT be saved as a backup.
_CLI_ERROR_SIGNATURES = [
    "invalid input detected",       # Cisco IOS/ASA/NXOS, Allied Telesis, Aruba AOS
    "unrecognized command",         # Cisco, Huawei, Aruba AOS-CX
    "ambiguous command",            # Cisco
    "incomplete command",           # Cisco
    "unknown command",              # Juniper, Aruba, generic
    "wrong parameter found",        # Huawei
    "bad command name",             # MikroTik
    "no such item",                 # MikroTik
    "expected end of command",      # MikroTik
    "syntax error",                 # Juniper, Fortinet
    "command fail",                 # Fortinet
    "entry not found",              # Fortinet
]


def _looks_like_cli_error(output: str) -> bool:
    """Detect a device CLI error response so it isn't mistaken for real config content."""
    lowered = output.lower()
    return any(sig in lowered for sig in _CLI_ERROR_SIGNATURES)


def _get_config_command(vendor: str) -> str:
    """Get the appropriate command to retrieve configuration based on vendor."""
    vendor_lower = vendor.lower()
    
    # MikroTik uses /export
    if "mikrotik" in vendor_lower:
        return "/export"
    
    # Juniper uses show configuration
    elif "juniper" in vendor_lower or "junos" in vendor_lower:
        return "show configuration"
    
    # Fortinet uses show (without running-config)
    elif "fortinet" in vendor_lower or "fortigate" in vendor_lower:
        return "show"
    
    # Huawei uses display current-configuration
    elif "huawei" in vendor_lower:
        return "display current-configuration"
    
    # Aruba AOS-CX uses show running-config
    elif "aruba" in vendor_lower and "aoscx" in vendor_lower:
        return "show running-config"
    
    # Aruba AOS uses show running-config
    elif "aruba" in vendor_lower:
        return "show running-config"
    
    # Cisco and Allied Telesis (default)
    else:
        return "show running-config"


def _read_all(tn, timeout=3):
    """Read until connection is idle for 'timeout' seconds. Handles large configs."""
    import time
    buf = b""
    last = time.time()

    while time.time() - last < timeout:
        data = tn.read_very_eager()
        if data:
            buf += data
            last = time.time()
        time.sleep(0.2)

    return buf


def _connect_telnet_manual(
    host: str,
    username: str,
    password: str,
    secret: str | None,
    port: int,
    session_log: str,
):
    """Telnet login manual using raw telnetlib - PROVEN WORKING!"""
    import telnetlib  # type: ignore  # deprecated but still works in Python 3.11
    import time
    
    # Use telnetlib directly
    tn = telnetlib.Telnet(host, port, timeout=30)
    time.sleep(1)
    
    # FLEXIBLE login prompt detection (Username, login, User Name, etc)
    index, match, text = tn.expect([
        b"Username:", b"username:", b"User Name:", b"User:", 
        b"Login:", b"login:", b"USER:"
    ], timeout=15)
    
    # Send username
    tn.write(username.encode('ascii') + b"\n")
    time.sleep(1)
    
    # Wait for password prompt (flexible detection)
    tn.expect([b"Password:", b"password:", b"PASS:"], timeout=15)
    tn.write(password.encode('ascii') + b"\n")
    time.sleep(2)
    
    # Enter enable mode if secret provided
    if secret:
        tn.write(b"enable\n")
        time.sleep(1)
        tn.expect([b"Password:", b"password:"], timeout=15)
        tn.write(secret.encode('ascii') + b"\n")
        time.sleep(2)
    
    # Disable paging (try multiple times for reliability)
    tn.write(b"terminal length 0\n")
    time.sleep(1)
    tn.read_very_eager()  # Clear buffer
    
    # Double-send for stubborn devices
    tn.write(b"terminal length 0\n")
    time.sleep(0.5)
    tn.read_very_eager()
    
    return tn


def _connect_ssh_normal(
    vendor: str,
    host: str,
    username: str,
    password: str,
    secret: str | None,
    port: int,
    session_log: str,
):
    """SSH biasa pakai mapping vendor."""
    device_type = _device_type_ssh(vendor)
    device = {
        "device_type": device_type,
        "host": host,
        "username": username,
        "password": password,
        "secret": secret,
        "port": port,
        "session_log": session_log,
        "fast_cli": False,
        # Fix: support MikroTik & perangkat lama yang pakai algoritma SSH lama (ssh-rsa)
        # Paramiko versi baru memblokir algoritma ini by default
        "disabled_algorithms": {
            "pubkeys": ["rsa-sha2-256", "rsa-sha2-512"],
        },
        "conn_timeout": 30,
    }

    conn = ConnectHandler(**device)

    # Always try to reach privileged/enable mode, even if no enable secret was
    # configured - some devices allow "enable" with a blank password. Previously
    # this was skipped entirely whenever `secret` was empty, which left the
    # session in user EXEC mode on devices that need it, causing commands like
    # 'show running-config' to be rejected as "Invalid input detected" instead
    # of a clear permission error.
    # check_state=False: don't trust check_enable_mode()'s prompt detection here -
    # on some devices it can misreport already being privileged (skipping enable()
    # entirely, including netmiko's own internal check inside enable() by default).
    # Forcing the attempt is harmless on an already-privileged session and is the
    # only way to reliably escalate on ones that aren't. Wrapped safely: some
    # platforms don't support enable mode at all.
    try:
        conn.enable(check_state=False)
        conn._abs_enable_error = None  # type: ignore[attr-defined]
    except Exception as e:
        # Don't swallow this silently - stash it on the connection so
        # fetch_running_config can report exactly why enable() failed
        # (wrong/missing secret, unexpected prompt, timeout, etc.) instead
        # of just showing the downstream "Invalid input detected" reply.
        conn._abs_enable_error = str(e)  # type: ignore[attr-defined]

    return conn


def fetch_running_config(
    *,
    vendor: str,
    host: str,
    username: str,
    password: str,
    secret: str | None,
    protocol: str,
    port: int,
    cmd: str | None = None,
) -> tuple[str, bytes]:
    """
    - Kalau protocol = 'Telnet'  -> pakai terminal_server + login manual
    - Kalau protocol = 'SSH'     -> pakai Netmiko normal (device_type dari vendor)
    """
    import tempfile
    import os
    import traceback

    session_log = os.path.join(tempfile.gettempdir(), f"netmiko_{host}.log")

    conn = None
    output = ""
    tn = None  # For telnetlib connection
    session_log_tail = ""  # raw transcript for diagnostics, captured before cleanup deletes it
    enable_error = "n/a (telnet path)"  # why conn.enable() failed, if it did (SSH path only)

    try:
        # SAFE protocol detection (strip whitespace)
        proto = (protocol or "").strip().lower()

        if proto == "telnet":
            tn = _connect_telnet_manual(
                host=host,
                username=username,
                password=password,
                secret=secret,
                port=port,
                session_log=session_log,
            )
            
            # Send command to get config using telnetlib
            command = cmd or _get_config_command(vendor)
            tn.write(command.encode('ascii') + b"\n")
            import time
            time.sleep(2)  # Initial wait
            
            # Read ALL output using robust method (handles large configs)
            raw_output = _read_all(tn, timeout=3)
            
            # Handle --More-- prompts if paging not fully disabled
            while b"--More--" in raw_output or b"-- More --" in raw_output:
                tn.write(b" ")
                time.sleep(1)
                additional = _read_all(tn, timeout=2)
                raw_output += additional
                if not additional:
                    break
            
            # Decode output
            output = raw_output.decode('ascii', errors='ignore')
            
            # Clean up output - remove command echo by splitting on command
            if command in output:
                output = output.split(command, 1)[-1]
            
            # Remove trailing prompt/garbage
            output = output.strip()
            
            # Remove lines that are just prompts (but keep config lines with #)
            lines = output.split('\n')
            cleaned = []
            for line in lines:
                stripped = line.strip()
                # Skip empty lines and pure prompt lines
                if not stripped or (stripped.endswith('#') and len(stripped) < 20) or (stripped.endswith('>') and len(stripped) < 20):
                    continue
                cleaned.append(line)
            output = '\n'.join(cleaned)
            
        else:
            conn = _connect_ssh_normal(
                vendor=vendor,
                host=host,
                username=username,
                password=password,
                secret=secret,
                port=port,
                session_log=session_log,
            )
            
            enable_error = getattr(conn, "_abs_enable_error", "unknown") or "succeeded, no error"

            # Get appropriate command for this vendor
            config_cmd = cmd or _get_config_command(vendor)
            output = conn.send_command(config_cmd, read_timeout=60)

    except Exception as e:
        error_msg = str(e)
        # Session log available at: session_log (for debugging if needed)
        raise Exception(f"Connection failed: {host} | Error: {error_msg}")

    finally:
        # Capture a tail of the raw session transcript before it gets deleted below,
        # so a CLI-error failure message can show exactly what the device sent back
        # (including the enable attempt) instead of just the final command's reply.
        try:
            if os.path.exists(session_log):
                with open(session_log, "rb") as f:
                    session_log_tail = f.read().decode("utf-8", errors="ignore")[-800:]
        except Exception:
            pass

        # Cleanup connections
        if tn:
            try:
                tn.write(b"exit\n")
                import time
                time.sleep(1)
                tn.close()
            except Exception:
                pass
        
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass
            # hard-close socket
            try:
                if hasattr(conn, "remote_conn"):
                    conn.remote_conn.close()
            except Exception:
                pass

        try:
            if os.path.exists(session_log):
                os.remove(session_log)
        except Exception:
            pass

    # Validasi isi output sebelum dianggap sukses
    # Limit diubah menjadi 10 karakter karena beberapa device (seperti MikroTik SwitchOS atau switch basic) 
    # bisa memiliki konfigurasi yang sangat pendek (sekitar 20-40 karakter).
    if len(output.strip()) < 10:
        raise Exception("Backup failure: Output is empty or suspiciously short (less than 10 chars). The device might be busy, slow to respond, or the prompt was not detected correctly.")

    if _looks_like_cli_error(output):
        transcript_note = f" | Session transcript tail: {session_log_tail!r}" if session_log_tail else ""
        raise NonRetryableBackupError(
            f"Backup failure: Device returned a command error instead of configuration "
            f"(command '{cmd or _get_config_command(vendor)}' may be wrong for this device's "
            f"vendor/firmware, or the session wasn't in the right privilege level). "
            f"Raw reply: {output.strip()[:200]!r} | enable() result: {enable_error!r}{transcript_note}"
        )

    # Simpan ke file
    content = output.encode()
    filehash = sha256(content).hexdigest()[:8]
    Path(settings.BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    filename = f"{host}_{filehash}.cfg"
    fullpath = Path(settings.BACKUP_DIR) / filename
    fullpath.write_bytes(content)

    return str(fullpath), content
