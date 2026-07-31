from netmiko import ConnectHandler
from hashlib import sha256
from pathlib import Path
import re
from ..settings import settings


class NonRetryableBackupError(Exception):
    """A backup failure that retrying won't fix (e.g. the device rejected the
    command itself) - as opposed to transient issues like a timeout or a busy
    device. Callers should fail fast on this instead of retrying, both because
    it wastes time on a guaranteed-repeat failure and because hammering a
    device with repeated login/command attempts can trip its own lockout
    policy, breaking even manual troubleshooting logins right after."""
    pass


class IncompleteExportError(Exception):
    """Raised when a device (currently: MikroTik) reports it failed to
    export one or more config sections (RouterOS writes a literal
    '#error exporting <path>' line for each one), but most of the config
    still came through fine. Carries the partial content so a caller that's
    exhausted its retries can save it as a best-effort backup instead of
    ending up with nothing, while still trying a clean retry first (a
    fresh attempt often succeeds outright)."""
    def __init__(self, message: str, content: bytes, missing_sections: list[str]):
        super().__init__(message)
        self.content = content
        self.missing_sections = missing_sections


class TelnetAuthError(Exception):
    """Raised when the device itself rejected the username/password/enable
    secret during the Telnet login sequence (e.g. '% Bad passwords'), as
    opposed to a network/socket-level failure. Distinguished from generic
    connection errors so the caller can surface a clear, actionable message
    instead of the confusing downstream symptom (the device closes the
    socket after rejecting the login, so the next write() raises a raw
    'Broken pipe' if this isn't caught first)."""
    pass


_TELNET_AUTH_FAILURE_MARKERS = (
    b"% Bad passwords",
    b"% Bad secrets",
    b"% Login invalid",
    b"% Access denied",
    b"Authentication failed",
    b"Access denied",
)


