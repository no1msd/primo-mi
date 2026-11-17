"""Drive the headless PRIMO emulator from Python: type on its keyboard, read its screen.

Nothing is shown on the desktop.  The screen is read back as text by comparing the
6x12 pixel character cells with the ROM's own font (printed once and cached).
"""
import os
import pickle
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMU = os.path.join(ROOT, "build", "primo-headless")
GLYPHS = os.path.join(ROOT, "build", "glyphs.pkl")
COLS, ROWS, CW, CH, LEFT = 42, 16, 6, 12, 4

# what the keys give without and with SHIFT (found by pressing them in the emulator)
PLAIN = {" ": "SPACE", "+": "+", "-": "-", ".": ".", ",": ",", ">": "<", "*": "0x31", "↑": "UP",
         "ü": "0x30", "ú": "0x33", "é": "0x3a", "ó": "0x3b", "á": "0x3c", "ö": "0x3e"}
SHIFT = {"!": "1", '"': "2", "#": "3", "$": "4", "%": "5", "&": "6", "/": "7", "(": "8", ")": "9",
         "=": "0", "?": "+", "í": "-", ":": ".", ";": ",", "<": "<", "'": "0x31",
         "Ü": "0x30", "ű": "0x33", "É": "0x3a", "ő": "0x3b", "Á": "0x3c", "Ö": "0x3e"}
# PRIMO character codes of the accented letters
CODES = {0x7D: "á", 0x60: "é", 0x5B: "ó", 0x7C: "ö", 0x7B: "ő", 0x5F: "ú", 0x7E: "ü", 0x7F: "ű",
         0x5D: "Á", 0x40: "É", 0x5C: "Ö", 0x5E: "Ü"}


def as_typed(text):
    """BASIC as a child types it: lower case (no SHIFT) outside quotation marks."""
    out, quoted = "", False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        out += ch if quoted else ch.lower()
    return out


def keys(text):
    """Script commands that type the text."""
    out = []
    for ch in text:
        if ch in PLAIN:
            out.append(f"press {PLAIN[ch]} 4")
        elif ch.isdigit() or "a" <= ch <= "z":
            out.append(f"press {ch.upper()} 4")
        elif "A" <= ch <= "Z":
            out += ["down SHIFT", "wait 2", f"press {ch} 4", "up SHIFT"]
        elif ch in SHIFT:
            out += ["down SHIFT", "wait 2", f"press {SHIFT[ch]} 4", "up SHIFT"]
        else:
            raise ValueError(f"the PRIMO keyboard cannot type {ch!r}")
        out.append("wait 3")
    return out


def session(steps, extra=()):
    """steps: ('type', lines) | ('wait', frames) | ('raw', script command).  Every typed line
    ends with RETURN.  Returns the emulator's output."""
    sc = ["wait 150"]
    for kind, arg in steps:
        if kind == "type":
            for line in arg.split("\n"):
                sc += keys(line) + ["press RETURN 4", "wait 25"]
        elif kind == "wait":
            sc.append(f"wait {arg}")
        else:
            sc.append(arg)
    r = subprocess.run([EMU, "-scale", "1", *extra], input="\n".join(sc) + "\n",
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def _cells(mem):
    scr = mem[0xE800:0x10000]
    rows = [int.from_bytes(scr[y * 32:y * 32 + 32], "big") for y in range(192)]
    return [[bytes((rows[r * CH + y] >> (256 - LEFT - (c + 1) * CW)) & 63 for y in range(CH))
             for c in range(COLS)] for r in range(ROWS)]


def _glyphs():
    if os.path.exists(GLYPHS):
        return pickle.load(open(GLYPHS, "rb"))
    mem = memory([("type", "cls:for c=33 to 127:print chr$(c);:next"), ("wait", 150)])
    flat = [x for row in _cells(mem)[0:3] for x in row]
    table = {bytes(CH): " "}
    for i, c in enumerate(range(33, 128)):
        table.setdefault(flat[i], CODES.get(c, chr(c)))
    pickle.dump(table, open(GLYPHS, "wb"))
    return table


def memory(steps, extra=()):
    """Run a session and return the PRIMO's 64 KB of memory at its end."""
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        path = f.name
    try:
        session(list(steps) + [("raw", f"dump {path}")], extra)
        return open(path, "rb").read()
    finally:
        os.unlink(path)


def text(mem):
    """The screen as lines of text ('~' where a cell is not a ROM character)."""
    table = _glyphs()
    lines = ["".join(table.get(c, "~") for c in row).rstrip() for row in _cells(mem)]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def lit(mem, x, y):
    """Is the point (x, y) lit?  As in BASIC's SET: (0, 0) is the bottom left corner."""
    return bool(mem[0xE800 + (191 - y) * 32 + x // 8] & (0x80 >> (x % 8)))
