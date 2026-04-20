"""Attack payloads for input validation and injection testing."""

# XSS payloads targeting various contexts
XSS_PAYLOADS = [
    # Classic script tags
    '<script>alert(1)</script>',
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "javascript:alert(1)",
    # Template injection style
    "{{7*7}}",
    "${7*7}",
    # Event handlers
    '" onmouseover=alert(1) "',
    "' onfocus=alert(1) autofocus '",
    # Polyglots
    "';alert(1);//",
    "\x3cscript\x3ealert(1)\x3c/script\x3e",
    # Unicode variations
    "<scrİpt>alert(1)</scrİpt>",  # Turkish I
    "<sCriPt>alert(1)</sCriPt>",
]

# SQL injection probes — all should be safely handled by parameterized queries
SQLI_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "1' UNION SELECT * FROM users --",
    "' OR 1=1#",
    "\" OR \"\"=\"",
    "') OR ('1'='1",
    "1; DELETE FROM users WHERE '1'='1",
    "\xbf\x27 OR 1=1 --",  # multibyte
    "admin'--",
    "' OR 'x'='x",
]

# Unicode normalization attacks
UNICODE_ATTACKS = [
    # Homoglyphs
    ("аdmin", "Cyrillic а vs Latin a"),   # U+0430
    ("ａdmin", "Fullwidth a"),              # U+FF41
    # NFKC equivalence
    ("ﬁnance", "fi ligature → finance"),    # U+FB01
    ("№umber", "No sign → number"),         # U+2116
    # Confusables
    ("gοοgle", "Greek omicron o"),          # U+03BF
    ("paypaℓ", "Letter L vs script l"),     # U+2113
]

# Oversized payloads
OVERSIZED = {
    "username": "a" * 100,       # max 32
    "password": "a" * 5,         # min 8
    "email": "a" * 300,          # no explicit max, but should be reasonable
    "server_name": "a" * 200,    # max 100
    "channel_name": "a" * 200,   # max 80
    "message": "a" * 10000,      # max 4000
}

# Path traversal / injection
PATH_PAYLOADS = [
    "../../../etc/passwd",
    r"..\..\..\windows\system32\config\sam",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "....//....//....//etc/passwd",
    "\n",
    "\x00",
]
