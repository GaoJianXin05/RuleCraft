"""Sorts DeepSeek's own reasoning (thinking on, bare image, hard passive conflict rules) by how it treats the game.

Reads results/r2/t6_think_deepseek/trace.json (written by think_trace.py); a text-only judge call (DeepSeek, thinking
off, temperature 0) puts each reasoning into one of four classes. Writes trace_classes.json and prints the counts.
Usage (in rulecraft/): python think_trace_classify.py
"""
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot
from item_sets import groups

OUT = llm.RESULTS / "r2" / "t6_think_deepseek"
PROMPT = ("Below is a model's private reasoning about a question on an image. The image is a Minecraft screenshot, but "
          "the question did not say so. Two outcomes matter:\n"
          "GAME outcome (what vanilla Minecraft does): {game}\nREAL-WORLD outcome: {real}\n\n"
          "Reasoning:\n\"\"\"\n{reasoning}\n\"\"\"\n\n"
          "Which description fits the reasoning best? Reply with one digit only.\n"
          "1: It works out or states that in Minecraft the GAME outcome would hold, and it answers with the GAME outcome.\n"
          "2: It states or concedes that in Minecraft the GAME outcome would hold (or that Minecraft does not simulate "
          "the change), but decides to answer by real-world logic or common sense instead.\n"
          "3: It claims that Minecraft's own mechanics produce the REAL-WORLD outcome (a mistaken game rule).\n"
          "4: It uses the word Minecraft only to describe the image or its style, and reasons about the outcome with "
          "real-world logic alone, without considering what the game's rules would give.\n"
          "5: None of these.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    trace = json.loads((OUT / "trace.json").read_text(encoding="utf-8"))["C0"]
    xs = [i for i in groups("hard")["conflict, passive"] if trace.get(i["id"])]
    llm.set_guard(floor_cny=1.0, wait_off_peak=True)
    llm.set_sampling(temperature=0.0, seed=0)

    def one(it):
        t = trace[it["id"]]
        text = {o[2]: o[1] for o in it["options"]}
        llm.LABEL.item = f"{it['id']}#traceclass#0"
        r = llm.chat([llm.user(PROMPT.format(game=text["vanilla"], real=text["real"], reasoning=t["reasoning"][:8000]))],
                     max_tokens=5, tag="TraceClass")
        d = next((c for c in r["text"] if c in "12345"), None)
        return {"id": it["id"], "class": d, "correct": t["correct"], "mention": t["mention"]}
    with ThreadPoolExecutor(pilot.WORKERS) as ex:
        rows = list(ex.map(one, xs))
    (OUT / "trace_classes.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for ok in (True, False):
        n = Counter(r["class"] for r in rows if r["correct"] == ok)
        print("answer right" if ok else "answer wrong", sum(n.values()), dict(sorted(n.items(), key=lambda kv: str(kv[0]))))


if __name__ == "__main__":
    main()
