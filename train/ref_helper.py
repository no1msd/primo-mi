#!/usr/bin/env python3
"""The BASIC helper's PRIMO program, repeated in Python on the exported bytes.

Everything z80/mi.asm computes is computed here the same way, from the same
files: the typed line as PRIMO character codes, the symbols, the buckets, the sums,
the scores, the chosen answer and the text that is printed.  tools/check_helper.py
compares the two.

    python train/ref_helper.py                  ask it questions here, without a PRIMO
    python train/ref_helper.py "hogyan törlöm a képernyőt" "sn error in 30"
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# PRIMO A-64 character codes.  Codes 1..6 select the glyphs the program adds to the
# ROM font; the keyboard gives $1E for i-acute and $1F for the power sign.
PRIMO = {
    "á": 0x7D, "é": 0x60, "ó": 0x5B, "ö": 0x7C, "ő": 0x7B, "ú": 0x5F, "ü": 0x7E, "ű": 0x7F,
    "Á": 0x5D, "É": 0x40, "Ö": 0x5C, "Ü": 0x5E,
    "í": 1, "Í": 2, "Ó": 3, "Ő": 4, "Ú": 5, "Ű": 6,
    "\n": 0x0D, "↑": 0x1F,
}
TYPED = dict(PRIMO, **{"í": 0x1E})      # what the keyboard puts into the line
MAXLINE = 60
SEEN = {v: k for k, v in PRIMO.items()}          # PRIMO code -> character, as printed


class Ref:
    def __init__(self, d):
        rd = lambda n, t=np.uint8: np.fromfile(os.path.join(d, n + ".bin"), dtype=t)
        self.meta = json.load(open(os.path.join(d, "meta.json")))
        self.B, self.D, self.C = self.meta["B"], self.meta["D"], self.meta["C"]
        self.table = rd("table").reshape(self.B, 2 * self.D // 8)
        self.tanh = rd("tanh", np.int8).astype(int)
        self.levels = np.cumsum(rd("dlevels").astype(int))
        self.ocodes = rd("ocodes").reshape(self.D, self.C // 2)
        self.bias = rd("bias", "<i2").astype(int)
        self.charmap = rd("charmap")
        self.anstab = rd("anstab", "<u2")
        self.answers = rd("answers").tobytes()
        self.hedge = rd("hedge").tobytes().rstrip(b"\0")

    # ---- the typed line ----
    @staticmethod
    def typed(line):
        """The line as the keyboard delivers it (a line given as bytes is taken as it is)."""
        if isinstance(line, bytes):
            return line[:MAXLINE]
        codes = (TYPED.get(c, ord(c)) for c in line)
        return bytes(c for c in codes if c < 256)[:MAXLINE]     # (a PRIMO has no other keys)

    def symbols(self, raw):
        out, last = [1], 1
        for c in raw:
            s = self.charmap[c] if c < 128 else 0
            if s == 0 or (s == 1 and last == 1):
                continue
            out.append(int(s))
            last = s
        if last != 1:
            out.append(1)
        return out

    # ---- the network ----
    def scores(self, line):
        syms = self.symbols(self.typed(line))
        plus = np.zeros(self.D, dtype=int)
        minus = np.zeros(self.D, dtype=int)
        for n in (1, 2, 3, 4):
            for i in range(len(syms) - n + 1):
                h = (n * 0x2F31) & 0xFFFF
                for c in syms[i:i + n]:
                    h = ((h * 33) ^ c) & 0xFFFF
                row = self.table[(h ^ (h >> 7)) & (self.B - 1)]
                bits = np.unpackbits(row)
                plus += bits[:self.D]
                minus += bits[self.D:]
        u = self.tanh[np.clip(plus - minus, -128, 127) + 128]
        z = self.bias.copy()
        for d in range(self.D):
            v = int(u[d])
            pt = [0] * 16
            for i, lv in enumerate(self.levels):
                pt[8 + i] = ((lv * v + 32) >> 6) + 64
                pt[7 - i] = ((-lv * v + 32) >> 6) + 64
            row = self.ocodes[d]
            z[0::2] += [pt[b & 15] for b in row]
            z[1::2] += [pt[b >> 4] for b in row]
        return ((z + 32768) % 65536) - 32768

    def choose(self, line):
        """Index of the answer; None if the line has nothing in it."""
        if len(self.symbols(self.typed(line))) < 2:
            return None
        return int(np.argmax(self.scores(line)))

    def unsure(self, line):
        """Is the best score less than the threshold above the second best?  (Never said of
        the answer "I do not know that".)"""
        z = np.sort(self.scores(line))
        return bool(z[-1] - z[-2] < self.meta["unsure"]) and self.choose(line) != self.meta["none"]

    # ---- the numbers taken from the line ----
    def isletter(self, c):
        return c < 128 and 2 <= self.charmap[c] <= 27

    def number(self, raw):
        best, i = None, 0
        while i < len(raw):
            if not 48 <= raw[i] <= 57:
                i += 1
                continue
            j = i
            while j < len(raw) and 48 <= raw[j] <= 57:
                j += 1
            before = raw[i - 1] if i else 32
            if before != 47 and not self.isletter(before) and j - i <= 4:
                n = raw[i:j].lstrip(b"0") or b"0"
                if best is None or (len(n), n) > (len(best), best):
                    best = n
            i = j
        return best

    def sum(self, raw):
        raw = raw + b"\0"
        digit = lambda p: 48 <= raw[p] <= 57

        def num(p):
            while digit(p):
                p += 1
            if raw[p] == 46 and digit(p + 1):
                p += 1
                while digit(p):
                    p += 1
            return p
        for start in range(len(raw)):
            if not digit(start):
                continue
            end, groups, p = num(start), 0, None
            while True:
                p = end
                while raw[p] == 32:
                    p += 1
                if raw[p] not in b"+-*/":
                    break
                p += 1
                while raw[p] == 32:
                    p += 1
                if not digit(p):
                    break
                end = num(p)
                groups += 1
            if groups:
                return raw[start:end].replace(b" ", b"")
        return None

    # ---- the answer ----
    def answer(self, line):
        """The text the PRIMO prints (None for an empty line)."""
        j = self.choose(line)
        if j is None:
            return None
        raw = self.typed(line)
        n, x = self.number(raw), self.sum(raw)
        src = self.answers[self.anstab[j]:]
        out, i = bytearray(self.hedge if self.unsure(line) else b""), 0
        while src[i]:
            c = src[i]
            i += 1
            if c in (0x10, 0x12):
                have = n if c == 0x10 else x
                if have:
                    out += have
                    i = src.index(0x11, i) + 1
            elif c == 0x13:
                if not n:
                    i = src.index(0x14, i) + 1
            elif c == 0x15:
                out += n
            elif c not in (0x11, 0x14):
                out.append(c)
        return "".join(SEEN.get(c, chr(c)) for c in out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="mi")
    ap.add_argument("line", nargs="*")
    args = ap.parse_args()
    r = Ref(os.path.join(ROOT, args.dir))
    for q in args.line:
        print(f"> {q}\n{r.answer(q)}\n")
    if not args.line:
        print(f"The PRIMO helper, computed here from the bytes in {args.dir}/.  Empty line: quit.\n")
        while True:
            try:
                q = input("> ")
            except EOFError:
                break
            if not q.strip():
                break
            a = r.answer(q)
            if a is not None:
                print(a + "\n")
