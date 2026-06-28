#!/usr/bin/env python3
"""
Grocery List Formatter
-----------------------
Cleans up a grocery order list so it's ready to paste into Google Keep
(or WhatsApp, or anywhere else) -- whether you copy it straight from
Google Sheets (tab-separated cells) or from somewhere that already
mangled it into one-token-per-line (like a previous Keep paste).

Setup (one-time):
    pip install pyperclip

    On Linux only, pyperclip also needs a clipboard backend installed:
        sudo apt-get install xclip
    (Not needed on Mac or Windows -- clipboard support works out of the box.)

Usage:
    Run the script, paste your list, then type END on its own line
    and press Enter to finish.

What it does:
    1. Reads the header (Date, Address, delivery note, etc.) and tidies
       it into "Date: <value>" and "*Address*: <value>" -- removing any
       extra standalone ":" line/cell if present.
    2. Reads the item list between the ``` fences and rebuilds each row
       into the format:  <SlNo> | <name> - <quantity> #
    3. Puts exactly one blank line between the header and the ``` block.
    4. Copies the final result to your clipboard and prints it.
"""

import sys

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


END_SENTINEL = ["END", "end"]


def read_input():
    """Read multi-line pasted text from the terminal until the user
    types END on its own line. Works the same way on Mac/Linux/Windows,
    no Ctrl+D / Ctrl+Z fiddling required."""
    print("Paste your grocery list below (from Google Sheets or Keep).")
    print(f"When you're done, type \"{END_SENTINEL [0]}\" or \"{END_SENTINEL [1]}\" on its own line and press Enter:\n")

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() in END_SENTINEL:
            break
        lines.append(line)

    return "\n".join(lines)


def row_to_cells(line):
    """Split one line of input into non-empty cells. Handles tab
    separation (direct Sheets paste puts multiple cells on one line)."""
    return [c.strip() for c in line.split("\t") if c.strip() != ""]


def split_header_and_body_rows(raw_text):
    """Split the raw text into header ROWS (list of cell-lists, before
    the first ```) and body tokens (flattened, between the ``` fences).
    Keeping rows intact for the header lets us know exactly which cells
    belong to the Date/Address line vs. the next line."""
    rows = [row_to_cells(line) for line in raw_text.splitlines()]
    rows = [r for r in rows if r]  # drop fully empty rows

    fence_row_idx = None
    for idx, row in enumerate(rows):
        if row and row[0] == "```":
            fence_row_idx = idx
            break

    if fence_row_idx is None:
        return rows, []

    header_rows = rows[:fence_row_idx]

    # Find the matching closing fence row (last row that is just ```)
    closing_idx = None
    for idx in range(len(rows) - 1, fence_row_idx, -1):
        if rows[idx] and rows[idx][0] == "```":
            closing_idx = idx
            break

    if closing_idx is not None:
        body_rows = rows[fence_row_idx + 1:closing_idx]
    else:
        body_rows = rows[fence_row_idx + 1:]

    body_tokens = []
    for row in body_rows:
        body_tokens.extend(row)

    return header_rows, body_tokens


