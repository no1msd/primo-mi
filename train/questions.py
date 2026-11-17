#!/usr/bin/env python3
"""The questions the BASIC helper is trained and tested on.

data/basic/train_a.json, train_b.json, train_c.json   questions written for every entry of
        train/kb.py by three different writers (language models briefed as children of
        different ages and moods)
data/basic/test_1.json, test_2.json                   questions by two further writers that
        never saw the training questions; used for testing only
templates (below)       plain questions about a BASIC word or an error message
none                    anything that is not about BASIC: the writers' off-topic questions and
                        ordinary Hungarian sentences (Tatoeba, translated TinyStories)

Training questions are roughed up the way children type: missing accents, missing question
marks, slips of the finger, a "légyszi" here and there.  Everything is lower case, because
that is what the PRIMO's keyboard types.
"""
import json
import os
import random
import re

from kb import KB, BY_ID, expression

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "basic")

ALLOWED = set("abcdefghijklmnopqrstuvwxyzáéíóöőúüű0123456789 ?!.,:;\"()=+-*/<>$")
MAXLEN = 45
VOWELS = "aeiouáéíóöőúüű"
# letters whose names begin with a vowel, for "az RND", "az SN error"
VOWEL_NAMED = "aefilmnorsuxy"


def norm(q):
    """A typed line as the PRIMO program hands it to the network."""
    q = "".join(c for c in q.lower() if c in ALLOWED)
    return re.sub(r" +", " ", q).strip()[:MAXLEN].strip()


def load(name):
    d = json.load(open(os.path.join(DATA, name + ".json"), encoding="utf-8"))
    return {k: [q for q in dict.fromkeys(norm(x) for x in v) if q] for k, v in d.items()}


# ---- generated questions ------------------------------------------------------------------
WORD = ["{w}", "{w}", "{w}?", "mi az a {w}", "mi az a {w}?", "mi a {w}", "mit csinál a {w}", "mire jó a {w}",
        "mire való a {w}", "mit jelent a {w}", "{w} parancs", "a {w} parancs", "mi az a {w} parancs",
        "{w} mit csinál", "{w} mire jó", "{w} mit jelent", "hogyan használjam a {w} parancsot",
        "hogy kell használni a {w} parancsot", "hogy működik a {w}", "{w} használata", "{w} példa",
        "mutass példát a {w} parancsra", "magyarázd el a {w} parancsot", "nem értem a {w} parancsot",
        "mi az hogy {w}", "{w} utasítás", "mit tud a {w}", "{w} jelentése", "segíts: {w}", "{w} mi ez",
        "mi ez a {w}", "mesélj a {w} parancsról", "a {w} mire szolgál", "mikor kell a {w}",
        "mit írjak a {w} után", "{w} hogyan", "{w} szó", "mi az a {w} szó"]
MESSAGE = ["{w}", "{w}?", "mit jelent az hogy {w}", "azt írta ki: {w}", "azt írja {w}", "mi az a {w}",
           "kiírta hogy {w}", "{w} mit jelent", "mi ez: {w}", "miért írja hogy {w}", "{w} lett kiírva"]
ERROR = ["{e}", "{e}", "{e}?", "mi az a {e}", "mi az a {e}?", "mit jelent a {e}", "{e} in {n}", "{e} in {n}",
         "{e} in {n} mit jelent", "azt írja ki {e}", "azt írja {e} in {n}", "kiírta hogy {e}",
         "miért írja hogy {e}", "{e} mi ez", "{e} mi a baj", "mi a baj {e}", "{c} hiba", "mi az a {c} hiba",
         "{e} in {n} mit csináljak", "? {e}", "hibát ír: {e}", "{e} lett", "megint {e}", "{e} jött ki",
         "mit rontottam el {e}", "{c} error mit jelent", "{e} van a {n} sorban", "a gép azt mondja {e}",
         "{e} in {n} miért", "mi az hogy {e}", "{e} in {n}?", "segíts {e}"]
NOUN = ["{w}", "{w}?", "mi az a {w}", "mi az a {w}?", "mit jelent a {w}", "{w} mit jelent", "mi az hogy {w}",
        "a {w} micsoda", "{w} mi ez", "mire jó a {w}", "mi a {w}"]