def save_backup_file(host: str, content: bytes) -> Path:
    """Write a fetched config to BACKUP_DIR and return its path. Shared by
    fetch_running_config's normal success path and by callers (scheduler,
    manual-trigger job runner) that save a best-effort partial backup after
    catching IncompleteExportError on the final retry attempt."""
    filehash = sha256(content).hexdigest()[:8]
    Path(settings.BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    filename = f"{host}_{filehash}.cfg"
    fullpath = Path(settings.BACKUP_DIR) / filename
    fullpath.write_bytes(content)
    return fullpath


def _redact(text: str, *secret_values: str | None) -> str:
    """Scrub known credential values out of a string before it's put
    somewhere less trusted than the connection code itself (job logs,
    which viewer-role users can read via GET /jobs)."""
    for value in secret_values:
        if value:
            text = text.replace(value, "***REDACTED***")
    return text

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
    connect_timeout: int = 30,
):
    """Telnet login manual using raw telnetlib - PROVEN WORKING!"""
    import telnetlib  # type: ignore  # deprecated but still works in Python 3.11
    import time

    def _log(data: bytes):
        # Unlike netmiko (SSH path), telnetlib has no built-in session_log -
        # append the raw exchange ourselves so Telnet failures get the same
        # diagnostic transcript tail (session_log_tail) that SSH failures do,
        # instead of always showing "n/a (telnet path)". Credentials written
        # here are scrubbed by _redact() wherever this file is later read.
        if not data:
            return
        try:
            with open(session_log, "ab") as f:
                f.write(data)
        except Exception:
            pass

    # Use telnetlib directly
    tn = telnetlib.Telnet(host, port, timeout=connect_timeout)
    time.sleep(1)

    # FLEXIBLE login prompt detection. Some devices ask for a username first
    # (Username:/Login:/etc), others are configured for line-password-only
    # auth and go straight to "Password:" - watch for both in one expect()
    # so we don't blindly write `username` into a Password prompt (which
    # burns one of the device's limited login attempts on garbage and, once
    # the device gives up and closes the socket, surfaces downstream as a
    # confusing raw "Broken pipe" instead of a clear auth error).
    username_prompts = [b"Username:", b"username:", b"User Name:", b"User:", b"Login:", b"login:", b"USER:"]
    password_prompts = [b"Password:", b"password:", b"PASS:"]
    index, match, text = tn.expect(username_prompts + password_prompts, timeout=15)
    _log(text)

    if index != -1 and index < len(username_prompts):
        # Device asked for a username first - answer it, then wait for Password:.
        tn.write(username.encode('ascii') + b"\n")
        time.sleep(1)
        idx2, m2, text2 = tn.expect(password_prompts, timeout=15)
        _log(text2)
    # else: either the device went straight to Password: (index in the
    # password_prompts range) or neither prompt appeared within 15s (index
    # == -1, e.g. a slow/unusual banner) - in both cases don't send the
    # username, just proceed to answer whatever password prompt is current.

    tn.write(password.encode('ascii') + b"\n")
    time.sleep(2)

    post_password = tn.read_very_eager()
    _log(post_password)
    if any(marker in post_password for marker in _TELNET_AUTH_FAILURE_MARKERS) or (
        b"Password:" in post_password or b"password:" in post_password
    ):
        # Either an explicit rejection message, or the device re-displayed
        # the Password: prompt (i.e. asking again = the one we just sent
        # was wrong). Bail out now with a clear message instead of
        # continuing to write "enable"/commands into a session the device
        # is about to close on its own.
        tn.close()
        raise TelnetAuthError(
            f"Device rejected the username/password (response: {post_password.strip()[:200]!r})"
        )

    # Always try to reach privileged/enable mode, even if no enable secret was
    # configured - some devices allow "enable" with a blank password. Previously
    # this was skipped entirely whenever `secret` was empty (same bug fixed on
    # the SSH path, missed here), leaving the session in user EXEC mode where
    # commands like 'show running-config' get rejected as "Invalid input
    # detected" instead of a clear permission error.
    tn.write(b"enable\n")
    time.sleep(1)
    idx, _, enable_prompt_text = tn.expect([b"Password:", b"password:"], timeout=5)
    _log(enable_prompt_text)
    if idx != -1:
        # Device asked for an enable password - send whatever we have
        # (blank if none configured; some devices accept that too).
        tn.write((secret or "").encode('ascii') + b"\n")
        time.sleep(2)
    # else: no password prompt within 5s - device went straight to privileged
    # mode (blank-enable or already-privileged login), nothing more to send.

    # Disable paging (try multiple times for reliability)
    tn.write(b"terminal length 0\n")
    time.sleep(1)
    _log(tn.read_very_eager())  # Clear buffer

    # Double-send for stubborn devices
    tn.write(b"terminal length 0\n")
    time.sleep(0.5)
    _log(tn.read_very_eager())
    
    return tn


