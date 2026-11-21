"""Batch 5 (test6): which card note DeepSeek's GDC answers name, replayed offline from the response cache
(the same replay as note_use.py, on the t6_ folders). No API call: a cache miss is counted and skipped.

Usage: python note_use_t6.py      writes results/r2/note_use_t6_deepseek.json
"""
import json
import re
import sys
from collections import Counter, defaultdict

import note_use as nu
from gdc2 import load_card, system_of

import llm
import pilot
from pilot import CONTEXT
from tune2 import REASON_TAIL


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    card = load_card()
    system_all = system_of(card)
    by_id = {d["id"]: d for d in card}
    pat = re.compile(r"\b(" + "|".join(map(re.escape, sorted(by_id, key=len, reverse=True))) + r")\b")
    items = {i["id"]: i for i in pilot.load_items() if i.get("split") == "test6"}
    out, miss = [], 0
    for rep in range(3):
        p = nu.OUT / f"t6_final_rep{rep}" / "GDC.jsonl"
        for r in map(json.loads, p.read_text(encoding="utf-8").splitlines()):
            it = items.get(r["id"])
            if it is None or r.get("path") != "card" or r.get("error"):
                continue
            llm.set_sampling(temperature=1.0, seed=rep + 1)
            try:
                pred, text = pilot.ask(it, CONTEXT["C0"], tail=REASON_TAIL, max_tokens=300, system=system_all, tag="GDC2")
            except RuntimeError:
                miss += 1
                continue
            named = pat.findall(text)
            out.append(dict(id=it["id"], rule=it["rule"], kind=it["kind"], rep=rep, correct=bool(r["correct"]),
                            same=pred == r["pred"], named=named[0] if named else None, text=text))
    print(f"replayed {len(out)} GDC replies, {miss} cache misses, {sum(not o['same'] for o in out)} answers differ from the log")
    for kind in ("consistent", "conflict"):
        xs = [o for o in out if o["kind"] == kind]
        err = [o for o in xs if not o["correct"]]
        notes = Counter(o["named"] for o in err)
        print(f"\n{kind}: {len(xs)} replies, {len(err)} wrong; notes named in the wrong ones: {notes.most_common(8)}")
        if kind == "consistent":
            per = defaultdict(Counter)
            for o in err:
                per[o["rule"]][o["named"]] += 1
            for rule, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
                print(f"  {rule}: {dict(c)}")
            for note, _ in notes.most_common(5):
                if note:
                    d = by_id[note]
                    print(f"  note {note}: objects {d.get('objects')} | when {d.get('trigger')} | game: {d.get('minecraft')[:160]}")
    (nu.OUT / "note_use_t6_deepseek.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")


if __name__ == "__main__":
    main()
