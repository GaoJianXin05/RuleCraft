"""Matched control for the card: the gate with the told prompt and no card.

GateTold takes the saved gate reply of the same run (no new gate call). If the gate names Minecraft, the question carries
the told wording of C2 (vanilla Minecraft, Java Edition 1.20.1) and the chain-of-thought tail of GateOnly, with no card.
Otherwise the item takes GateOnly's row of the same run, which is the same chain-of-thought request.

DeepSeek (default profile): reads <t>_rep<k>/GATE.jsonl and <t>_final_rep<k>/GateOnly.jsonl, writes GateTold.jsonl there.
Other models: reads and writes nothink_<profile>/rep<k>/. A call that fails is asked again, up to four times, with a new
sampling label, which the row keeps as "seed".

Usage (Git Bash, from rulecraft/):
  ALLOW_PEAK=1 PEAK_CAP_USD=1.0 PEAK_CAP_SINCE=<t> python gate_told.py --reps 3
  LLM_PROFILE=solrun WORKERS=6 SPEND_CAP_USD=<cap> python gate_told.py --reps 1
  LLM_PROFILE=qwenflash WORKERS=8 SPEND_CAP_CNY=<cap> python gate_told.py --reps 3
"""
import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import gdc
import llm
import pilot
from pilot import CONTEXT, COT_TAIL, ask

OUT = llm.RESULTS / "r2"
SPLITS = {"test3": "t3_", "test4": "t4_", "test5": "t5_"}
PROFILE_PREFIX = ""          # folder prefix of the other models' runs; --split/--prefix point both at one batch
FALLBACK = {"world": "unknown", "game_name": "", "objects": [], "is_mc": False}
def load(path):
    return {r["id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if r} if path.exists() else {}


def save(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows.values()), encoding="utf-8")


def folders(rep):
    """(gate file, GateOnly file, output file, held-out Minecraft items) per folder of this model and run."""
    items = [i for i in pilot.load_items() if i["set"] == "mc"]
    if llm.PROFILE_CFG:
        d = OUT / f"{PROFILE_PREFIX}nothink_{llm.PROFILE}" / f"rep{rep}"
        yield d / "GATE.jsonl", d / "GateOnly.jsonl", d / "GateTold.jsonl", [i for i in items if i["split"] in SPLITS]
    else:
        for split, prefix in SPLITS.items():
            yield (OUT / f"{prefix}rep{rep}" / "GATE.jsonl", OUT / f"{prefix}final_rep{rep}" / "GateOnly.jsonl",
                   OUT / f"{prefix}final_rep{rep}" / "GateTold.jsonl", [i for i in items if i["split"] == split])


def told(it):
    """One GateTold call under the current sampling label."""
    pred, _ = ask(it, CONTEXT["C2"], tail=COT_TAIL, max_tokens=700, tag="GateTold")
    return {"pred": pred, "correct": pred == it["answer"]["C0"], "path": "told"}


def run(reps):
    for rep in range(reps):
        for gate_f, only_f, out_f, items in folders(rep):
            gates, only, rows = load(gate_f), load(only_f), load(out_f)
            todo = []
            for it in items:
                g = gates.get(it["id"], FALLBACK)
                g = FALLBACK if g.get("error") else g
                if not g["is_mc"]:                       # the same chain-of-thought request as GateOnly
                    o = only[it["id"]]
                    assert o.get("path") in ("default", None), (it["id"], o.get("path"))
                    rows[it["id"]] = dict(o, copied="GateOnly")
                elif it["id"] not in rows or rows[it["id"]].get("error"):
                    todo.append((it, g))
            asked = len(todo)
            for attempt in range(4):                     # a new sampling label per attempt: same request, new cache key
                if not todo:
                    break
                seed = rep + 1 + (0 if attempt == 0 else 2000 + 100 * attempt)
                llm.set_sampling(temperature=1.0 if llm.PROFILE_CFG else gdc.TEMPERATURE, seed=seed)

                def one(arg, a=attempt, s=seed):
                    it, g = arg
                    llm.LABEL.item = f"{it['id']}#GateTold#{rep}#{a}"
                    try:
                        res = told(it)
                    except llm.BudgetExceeded:
                        raise
                    except (RuntimeError, OSError) as e:
                        return dict(id=it["id"], pred=None, correct=False, error=str(e)[:300], world=g["world"])
                    return dict(id=it["id"], world=g["world"], **res, seed=s)

                with ThreadPoolExecutor(pilot.WORKERS) as ex:
                    got = list(ex.map(one, todo))
                for r in got:
                    rows[r["id"]] = r
                todo = [arg for arg, r in zip(todo, got) if r.get("error")]
            rows = {i["id"]: rows[i["id"]] for i in items if i["id"] in rows}
            save(out_f, rows)
            ok = [r for r in rows.values() if not r.get("error")]
            print(f"{llm.PROFILE} rep{rep} {out_f.parent.name}: {asked} asked, {len(ok)}/{len(items)} answered, "
                  f"acc={sum(bool(r['correct']) for r in ok) / max(1, len(ok)):.3f}, errors={len(rows) - len(ok)}; "
                  f"spend={llm.profile_spend() if llm.PROFILE_CFG else llm.spend_report()}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--split", default=None, help="one batch instead of the held-out batches 2-4, e.g. test6")
    ap.add_argument("--prefix", default="", help="folder prefix of that batch, e.g. t6_")
    a = ap.parse_args()
    if a.split:
        SPLITS = {a.split: a.prefix}
        PROFILE_PREFIX = a.prefix
    if not llm.PROFILE_CFG and not llm.MOCK:
        llm.set_guard(floor_cny=gdc.FLOOR_CNY, wait_off_peak=os.environ.get("ALLOW_PEAK") != "1")
    run(a.reps)
