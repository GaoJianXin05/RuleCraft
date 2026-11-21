"""Terraria extension: Image (no hint), Told (named the game) and Text (scene as words) on the 160 items.
Prompts mirror pilot.py (C0 / C2 / T). Every arm is scored against the game answer (correct_letter).
Arm R asks which game the image is from, for a recognised-only subset analysis.

Usage: LLM_PROFILE=deepseek python run_terraria.py run [--arms Image Told Text R] [--ids T_P01_V1 ...]
       python run_terraria.py report
"""
import argparse, json, os, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

ITEMS = json.load(open(HERE / "items_terraria.json", encoding="utf-8"))["items"]
IMG = HERE / "images_real"
OUT = HERE / "results"
GAME = "vanilla Terraria (version 1.4.4)"
TOLD = f"This image is a screenshot from {GAME}. Answer according to the rules of {GAME.split(' (')[0]}.\n"
TAIL = "Reply with a single letter."
NAMES = {0: "dirt", 1: "stone", 2: "grass", 6: "iron ore", 7: "copper ore", 8: "gold ore", 9: "silver ore",
         19: "wood platform", 23: "corrupt grass", 38: "gray brick", 39: "red brick", 40: "clay", 41: "blue brick",
         45: "gold brick", 46: "silver brick", 51: "cobweb", 53: "sand", 54: "glass", 56: "obsidian", 57: "ash",
         59: "mud", 60: "jungle grass", 70: "mushroom grass"}


def letters(it):
    return "ABC"[:len(it["options_ordered"])]


def question_block(it):
    opts = "\n".join(f"{l}. {it['options'][k]}" for l, k in zip(letters(it), it["options_ordered"]))
    return f"{it['question_en']}\n{opts}"


def text_scene(it):
    """Describe the rendered scene in words: same blocks, same layout as images_real (ground = row below lowest block)."""
    first = {}
    for t in it["scene"]["tiles"]:
        if t["type"] >= 0:
            first.setdefault((t["x"], t["y"]), t["type"])
    ground = max(y for _, y in first) + 1
    x0 = min(x for x, _ in first)
    parts = []
    for (x, y), tid in sorted(first.items(), key=lambda p: (p[0][0], -p[0][1])):
        h = ground - y
        gap = h - 1
        where = ("resting directly on the ground" if h == 1
                 else "1 block above the ground" if gap == 1 else f"{gap} blocks above the ground")
        parts.append(f"a {NAMES.get(tid, 'block')} block in column {x - x0 + 1}, {where}")
    return ("The scene is a flat surface of grass over dirt and stone, with open sky above. "
            "It contains " + "; ".join(parts) + ". Every other position above the ground is empty air "
            f"(the {it['tile_color']} block is the {it['tile_name']} block).")


def ask(it, arm):
    import llm
    if arm == "R":
        r = llm.chat([llm.user("Which video game is this screenshot from? Reply with the name of the game only.",
                               [str(IMG / f"{it['id']}.png")])], max_tokens=20, tag="TR_R")
        return {"pred": r["text"].strip(), "correct": "terraria" in r["text"].lower()}
    if arm == "Text":
        prompt = f"In {GAME}: {text_scene(it)}\n{question_block(it)}\n{TAIL}"
        r = llm.chat([llm.user(prompt)], max_tokens=20, tag="TR_T")
    else:
        ctx = TOLD if arm == "Told" else ""
        prompt = f"{ctx}Look at the image.\n{question_block(it)}\n{TAIL}"
        r = llm.chat([llm.user(prompt, [str(IMG / f"{it['id']}.png")])], max_tokens=20, tag=f"TR_{arm}")
    pred = llm.parse_letter(r["text"], letters(it))
    return {"pred": pred, "correct": pred == it["correct_letter"], "raw": r["text"]}


def run(arms, ids):
    import llm
    sys.stdout.reconfigure(encoding="utf-8")
    llm.set_sampling(temperature=1.0, seed=1)
    items = [i for i in ITEMS if not ids or i["id"] in ids]
    out = OUT / llm.PROFILE
    out.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        def one(it, a=arm):
            try:
                return ask(it, a)
            except llm.BudgetExceeded:
                raise
            except (RuntimeError, OSError) as e:
                return {"pred": None, "correct": False, "error": str(e)[:300]}
        with ThreadPoolExecutor(int(os.environ.get("WORKERS", 8))) as ex:
            rows = list(ex.map(one, items))
        path = out / f"{arm}.jsonl"
        old = {}
        if path.exists():
            old = {r["id"]: r for r in map(json.loads, open(path, encoding="utf-8"))}
        old.update({i["id"]: dict(id=i["id"], category=i["category"], **r) for i, r in zip(items, rows)})
        with open(path, "w", encoding="utf-8") as f:
            for r in old.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        good = [r for r in rows if not r.get("error")]
        print(f"{llm.PROFILE}/{arm}: {len(good)}/{len(rows)} answered, "
              f"acc={sum(r['correct'] for r in good) / max(1, len(good)):.3f}", flush=True)


def report():
    for prof in sorted(p.name for p in OUT.iterdir() if p.is_dir()):
        print(f"== {prof}")
        for arm in ["R", "Image", "Told", "Text"]:
            path = OUT / prof / f"{arm}.jsonl"
            if not path.exists():
                continue
            rows = [r for r in map(json.loads, open(path, encoding="utf-8")) if not r.get("error")]
            acc = defaultdict(list)
            for r in rows:
                kind = "cons" if r["category"] == "consistent" else "conf"
                acc[kind].append(r["correct"]); acc["all"].append(r["correct"])
            m = {k: 100 * sum(v) / len(v) for k, v in acc.items()}
            print(f"  {arm:5s} n={len(rows):3d}  all={m['all']:5.1f}  conflict={m['conf']:5.1f}  "
                  f"consistent={m['cons']:5.1f}  lean={m['conf'] - m['cons']:+6.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--arms", nargs="+", default=["Image", "Told", "Text", "R"])
    ap.add_argument("--ids", nargs="*", default=[])
    a = ap.parse_args()
    run(a.arms, a.ids) if a.cmd == "run" else report()
