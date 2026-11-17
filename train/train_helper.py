#!/usr/bin/env python3
"""Train the BASIC helper's network (train/helper.py).

Two phases: floating point first, then the PRIMO's integer arithmetic - a 2-bit table
and a 4-bit output layer - reached gradually, while imitating the floating-point
network.  The held-out test questions are not touched here (train/eval_helper.py).

    python train/train_helper.py --name mi
Writes build/<name>.float.pt and build/<name>.pt
"""
import argparse
import copy
import os
import random
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helper import Net, features
from kb import KB
from questions import Questions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = [k["id"] for k in KB]


def bags(lines, B, dev, rng=None, drop=0.0):
    parts = [features(q, B) for q in lines] if isinstance(lines[0], str) else lines
    if rng is not None and drop:
        parts = [p[rng.random(len(p)) > drop] for p in parts]
    off = np.cumsum([0] + [len(p) for p in parts[:-1]])
    return torch.from_numpy(np.concatenate(parts)).to(dev), torch.from_numpy(off).to(dev)


@torch.no_grad()
def choose(model, lines, n=2048):
    """The entry the network chooses for every line."""
    model.eval()
    out = []
    for i in range(0, len(lines), n):
        out += model(*bags(lines[i:i + n], model.B, model.T.device)).argmax(-1).tolist()
    model.train()
    return [IDS[j] for j in out]


def accuracy(model, pairs):
    got = choose(model, [q for q, _ in pairs])
    return 100 * sum(a == i for a, (_, i) in zip(got, pairs)) / len(pairs)


def run(model, feat, Y, val, steps, batch, lr, wd, drop, hdrop, label, ramp=0, teacher=None, soft=None,
        every=1000):
    """teacher: a network whose scores are imitated (on the same character groups);
    soft: instead, the scores a larger network gave to every question of the pool."""
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.05)
    rng = np.random.default_rng(0)
    t0 = time.time()
    for step in range(1, steps + 1):
        if ramp:
            model.qalpha = min(1.0, step / ramp)
        rows = rng.integers(0, len(feat), batch)
        idx, off = bags([feat[r] for r in rows], model.B, Y.device, rng, drop)
        logits = model(idx, off) if model.quant else model(idx, off, hdrop)
        loss = F.cross_entropy(logits, Y[rows])
        if teacher is not None or soft is not None:
            with torch.no_grad():
                tl = soft[rows].float() if soft is not None else teacher(idx, off)
            loss = 0.5 * loss + 0.5 * F.kl_div(F.log_softmax(logits, -1), F.softmax(tl, -1),
                                               reduction="batchmean")
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        sched.step()
        if step % every == 0 or step == steps:
            print(f"  {label} step {step:6d} loss {loss.item():.4f}  kept-back questions right "
                  f"{accuracy(model, val):5.1f}%  ({time.time() - t0:.0f}s)", flush=True)
    model.qalpha = 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="mi")
    ap.add_argument("--buckets", type=int, default=1024)
    ap.add_argument("--dim", type=int, default=64)
    ap.add_argument("--steps", type=int, default=8000)
    ap.add_argument("--qsteps", type=int, default=6000)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--qlr", type=float, default=1e-3)
    ap.add_argument("--wd", type=float, default=0.01)
    ap.add_argument("--drop", type=float, default=0.3, help="share of character groups left out")
    ap.add_argument("--hdrop", type=float, default=0.2)
    ap.add_argument("--thresh", type=float, default=0.7)
    ap.add_argument("--ramp", type=float, default=0.5)
    ap.add_argument("--pool", type=int, default=300000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--float-from", default="")
    ap.add_argument("--teacher", default="", help="imitate build/<this>.float.pt, a larger network")
    args = ap.parse_args()

    dev = "cuda"
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    Q = Questions(seed=args.seed)
    pool = [Q.draw() for _ in range(args.pool)]
    feat = [features(q, args.buckets) for q, _ in pool]
    Y = torch.tensor([IDS.index(i) for _, i in pool], device=dev)
    model = Net(args.buckets, args.dim, len(IDS)).to(dev)
    size = args.buckets * args.dim // 4 + args.dim * len(IDS) // 2 + 2 * len(IDS) + 256
    print(f"{args.name}: {len(IDS)} answers, table {args.buckets} x {args.dim}, {size} bytes on the PRIMO; "
          f"a question has {sum(map(len, feat)) / len(feat):.0f} character groups", flush=True)
    out = os.path.join(ROOT, "build", args.name)
    soft = None
    if args.teacher:
        ck = torch.load(os.path.join(ROOT, "build", args.teacher + ".float.pt"), map_location=dev)
        big = Net(ck["args"]["buckets"], ck["args"]["dim"], len(IDS)).to(dev)
        big.load_state_dict(ck["state"])
        big.eval()
        with torch.no_grad():
            soft = torch.cat([big(*bags([q for q, _ in pool[i:i + 4096]], big.B, dev)).half()
                              for i in range(0, len(pool), 4096)])
        print(f"teacher {args.teacher}: kept-back questions right {accuracy(big, Q.val):.1f}%", flush=True)
        del big
    if args.float_from:
        ck = torch.load(os.path.join(ROOT, "build", args.float_from + ".float.pt"), map_location=dev)
        model.load_state_dict(ck["state"])
    else:
        run(model, feat, Y, Q.val, args.steps, args.batch, args.lr, args.wd, args.drop, args.hdrop, "float",
            soft=soft)
        torch.save({"state": model.state_dict(), "args": vars(args), "quant": False}, out + ".float.pt")
    print(f"float: kept-back questions right {accuracy(model, Q.val):.1f}%", flush=True)
    if args.qsteps:
        teacher = copy.deepcopy(model).eval()
        for p in teacher.parameters():
            p.requires_grad_(False)
        model.init_quant(args.thresh)
        t, _ = model.table()
        print(f"table: {100 * float((t == 0).float().mean()):.0f}% zeros; output levels "
              f"{[int(v) for v in model.levels.tolist()[8:]]}; before fine-tuning "
              f"{accuracy(model, Q.val):.1f}%", flush=True)
        run(model, feat, Y, Q.val, args.qsteps, args.batch, args.qlr, 0.0, args.drop / 2, 0.0, "PRIMO",
            ramp=int(args.ramp * args.qsteps), teacher=None if args.teacher else teacher, soft=soft)
        torch.save({"state": model.state_dict(), "args": vars(args), "quant": True}, out + ".pt")


if __name__ == "__main__":
    main()
