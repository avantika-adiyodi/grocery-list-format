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


def row_to_body_tokens(line):
    """Split one BODY line into tokens, same as row_to_cells but also
    breaking apart already-formatted single-line items like:
        '1 | Beans HARICOT - 250 gm #'
    into ['1', '|', 'Beans HARICOT', '-', '250 gm', '#'].

    This is needed because a line like that has no tabs, so a plain
    tab-split would leave it as one giant cell and parse_items would
    never see a standalone '#' token to close the item out.

    We only split on '|' and '#' here (always safe -- these never
    legitimately appear inside an item name/quantity in this format).
    We deliberately do NOT split every '-' here, since item names can
    contain hyphens (e.g. 'Harpic - blue normal medium size'); the
    existing last-dash-wins logic in format_item already handles that
    correctly as long as '-' surrounded by spaces becomes its own
    token. We split on ' - ' (dash with spaces on both sides) which
    covers both the field separator and safely leaves things like
    '100gms' or hyphenated words without spaces intact.
    """
    cells = row_to_cells(line) # split based on tab ("\t")
    tokens = []
    for cell in cells:
        # First split out '|' and '#' as their own tokens.
        parts = [cell]
        for sep in ("|", "#"):
            new_parts = []
            for part in parts:
                pieces = part.split(sep)
                for j, piece in enumerate(pieces):
                    piece = piece.strip()
                    if piece != "":
                        new_parts.append(piece)
                    if j != len(pieces) - 1:
                        new_parts.append(sep)
            parts = new_parts
        # Now split each remaining part on ' - ' (dash with spaces)
        # to separate name from quantity in already-formatted lines,
        # without breaking hyphens that have no surrounding spaces.
        final_parts = []
        for part in parts:
            if part in ("|", "#"):
                final_parts.append(part)
                continue
            segments = part.split(" - ")
            for k, segment in enumerate(segments):
                segment = segment.strip()
                if segment != "":
                    final_parts.append(segment)
                if k != len(segments) - 1:
                    final_parts.append("-")
        tokens.extend(final_parts)
    return tokens


def split_header_and_body_rows(raw_text):
    """Split the raw text into header ROWS (list of cell-lists, before
    the first ```) and body tokens (flattened, between the ``` fences).

    Header rows keep using plain tab/cell splitting, since header text
    shouldn't be broken apart on '|', '-', or '#'.

    Body lines use row_to_body_tokens, since item lines might arrive
    already-formatted on a single line (e.g. '1 | Rice - 5 kg #') and
    need to be broken apart into individual tokens to be re-parsed.
    """
    original_lines = raw_text.splitlines()

    fence_line_indices = [
        idx for idx, line in enumerate(original_lines)
        if line.strip() == "```"
    ]

    if not fence_line_indices:
        rows = [row_to_cells(line) for line in original_lines]
        rows = [r for r in rows if r]
        return rows, []

    first_fence_line = fence_line_indices[0]
    header_lines = original_lines[:first_fence_line]
    header_rows = [row_to_cells(line) for line in header_lines]
    header_rows = [r for r in header_rows if r]

    if len(fence_line_indices) >= 2:
        last_fence_line = fence_line_indices[-1]
        body_lines = original_lines[first_fence_line + 1:last_fence_line]
    else:
        body_lines = original_lines[first_fence_line + 1:]

    body_tokens = []
    for line in body_lines:
        body_tokens.extend(row_to_body_tokens(line))

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

    def is_any_label(row):
        return bool(row) and (is_date_label(row[0]) or is_address_label(row[0]))

    def extract_field(rows, start, output_label):
        """Consume the label row at `start` (and, if its value is
        empty, look ahead for a ':' row and/or one value row) and
        return (formatted line, next index to resume from)."""
        row = rows[start]
        value_cells = [cell for cell in row[1:] if cell != ":"]
        i = start + 1

        if not value_cells and i < len(rows):
            if rows[i] == [":"]:
                i += 1
            if i < len(rows) and not is_any_label(rows[i]):
                value_cells = [cell for cell in rows[i] if cell != ":"]
                i += 1

        value = " ".join(value_cells).strip()
        return f"{output_label} {value}".strip(), i

    output_lines = []
    i = 0
    n = len(header_rows)

    while i < n:
        row = header_rows[i]

        if row and is_date_label(row[0]):
            line, i = extract_field(header_rows, i, "Date:")
            output_lines.append(line)
        elif row and is_address_label(row[0]):
            line, i = extract_field(header_rows, i, "*Address*:")
            output_lines.append(line)
        else:
            output_lines.append(" ".join(row))
            i += 1

    return output_lines


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


def build_output(header_lines, body_tokens):
    """Assemble the final output: header, one blank line, then the
    fenced item list. Body tokens are grouped into individual items
    (each a run of tokens ending in '#') and formatted as we go 
    ("turn tokens into output lines")."""
    output_lines = []
    output_lines.extend(header_lines)
    output_lines.append("")  # exactly one blank line between header and list
    output_lines.append("```")

    current_item = []
    for tok in body_tokens:
        current_item.append(tok)
        if tok == "#":
            formatted = format_item(current_item)
            if formatted:
                output_lines.append(formatted)
            current_item = []
    # Any leftover tokens that never reached a closing '#' (e.g. a lone
    # trailing serial number with nothing filled in) are simply dropped.

    output_lines.append("```")
    return "\n".join(output_lines)


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
    output = build_output(header_lines, body_tokens)

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