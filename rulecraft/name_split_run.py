"""The told prompt taken apart on the hard set, and the text condition with no world named.

NameOnly     "This image is a screenshot from Minecraft."                                (the game's name, no instruction)
NameVer      "This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1)."  (name and version, no instruction)
TextUnnamed  the text condition without its opening "In vanilla Minecraft (Java Edition 1.20.1):"

The image arms run for the three cue models (deepseek, solrun, qwenflash) with the plan of the neutral prompt (three
runs; GPT-6.1-Sol conflict rules only from the second run on). TextUnnamed runs for the six core models with the plan
of the text condition (DeepSeek three runs, the others one). Temperature 1.0, the seed labels the run, as for C0 and C2.
The answer key is the game outcome, as in every condition. No prompt was changed after any answer was seen.
Writes results/r2/t6_namesplit_<profile>/rep<k>/<arm>.jsonl; finished calls come from the cache.

Usage: LLM_PROFILE=qwenflash python name_split_run.py --arms NameOnly,NameVer --reps 3 --budget 10
       python name_split_run.py --arms TextUnnamed --reps 1 --limit 12     (probe)
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot

OUT = llm.RESULTS / "r2"
NAME = {"NameOnly": "This image is a screenshot from Minecraft.\n",
        "NameVer": "This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1).\n"}


def text_unnamed(it):
    prompt = f"{it['text_scene']}\n{pilot.question_block(it)}\n{pilot.TAIL}"
    r = llm.chat([llm.user(prompt)], max_tokens=20, tag="TextUnnamed")
    pred = llm.parse_letter(r["text"], pilot.letters_of(it))
    return {"pred": pred, "correct": pred == it["answer"]["T"]}


def image_arm(arm):
    def f(it):
        pred, _ = pilot.ask(it, NAME[arm], tag=arm)
        return {"pred": pred, "correct": pred == it["answer"]["C0"]}
    return f


def one(fn, it, arm, rep):
    llm.LABEL.item = f"{it['id']}#{arm}#{rep}"
    try:
        return dict(id=it["id"], **fn(it))
    except llm.BudgetExceeded:
        raise
    except (RuntimeError, OSError) as e:
        return {"id": it["id"], "pred": None, "correct": False, "error": str(e)[:300]}


def main(arms, reps, conflict_only_after, limit):
    sys.stdout.reconfigure(encoding="utf-8")
    items = [i for i in pilot.load_items() if i["set"] == "mc" and i["split"] == "test6"]
    if limit:
        items = items[::max(1, len(items) // limit)][:limit]
    for rep in range(reps):
        llm.set_sampling(temperature=1.0, seed=rep + 1)
        out = OUT / ("probe_namesplit" if limit else "t6_namesplit") / llm.PROFILE / f"rep{rep}"
        out.mkdir(parents=True, exist_ok=True)
        xs = [i for i in items if conflict_only_after is None or rep < conflict_only_after or i["kind"] == "conflict"]
        for arm in arms:
            fn = text_unnamed if arm == "TextUnnamed" else image_arm(arm)
            with ThreadPoolExecutor(pilot.WORKERS) as ex:
                rows = list(ex.map(lambda it: one(fn, it, arm, rep), xs))
            (out / f"{arm}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            good = [r for r in rows if not r.get("error")]
            conf = [r for r, i in zip(rows, xs) if i["kind"] == "conflict" and not r.get("error")]
            print(f"{llm.PROFILE} rep{rep}/{arm}: {len(good)}/{len(rows)} answered, "
                  f"conflict {sum(r['correct'] for r in conf) / max(1, len(conf)):.3f} ({len(conf)})", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="NameOnly,NameVer")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--conflict-only-after", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0, help="probe on this many items")
    ap.add_argument("--budget", type=float, default=None, help="cap this run's spend (CNY, or USD for solrun)")
    a = ap.parse_args()
    if llm.PROFILE_CFG:
        if a.budget is not None:
            _, usd, cny = llm.profile_spend()
            if llm.PROFILE == "solrun":
                os.environ["SPEND_CAP_USD"] = str(usd + a.budget)
            else:
                os.environ["SPEND_CAP_CNY"] = str(cny + a.budget)
    else:
        llm.set_guard(floor_cny=1.0, wait_off_peak=not os.environ.get("ALLOW_PEAK"))
    main(a.arms.split(","), a.reps, a.conflict_only_after, a.limit)
    print("spend:", llm.profile_spend() if llm.PROFILE_CFG else llm.spend_report(), flush=True)