def _connect_ssh_normal(
    vendor: str,
    host: str,
    username: str,
    password: str,
    secret: str | None,
    port: int,
    session_log: str,
    connect_timeout: int = 30,
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
        "conn_timeout": connect_timeout,
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
    tags: str | None = None,
) -> tuple[str, bytes]:
    """
    - Kalau protocol = 'Telnet'  -> pakai terminal_server + login manual
    - Kalau protocol = 'SSH'     -> pakai Netmiko normal (device_type dari vendor)
    """
    import tempfile
    import os
    import traceback

    session_log = os.path.join(tempfile.gettempdir(), f"netmiko_{host}.log")

    # Factory-site devices tend to sit behind a slower/less reliable WAN link than
    # HQ - give them more time to complete the initial connection before giving up,
    # instead of just retrying the same too-short timeout repeatedly.
    is_factory = bool(tags) and "factory" in tags.lower()
    connect_timeout = 60 if is_factory else 30

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
                connect_timeout=connect_timeout,
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

            # Append the command's raw reply to the same transcript file the
            # login sequence was logged to, so a CLI-error failure on the
            # Telnet path gets a populated session_log_tail too (previously
            # only the SSH path did, via netmiko's built-in session_log).
            try:
                with open(session_log, "ab") as _f:
                    _f.write(raw_output)
            except Exception:
                pass

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
                connect_timeout=connect_timeout,
            )
            
            enable_error = getattr(conn, "_abs_enable_error", "unknown") or "succeeded, no error"

            # Get appropriate command for this vendor
            config_cmd = cmd or _get_config_command(vendor)
            output = conn.send_command(config_cmd, read_timeout=60)

    except TelnetAuthError as e:
        # The device itself rejected the login (not a network/socket issue) -
        # surface that plainly instead of letting the next write() fail with
        # a confusing raw socket error once the device hangs up. Non-retryable:
        # retrying with the same wrong credentials will just fail again and
        # risks tripping the device's own lockout policy.
        raise NonRetryableBackupError(f"Authentication failed: {host} | {_redact(str(e), password, secret)}")

    except Exception as e:
        error_msg = _redact(str(e), password, secret)
        auth_exc_names = ("NetmikoAuthenticationException", "AuthenticationException")
        if type(e).__name__ in auth_exc_names:
            # Same idea on the SSH path: netmiko already raises a dedicated
            # exception for rejected credentials - relabel it clearly instead
            # of the generic "Connection failed" wrapper used for everything else.
            raise NonRetryableBackupError(f"Authentication failed: {host} | {error_msg}")
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
                # The raw transcript includes whatever was typed into the
                # channel, including the enable secret and login password -
                # this tail ends up in job.log, which viewer-role users can
                # read via GET /jobs. Scrub known secret values before they
                # ever leave this function.
                session_log_tail = _redact(session_log_tail, password, secret)
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

    if "#error exporting" in output:
        # RouterOS failed to export one or more config sections on this run.
        # The sanitizer used to just strip this marker out before hashing,
        # which meant an incomplete backup got saved and counted as a normal
        # success with no trace of what was missing - fixed by detecting it
        # here instead. But some devices hit this on effectively every run
        # (a persistent RouterOS/model quirk on a specific section, not a
        # one-off blip) - failing the job forever means that device never
        # gets backed up again at all, which is worse than a backup that's
        # missing a section or two. So: measure how much of the export
        # actually failed (failed section count vs successfully-exported
        # section count, from RouterOS's own "/path" headers) rather than
        # just failing outright on any mention of the marker.
        missing_sections = re.findall(r"^#error exporting (\S.*)$", output, re.MULTILINE)
        ok_sections = re.findall(r"^(/\S.*)$", output, re.MULTILINE)
        total_attempted = len(missing_sections) + len(ok_sections)
        fail_ratio = (len(missing_sections) / total_attempted) if total_attempted else 1.0

        if fail_ratio > 0.5:
            # Most of the export failed - this isn't "a couple of sections
            # missing", something is seriously wrong. Keep failing the job
            # (retryable) rather than saving what's likely a near-empty file.
            raise Exception(
                f"Backup failure: Device reported an incomplete config export - most "
                f"sections failed ({len(missing_sections)}/{total_attempted}). "
                f"Missing: {', '.join(missing_sections)}"
            )

        # Minority of sections failed - let the caller retry for a clean
        # export first, but carry the partial content so it can be saved
        # as a best-effort backup if every retry hits the same problem.
        raise IncompleteExportError(
            f"Backup incomplete: {len(missing_sections)}/{total_attempted} section(s) "
            f"failed to export: {', '.join(missing_sections)}",
            output.encode(),
            missing_sections,
        )

    if _looks_like_cli_error(output):
        transcript_note = f" | Session transcript tail: {session_log_tail!r}" if session_log_tail else ""
        safe_output = _redact(output.strip()[:200], password, secret)
        safe_enable_error = _redact(str(enable_error), password, secret)
        raise NonRetryableBackupError(
            f"Backup failure: Device returned a command error instead of configuration "
            f"(command '{cmd or _get_config_command(vendor)}' may be wrong for this device's "
            f"vendor/firmware, or the session wasn't in the right privilege level). "
            f"Raw reply: {safe_output!r} | enable() result: {safe_enable_error!r}{transcript_note}"
        )

    content = output.encode()
    fullpath = save_backup_file(host, content)
    return str(fullpath), content
