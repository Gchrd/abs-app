import re

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
            
    return "\n".join(cleaned_lines)

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
    ]
    return sanitize_regex(content, patterns)

def sanitize_config(content: str, vendor: str = 'cisco_ios') -> str:
    """
    Generic sanitizer wrapper. Dispatches to specific vendor logic.
    """
    if vendor == 'cisco_ios':
        return sanitize_cisco_ios(content)
    elif 'mikrotik' in vendor:  # Handle mikrotik_routeros and variants
        return sanitize_mikrotik_routeros(content)
    
    # Default: return content as-is
    return content
