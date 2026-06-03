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
    ]
    return sanitize_regex(content, patterns)


def sanitize_aruba(content: str) -> str:
    patterns = [
        # Aruba timestamp lines
        r"^; Generated on ",
        r"^; Current System Time:",
        r"^Current system time:",
    ]
    return sanitize_regex(content, patterns)


def sanitize_huawei(content: str) -> str:
    patterns = [
        # Huawei timestamp headers
        r"^#\s*$",  # standalone # lines (separators)
        r"^ sysname ",  # can contain variable info in some configs
        r"^  undo info-center loghost",  # dynamic logging entries
    ]
    # Only strip the pure timestamp header line
    ts_pattern = [r"^!Software Version V", r"^ Current configuration :", r"^#\d{4}-"]
    return sanitize_regex(content, ts_pattern)


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
