"""Open recognition probe on Minecraft: the image alone and the question the games use (run_terraria.py, arm R),
"Which video game is this screenshot from? Reply with the name of the game only." No candidate list, no question
about the scene. One call per image of the main and hard sets (1,240), one run.
Output: results/r2/worldopen_<profile>/R.jsonl with the reply and whether it names Minecraft.

Usage (in rulecraft/): LLM_PROFILE=qwenmax WORKERS=8 SPEND_CAP_USD=... python world_open.py [--limit 20]
DeepSeek waits for off-peak hours unless ALLOW_PEAK is set. Finished calls are cached.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot

OUT = llm.RESULTS / "r2"
ASK = "Which video game is this screenshot from? Reply with the name of the game only."
SPLITS = {"test2", "test3", "test4", "test5", "test6"}      # main set (95 rules) and hard set (60 rules)


def main(limit=None):
    sys.stdout.reconfigure(encoding="utf-8")
    llm.set_guard(wait_off_peak=llm.PROFILE == "deepseek" and not os.environ.get("ALLOW_PEAK"))
    items = [i for i in pilot.load_items() if i["set"] == "mc" and i["split"] in SPLITS]
    assert len(items) == 1240, len(items)
    if limit:
        items = items[:limit]
    llm.set_sampling(temperature=1.0, seed=1)

    def one(it):
        llm.LABEL.item = f"{it['id']}#OPENR#0"
        try:
            r = llm.chat([llm.user(ASK, [it["image"]])], max_tokens=20, tag="OPENR")
            text = r["text"].strip()
            return dict(id=it["id"], split=it["split"], reply=text, is_mc="minecraft" in text.lower())
        except llm.BudgetExceeded:
            raise
        except (RuntimeError, OSError) as e:
            return dict(id=it["id"], split=it["split"], reply="", is_mc=False, error=str(e)[:200])

    with ThreadPoolExecutor(pilot.WORKERS) as ex:
        rows = list(ex.map(one, items))
    folder = OUT / f"worldopen_{llm.PROFILE}"
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "R.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = [r for r in rows if not r.get("error")]
    print(f"{llm.PROFILE}: {len(ok)}/{len(rows)} answered, names Minecraft {sum(r['is_mc'] for r in ok)}/{len(ok)}",
          flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    main(ap.parse_args().limit)
