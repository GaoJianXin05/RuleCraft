"""Which note did GDC name? Replays the GDC answer calls of the held-out runs from the cache (no network) and reads the
reply text: did the model name a card note before answering, and how accurate is it with and without one.

Usage: python note_use.py            (DeepSeek, from t3/t4/t5_final_rep<k>)
       LLM_PROFILE=qwenflash python note_use.py   (from nothink_qwenflash/rep<k>)
Writes results/r2/note_use_<profile>.json.
"""
import json
import re
import sys
import urllib.request

import llm
import pilot
import own_card as s
from gdc2 import load_card, system_of
from pilot import CONTEXT
from tune2 import REASON_TAIL


def offline(*a, **k):
    raise RuntimeError("cache miss: note_use.py runs offline")


urllib.request.urlopen = offline
OUT = llm.RESULTS / "r2"


def runs():
    """(rep, rows by id) for the GDC arm on the held-out batches."""
    if llm.PROFILE_CFG:
        for rep in range(3):
            p = OUT / f"nothink_{llm.PROFILE}" / f"rep{rep}" / "GDC.jsonl"
            if p.exists():
                yield rep, {r["id"]: r for r in map(json.loads, p.read_text(encoding="utf-8").splitlines()) if r}
    else:
        for rep in range(3):
            rows = {}
            for t in ("t3", "t4", "t5"):
                p = OUT / f"{t}_final_rep{rep}" / "GDC.jsonl"
                rows.update({r["id"]: r for r in map(json.loads, p.read_text(encoding="utf-8").splitlines()) if r})
            yield rep, rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    card = json.loads(s.card_paths()[1].read_text(encoding="utf-8"))["departures"] if llm.PROFILE_CFG else load_card()
    system_all = system_of(card)
    ids = sorted({d["id"] for d in card}, key=len, reverse=True)
    pat = re.compile(r"\b(" + "|".join(map(re.escape, ids)) + r")\b")
    items = {i["id"]: i for i in pilot.load_items() if i["set"] == "mc" and i["split"] in ("test3", "test4", "test5")}
    out, miss, mismatch = [], 0, 0
    for rep, rows in runs():
        llm.set_sampling(temperature=1.0, seed=rep + 1)
        for iid, r in rows.items():
            it = items.get(iid)
            if it is None or r.get("path") != "card" or r.get("error"):
                continue
            llm.set_sampling(temperature=1.0, seed=r.get("seed") or rep + 1)   # re-asked rows carry their own label
            ctx = CONTEXT["C0"].format(mod=it.get("mod", ""))
            try:
                pred, text = pilot.ask(it, ctx, tail=REASON_TAIL, max_tokens=300, system=system_all, tag="GDC2")
            except RuntimeError:
                miss += 1
                continue
            mismatch += pred != r["pred"]
            named = pat.findall(text)
            out.append(dict(id=iid, rule=it["rule"], kind=it["kind"], rep=rep, correct=bool(r["correct"]),
                            named=named[0] if named else None, text=text))
    res = {"profile": llm.PROFILE, "replies": len(out), "cache_misses": miss, "pred_mismatch": mismatch}
    for kind in ("conflict", "consistent"):
        xs = [o for o in out if o["kind"] == kind]
        nm = [o for o in xs if o["named"]]
        no = [o for o in xs if not o["named"]]
        acc = lambda v: round(100 * sum(o["correct"] for o in v) / max(1, len(v)), 1)
        res[kind] = dict(n=len(xs), named_rate=round(100 * len(nm) / max(1, len(xs)), 1), acc_named=acc(nm),
                         acc_none=acc(no), n_named=len(nm), n_none=len(no),
                         errors_named_share=round(100 * sum(not o["correct"] for o in nm)
                                                  / max(1, sum(not o["correct"] for o in xs)), 1))
    print(json.dumps(res, indent=1))
    (OUT / f"note_use_{llm.PROFILE}.json").write_text(json.dumps({"summary": res, "replies": out}, ensure_ascii=False,
                                                                 indent=0), encoding="utf-8")


if __name__ == "__main__":
    main()