MESSAGES = {"Ok", "Break in", "Break", "?REDO", "REDO", "?Extra ignored", "Extra ignored"}
NOUNS = {"RAM", "ROM", "BASIC", "BRK", "SHIFT", "$", "?"}
PRE = ["légyszi ", "kérlek ", "primo, ", "na ", "és ", "figyelj, ", "hé ", "te, ", "figyu ", "amúgy ",
       "mondd, ", "bocsi, ", "kérdés: ", "szia, "]
POST = [" légyszi", " kérlek", " lécci", " na", " gyorsan", " lsz", " ha tudod", " pls", " mondd már"]
SHORT = str.maketrans("őűíóú", "öüiou")
PLAIN = str.maketrans("áéíóöőúüű", "aeiooouuu")


def article(text, w, rnd):
    """ "a {w}" -> "az ..." where Hungarian wants it (children get it wrong now and then)."""
    first = w.lstrip("?/")[:1]
    vowel = first in VOWELS or (len(w.rstrip("$")) <= 3 and first in VOWEL_NAMED)
    if rnd.random() < (0.85 if vowel else 0.05):
        text = text.replace(" a {w}", " az {w}").replace(" a {e}", " az {e}").replace(" a {c}", " az {c}")
        if text.startswith("a {"):
            text = "az" + text[1:]
    return text


def generated(k, rnd):
    """One generated question for an entry that explains a BASIC word or a message, or None."""
    if not k["kw"]:
        return None
    w = rnd.choice(k["kw"])
    if k["kind"] == "err":
        code = w.split()[0].lower()
        t = article(rnd.choice(ERROR), code, rnd)
        return t.format(e=code + " error", c=code, n=rnd.choice([10, 20, 30, 40, 50, 60, 70, 80, 100, 110,
                                                                   120, 150, 200, 210, 300, 1000,
                                                                   rnd.randrange(1, 999)]))
    t = rnd.choice(MESSAGE if w in MESSAGES else NOUN if w in NOUNS else WORD)
    return article(t, w.lower(), rnd).format(w=w.lower())


SUM = ["mennyi {x}", "mennyi {x}?", "{x}", "{x}", "{x}=", "{x} = ?", "számold ki {x}", "számold ki: {x}",
       "mennyi az hogy {x}", "{x} mennyi", "mi az eredménye {x}", "{x} az mennyi", "számolj: {x}",
       "hogy számolom ki {x}", "mennyi lesz {x}", "{x} mennyi lesz", "ki tudod számolni {x}", "{x}?",
       "na mennyi {x}", "mondd meg mennyi {x}", "számológép {x}", "add meg {x} eredményét"]


def a_sum(rnd):
    """A question with a sum in it, as children type sums."""
    def num():
        r = rnd.random()
        n = str(rnd.randrange(1, 10 if r < 0.3 else 100 if r < 0.75 else 1000 if r < 0.95 else 10000))
        return n + "." + str(rnd.randrange(1, 10)) if rnd.random() < 0.05 else n
    gap = rnd.choice(["", "", "", " "])
    x = num()
    for _ in range(1 if rnd.random() < 0.8 else 2):
        x += gap + rnd.choice("+-*/") + gap + num()
    return rnd.choice(SUM).format(x=x)


def sloppy(q, rnd):
    """How children type."""
    r = rnd.random()
    if r < 0.12:
        q = q.translate(PLAIN)
    elif r < 0.24:
        q = q.translate(SHORT)
    if rnd.random() < 0.35:
        q = q.rstrip("?!. ")
    elif rnd.random() < 0.1 and q[-1:] not in "?!.":
        q += "?"
    if rnd.random() < 0.06:
        q = rnd.choice(PRE) + q
    if rnd.random() < 0.05:
        q = q.rstrip("?!. ") + rnd.choice(POST)
    if rnd.random() < 0.18 and len(q) > 5:
        i = rnd.randrange(1, len(q) - 1)
        r = rnd.random()
        if r < 0.3:
            q = q[:i] + q[i + 1:]                                   # a letter left out
        elif r < 0.55:
            q = q[:i] + q[i + 1] + q[i] + q[i + 2:]                 # two letters swapped
        elif r < 0.8:
            q = q[:i] + rnd.choice("abdegiklmnorstuzé") + q[i + 1:]  # a wrong key
        else:
            q = q[:i] + q[i] + q[i:]                                # a letter twice
    if rnd.random() < 0.04:
        q = q.replace(" ", "  ", 1)
    return norm(q) or "?"


