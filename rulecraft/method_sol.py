"""The method on a hosted model with thinking off. Prompts are DeepSeek's frozen version; the card is the model's own.
Writes results/r2/nothink_<profile>/rep<k>/, merging with rows already there, so parts can run one at a time.
Finished calls come from the cache.

Usage: LLM_PROFILE=solrun REASONING_EFFORT=none WORKERS=8 python method_sol.py --splits test2 --variants 0,1,2,3 --no-ext
       LLM_PROFILE=solrun REASONING_EFFORT=none WORKERS=8 python method_sol.py --splits test2 --ext-all
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import gdc
import gdc2
import llm
import pilot
import own_card as s

OUT = llm.RESULTS / "r2"
ARMS = ["GATE", "GDC", "GateOnly", "CoT", "GKP", "FixedGame"]
EXT_ARMS = ["C0", "GATE", "CoT", "GDC", "NoGate", "FixedGame"]
MODES = {"GDC": dict(tag="GDC2"), "GateOnly": dict(use_card=False, tag="GateOnly2"), "NoGate": dict(use_gate=False, tag="NoGate2")}


def run_arm(arm, xs, gates, card, system_all, rep):
    fallback = {"world": "unknown", "game_name": "", "objects": [], "is_mc": False}

    def fn(it):
        if arm == "GATE":
            return gdc.gate(it)
        if arm == "C0":
            return pilot.run_context(it, "C0")
        if arm == "CoT":
            return pilot.run_cot(it)
        if arm == "GKP":
            return pilot.run_gkp(it)
        if arm == "FixedGame":
            return pilot.run_fixed(it)
        g = gates.get(it["id"], fallback)
        return gdc2.answer(it, fallback if g.get("error") else g, card, system_all, **MODES[arm])

    def one(it):
        llm.LABEL.item = f"{it['id']}#{arm}#{rep}"
        try:
            return fn(it)
        except llm.BudgetExceeded:
            raise
        except (RuntimeError, OSError) as e:          # one rejected request must not sink the run; counted, left out, re-asked on rerun
            return {"pred": None, "correct": False, "error": str(e)[:300]}

    with ThreadPoolExecutor(pilot.WORKERS) as ex:
        return list(ex.map(one, xs))


def merge_save(path, xs, rows):
    merged = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                merged[r["id"]] = r
    for i, r in zip(xs, rows):
        merged[i["id"]] = dict(id=i["id"], **r)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in merged.values()), encoding="utf-8")


def main(splits, variants=None, ext_mode="sample", rep=0, prefix=""):
    sys.stdout.reconfigure(encoding="utf-8")
    items = [i for i in pilot.load_items() if i["split"] in splits and i["set"] == "mc"
             and (variants is None or int(i["id"].rsplit("_v", 1)[1]) in variants)]
    if ext_mode == "all":
        ext = [i for i in pilot.load_items() if i["set"] in ("glitch", "physbench") and i["split"] == "test2"]
    elif ext_mode == "sample":
        ext = s.choose_items()[1]
    else:
        ext = []
    card_path = s.card_paths()[1]
    card = json.loads(card_path.read_text(encoding="utf-8"))["departures"]
    system_all = gdc2.system_of(card)
    llm.set_sampling(temperature=1.0, seed=rep + 1)    # the seed labels the repeat
    out = OUT / f"{prefix}nothink_{llm.PROFILE}" / f"rep{rep}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"{llm.PROFILE}: {len(items)} items, {len(ext)} outside items, card {len(card)} entries from {card_path.name}", flush=True)
    for label, xs, arms in (("", items, ARMS), ("ext_", ext, EXT_ARMS)):
        if not xs:
            continue
        gates = {}
        for arm in arms:
            rows = run_arm(arm, xs, gates, card, system_all, rep)
            if arm == "GATE":
                gates = {i["id"]: r for i, r in zip(xs, rows)}
            merge_save(out / f"{label}{arm}.jsonl", xs, rows)
            good = [r for r in rows if not r.get("error")]
            print(f"{llm.PROFILE}/{label}{arm}: {len(good)}/{len(rows)} answered, acc={sum(bool(r.get('correct')) for r in good) / max(1, len(good)):.3f}; "
                  f"spend (calls, list USD, CNY)={llm.profile_spend()}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="test3,test4")
    ap.add_argument("--variants", default=None, help="comma-separated variant numbers; all by default")
    ap.add_argument("--no-ext", action="store_true")
    ap.add_argument("--ext-all", action="store_true")
    ap.add_argument("--rep", type=int, default=0, help="run index; it labels the sampling")
    ap.add_argument("--prefix", default="", help="folder prefix, e.g. t6_ for batch 5")
    a = ap.parse_args()
    main(set(a.splits.split(",")), {int(x) for x in a.variants.split(",")} if a.variants else None,
         "none" if a.no_ext else "all" if a.ext_all else "sample", a.rep, a.prefix)
