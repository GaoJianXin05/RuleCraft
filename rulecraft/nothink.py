"""The phenomenon on any model other than DeepSeek, without a reasoning phase: the same questions and prompts DeepSeek answered (52 conflict rules and
19 consistent rules, 8 variants each), without a hint (C0), told the world (C2) and as text (T).

Usage: LLM_PROFILE=solrun WORKERS=12 SPEND_CAP_USD=35 python nothink.py run --reps 1
Finished calls come from the cache, so raising --reps later only pays for the new repeats.
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import comb

import llm
import pilot
from analyze import cluster_ci, fmt
from analyze2 import shift_ci

OUT = llm.RESULTS / "r2"
SPLITS = {"test2": "", "test3": "t3_", "test4": "t4_"}
ARMS = {"C0": lambda it: pilot.run_context(it, "C0"), "C2": lambda it: pilot.run_context(it, "C2"), "T": pilot.run_T}


def all_items(splits=None):
    return [i for i in pilot.load_items() if i["split"] in (splits or SPLITS) and i["set"] == "mc"]


def run(reps, prefix="", start_rep=0, arms=None, kinds=None, splits=None, variants=None):
    sys.stdout.reconfigure(encoding="utf-8")
    items = [i for i in all_items(splits) if (kinds is None or i["kind"] in kinds)
             and (variants is None or int(i["id"].rsplit("_v", 1)[1]) in variants)]
    for rep in range(start_rep, reps):
        llm.set_sampling(temperature=1.0, seed=rep + 1)     # the seed labels the repeat; the hosted models use default sampling
        out = OUT / f"{prefix}nothink_{llm.PROFILE}" / f"rep{rep}"
        out.mkdir(parents=True, exist_ok=True)
        for arm, fn in ARMS.items():
            if arms is not None and arm not in arms:
                continue

            def one(it, f=fn, a=arm, r=rep):
                llm.LABEL.item = f"{it['id']}#{a}#{r}"
                try:
                    return f(it)
                except llm.BudgetExceeded:
                    raise
                except (RuntimeError, OSError) as e:      # one rejected request must not sink the run; counted, left out, re-asked on rerun
                    return {"pred": None, "correct": False, "error": str(e)[:300]}
            with ThreadPoolExecutor(pilot.WORKERS) as ex:
                rows = list(ex.map(one, items))
            merged = load(out / f"{arm}.jsonl")     # keep rows from other parts already saved in this repeat
            merged.update({i["id"]: dict(id=i["id"], **r) for i, r in zip(items, rows)})
            with open(out / f"{arm}.jsonl", "w", encoding="utf-8") as f:
                for r in merged.values():
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            good = [r for r in rows if not r.get("error")]
            print(f"{llm.PROFILE} rep{rep}/{arm}: {len(good)}/{len(rows)} answered, acc={sum(bool(r.get('correct')) for r in good) / max(1, len(good)):.3f}; "
                  f"spend (calls, list USD, CNY)={llm.profile_spend()}", flush=True)


def load(path):
    if not path.exists():
        return {}
    return {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def model_rows(reps, arm, prefix=""):
    return [load(OUT / f"{prefix}nothink_{llm.PROFILE}" / f"rep{k}" / f"{arm}.jsonl") for k in range(reps)]


def deepseek_rows(reps, arm):
    out = []
    for k in range(reps):
        d = {}
        for p in SPLITS.values():
            d.update(load(OUT / f"{p}rep{k}" / f"{arm}.jsonl"))
        out.append(d)
    return out


def mean_item(rep_rows):
    vals = defaultdict(list)
    for rows in rep_rows:
        for k, r in rows.items():
            if not r.get("error"):
                vals[k].append(float(bool(r.get("correct"))))
    return {k: sum(v) / len(v) for k, v in vals.items()}


def by_rule(items, a):
    d = defaultdict(list)
    for i in items:
        if i["id"] in a:
            d[i["rule"]].append(a[i["id"]])
    return d


def diff(items, a, b):
    d = defaultdict(list)
    for i in items:
        if i["id"] in a and i["id"] in b:
            d[i["rule"]].append(a[i["id"]] - b[i["id"]])
    return d




if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--start-rep", type=int, default=0)
    ap.add_argument("--arms", default=None)
    ap.add_argument("--kinds", default=None, help="conflict and/or consistent; all by default")
    ap.add_argument("--splits", default=None, help="comma-separated; test2, test3 and test4 by default")
    ap.add_argument("--variants", default=None, help="comma-separated variant numbers; all by default")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.reps, a.prefix, a.start_rep, set(a.arms.split(",")) if a.arms else None, set(a.kinds.split(",")) if a.kinds else None,
            set(a.splits.split(",")) if a.splits else None, {int(x) for x in a.variants.split(",")} if a.variants else None)