# ---- anything else --------------------------------------------------------------------------
ABOUT_BASIC = ["program", "számítógép", "szamitogep", "basic", "primo", "parancs", "képerny", "hiba",
               "error", "billenty", "számol", "rajzol", "kiír", "ciklus", "változó", "memória", "kazett",
               "gomb", "betű", "szorzótábl", "véletlen", "töröl", "szám", "sor", "ment", "tölt", "hang",
               "pont", "vonal", "kör", "ismétel", "játék", "gép", "szöveg", "kód", "jel", "nyíl"]


def other_sentences(limit=40000, seed=7):
    """Ordinary Hungarian sentences with nothing about computers in them."""
    out = []
    for name in ("tatoeba", "stories"):
        path = os.path.join(ROOT, "data", "work", name + ".txt")
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        sents = re.split(r"(?<=[.!?])\s+|\n+", text) if name != "tatoeba" else text.split("\n")
        rnd = random.Random(seed)
        rnd.shuffle(sents)
        n = 0
        for s in sents:
            q = norm(s.strip("- "))
            if 6 <= len(q) < MAXLEN and len(s) <= MAXLEN and not any(w in q for w in ABOUT_BASIC):
                out.append(q)
                n += 1
                if n >= limit // 2:
                    break
    return out


class Questions:
    """Draws (question, entry id) pairs for training."""

    def __init__(self, seed=0, writers=("train_a", "train_b", "train_c")):
        self.rnd = random.Random(seed)
        self.sets = [load(w) for w in writers]
        self.other = other_sentences()
        self.ids = [k["id"] for k in KB if k["id"] != "none"]
        self.written = {i: [q for s in self.sets for q in s.get(i, [])] for i in BY_ID}
        self.written["calc_x"] = [q for q in self.written["calc"] if expression(q)]
        self.written["calc"] = [q for q in self.written["calc"] if not expression(q)]
        # two questions of every entry are kept back to watch the training with
        self.val = []
        for i in self.ids:
            for _ in range(2 if len(self.written[i]) > 10 else 0):
                self.val.append((self.written[i].pop(self.rnd.randrange(len(self.written[i]))), i))

    def seen(self):
        """Every question a writer wrote for training (to tell which test questions are new)."""
        return {q for qs in self.written.values() for q in qs}

    def draw(self):
        rnd = self.rnd
        if rnd.random() < 0.12:
            if self.other and rnd.random() < 0.6:
                return sloppy(rnd.choice(self.other), rnd), "none"
            return sloppy(rnd.choice(self.written["none"]), rnd), "none"
        i = rnd.choice(self.ids)
        k = BY_ID[i]
        q = None
        if i == "calc_x":
            q = a_sum(rnd) if rnd.random() < 0.85 or not self.written[i] else rnd.choice(self.written[i])
            q = sloppy(q, rnd) if rnd.random() < 0.5 else norm(q)
            return (q, i) if expression(q) else self.draw()
        if k["kw"] and rnd.random() < (0.5 if k["kind"] == "err" else 0.3):
            q = generated(k, rnd)
        if q is None:
            q = rnd.choice(self.written[i])
            if k["kind"] == "err" and rnd.random() < 0.5:       # another line number
                q = re.sub(r"\d+", lambda m: str(rnd.choice([10, 20, 30, 40, 50, 100, 200,
                                                              rnd.randrange(1, 999)])), q)
        return (sloppy(q, rnd) if rnd.random() < 0.8 else norm(q)), i


def tests():
    """{writer: [(question, entry id)]} - the held-out questions, as written."""
    return {name: [(q, "calc_x" if i == "calc" and expression(q) else i)
                   for i, qs in load(name).items() for q in qs] for name in ("test_1", "test_2")}


if __name__ == "__main__":
    Q = Questions()
    print(len(Q.other), "other sentences;", sum(map(len, Q.written.values())), "written questions")
    for _ in range(40):
        q, i = Q.draw()
        print(f"{i:12s} {q}")
