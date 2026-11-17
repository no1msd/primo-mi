"""The BASIC helper's network, in two forms that share their parameters.

It does not write its answers: it reads the typed question and chooses one of the
answers of train/kb.py.  The question is taken apart into overlapping groups of one
to four characters; every group points (through a hash) at one row of a table; the
rows are added up, squashed, and a second layer turns the result into one score per
answer.  The answer with the highest score is printed.

    line      lower case, accents folded away, digits -> '#', other signs dropped
    groups    all runs of 1..4 symbols of " line "
    bucket    h = seed(n); for each symbol c: h = (h*33 xor c) mod 65536
              bucket = (h xor (h >> 7)) mod B
    hidden    S[d] = sum over groups of T[bucket][d]            T in {-1, 0, +1}  (2 bits)
              u[d] = TANH[clamp(S[d], -128, 127)]               8 bits, -127..127
    scores    Z[j] = sum over d of (L[j][d]*u[d] + 32) >> 6  +  bias[j]
                                                                L: 16 levels, -32..32 (4 bits)
    answer    the j with the largest Z[j] (the first one, if several are equal)

float mode is the same network with real numbers, used for pretraining; quant mode
computes exactly the integers above and lets gradients through the float expressions
next to them.  reference() is the same arithmetic in plain numpy, on exported arrays.
"""
import re

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

SYMS = " abcdefghijklmnopqrstuvwxyz#?!.,:;\"()=+-*/<>$"
CODE = {c: i + 1 for i, c in enumerate(SYMS)}
FOLD = str.maketrans("áéíóöőúüű0123456789", "aeiooouuu##########")
NGRAMS = (1, 2, 3, 4)
LMAX, PSHIFT = 32, 6


def symbols(line):
    """The typed line as symbol codes, with one space before and after."""
    s = "".join(c for c in line.lower().translate(FOLD) if c in CODE)
    s = " " + re.sub(r" +", " ", s).strip() + " "
    return [CODE[c] for c in s]


def features(line, B):
    """The bucket of every character group of the line (with repeats)."""
    codes = symbols(line)
    out = []
    for n in NGRAMS:
        for i in range(len(codes) - n + 1):
            h = (n * 0x2F31) & 0xFFFF
            for c in codes[i:i + n]:
                h = ((h * 33) ^ c) & 0xFFFF
            out.append((h ^ (h >> 7)) & (B - 1))
    return np.array(out, dtype=np.int64)


class Net(nn.Module):
    def __init__(self, B, D, C):
        super().__init__()
        self.B, self.D, self.C = B, D, C
        self.T = nn.Parameter(torch.randn(B, D) * 0.1)
        self.O = nn.Linear(D, C)
        self.quant = False
        self.qalpha = 1.0
        self.register_buffer("alpha", torch.tensor(0.0))        # real value of table entry +1
        self.register_buffer("levels", torch.zeros(16))         # output codebook, integers
        self.register_buffer("oscale", torch.tensor(0.0))       # real value of level LMAX

    # ---- float ----
    def forward(self, idx, off, drop=0.0):
        if self.quant:
            return self.forward_quant(idx, off)
        u = torch.tanh(F.embedding_bag(idx, self.T, off, mode="sum"))
        return self.O(F.dropout(u, drop, self.training))

    # ---- the PRIMO's arithmetic ----
    @torch.no_grad()
    def init_quant(self, thresh=0.7):
        """Fix the scale of the table (so that about the smallest half of it becomes 0) and
        fit the output layer's 16 levels to its weights."""
        a = self.T.abs()
        cut = thresh * a.mean()
        self.alpha.copy_(a[a > cut].mean())
        w = self.O.weight.abs().reshape(-1)
        w = (w / w.mean()).sort().values
        n = w.numel()
        c = torch.stack([w[int((i + 0.5) * n / 8)] for i in range(8)])
        for _ in range(60):
            idx = torch.bucketize(w, (c[1:] + c[:-1]) / 2)
            for i in range(8):
                if (idx == i).any():
                    c[i] = w[idx == i].mean()
        lv = torch.round(c / c[7] * LMAX).clamp(1, LMAX)
        for i in range(1, 8):
            if lv[i] <= lv[i - 1]:
                lv[i] = lv[i - 1] + 1
        self.levels.copy_(torch.cat([-lv.flip(0), lv.clamp(max=LMAX)]))
        self.oscale.copy_(c[7] * self.O.weight.abs().mean())
        self.quant = True

    def unit(self):
        """Real value of one step of a score."""
        return 2.0 * self.oscale / 127.0

    def table(self):
        """Integer table in {-1, 0, 1}, and the float table that stands for it."""
        t = torch.round(torch.clamp(self.T.detach() / self.alpha, -1, 1))
        return t, self.T + self.qalpha * (self.alpha * t - self.T).detach()

    def out_levels(self):
        w = self.O.weight
        t = w.detach() / self.oscale * LMAX
        code = torch.bucketize(t, (self.levels[1:] + self.levels[:-1]) / 2)
        L = self.levels[code]
        return L, code, w + self.qalpha * (L * (self.oscale / LMAX) - w).detach()

    def tanh_lut(self):
        i = torch.arange(-128, 128, device=self.T.device, dtype=torch.float32)
        return torch.round(127 * torch.tanh(self.alpha * i))

    def forward_quant(self, idx, off):
        t, tf = self.table()
        L, _, wf = self.out_levels()
        s = F.embedding_bag(idx, tf, off, mode="sum")
        u = torch.tanh(s)
        if self.qalpha < 1.0:                       # on the way to the integers: plain floats
            return u @ wf.t() + self.O.bias
        with torch.no_grad():
            S = F.embedding_bag(idx, t, off, mode="sum")
            ui = self.tanh_lut()[(S.clamp(-128, 127) + 128).long()]
            prod = ui[:, None, :] * L[None]
            Z = torch.floor((prod + (1 << (PSHIFT - 1))) / (1 << PSHIFT)).sum(-1)
            Z = Z + torch.round(self.O.bias / self.unit())
        u = u + (ui / 127.0 - u).detach()
        z = (u @ wf.t() + self.O.bias) / self.unit()
        return (z + (Z - z).detach()) * self.unit()

    @torch.no_grad()
    def arrays(self):
        """What the PRIMO program stores."""
        t, _ = self.table()
        L, code, _ = self.out_levels()
        return dict(table=t.cpu().numpy().astype(np.int8),
                    tanh=self.tanh_lut().cpu().numpy().astype(np.int16),
                    levels=self.levels.cpu().numpy().astype(np.int16),
                    codes=code.cpu().numpy().astype(np.uint8),
                    bias=torch.round(self.O.bias / self.unit()).cpu().numpy().astype(np.int32))


def reference(arr, line):
    """Scores of all answers for a typed line: the PRIMO's arithmetic on exported arrays."""
    B = arr["table"].shape[0]
    S = arr["table"][features(line, B)].astype(np.int32).sum(0)
    u = arr["tanh"][np.clip(S, -128, 127) + 128].astype(np.int32)
    L = arr["levels"][arr["codes"]].astype(np.int32)                 # [C, D]
    return ((L * u[None, :] + 32) >> 6).sum(1) + arr["bias"]
