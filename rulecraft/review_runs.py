"""The told prompt taken apart, DeepSeek (thinking off, same sampling as the other DeepSeek runs).

name  : the told prompt split into its parts, on all 760 Minecraft items, three repeats.
        NameOnly  "This image is a screenshot from Minecraft."                                  (the game's name)
        NameVer   "This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1)."    (name and version)
        Told (C2) adds "Answer according to the rules of vanilla Minecraft." and already exists.
        Writes results/r2/review_ds/rep<k>/<arm>.jsonl.

Usage: ALLOW_PEAK=1 PEAK_CAP_USD=1.0 PEAK_CAP_SINCE=<unix time> python review_runs.py name --reps 3
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import gdc
import llm
import pilot

NAME_ARMS = {"NameOnly": "This image is a screenshot from Minecraft.\n",
             "NameVer": "This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1).\n"}


def run_name(reps):
    items = [i for i in pilot.load_items() if i["set"] == "mc" and i["split"] in ("test2", "test3", "test4", "test5")]
    for rep in range(reps):
        llm.set_sampling(temperature=gdc.TEMPERATURE, seed=rep + 1)
        out = gdc.OUT / "review_ds" / f"rep{rep}"
        out.mkdir(parents=True, exist_ok=True)
        for arm, context in NAME_ARMS.items():
            def one(it, c=context, a=arm):
                pred, raw = pilot.ask(it, c, tag=a)
                return {"id": it["id"], "pred": pred, "correct": pred == it["answer"]["C2"]}
            with ThreadPoolExecutor(pilot.WORKERS) as ex:
                rows = list(ex.map(one, items))
            (out / f"{arm}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            conf = [r for r, i in zip(rows, items) if i["kind"] == "conflict"]
            print(f"rep{rep}/{arm}: conflict acc {sum(r['correct'] for r in conf) / len(conf):.3f} ({len(conf)} items)", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["name"])
    ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    llm.set_guard(floor_cny=gdc.FLOOR_CNY, wait_off_peak=False)
    run_name(a.reps)
    print("spend:", llm.spend_report(), flush=True)
