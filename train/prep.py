#!/usr/bin/env python3
"""Prepare the ordinary Hungarian sentences, from which the network learns what is
not a question about BASIC (train/questions.py draws from them).

    data/work/tatoeba.txt   the Hungarian sentences of Tatoeba, one per line
                            (from data/raw/hun_sentences.tsv.bz2, see tools/fetch.sh)
    data/work/stories.txt   English TinyStories translated by train/translate.py,
                            folded to a small alphabet (Hungarian letters in both
                            cases, space, newline and a little punctuation); stories
                            are separated by an empty line

    python train/prep.py
"""
import bz2
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "work")

LOWER = "aábcdeéfghiíjklmnoóöőpqrstuúüűvwxyz"
UPPER = "AÁBCDEÉFGHIÍJKLMNOÓÖŐPQRSTUÚÜŰVWXYZ"
PUNCT = " \n.,!?-:"
ALPHABET = LOWER + UPPER + PUNCT

FOLD = {
    "–": "-", "—": "-", "―": "-", "‐": "-", "‑": "-", "−": "-",
    "…": ".", ";": ",",
    "õ": "ő", "û": "ű", "Õ": "Ő", "Û": "Ű", "ô": "ő", "Ô": "Ő",
    "ä": "a", "ë": "e", "à": "a", "è": "e", "â": "a", "ê": "e", "ï": "i", "î": "i",
    "ç": "c", "ñ": "n", "ý": "y", "ß": "s",
    "\t": " ", "\r": "", "\xa0": " ",
}
DROP = set("„”“\"'’‘»«()[]*_/")


def fold(text):
    out = []
    for ch in text:
        ch = FOLD.get(ch, ch)
        if ch in DROP:
            continue
        if ch in ALPHABET:
            out.append(ch)
        elif ch.isdigit():
            out.append("")
        else:
            out.append(" ")
    t = "".join(out)
    t = re.sub(r" +", " ", t)
    t = re.sub(r" ?\n ?", "\n", t)
    t = re.sub(r" ([.,!?:])", r"\1", t)
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r"-{2,}", "-", t)
    return t.strip()


def stories():
    """data/raw/tinystories_mt_hu.txt, written by train/translate.py."""
    path = os.path.join(RAW, "tinystories_mt_hu.txt")
    if not os.path.exists(path):
        print("stories: data/raw/tinystories_mt_hu.txt is not there, run train/translate.py")
        return
    docs = []
    for d in open(path, encoding="utf-8").read().split("\x00"):
        d = d.strip()
        if not d or sum(c in "wqxWQX" for c in d) > 2:       # untranslated English left in
            continue
        t = fold(re.sub(r"\n\s*\n", "\n", d))
        if len(t) > 200:
            docs.append(t)
    with open(os.path.join(OUT, "stories.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(docs) + "\n")
    print(f"stories: {len(docs)} stories")


def tatoeba():
    path = os.path.join(RAW, "hun_sentences.tsv.bz2")
    if not os.path.exists(path):
        print("tatoeba: data/raw/hun_sentences.tsv.bz2 is not there, run tools/fetch.sh")
        return
    with bz2.open(path, "rt", encoding="utf-8") as f:
        sents = [line.rstrip("\n").split("\t")[2] for line in f if line.count("\t") >= 2]
    with open(os.path.join(OUT, "tatoeba.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sents) + "\n")
    print(f"tatoeba: {len(sents)} sentences")


def main():
    os.makedirs(OUT, exist_ok=True)
    stories()
    tatoeba()


if __name__ == "__main__":
    main()
