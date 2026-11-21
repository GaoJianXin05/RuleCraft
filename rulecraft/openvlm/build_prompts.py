"""Export the exact prompts of the API runs for the open-weight models, by calling the same prompt code with llm.chat
replaced by a recorder. Output: openvlm/bundle/prompts.jsonl and the images they use (bundle/img/...).

One line per (item, arm): id, group (mc / terraria / stardew / physbench), split, rule, kind, arm, text, image
(bundle-relative path or null), letters, answer (the letter scored as correct; null for R), mode (letter / gen).
Minecraft: main and hard sets (1,240) and the hard-set development rules (dev6, 80) under Image, Told and Text, and R on
the 1,240. Terraria and Stardew: Image, Told, Text and R. PhysBench real photos: Image, a control with no game.

Usage (in rulecraft/): python openvlm/build_prompts.py
"""
import json
import shutil
import sys
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PILOT))
import llm      # noqa: E402
import pilot    # noqa: E402

BUNDLE = Path(__file__).parent / "bundle"
CAPTURED = []


def fake_chat(messages, max_tokens=20, tag="", seed=None, **kw):
    msg = messages[-1]
    content = msg["content"]
    if isinstance(content, str):
        text, images = content, []
    else:
        text = next(p["text"] for p in content if p["type"] == "text")
        images = [p["_path"] for p in content if p["type"] != "text"]
    CAPTURED.append((text, images, max_tokens))
    return {"text": "A"}


def fake_user(text, images=()):
    if not images:
        return {"role": "user", "content": text}
    return {"role": "user", "content": [{"type": "image", "_path": str(p)} for p in images] + [{"type": "text", "text": text}]}


llm.chat, llm.user = fake_chat, fake_user


def capture(fn, *args):
    CAPTURED.clear()
    fn(*args)
    assert len(CAPTURED) == 1, len(CAPTURED)
    return CAPTURED[0]


def place(src, group):
    src = Path(src)
    dst = BUNDLE / "img" / group / src.name
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return f"img/{group}/{src.name}"


def row(rows, group, it_id, split, rule, kind, arm, cap, letters, answer, mode):
    text, images, _ = cap
    assert len(images) <= 1
    rows.append(dict(id=it_id, group=group, split=split, rule=rule, kind=kind, arm=arm, text=text,
                     image=place(images[0], group) if images else None, letters=letters, answer=answer, mode=mode))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = []
    items = pilot.load_items()
    mc = [i for i in items if i["set"] == "mc" and i["split"] in {"test2", "test3", "test4", "test5", "test6", "dev6"}]
    assert len(mc) == 1320, len(mc)
    for it in mc:
        L = pilot.letters_of(it)
        args = (it["id"], it["split"], it["rule"], it["kind"])
        row(rows, "mc", *args, "Image", capture(pilot.run_context, it, "C0"), L, it["answer"]["C0"], "letter")
        row(rows, "mc", *args, "Told", capture(pilot.run_context, it, "C2"), L, it["answer"]["C2"], "letter")
        row(rows, "mc", *args, "Text", capture(pilot.run_T, it), L, it["answer"]["T"], "letter")
        if it["split"] != "dev6":
            row(rows, "mc", *args, "R", capture(pilot.run_R, it), None, None, "gen")
    for it in (i for i in items if i["set"] == "physbench"):
        row(rows, "physbench", it["id"], it["split"], it["rule"], it["kind"], "Image",
            capture(pilot.run_context, it, "C0"), pilot.letters_of(it), it["answer"]["C0"], "letter")

    sys.path.insert(0, str(PILOT / "terraria"))
    import run_terraria as TR
    for it in TR.ITEMS:
        for arm in ("Image", "Told", "Text", "R"):
            row(rows, "terraria", it["id"], "terraria", it["base_rule"], it["category"], arm, capture(TR.ask, it, arm),
                None if arm == "R" else TR.letters(it), None if arm == "R" else it["correct_letter"],
                "gen" if arm == "R" else "letter")
    sys.path.insert(0, str(PILOT / "stardew"))
    import run_stardew as SD
    scenes = SD.scenes_by_id()
    for it in SD.load_items():
        for arm in ("Image", "Told", "Text", "R"):
            row(rows, "stardew", it["id"], "stardew", it["base_rule"], it["category"], arm,
                capture(SD.ask, it, arm, scenes), None if arm == "R" else SD.letters(it),
                None if arm == "R" else it["correct_letter"], "gen" if arm == "R" else "letter")

    BUNDLE.mkdir(exist_ok=True)
    with open(BUNDLE / "prompts.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(rows), "prompts;", dict(Counter((r["group"], r["arm"]) for r in rows)))


if __name__ == "__main__":
    main()
