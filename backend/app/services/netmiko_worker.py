from netmiko import ConnectHandler
from hashlib import sha256
from pathlib import Path
from ..settings import settings

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
    }

    conn = ConnectHandler(**device)

    if secret:
        conn.enable()

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
            
            # Get appropriate command for this vendor
            config_cmd = cmd or _get_config_command(vendor)
            output = conn.send_command(config_cmd, read_timeout=60)

    except Exception as e:
        error_msg = str(e)
        # Session log available at: session_log (for debugging if needed)
        raise Exception(f"Connection failed: {host} | Error: {error_msg}")

    finally:
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

    # Simpan ke file
    content = output.encode()
    filehash = sha256(content).hexdigest()[:8]
    Path(settings.BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    filename = f"{host}_{filehash}.cfg"
    fullpath = Path(settings.BACKUP_DIR) / filename
    fullpath.write_bytes(content)

    return str(fullpath), content
