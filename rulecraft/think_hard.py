"""DeepSeek with thinking on, on a fixed sample of the hard set (variants 0 and 5 of every rule: 120 items), bare image
(C0) and told (C2), one run. Thinking off is on file (t6_rep0-2); the comparison pairs the same items.

Usage (in rulecraft/): PEAK_CAP_USD=2 PEAK_CAP_SINCE=<unix time> WORKERS=8 python think_hard.py [--limit N]
Finished calls are cached, so running it again only asks what is missing.
"""
import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot
from item_sets import groups

OUT = llm.RESULTS / "r2" / "t6_think_deepseek"
# THINK_ALL=1: all eight variants (480 items); otherwise the 20% sample of variants 0 and 5. The sample's calls are
# cached, so the full run only asks the other variants.
VARIANTS = tuple(range(8)) if __import__("os").environ.get("THINK_ALL") == "1" else (0, 5)


def sample():
    return [i for i in pilot.load_items() if i["split"] == "test6" and i["set"] == "mc"
            and int(i["id"].rsplit("_v", 1)[1]) in VARIANTS]


def run(limit=None):
    OUT.mkdir(parents=True, exist_ok=True)
    llm.set_guard(floor_cny=None, wait_off_peak=False)
    llm.set_sampling(temperature=1.0, seed=1)
    llm.SAMPLING["thinking"] = True
    items = sample()[:limit] if limit else sample()
    for ctx in ("C0", "C2"):
        def one(it, c=ctx):
            llm.LABEL.item = f"{it['id']}#think{c}#0"
            try:
                return pilot.run_context(it, c)
            except llm.BudgetExceeded:
                raise
            except (RuntimeError, OSError) as e:
                return {"pred": None, "correct": False, "error": str(e)[:200]}
        with ThreadPoolExecutor(pilot.WORKERS) as ex:
            rows = list(ex.map(one, items))
        (OUT / f"{ctx}.jsonl").write_text("".join(json.dumps(dict(id=i["id"], **r), ensure_ascii=False) + "\n"
                                                  for i, r in zip(items, rows)), encoding="utf-8")
        bad = sum(1 for r in rows if r.get("error") or r.get("pred") is None)
        print(f"{ctx}: {len(rows)} asked, {bad} without a letter; spend {llm.spend_report(T0)}", flush=True)


def load(path):
    return {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def boot(by_rule, n=4000, seed=0):
    """Mean over rules of per-rule means, with a two-level bootstrap over rules and items within rules."""
    rng = random.Random(seed)
    rules = list(by_rule)
    est = statistics.mean(statistics.mean(v) for v in by_rule.values())
    draws = []
    for _ in range(n):
        rs = [rng.choice(rules) for _ in rules]
        draws.append(statistics.mean(statistics.mean(rng.choices(by_rule[r], k=len(by_rule[r]))) for r in rs))
    draws.sort()
    return 100 * est, 100 * draws[int(0.025 * n)], 100 * draws[int(0.975 * n)]




if __name__ == "__main__":
    import time
    sys.stdout.reconfigure(encoding="utf-8")
    T0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    run(a.limit)
