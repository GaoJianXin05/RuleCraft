"""How the human baseline (version 5) draws each participant's questions; shared by build.py (the page) and score.py
(the check).

Every participant answers 100 of the 155 rules, one variant each. The 100 are drawn at random, stratified by rule type so
that every participant gets the same mix: the quota of each stratum (main conflict, main consistent, hard passive
conflict, hard action conflict, hard consistent) is its share of the 155 rules times 100, rounded by largest remainder,
so every rule has nearly the same chance (about 64%) of being drawn. The draw, the variants and the order all follow
from the experiment id: offset = FNV-1a(id) mod 8 and the j-th rule of a set (in sorted order) uses variant
(offset + j) mod 8, the same variants as the 95-rule version 2; the page draws the rules and shuffles the order with a
generator seeded by the same hash.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
PILOT = HERE.parent / "rulecraft"
SPLITS = {"main": ("test2", "test3", "test4", "test5"), "hard": ("test6",)}
TOTAL = 100


def load_items():
    return {i["id"]: i for i in json.loads((PILOT / "data" / "items.json").read_text(encoding="utf-8"))}


def rule_lists(items):
    return {part: sorted({i["rule"] for i in items.values() if i.get("set") == "mc" and i["split"] in sp})
            for part, sp in SPLITS.items()}


def strata(items):
    """rule -> (set, kind, act); act only for hard conflict rules."""
    sys.path.insert(0, str(PILOT))
    from rules import RULE_BY_ID
    out = {}
    for i in items.values():
        part = next((p for p, sp in SPLITS.items() if i.get("set") == "mc" and i["split"] in sp), None)
        if part:
            act = RULE_BY_ID[i["rule"]]["act"] if part == "hard" and i["kind"] == "conflict" else ""
            out[i["rule"]] = (part, i["kind"], act)
    return out


def plan(items, total=TOTAL):
    """The strata in a fixed order, each with its sorted rules and its quota."""
    st = strata(items)
    keys = sorted(set(st.values()))
    n = len(st)
    raw = {k: total * sum(v == k for v in st.values()) / n for k in keys}
    take = {k: int(raw[k]) for k in keys}
    for k in sorted(keys, key=lambda k: raw[k] - take[k], reverse=True)[:total - sum(take.values())]:
        take[k] += 1
    return [{"key": "/".join(x for x in k if x), "rules": sorted(r for r, v in st.items() if v == k), "take": take[k]}
            for k in keys]


def rule_index(items):
    """j of every rule: its index in its set's sorted rule list."""
    return {r: j for rs in rule_lists(items).values() for j, r in enumerate(rs)}


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def check(pid, offset, item_ids, items, strata_plan, rj):
    """A version-5 item list is valid for this id: right offset, one item per rule, the id's variant of each rule, and
    the quota of every stratum. Returns an error message or None."""
    if offset != fnv1a(pid) % 8:
        return "offset does not match the id"
    rules = [i.rsplit("_v", 1)[0] for i in item_ids]
    if len(set(rules)) != len(rules) or len(rules) != TOTAL:
        return f"{len(rules)} items over {len(set(rules))} rules"
    if any(int(i.rsplit("_v", 1)[1]) != (offset + rj[r]) % 8 for i, r in zip(item_ids, rules)):
        return "a variant does not match the id"
    for s in strata_plan:
        if sum(r in s["rules"] for r in rules) != s["take"]:
            return f"stratum {s['key']} does not hold its quota"
    return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = plan(load_items())
    for s in p:
        print(f"{s['key']:22s} {len(s['rules']):3d} rules, draw {s['take']:3d} ({s['take'] / len(s['rules']):.0%})")
    print("total", sum(s["take"] for s in p))
