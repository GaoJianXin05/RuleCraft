"""Question groups and scoring helpers shared by the analysis scripts (no API call).

groups(part)   the questions of one set ("main": 95 rules, "hard": 60 rules) by kind and rule type: conflict rules
               split into passive (only time or weather acts) and action (something is done to the scene), and
               consistent rules
read, collect  answer rows of one file / of several runs, by question id
means          per question, the share of runs answered correctly
acc, dci       accuracy (%) and a paired difference (points) with a two-level bootstrap CI (rules, then questions)
direction      how many wrong answers pick the option of a given kind
"""
import json
import re
from collections import defaultdict
from pathlib import Path

from analyze import cluster_ci as _cluster_ci
from analyze2 import shift_ci as _shift_ci
from rules import RULE_BY_ID

HERE = Path(__file__).parent
ITEMS = {i["id"]: i for i in json.loads((HERE / "data" / "items.json").read_text(encoding="utf-8"))}
SETS = {"main": ("test2", "test3", "test4", "test5"), "hard": ("test6",)}
PASSIVE_MAIN_EXTRA = {"F13"}      # only weather acts ("It rains heavily for several hours"), without the word "pass"


def passive_main(it):
    """Main set: rule type read from the action text (the hard set has it fixed in its rule definitions)."""
    if it["rule"] in PASSIVE_MAIN_EXTRA:
        return True
    a = it["action"].lower()
    return bool(re.search(r"\bpass(es)?\b", a)) and not re.search(
        r"is (broken|placed|poured|lit|scooped|hit|punched|chopped)|are chopped", a)


def groups(part):
    items = [i for i in ITEMS.values() if i["set"] == "mc" and i["split"] in SETS[part]]
    if part == "main":
        act = lambda i: "passive" if passive_main(i) else "action"
    else:
        act = lambda i: RULE_BY_ID[i["rule"]]["act"]
    return {"conflict, passive": [i for i in items if i["kind"] == "conflict" and act(i) == "passive"],
            "conflict, action": [i for i in items if i["kind"] == "conflict" and act(i) == "action"],
            "conflict, all": [i for i in items if i["kind"] == "conflict"],
            "consistent": [i for i in items if i["kind"] == "consistent"]}


def read(path):
    rows = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("error"):
                    rows[r["id"]] = r
    return rows


def collect(paths):
    """{question id: [row per run]} over the given files."""
    out = defaultdict(list)
    for p in paths:
        for k, r in read(p).items():
            out[k].append(r)
    return out


def means(rows, items):
    return {i["id"]: sum(bool(r.get("correct")) for r in rows[i["id"]]) / len(rows[i["id"]])
            for i in items if rows.get(i["id"])}


def _by_rule(items, m):
    d = defaultdict(list)
    for i in items:
        if i["id"] in m:
            d[i["rule"]].append(m[i["id"]])
    return d


def acc(items, m):
    ci = _cluster_ci(_by_rule(items, m))
    return None if ci is None else 100 * ci[0]


def dci(items, a, b):
    d = defaultdict(list)
    for i in items:
        if i["id"] in a and i["id"] in b:
            d[i["rule"]].append(a[i["id"]] - b[i["id"]])
    ci = _shift_ci(d)
    return None if ci is None else tuple(100 * x for x in ci)


def key_of(it, letter):
    return {o[0]: o[2] for o in it["options"]}.get(letter)


def direction(rws, items, key):
    """Wrong answers (all runs) that pick the option with this key (vanilla, real, third, correct, over), and all."""
    hit = wrong = 0
    for it in items:
        for r in rws.get(it["id"], []):
            if not r.get("correct") and r.get("pred"):
                wrong += 1
                hit += key_of(it, r["pred"]) == key
    return hit, wrong


mt = __import__(__name__)       # older scripts reach the scoring helpers as S.mt.<name>
