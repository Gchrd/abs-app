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


def sanitize_redact(content: str, rules: list[tuple[str, str]]) -> str:
    """
    Like sanitize_regex, but instead of deleting a whole matching line,
    substitutes just the volatile part of it (e.g. a resalted ciphertext)
    with a fixed placeholder, via regex substitution. Dropping the whole
    line made an added/removed entry (a real config change) invisible to
    the hash, same as a value that's merely resalted on every export -
    keeping the line's structure means an added/removed entry still shows
    up, even though a same-slot value swap still can't be told apart from
    a resalt (that would require decrypting the vendor's ciphertext).
    """
    compiled = [(re.compile(p), r) for p, r in rules]
    out = []
    for line in content.splitlines():
        new_line = line
        for pattern, repl in compiled:
            if pattern.match(line):
                new_line = pattern.sub(repl, line)
                break
        out.append(new_line)
    return '\n'.join(out)


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
        # "controller config <N>" is an internal checkpoint/revision counter
        # that increments on its own over time - confirmed live: two backups
        # taken days apart had this as the ONLY differing line after the
        # redact rules below, with every actual config line identical, so it
        # doesn't track meaningful config changes and just causes false
        # "Changed" alerts.
        r"^controller config \d+",
    ]
    content = sanitize_regex(content, patterns)

    # Aruba re-encrypts passwords/keys with a fresh salt on every export even
    # when the underlying value is unchanged. Dropping these lines entirely
    # (previous behavior) also hid a genuine password/key ROTATION, since the
    # line just vanished from both old and new configs either way. Redacting
    # only the value keeps the line itself in the diff, so an added/removed
    # entry still changes the hash - a same-slot value change still can't be
    # distinguished from a resalt without decrypting Aruba's ciphertext.
    redact_rules = [
        (r"^(\s*(?:admin-passwd|key|ap-console-password|bkup-passwords|wpa-passphrase)\s+)\S+", r"\1<redacted-in-abs>"),
        (r"^(\s*peer-ip-address\s+\S+\s+ipsec\s+)\S+", r"\1<redacted-in-abs>"),
    ]
    return sanitize_redact(content, redact_rules)


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
    ]
    content = sanitize_regex(content, patterns)

    # Fortinet re-encrypts ENC fields with a fresh salt on every export even
    # when the value is unchanged. Dropping these lines entirely (previous
    # behavior) also hid a genuine password/secret/PSK ROTATION, since the
    # line vanished from both old and new configs either way. Redacting only
    # the value keeps the line itself in the diff, so an added/removed entry
    # still changes the hash - a same-slot value change still can't be told
    # apart from a resalt without decrypting Fortinet's ciphertext.
    redact_rules = [
        (r"^(\s*set (?:password|secret|psksecret|private-key|auth-password) ENC\s+)\S+", r"\1<redacted-in-abs>"),
        # Catch any other generic ENC fields just in case
        (r"^(\s*set \S+ ENC\s+)\S+", r"\1<redacted-in-abs>"),
    ]
    return sanitize_redact(content, redact_rules)


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