def clean_header(header_rows):
    """Rebuild header rows so a Date row becomes 'Date: <value>' and an
    Address row becomes '*Address*: <value>'.

    Handles two shapes of input:
      - Direct-from-Sheets: label, ':', value all on the SAME row
        (tab-separated cells collapsed into one row).
      - Old Keep-mangled: label, ':', value each on their OWN row.

    In both cases, exactly one "value" row is consumed for the field --
    just enough to capture the date/address itself -- so a separate
    line like a delivery note right after the address is left alone."""

    def is_date_label(cell):
        return cell.strip().lower() in ("date:", "date")

    def is_address_label(cell):
        return cell.strip().lower() in ("*address*", "*address*:", "address", "address:")

    out = []
    i = 0
    n = len(header_rows)

    while i < n:
        row = header_rows[i]

        if row and is_date_label(row[0]):
            value_cells = [c for c in row[1:] if c != ":"]
            i += 1
            # If no value on this row, look at the next row(s): skip a
            # lone ':' row, then take the next non-empty row as the value.
            if not value_cells and i < n:
                if header_rows[i] == [":"]:
                    i += 1
                if i < n and not (is_date_label(header_rows[i][0]) if header_rows[i] else False) \
                        and not (is_address_label(header_rows[i][0]) if header_rows[i] else False):
                    value_cells = [c for c in header_rows[i] if c != ":"]
                    i += 1
            value = " ".join(value_cells).strip()
            out.append(f"Date: {value}".strip())
            continue

        if row and is_address_label(row[0]):
            value_cells = [c for c in row[1:] if c != ":"]
            i += 1
            if not value_cells and i < n:
                if header_rows[i] == [":"]:
                    i += 1
                if i < n and not (is_date_label(header_rows[i][0]) if header_rows[i] else False) \
                        and not (is_address_label(header_rows[i][0]) if header_rows[i] else False):
                    value_cells = [c for c in header_rows[i] if c != ":"]
                    i += 1
            value = " ".join(value_cells).strip()
            out.append(f"*Address*: {value}".strip())
            continue

        out.append(" ".join(row))
        i += 1

    return out


def parse_items(body_tokens):
    """Group body tokens into individual items. Each item is a run of
    tokens ending in '#'. The first token of an item is always the
    serial number, which lets us realign cleanly."""
    items = []
    current_item = []

    for token in body_tokens:
        current_item.append(token)
        if token == "#":
            items.append(current_item)
            current_item = []

    # Drop any trailing incomplete item (e.g. a lone leftover serial
    # number with nothing filled in) -- nothing useful to print there.
    return items


def format_item(tokens):
    """Turn a token list like:
        ['1', '|', 'Beans HARICOT', '-', '250 gm', '#']
    into:
        '1 | Beans HARICOT - 250 gm #'

    Splits on the LAST standalone '-' token so names containing hyphens
    (e.g. 'Lotion Floor LIZOL JASMINE (Rs 115 - 125 approx)') still work.
    """
    if not tokens or not tokens[0].isdigit():
        return None

    slno = tokens[0]
    rest = tokens[1:]

    if rest and rest[0] == "|":
        rest = rest[1:]

    if rest and rest[-1] == "#":
        rest = rest[:-1]

    dash_positions = [i for i, t in enumerate(rest) if t == "-"]

    if dash_positions:
        last_dash = dash_positions[-1]
        name = " ".join(rest[:last_dash]).strip()
        quantity = " ".join(rest[last_dash + 1:]).strip()
    else:
        name = " ".join(rest).strip()
        quantity = ""

    if not name and not quantity:
        return None

    if quantity:
        return f"{slno} | {name} - {quantity} #"
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


def copy_to_clipboard(text):
    """Try to copy text to the system clipboard. Returns True on
    success, False if no clipboard backend is available."""
    if not CLIPBOARD_AVAILABLE:
        return False
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def main():
    raw_text = read_input()

    if not raw_text.strip():
        print("\nNo input received. Exiting.")
        return

    header_rows, body_tokens = split_header_and_body_rows(raw_text)
    header_lines = clean_header(header_rows)
    items = parse_items(body_tokens)
    output = build_output(header_lines, items)

    print("\n" + "=" * 50)
    print("CLEANED OUTPUT:")
    print("=" * 50 + "\n")
    print(output)
    print()

    if copy_to_clipboard(output):
        print("✅ Formatted output copied to your clipboard!")
    else:
        print("⚠️  Couldn't copy to clipboard automatically.")
        print("   Run: pip install pyperclip")
        print("   (Linux also needs: sudo apt-get install xclip)")
        print("   Please copy the output above manually for now.")


if __name__ == "__main__":
    main()