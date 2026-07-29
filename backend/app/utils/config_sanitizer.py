import re


def _normalize_content(content: str) -> str:
    """
    Normalize line endings and trailing whitespace for consistent hashing.
    - Converts \r\n and \r to \n (SSH vs Telnet can return different line endings)
    - Strips trailing whitespace from each line
    - Strips leading/trailing blank lines
    This ensures the same config always produces the same hash.
    """
    # Normalize all line endings to \n
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in content.split('\n')]
    # Remove leading/trailing blank lines
    return '\n'.join(lines).strip()


def sanitize_regex(content: str, patterns: list[str]) -> str:
    """
    Generic helper to remove lines matching regex patterns.
    """
    lines = content.splitlines()
    cleaned_lines = []
    
    compiled_patterns = [re.compile(p) for p in patterns]

    for line in lines:
        should_ignore = False
        for pattern in compiled_patterns:
            if pattern.search(line):
                should_ignore = True
                break
        
        if not should_ignore:
            cleaned_lines.append(line)
            
    return '\n'.join(cleaned_lines)


def sanitize_cisco_ios(content: str) -> str:
    patterns = [
        r"^! Last configuration change at",
        r"^! NVRAM config last updated at",
        r"^ntp clock-period",
        r"^Current configuration :",
        r"^! Time: ",
    ]
    return sanitize_regex(content, patterns)


def sanitize_mikrotik_routeros(content: str) -> str:
    patterns = [
        # Example: # feb/16/2026 22:04:09 by RouterOS 6.43.16
        r"^# \w+/\d+/\d+ .* by RouterOS",
        # Example: # software id = XXXX-XXXX (can change after upgrade)
        r"^# software id =",
        # RouterOS sometimes fails to export a section on a given run (transient
        # export-command quirk, not an actual config change) and writes an error
        # line straight into the output instead, e.g.:
        # "#error exporting /ip dhcp-server option sets"
        r"^#error exporting ",
    ]
    return sanitize_regex(content, patterns)


def sanitize_aruba(content: str) -> str:
    patterns = [
        # Aruba timestamp lines
        r"^; Generated on ",
        r"^; Current System Time:",
        r"^Current system time:",
        # Aruba dynamically hashes passwords/keys in exports
        r"^\s*(?:admin-passwd|key|ap-console-password|bkup-passwords|wpa-passphrase) ",
        # IPsec peer PSK is re-encrypted with a fresh salt/IV on every export -
        # the underlying key doesn't change, but the ciphertext always does, e.g.:
        # "    peer-ip-address 10.2.2.3 ipsec 2211d8470c1206c01cf971f554aaf205c2f3f40f1ee46f2e"
        r"^\s*peer-ip-address\s+\S+\s+ipsec\s+",
    ]
    return sanitize_regex(content, patterns)


def sanitize_huawei(content: str) -> str:
    patterns = [
        # Timestamp header rewritten on every export, e.g.:
        # "!Last configuration was updated at 2026-05-11 02:26:21+00:00 by SYSTEM automatically"
        r"^!Last configuration was updated at",
        r"^!Software Version V",
        r"^ Current configuration :",
        r"^#\d{4}-",
    ]
    return sanitize_regex(content, patterns)


def sanitize_fortinet(content: str) -> str:
    patterns = [
        # Fortinet config version line which changes every export
        r"^#conf_file_ver=",
        # Fortinet encrypts passwords with dynamic salts that change every export
        r"^\s*set (?:password|secret|psksecret|private-key|auth-password) ENC ",
        # Catch any other generic ENC fields just in case
        r"^\s*set .* ENC "
    ]
    return sanitize_regex(content, patterns)


def sanitize_config(content: str, vendor: str = 'cisco_ios') -> str:
    """
    Generic sanitizer wrapper. Dispatches to specific vendor logic.
    Always normalizes newlines FIRST for consistent hashing.
    """
    # STEP 1: Always normalize line endings & whitespace first
    content = _normalize_content(content)
    
    # STEP 2: Apply vendor-specific sanitization
    vendor_lower = vendor.lower() if vendor else ""
    
    if 'cisco' in vendor_lower or 'allied' in vendor_lower:
        return sanitize_cisco_ios(content)
    elif 'mikrotik' in vendor_lower:
        return sanitize_mikrotik_routeros(content)
    elif 'aruba' in vendor_lower:
        return sanitize_aruba(content)
    elif 'huawei' in vendor_lower:
        return sanitize_huawei(content)
    elif 'fortinet' in vendor_lower:
        return sanitize_fortinet(content)
    
    # Default: return normalized content as-is
    return content
