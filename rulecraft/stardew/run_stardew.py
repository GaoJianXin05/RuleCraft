"""Stardew Valley extension: Image (no hint), Told (named the game), Text (scene in words) and R (which game?) on the
verified items, as in rulecraft/terraria/run_terraria.py. Every arm is scored against the game answer.

Usage: python run_stardew.py images                       crops the verification screenshots to 768x480
       LLM_PROFILE=deepseek python run_stardew.py run [--arms Image Told Text R] [--ids ...]
       python run_stardew.py report
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

GAME = "Stardew Valley (version 1.6)"
TOLD = f"This image is a screenshot from {GAME}. Answer according to the rules of Stardew Valley.\n"
TAIL = "Reply with a single letter."
IMG = HERE / "images"
OUT = HERE / "results"

NAMES = {"472": "parsnip", "475": "potato", "477": "kale", "474": "cauliflower", "476": "garlic", "473": "green bean",
         "745": "strawberry", "490": "pumpkin", "488": "eggplant", "491": "bok choy", "494": "beet"}
OBJECTS = {"(O)93": "a lit torch stuck in the ground", "(BC)146": "a burning campfire", "(BC)130": "a wooden chest",
           "(O)343": "a rock", "(O)450": "a rock", "(O)294": "a fallen branch", "(O)295": "a fallen branch",
           "(O)674": "a clump of weeds", "(O)675": "a clump of weeds", "(O)784": "a clump of weeds", "(O)785": "a clump of weeds",
           "(O)16": "a wild horseradish plant", "(O)18": "a wild daffodil", "(O)20": "a wild leek", "(O)22": "a dandelion",
           "(O)322": "a wooden fence post", "(O)298": "a hardwood fence post"}
TREES = {"1": "oak", "2": "maple", "3": "pine"}
FRUIT = {"628": "cherry", "629": "apricot"}


def load_items():
    return json.loads((HERE / "items_stardew.json").read_text(encoding="utf-8"))["items"]


def letters(it):
    return "ABC"[:len(it["options_ordered"])]


def question_block(it):
    opts = "\n".join(f"{l}. {it['options'][k]}" for l, k in zip(letters(it), it["options_ordered"]))
    return f"{it['question_en']}\n{opts}"


def describe_tile(t):
    if t.get("hoe"):
        wet = "wet " if t.get("water") else "dry "
        if "crop" not in t:
            return f"a patch of {wet}tilled soil"
        name, ph = NAMES[t["crop"]], t.get("phase")
        if ph == "grown":
            return f"a ripe {name} plant in {wet}tilled soil"
        if ph == 0:
            return f"freshly planted {name} seeds in {wet}tilled soil"
        return f"a young {name} plant in {wet}tilled soil"
    if "tree" in t:
        kind = TREES.get(t["tree"], "")
        if t.get("stump"):
            return f"the stump of a cut {kind} tree"
        return f"a small {kind} sapling" if t.get("stage", 5) < 5 else f"a fully grown {kind} tree"
    if "fruittree" in t:
        return f"a fully grown {FRUIT[t['fruittree']]} tree with ripe fruit on it"
    if "obj" in t:
        return OBJECTS[t["obj"]]
    if "drop" in t:
        return "a few pieces of wood lying on the ground"
    return "an object"


def text_scene(sc):
    """The scene in words, from the same specification the game built (positions left to right, then rows)."""
    parts = []
    for t in sorted(sc["tiles"], key=lambda t: (t["d"][1], t["d"][0])):
        parts.append(describe_tile(t))
    if not parts:
        parts = ["a patch of untouched grassy ground"]
    when = {"spring": "It is spring", "fall": "It is autumn"}[sc["season"]]
    if sc["season"] == "fall" and sc["day"] == 28:
        when = "It is the last day of autumn"
    weather = "it is raining" if sc.get("rain_today") else "the weather is sunny"
    uniq = []
    for p in parts:
        n = parts.count(p)
        s = p if n == 1 else f"{n} of: {p}"
        if s not in uniq:
            uniq.append(s)
    return f"{when}, and {weather}. On a farm field there is " + "; ".join(uniq) + ", side by side on open ground."


def images():
    from PIL import Image
    import rules_stardew as R
    IMG.mkdir(exist_ok=True)
    n = 0
    for it in load_items():
        src = HERE / "shots" / it["image"]                 # the scene rebuilt without steps (see rules_stardew.py job --shots)
        im = Image.open(src).convert("RGB")
        w, h = im.size
        cw = min(w, round(h * 1.6))                        # 16:10 around the centre, as the other games
        box = ((w - cw) // 2, 0, (w - cw) // 2 + cw, h)
        im.crop(box).resize((768, 480), Image.LANCZOS).save(IMG / f"{it['id']}.png")
        n += 1
    print(f"{n} images -> {IMG}")


def ask(it, arm, scenes):
    import llm
    img = str(IMG / f"{it['id']}.png")
    if arm == "R":
        r = llm.chat([llm.user("Which video game is this screenshot from? Reply with the name of the game only.", [img])], max_tokens=20, tag="SD_R")
        return {"pred": r["text"].strip(), "correct": "stardew" in r["text"].lower()}
    if arm == "Text":
        prompt = f"In {GAME}: {text_scene(scenes[it['id']])}\n{question_block(it)}\n{TAIL}"
        r = llm.chat([llm.user(prompt)], max_tokens=20, tag="SD_T")
    else:
        ctx = TOLD if arm == "Told" else ""
        prompt = f"{ctx}Look at the image.\n{question_block(it)}\n{TAIL}"
        r = llm.chat([llm.user(prompt, [img])], max_tokens=20, tag=f"SD_{arm}")
    pred = llm.parse_letter(r["text"], letters(it))
    return {"pred": pred, "correct": pred == it["correct_letter"], "raw": r["text"]}


def scenes_by_id():
    import rules_stardew as R
    by = {r["id"]: r for r in R.RULES}
    return {it["id"]: R.scene(by[it["base_rule"]], it["variant"] - 1) for it in load_items()}


def run(arms, ids):
    import llm
    sys.stdout.reconfigure(encoding="utf-8")
    llm.set_sampling(temperature=1.0, seed=1)
    items = [i for i in load_items() if not ids or i["id"] in ids]
    scenes = scenes_by_id()
    out = OUT / llm.PROFILE
    out.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        def one(it, a=arm):
            try:
                return ask(it, a, scenes)
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
        print(f"{llm.PROFILE}/{arm}: {len(good)}/{len(rows)} answered, acc={sum(r['correct'] for r in good) / max(1, len(good)):.3f}", flush=True)


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
                acc[kind].append(r["correct"])
                acc[r["category"]].append(r["correct"])
            m = {k: 100 * sum(v) / len(v) for k, v in acc.items()}
            print(f"  {arm:5s} n={len(rows):3d}  passive={m.get('passive_conflict', 0):5.1f}  action={m.get('action_conflict', 0):5.1f}  "
                  f"conflict={m['conf']:5.1f}  consistent={m.get('cons', 0):5.1f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["images", "run", "report"])
    ap.add_argument("--arms", nargs="+", default=["Image", "Told", "Text", "R"])
    ap.add_argument("--ids", nargs="*", default=[])
    a = ap.parse_args()
    {"images": images, "report": report}.get(a.cmd, lambda: run(a.arms, a.ids))()
