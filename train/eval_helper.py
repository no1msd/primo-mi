#!/usr/bin/env python3
"""Test the BASIC helper on questions it has never seen.

The test questions (data/basic/test_1.json, test_2.json) were written by two writers
that never saw the training questions.  An answer is right only if the network chose
the entry the question was written for.

    python train/eval_helper.py --name mi [--float] [--show 20]
    python train/eval_helper.py --dir mi      the exported bytes, as the PRIMO runs them
"""
import argparse
import collections
import os
import random
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helper import Net
from kb import KB, BY_ID, fill
from questions import Questions, tests, sloppy
from train_helper import choose

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {"cmd": "BASIC words", "how": "how do I ...", "idea": "ideas and messages",
         "err": "error messages", "prog": "write me a program", "talk": "small talk"}


def load(name, floating=False):
    ck = torch.load(os.path.join(ROOT, "build", name + (".float.pt" if floating else ".pt")),
                    map_location="cuda")
    a = ck["args"]
    m = Net(a["buckets"], a["dim"], len(KB)).cuda()
    m.load_state_dict(ck["state"])
    m.quant = not floating
    return m.eval()


def exported(d):
    """The test with train/ref_helper.py: what the PRIMO program answers."""
    import ref_helper
    r = ref_helper.Ref(os.path.join(ROOT, d))
    ids = r.meta["ids"]
    seen = Questions().seen()
    for name, pairs in tests().items():
        rnd = random.Random(1)
        rough = [(sloppy(q, rnd), i) for q, i in pairs]
        for label, ps in ((name, pairs), (name + ", typed sloppily", rough)):
            got = [ids[r.choose(q)] for q, _ in ps]
            right = [g == i for g, (_, i) in zip(got, ps)]
            line = f"{label:28s} right {sum(right):5d} of {len(ps)} ({100 * sum(right) / len(ps):.1f}%)"
            if label == name:
                new = [ok for ok, (q, _) in zip(right, ps) if q not in seen]
                off = [g == "none" for g, (_, i) in zip(got, ps) if i == "none"]
                hedged = [r.unsure(q) for q, _ in ps]
                hw = sum(h and not ok for h, ok in zip(hedged, right))
                line += (f"\n    new to the network: {sum(new)} of {len(new)} ({100 * sum(new) / len(new):.1f}%)"
                         f"\n    not about BASIC, answered 'I do not know that': {sum(off)} of {len(off)}"
                         f"\n    'not sure' said before {sum(hedged)} answers, {hw} of them wrong; "
                         f"wrong without that warning: {len(ps) - sum(right) - hw} ({100 * (len(ps) - sum(right) - hw) / len(ps):.1f}%)")
            print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="mi")
    ap.add_argument("--dir", default="", help="test the exported bytes in this directory instead")
    ap.add_argument("--float", action="store_true")
    ap.add_argument("--show", type=int, default=0, help="print this many wrong answers")
    ap.add_argument("--brief", action="store_true")
    args = ap.parse_args()
    if args.dir:
        return exported(args.dir)
    m = load(args.name, args.float)
    Q = Questions()
    seen = Q.seen() | {q for q, _ in Q.val}
    wrong = []
    for name, pairs in tests().items():
        rnd = random.Random(1)
        rough = [(sloppy(q, rnd), i) for q, i in pairs]
        for label, ps in ((name, pairs), (name + ", typed sloppily", rough)):
            got = choose(m, [q for q, _ in ps])
            rows = collections.defaultdict(lambda: [0, 0])
            shrug = 0
            for g, (q, i) in zip(got, ps):
                group = "not about BASIC" if i == "none" else KINDS[BY_ID[i]["kind"]]
                for key in (group, "all") + (("new to the network",) if q not in seen else ()):
                    rows[key][0] += g == i
                    rows[key][1] += 1
                shrug += i != "none" and g == "none"
                if g != i and label == name:
                    wrong.append((q, i, g))
            if args.brief:
                print(f"{label:28s} {100 * rows['all'][0] / rows['all'][1]:5.1f}%   new to the network "
                      f"{100 * rows['new to the network'][0] / rows['new to the network'][1]:5.1f}%")
                continue
            print(f"{label}: {len(ps)} questions")
            for key in ["all", "new to the network", *KINDS.values(), "not about BASIC"]:
                r, n = rows[key]
                print(f"    {key:22s} {r:5d} of {n:5d} right ({100 * r / n:5.1f}%)")
            print(f"    'I do not know' to a question about BASIC: {shrug}")
    random.Random(2).shuffle(wrong)
    for q, i, g in wrong[:args.show]:
        print(f"  {q!r}\n      wanted [{i}], got [{g}]: {fill(BY_ID[g]['a'], q)!r}")


if __name__ == "__main__":
    main()
