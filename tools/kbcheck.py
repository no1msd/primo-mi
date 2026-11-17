#!/usr/bin/env python3
"""Check everything the BASIC helper is taught against the PRIMO's own BASIC.

For every entry of train/kb.py:
  * each example statement is typed into the emulated PRIMO in direct mode; it must
    not give an error and must print what the answer claims;
  * each program is typed in, LISTed (the listing must be the answer, letter for
    letter) and RUN with its inputs; it must not give an error and must print or
    draw what is expected;
  * the example quoted in the answer must be the one that was checked.

    python tools/kbcheck.py [id ...]
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "train"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import primo
from kb import KB, fill


def chunks(s):
    return [s[i:i + primo.COLS].rstrip() for i in range(0, max(1, len(s)), primo.COLS)]


def squeeze(s):
    return s.replace(" ", "").replace("↑", "~")


def check_direct(k):
    problems = []
    for stmt, want in k["direct"]:
        a = fill(k["a"])
        if ("Például" in a or "Írd be" in a) and stmt not in a and not any(part in a for part in stmt.split(":")):
            problems.append(f"example not quoted in the answer: {stmt}")
        typed = primo.as_typed(stmt)
        mem = primo.memory([("type", typed), ("wait", k["wait"])])
        lines = primo.text(mem)
        echo = set(chunks(typed.replace("↑", "~")))
        if lines and "BASIC SYSTEM" in lines[0]:
            lines = lines[2:]
        out = [l for l in lines if l not in echo]
        if any("Error" in l for l in out):
            problems.append(f"{stmt}: {[l for l in out if 'Error' in l][0]}")
        elif "Ok" not in out:
            problems.append(f"{stmt}: did not finish")
        elif want is not None and not any(want in l for l in out):
            problems.append(f"{stmt}: expected {want!r}, the PRIMO printed {out}")
    return problems


def check_prog(k, q=""):
    """q: a question whose number goes into the program ("" = the number it has by itself)."""
    problems = []
    code = fill(k["a"], q)
    inputs, wants, points = k["prog"] if not q else (k["prog"][0], [], [])
    typed = "\n".join(primo.as_typed(l) for l in code.split("\n"))
    # 1. the listing is the answer
    # (LIST shows one line and goes on while a key is held down)
    mem = primo.memory([("type", typed), ("type", "cls:list"), ("wait", 50),
                        ("raw", f"press SPACE {40 + 10 * code.count(chr(10))}"), ("wait", 100)])
    listing = [l for l in primo.text(mem) if l != "Ok" and l.strip() != "~"]      # "~": the cursor
    if squeeze("".join(listing)) != squeeze(code.replace("\n", "")):
        problems.append(f"LIST shows {listing}")
    # 2. it runs
    steps = [("type", typed), ("type", "cls:run"), ("wait", 60)]
    for line in inputs:
        steps += [("type", line), ("wait", 40)]
    steps.append(("wait", k["wait"]))
    mem = primo.memory(steps)
    lines = primo.text(mem)
    if any("Error" in l for l in lines):
        problems.append(f"RUN: {[l for l in lines if 'Error' in l][0]}")
    for w in wants:
        if not any(w in l for l in lines):
            problems.append(f"RUN: expected {w!r}, the screen shows {lines}")
    for x, y in points:
        if not any(primo.lit(mem, x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            problems.append(f"RUN: the point ({x},{y}) is not lit")
    return problems


def check(k):
    try:
        p = check_direct(k)
        if k["prog"]:
            p += check_prog(k)
            if "{N" in k["a"]:                      # ... and with another number filled in
                p += [f"with 7: {x}" for x in check_prog(k, "7")]
    except ValueError as e:
        p = [str(e)]
    return k["id"], p


def main():
    only = set(sys.argv[1:])
    todo = [k for k in KB if (k["direct"] or k["prog"]) and (not only or k["id"] in only)]
    primo._glyphs()
    bad = 0
    with ThreadPoolExecutor(os.cpu_count()) as ex:
        for id_, problems in ex.map(check, todo):
            for p in problems:
                bad += 1
                print(f"{id_}: {p}")
    n_direct = sum(len(k["direct"]) for k in todo)
    n_prog = sum(1 for k in todo if k["prog"])
    print(f"{n_direct} statements and {n_prog} programs checked on the emulated PRIMO, {bad} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
