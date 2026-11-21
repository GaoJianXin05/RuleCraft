"""Experiment A: does each model recognize the world of a hard-set image when asked?

Only the first call of self-named world (gdc.gate): the image and the question, and the model returns which world the
image shows, without answering. One call per hard-set image (480), one run, for the models whose gate was not yet
measured. Output: results/r2/worldid_<profile>/GATE.jsonl (same fields as the gate files of the method runs).

Usage (in rulecraft/): LLM_PROFILE=qwenmax WORKERS=8 SPEND_CAP_USD=3 python world_id.py [--limit 20]
Finished calls are cached, so running it again only asks what is missing.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import gdc
import llm
import pilot

OUT = llm.RESULTS / "r2"


def gate(item):
    """gdc.gate with a lenient reading of the reply: some models break lines inside JSON strings ("world": "\\nminecraft"),
    which strict JSON rejects. The request is the same as gdc.gate's, so cached replies are reused."""
    r = llm.chat([llm.user(gdc.GATE_PROMPT.format(q=gdc.question_block(item)), [item["image"]])], max_tokens=150,
                 json_mode=True, tag="GATE")
    g = llm.parse_json(r["text"]) or llm.parse_json(r["text"].replace("\r", " ").replace("\n", " ")) or {}
    if isinstance(g, list):
        dicts = [x for x in g if isinstance(x, dict)]
        g = dicts[0] if dicts else (dict(zip(g[::2], g[1::2])) if len(g) % 2 == 0
                                    and all(isinstance(x, str) for x in g[::2]) else {})
    world = str(g.get("world", "unknown")).strip()
    return {"world": world, "game_name": str(g.get("game_name") or "").strip(), "is_mc": world.startswith("minecraft")}


def main(limit=None):
    sys.stdout.reconfigure(encoding="utf-8")
    items = [i for i in pilot.load_items() if i["split"] == "test6" and i["set"] == "mc"]
    if limit:
        items = items[:limit]
    llm.set_sampling(temperature=1.0, seed=1)

    def one(it):
        llm.LABEL.item = f"{it['id']}#GATE#0"
        try:
            return dict(id=it["id"], **gate(it))
        except llm.BudgetExceeded:
            raise
        except (RuntimeError, OSError) as e:
            return dict(id=it["id"], world="unknown", game_name="", is_mc=False, error=str(e)[:200])

    with ThreadPoolExecutor(pilot.WORKERS) as ex:
        rows = list(ex.map(one, items))
    folder = OUT / f"worldid_{llm.PROFILE}"
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "GATE.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = [r for r in rows if not r.get("error")]
    print(f"{llm.PROFILE}: {len(ok)}/{len(rows)} answered, names Minecraft {sum(r['is_mc'] for r in ok)}/{len(ok)}; "
          f"errors {len(rows) - len(ok)}; spend (calls, list USD, CNY)={llm.profile_spend()}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    main(ap.parse_args().limit)
