"""Build the human-baseline answer site: site/index.html plus site/img/<item>.webp (one image per item).

Version 5 covers both sets, the 95 main-set rules (splits test2-test5) and the 60 hard-set rules (split test6). Every
participant answers 100 of the 155 rules, drawn at random within rule types (sampling.py), with a rest screen after 50.
On the start page a participant types an experiment id and fills a short Minecraft questionnaire; the id decides the
draw, one variant of each drawn rule (variant (offset + j) mod 8, offset = FNV-1a(id) mod 8) and the order. The image,
action, question and the A/B/C options are exactly what the models saw, each line with a Chinese translation
underneath. Answer keys are not in the page.

The site is static: host the folder on any static web host (phones need a URL), or open index.html directly on a
computer. Answers are saved in the participant's browser after every item and exported as text or a file.

Usage: python build.py            (images are converted once and reused on later builds)
"""
import json
import re
from pathlib import Path

from PIL import Image

import sampling as S

HERE = Path(__file__).parent
PILOT = HERE.parent / "rulecraft"
SITE = HERE / "site"
VERSION = "5"
SPLITS = {"main": ("test2", "test3", "test4", "test5"), "hard": ("test6",)}
# consistent Chinese terms (official Minecraft Simplified Chinese names) where the translations vary
TERMS = [(r"岩浆(?!块)", "熔岩"), (r"青柠色", "黄绿色")]


def items():
    data = json.loads((PILOT / "data" / "items.json").read_text(encoding="utf-8"))
    out = {}
    for part, splits in SPLITS.items():
        for i in data:
            if i["set"] == "mc" and i["split"] in splits:
                out[i["id"]] = dict(i, part=part)
    return out


def zh(text, tr):
    out = tr[text]
    for a, b in TERMS:
        out = re.sub(a, b, out)
    if re.search(r"\bpath\b", text, re.I):
        out = out.replace("路径", "土径")
    return out


def webp(src, dst):
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    Image.open(src).convert("RGB").save(dst, "WEBP", quality=80, method=6)


def main():
    its = items()
    rules = {part: sorted({i["rule"] for i in its.values() if i["part"] == part}) for part in SPLITS}
    assert len(rules["main"]) == 95 and len(rules["hard"]) == 60
    assert all(f"{r}_v{v}" in its for rs in rules.values() for r in rs for v in range(8))
    tr = json.loads((HERE / "translations.json").read_text(encoding="utf-8"))
    question = {i["question"] for i in its.values()}
    assert len(question) == 1
    question = question.pop()
    missing = sorted({s for i in its.values() for s in [i["action"]] + [o[1] for o in i["options"]] if s not in tr})
    assert not missing, f"{len(missing)} strings without a translation, e.g. {missing[:3]}"
    every = S.load_items()
    data = {"version": VERSION, "question": question, "question_zh": tr[question], "total": S.TOTAL,
            "strata": [{"rules": s["rules"], "take": s["take"]} for s in S.plan(every)], "rj": S.rule_index(every),
            "items": {iid: {"action": it["action"], "action_zh": zh(it["action"], tr),
                            "options": [[o[0], o[1], zh(o[1], tr)] for o in it["options"]]} for iid, it in sorted(its.items())}}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (SITE / "img").mkdir(parents=True, exist_ok=True)
    for iid, it in sorted(its.items()):
        webp(Path(it["image"]), SITE / "img" / f"{iid}.webp")
    stale = [f for f in (SITE / "img").glob("*.webp") if f.stem not in its]
    for f in stale:
        f.unlink()
    html = (HERE / "page_template.html").read_text(encoding="utf-8").replace("__DATA__", payload)
    (SITE / "index.html").write_text(html, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")      # GitHub Pages: serve the files as they are
    size = sum(f.stat().st_size for f in (SITE / "img").glob("*.webp"))
    print(f"site/index.html: {len(its)} items ({len(rules['main'])} main + {len(rules['hard'])} hard rules), "
          f"{(SITE / 'index.html').stat().st_size / 1e3:.0f} kB; site/img: {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
