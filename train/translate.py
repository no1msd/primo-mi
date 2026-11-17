#!/usr/bin/env python3
"""Make ordinary Hungarian text by machine translation.

English TinyStories (stories in the vocabulary of a small child, CDLA-Sharing-1.0)
are translated sentence by sentence with Helsinki-NLP/opus-mt-en-hu (CC-BY-4.0)
on the GPU.  English names are replaced by Hungarian ones first, so that the
translation inflects them like Hungarian words.

    python train/translate.py --stories 30000

Reads  data/raw/TinyStoriesV2-GPT4-valid.txt
Writes data/raw/tinystories_mt_hu.txt   (stories separated by a NUL line; resumable)
"""
import argparse
import os
import re
import sys

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "raw", "TinyStoriesV2-GPT4-valid.txt")
DST = os.path.join(ROOT, "data", "raw", "tinystories_mt_hu.txt")
MODEL = "Helsinki-NLP/opus-mt-en-hu"

NAMES = {
    "Tim": "Peti", "Timmy": "Peti", "Lily": "Lili", "Tom": "Tomi", "Tommy": "Tomi",
    "Sue": "Zsuzsi", "Max": "Marci", "Sam": "Samu", "Sammy": "Samu", "Ben": "Bence",
    "Benny": "Bence", "Spot": "Folti", "Mia": "Mia", "Lucy": "Luca", "Bob": "Robi",
    "Bobby": "Robi", "Amy": "Emmi", "Anna": "Anna", "Ann": "Anna", "Sally": "Sári",
    "Sara": "Sára", "Sarah": "Sára", "Fluffy": "Bolyhos", "Kitty": "Cirmi", "Jack": "Jancsi",
    "Johnny": "Jancsi", "Jane": "Janka", "Bobo": "Bobó", "Buddy": "Buksi", "John": "János",
    "Billy": "Vili", "Bill": "Vili", "Will": "Vili", "Lila": "Lilla", "Joe": "Jocó",
    "Leo": "Leó", "Whiskers": "Bajszi", "Momo": "Momó", "Mark": "Márk", "Molly": "Panni",
    "Fred": "Feri", "Ollie": "Oli", "Jen": "Jenni", "Jenny": "Jenni", "Remy": "Remi",
    "Lisa": "Liza", "Jill": "Juli", "Jerry": "Gergő", "Mary": "Mari", "Andy": "Andris",
    "Emily": "Emese", "Jake": "Jakab", "Jimmy": "Jani", "Jim": "Jani", "Pete": "Peti",
    "Peter": "Péter", "Toby": "Tóbi", "Chirpy": "Csipi", "Ducky": "Hápi", "Kim": "Kinga",
    "Rex": "Rex", "Ella": "Ella", "Emma": "Emma", "Luna": "Luna", "Bella": "Bella",
    "Mimi": "Mimi", "Lulu": "Lulu", "Daisy": "Dézi", "Poppy": "Pipacs", "Dolly": "Dolli",
}
NAME_RE = re.compile(r"\b(" + "|".join(sorted(NAMES, key=len, reverse=True)) + r")\b")
SENT_RE = re.compile(r"(?<=[.!?])[\"”’']?\s+(?=[\"“‘']?[A-Z])")
VERBS = ("mondta", "kérdezte", "válaszolta", "kiáltotta", "kiáltott", "felelte", "suttogta",
         "szólt", "sírt", "nevetett", "gondolta", "sóhajtott", "javasolta", "magyarázta")
SAID_RE = re.compile(r"[\"„”]([^\"„”]+)[\"”]\s+(" + "|".join(v.capitalize() for v in VERBS) + r")\b")


def sentences(story):
    """Paragraphs of sentences."""
    out = []
    for para in story.split("\n"):
        para = para.strip()
        if para:
            out.append([s.strip() for s in SENT_RE.split(para) if s.strip()])
    return out


def tidy(hu):
    """ "Mi ez?" Kérdezte -> - Mi ez? - kérdezte """
    return SAID_RE.sub(lambda m: f"- {m.group(1)} - {m.group(2).lower()}", hu)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stories", type=int, default=30000)
    ap.add_argument("--batch", type=int, default=192)
    ap.add_argument("--beams", type=int, default=3)
    args = ap.parse_args()

    text = open(SRC, encoding="utf-8").read()
    stories = [s.strip() for s in text.split("<|endoftext|>") if s.strip()]
    stories = [s for s in stories if 300 <= len(s) <= 1500 and s[0].isupper()][:args.stories]
    done = 0
    if os.path.exists(DST):
        done = open(DST, encoding="utf-8").read().count("\x00")
    print(f"{len(stories)} stories, {done} already translated", flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, torch_dtype=torch.float16).cuda().eval()
    out = open(DST, "a", encoding="utf-8")
    chunk = 400
    for a in range(done, len(stories), chunk):
        part = [sentences(NAME_RE.sub(lambda m: NAMES[m.group(1)], s)) for s in stories[a:a + chunk]]
        flat = [s for st in part for para in st for s in para]
        order = sorted(range(len(flat)), key=lambda i: len(flat[i]))
        hu = [None] * len(flat)
        for b in range(0, len(order), args.batch):
            idx = order[b:b + args.batch]
            x = tok([flat[i] for i in idx], return_tensors="pt", padding=True, truncation=True,
                    max_length=128).to("cuda")
            with torch.no_grad():
                y = model.generate(**x, num_beams=args.beams, max_new_tokens=128)
            for i, t in zip(idx, tok.batch_decode(y, skip_special_tokens=True)):
                hu[i] = t
        k = 0
        for st in part:
            paras, ok = [], True
            for para in st:
                sents = []
                for s in para:
                    t = hu[k]
                    k += 1
                    if len(t) > 2.2 * len(s) + 20 or len(t) < 0.3 * len(s):
                        ok = False          # the translator lost the plot
                    sents.append(tidy(t))
                paras.append(" ".join(sents))
            out.write(("\n".join(paras) if ok else "") + "\n\x00\n")
        out.flush()
        print(f"  {min(a + chunk, len(stories))} stories", flush=True)


if __name__ == "__main__":
    main()
