"""Debug version of FlowScope to identify what escape sequences are being captured.

Run this to see exactly what control sequences are in the raw output.
"""

import sys
import re

# Same regex from the patched version
_CONTROL_SEQUENCE_RE = re.compile(
    r'\x1b\[[\?0-9;]*[a-zA-Z]'
)

def analyze_text(text: str) -> None:
    """Find and print all escape sequences in the text."""
    
    matches = list(_CONTROL_SEQUENCE_RE.finditer(text))
    
    if matches:
        print(f"\n[DEBUG] Found {len(matches)} escape sequence(s):")
        for i, match in enumerate(matches, 1):
            seq = match.group()
            # Show hex representation
            hex_repr = ' '.join(f'{ord(c):02x}' for c in seq)
            print(f"  {i}. {repr(seq)} (hex: {hex_repr})")
    
    # Show what it looks like after filtering
    filtered = _CONTROL_SEQUENCE_RE.sub('', text)
    if text != filtered:
        print(f"[DEBUG] Original: {repr(text)}")
        print(f"[DEBUG] Filtered: {repr(filtered)}")


# Test with the example from the screenshot
test_string = "Copyright (C) Microsoft Corporation. All rig> [?61;4cved."

print("=" * 60)
print("Testing with example from screenshot:")
print("=" * 60)
analyze_text(test_string)

# Test with raw escape sequence
test_with_escape = "Copyright (C) Microsoft Corporation. All rig\x1b[?61;4c> ved."
print("\n" + "=" * 60)
print("Testing with raw escape sequence:")
print("=" * 60)
analyze_text(test_with_escape)

print("\n" + "=" * 60)
print("Regex pattern used:")
print(_CONTROL_SEQUENCE_RE.pattern)
print("=" * 60)