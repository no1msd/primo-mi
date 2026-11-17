#!/usr/bin/env python3
"""Run the BASIC helper's tape in the headless PRIMO emulator and compare it with
the reference.

Loads the tape, types LOAD and RUN, then types questions on the PRIMO's keyboard
and checks, for every one of them, that
  * the answer the Z80 program chose is the one train/ref_helper.py chooses,
  * the text on the PRIMO's screen is the text the reference prints,
both for the line as it arrived in the PRIMO's memory (the script's key presses are
short, and the PRIMO misses one now and then while it scrolls the screen; such
lines are counted and still checked), and at the end that the network's bytes in the emulated memory are still the bytes
of the tape.  Reports the time from RETURN to the choice.  Nothing is shown on the
desktop.

    python tools/check_helper.py --dir mi --ptp MI.ptp --questions 300
"""
import argparse
import math
import os
import random
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "train"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import primo
import ref_helper
from questions import tests, sloppy

CLOCK = 2_500_000
# things the test questions do not contain: capitals, long lines, empty lines, odd numbers
SPECIAL = ["", "   ", "MI AZ A GOTO", "Hogyan Törlöm A Képernyőt?", "sn error in 007", "l3 error", "/0 error in 40",
           "számolj el 12345-ig", "számolj 1-től 250-ig", "mennyi 12 * 7 + 3.5 ?", "mennyi 3. 4+5", "99/3",
           "nagyon de nagyon hosszú kérdés ami biztosan nem fér ki hatvan betűbe: mi az a for",
           "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
           "?", "árvíztűrő tükörfúrógép", "ul error in 20 és 300", "kört rajzolj!!!", "'%&#", "szia"]


def symbols(path):
    out = {}
    for line in open(path):
        m = re.match(r"(\w+)\s*=\s*\$([0-9A-Fa-f]+)", line)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    return out


def typing(q):
    out = []
    for ch in q:
        out += primo.keys(ch) if ch != "'" else ["down SHIFT", "wait 2", "press 0x31 4", "up SHIFT", "wait 3"]
    return out + ["press RETURN 4"]


def squeeze(s):
    return re.sub(r"[íÍÓŐÚŰ↑]", "~", s.replace(" ", "").replace("\n", ""))


def session(args):
    """Type the questions of one session; returns [(chosen or None, screen text, cycles)]."""
    ptp, sym, questions, tmp, n = args
    script = ["wait 150"] + primo.keys("load") + ["press RETURN 4", "wait 1100"] + \
        primo.keys("run") + ["press RETURN 4", "wait 150"]
    dumps = []
    for i, q in enumerate(questions):
        d = os.path.join(tmp, f"s{n}_{i}.bin")
        dumps.append(d)
        script += [f"echo Q{i}"] + typing(q) + ["wait 230", f"dump {d}"]
    cmd = [primo.EMU, "-ptp", ptp, "-scale", "1", "-hits", "100000",
           "-break", f"got_line={sym['got_line']:04x},chosen={sym['chosen']:04x}"]
    out = subprocess.run(cmd, input="\n".join(script) + "\n", capture_output=True, text=True).stdout
    res, cur = [], None
    hits = {}
    for line in out.splitlines():
        m = re.search(r"\] Q(\d+)$", line)
        if m:
            cur = int(m.group(1))
            hits[cur] = {}
        m = re.search(r"hit (got_line|chosen) .* af=(\w\w).* T=(\d+) dT", line)
        if m and cur is not None:
            hits[cur][m.group(1)] = (int(m.group(2), 16), int(m.group(3)))
    for i, q in enumerate(questions):
        h = hits.get(i, {})
        mem = open(dumps[i], "rb").read()
        os.unlink(dumps[i])
        lines = primo.text(mem)
        text = None
        if lines and re.match(r"^>( [~_]?)?$", lines[-1]):
            start = max((j for j in range(len(lines) - 1) if lines[j].startswith("> ")), default=None)
            if start is not None:
                skip = max(1, math.ceil((2 + len(q)) / primo.COLS))
                text = "".join(lines[start + skip:-1])
        chosen = h["chosen"][0] if "chosen" in h else None
        cycles = h["chosen"][1] - h["got_line"][1] if "chosen" in h and "got_line" in h else None
        line = mem[sym["LINE"]:sym["LINE"] + ref_helper.MAXLINE + 1].split(b"\0")[0]
        res.append((chosen, text, cycles, line, mem if i == len(questions) - 1 else None))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="mi")
    ap.add_argument("--ptp", default="MI.ptp")
    ap.add_argument("--questions", type=int, default=300)
    ap.add_argument("--show", type=int, default=3)
    args = ap.parse_args()

    r = ref_helper.Ref(os.path.join(ROOT, args.dir))
    sym = symbols(os.path.join(ROOT, "build", "asm", "mi.map"))
    image = open(os.path.join(ROOT, "build", "asm", "mi.bin"), "rb").read()
    rnd = random.Random(4)
    pool = [q for ps in tests().values() for q, _ in ps]
    rnd.shuffle(pool)
    qs = SPECIAL + [q if i % 3 else sloppy(q, rnd) for i, q in enumerate(pool[:max(0, args.questions - len(SPECIAL))])]
    per = 20
    primo._glyphs()
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [(os.path.join(ROOT, args.ptp), sym, qs[i:i + per], tmp, i) for i in range(0, len(qs), per)]
        with ThreadPoolExecutor(os.cpu_count()) as ex:
            results = [x for res in ex.map(session, jobs) for x in res]

    bad_choice = bad_text = lost = 0
    times, shown, intact = [], 0, True
    for q, (chosen, text, cycles, line, mem) in zip(qs, results):
        lost += line != r.typed(q)
        want = r.choose(line)
        want_text = r.answer(line)
        if mem is not None:
            lo, hi = sym["title"], sym["image_end"]
            intact &= mem[lo:hi] == image[lo - 0x4400:hi - 0x4400]
        if chosen != want:
            bad_choice += 1
            print(f"CHOICE  {q!r}: the PRIMO chose {chosen}, the reference {want}")
        if want is not None:
            if text is None or squeeze(text) != squeeze(want_text):
                bad_text += 1
                print(f"TEXT    {q!r}:\n   PRIMO     {text!r}\n   reference {want_text!r}")
            elif shown < args.show:
                shown += 1
                print(f"> {q}\n{want_text}\n")
            if cycles:
                times.append(cycles)
    print(f"{len(qs)} lines typed on the emulated PRIMO; {len(qs) - lost} arrived as typed")
    print(f"choice identical to the reference:  {len(qs) - bad_choice} of {len(qs)}")
    print(f"printed answer identical:            {len(times) - bad_text} of {len(times)}")
    print(f"network bytes intact after the runs: {'yes' if intact else 'NO'}")
    print(f"from RETURN to the choice: {sum(times) / len(times) / CLOCK:.2f} s at 2.5 MHz "
          f"(shortest {min(times) / CLOCK:.2f}, longest {max(times) / CLOCK:.2f})")
    sys.exit(0 if not bad_choice and not bad_text and intact else 1)


if __name__ == "__main__":
    main()
