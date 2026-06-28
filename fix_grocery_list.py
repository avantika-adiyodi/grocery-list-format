#!/usr/bin/env python3
"""
Grocery List Formatter
-----------------------
Fixes the formatting of a grocery order list that got mangled when pasted
from Google Sheets into Google Keep (or similar apps that split tab-separated
cells onto their own lines).

Usage:
    Run the script, paste your messy text when prompted, then press
    Enter on an empty line (or Ctrl+D) to finish input. The cleaned,
    WhatsApp-ready version will be printed out.

Expected item structure once fixed:
    <Slno> | <name> - <quantity> #

The header (Date, Address, delivery note, etc.) stays at the top,
followed by exactly one blank line, then the ``` fenced item list.
"""

import sys


def read_input():
    """Read multi-line pasted text from stdin until EOF (Ctrl+D) or a
    double-blank-line signal isn't required -- we just read everything."""
    print("Paste your grocery list below.")
    print("When done, press Enter then Ctrl+D (or Ctrl+Z then Enter on Windows):\n")
    data = sys.stdin.read()
    return data


def split_header_and_body(raw_text):
    """Split the raw text into header lines (before the first ```) and
    the body lines (between the ``` fences, or after the first ``` if
    only one fence is present)."""
    lines = raw_text.splitlines()

    fence_indices = [i for i, line in enumerate(lines) if line.strip() == "```"] # gets the indices of ```

    if not fence_indices:
        # No fences found at all -- treat everything as header, no items.
        header_lines = [l for l in lines if l.strip() != ""]
        return header_lines, []

    first_fence = fence_indices[0] 
    header_lines = [l for l in lines[:first_fence] if l.strip() != ""] # takes lines before first ```

    if len(fence_indices) >= 2:
        last_fence = fence_indices[-1]
        body_lines = lines[first_fence + 1:last_fence]  # takes lines after last ```
    else:
        body_lines = lines[first_fence + 1:]

    return header_lines, body_lines


def parse_items(body_lines):
    """Parse the flattened body lines back into individual items.

    Each item, when intact, is 5 logical pieces:
        slno, '|', name, '-', quantity, '#'
    wait -- actually 6 pieces: slno | name - quantity #

    But since cells get split one-per-line, an item is represented by
    consecutive non-empty lines until we hit the '#' line, which marks
    the end of that item. The very first token of an item is always a
    number (the serial number). This lets us realign even if a name or
    quantity happens to contain a stray newline artifact.
    """
    # Drop truly empty lines (Google Keep sometimes adds blank lines)
    cleaned = [l for l in body_lines if l.strip() != ""] # removes leading white strips

    items = []
    current = []

    for line in cleaned:
        current.append(line.strip()) # append all lines until 
        if line.strip() == "#":
            items.append(current)
            current = []

    # Leftover lines that never reached a closing '#' (e.g. a trailing
    # incomplete entry like a lone serial number "44" with nothing after
    # it). We just drop these silently since there's no real item there.
    leftover_has_content = any(
        tok for tok in current if tok not in ("#",) and not tok.isdigit()
    )
    if leftover_has_content:
        items.append(current)  # keep it, we'll format best-effort

    return items


def format_item(tokens):
    """Turn a token list like:
        ['1', '|', 'ബീൻസ് Beans HARICOT', '-', '250 gm', '#']
    into:
        '1 | ബീൻസ് Beans HARICOT - 250 gm #'

    Handles cases where the name itself contains a stray '|' or '-'
    inside parentheses by reconstructing positionally: first token is
    slno, second is '|', then everything between '|' and the LAST '-'
    before quantity is the name, then quantity, then '#'.
    """
    if not tokens:
        return None

    # Must have at least a serial number to be worth formatting
    if not tokens[0].isdigit():
        return None

    slno = tokens[0]

    # Find the separator '|' (should be tokens[1])
    rest = tokens[1:]
    if rest and rest[0] == "|":
        rest = rest[1:]

    # The last two meaningful tokens before '#' are quantity and the '-' sign.
    # Strip trailing '#' if present
    if rest and rest[-1] == "#":
        rest = rest[:-1]

    # Now rest should be: [name_parts...] '-' quantity
    # Find the LAST standalone '-' token to split name from quantity,
    # since item names can sometimes contain hyphens within text.
    dash_positions = [i for i, t in enumerate(rest) if t == "-"]

    if dash_positions:
        last_dash = dash_positions[-1]
        name = " ".join(rest[:last_dash]).strip()
        quantity = " ".join(rest[last_dash + 1:]).strip()
    else:
        # No standalone dash found; best effort fallback
        name = " ".join(rest).strip()
        quantity = ""

    # If there's no real content (no name and no quantity), this was just
    # a stray/incomplete row (e.g. a trailing serial number with nothing
    # filled in) -- skip it entirely rather than printing an empty item.
    if not name and not quantity:
        return None

    if quantity:
        return f"{slno} | {name} - {quantity} #"
    else:
        return f"{slno} | {name} #"


def build_output(header_lines, items):
    out_lines = []
    out_lines.extend(header_lines)
    out_lines.append("")  # exactly one blank line between header and list
    out_lines.append("```")

    for tokens in items:
        formatted = format_item(tokens)
        if formatted:
            out_lines.append(formatted)

    out_lines.append("```")
    return "\n".join(out_lines)


def main():
    raw_text = read_input()

    if not raw_text.strip():
        print("\nNo input received. Exiting.")
        return

    header_lines, body_lines = split_header_and_body(raw_text)
    items = parse_items(body_lines)
    output = build_output(header_lines, items)

    print("\n" + "=" * 50)
    print("CLEANED OUTPUT (copy everything below this line):")
    print("=" * 50 + "\n")
    print(output)


if __name__ == "__main__":
    main()
