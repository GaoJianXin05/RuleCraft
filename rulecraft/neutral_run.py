"""A neutral prompt: asks for the rules of the world shown, with neither the game's name nor a word about real-world
physics. It tests one reading of the bare-image gap: that the question merely leaves open which world to answer for.

Neutral  "Answer according to the rules that govern the world shown in the image."

Items: the Minecraft test items (all four batches by default; --splits to restrict) and the 160 outside items
(GlitchBench, PhysBench). Thinking off, temperature 1.0, the seed labels the run, as for C0 and C2.
Writes results/r2/neutral_<profile>/rep<k>/Neutral.jsonl and ext_Neutral.jsonl; finished calls come from the cache.

Usage: python neutral_run.py --reps 3
       LLM_PROFILE=qwenflash WORKERS=8 SPEND_CAP_CNY=8 python neutral_run.py --reps 3 --splits test3,test4,test5
Hard set (2026-11-17), written to results/r2/t6_neutral_<profile>/:
       python neutral_run.py --reps 3 --splits test6 --prefix t6_ --no-ext
       LLM_PROFILE=solrun WORKERS=12 python neutral_run.py --reps 3 --splits test6 --prefix t6_ --no-ext --conflict-only-after 1
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot

NEUTRAL = "Answer according to the rules that govern the world shown in the image.\n"
OUT = llm.RESULTS / "r2"


def one(it, rep):
    llm.LABEL.item = f"{it['id']}#Neutral#{rep}"
    try:
        pred, _ = pilot.ask(it, NEUTRAL, tag="Neutral")
        return {"id": it["id"], "pred": pred, "correct": pred == it["answer"]["C0"]}
    except llm.BudgetExceeded:
        raise
    except (RuntimeError, OSError) as e:       # a rejected request is recorded as missing and re-asked on the next run
        return {"id": it["id"], "pred": None, "correct": False, "error": str(e)[:300]}


def main(reps, splits, prefix="", no_ext=False, conflict_only_after=None):
    sys.stdout.reconfigure(encoding="utf-8")
    items = pilot.load_items()
    mc_all = [i for i in items if i["set"] == "mc" and i["split"] in splits]
    ext = [] if no_ext else [i for i in items if i["set"] in ("glitch", "physbench") and i["split"] == "test2"]
    for rep in range(reps):
        llm.set_sampling(temperature=1.0, seed=rep + 1)
        out = OUT / f"{prefix}neutral_{llm.PROFILE}" / f"rep{rep}"
        out.mkdir(parents=True, exist_ok=True)
        # GPT-6.1-Sol answered consistent rules once and conflict rules three times; the same plan here
        mc = [i for i in mc_all if conflict_only_after is None or rep < conflict_only_after or i["kind"] == "conflict"]
        for name, xs in (("Neutral", mc), ("ext_Neutral", ext)):
            if not xs:
                continue
            with ThreadPoolExecutor(pilot.WORKERS) as ex:
                rows = list(ex.map(lambda it: one(it, rep), xs))
            (out / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            good = [r for r in rows if not r.get("error")]
            conf = [r for r, i in zip(rows, xs) if i["kind"] == "conflict" and not r.get("error")]
            print(f"{llm.PROFILE} rep{rep}/{name}: {len(good)}/{len(rows)} answered, acc {sum(r['correct'] for r in good) / max(1, len(good)):.3f}"
                  + (f", conflict {sum(r['correct'] for r in conf) / len(conf):.3f} ({len(conf)} items)" if conf else ""), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--splits", default="test2,test3,test4,test5")
    ap.add_argument("--prefix", default="", help="t6_ for the hard set, so that the main-set files are left alone")
    ap.add_argument("--no-ext", action="store_true", help="skip the outside items")
    ap.add_argument("--conflict-only-after", type=int, default=None, help="from this repeat on, conflict rules only")
    a = ap.parse_args()
    if not llm.PROFILE_CFG:
        llm.set_guard(floor_cny=1.0, wait_off_peak=True)
    main(a.reps, set(a.splits.split(",")), a.prefix, a.no_ext, a.conflict_only_after)
    print("spend:", llm.profile_spend() if llm.PROFILE_CFG else llm.spend_report(), flush=True)
