"""Stage-1 summary for the open-weight models: accuracy per set, rule kind and condition, Told - Image with the paper's
cluster bootstrap (rules), where bare-image errors go, recognition, and the gate for stage 2.

Usage (in rulecraft/): python openvlm/analyze_open.py openvlm/out/qwen35_9b/answers.jsonl [more answers.jsonl ...]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import item_sets as S  # noqa: E402
import item_sets as mt  # noqa: E402

GAMES = {"terraria": "terraria", "stardew": "stardew valley"}


def load(path):
    rows = defaultdict(lambda: defaultdict(list))      # (group, arm) -> id -> [answer]
    for r in map(json.loads, open(path, encoding="utf-8")):
        rows[(r["group"], r["arm"])][r["id"]].append(r)
    return rows


def fmt(ci):
    return "--" if ci is None else f"{ci[0]:+.1f} [{ci[1]:.1f}, {ci[2]:.1f}]"




def _num(x):
    return float("nan") if x is None else x


def report(path):
    rows = load(path)
    name = Path(path).parent.name
    print(f"\n===== {name}")
    gate = []
    for part in ("main", "hard"):
        g = S.groups(part)
        for kind in ("conflict, all", "conflict, passive", "conflict, action", "consistent"):
            items = g[kind]
            m = {a: mt.means(rows[("mc", a)], items) for a in ("Text", "Told", "Image")}
            acc = {a: _num(mt.acc(items, m[a])) for a in m}
            d = mt.dci(items, m["Told"], m["Image"])
            print(f"  {part:4s} {kind:17s} n={len(items):3d}  Text {acc['Text']:5.1f}  Told {acc['Told']:5.1f}  "
                  f"Image {acc['Image']:5.1f}  Told-Image {fmt(d)}")
            if kind == "conflict, all":
                gate.append((part, acc["Told"], d))
        conf = g["conflict, all"]
        hit, wrong = S.direction(rows[("mc", "Image")], conf, "real")
        print(f"  {part:4s} bare-image errors on conflict rules picking the real-world outcome: {hit}/{wrong}"
              f" = {100 * hit / max(1, wrong):.0f}%")
    # recognition and the other games
    rec = rows[("mc", "R")]
    print(f"  recognition, Minecraft: {sum('minecraft' in v[0]['reply'].lower() for v in rec.values())}/{len(rec)}")
    for game, word in GAMES.items():
        ids = {i for (gr, a), v in rows.items() if gr == game for i in v}
        if not ids:
            continue
        kinds = {i: rows[(game, "Image")][i][0]["kind"] for i in rows[(game, "Image")]}
        items = [{"id": i, "set": "mc", "rule": rows[(game, "Image")][i][0]["rule"]} for i in kinds]
        conf = [it for it in items if "conflict" in kinds[it["id"]]]
        cons = [it for it in items if "conflict" not in kinds[it["id"]]]
        for label, its in (("conflict", conf), ("consistent", cons)):
            m = {a: mt.means(rows[(game, a)], its) for a in ("Text", "Told", "Image")}
            acc = {a: _num(mt.acc(its, m[a])) for a in m}
            print(f"  {game:8s} {label:10s} n={len(its):3d}  Text {acc['Text']:5.1f}  Told {acc['Told']:5.1f}  "
                  f"Image {acc['Image']:5.1f}  Told-Image {fmt(mt.dci(its, m['Told'], m['Image']))}")
        r = rows[(game, "R")]
        print(f"  {game:8s} recognition: {sum(word.split()[0] in v[0]['reply'].lower() for v in r.values())}/{len(r)}")
    phys = rows[("physbench", "Image")]
    if phys:
        print(f"  real photos (PhysBench), Image accuracy: {sum(v[0]['correct'] for v in phys.values())}/{len(phys)}")
    mass = [r["letter_mass"] for (gr, a), v in rows.items() for x in v.values() for r in x if "letter_mass" in r]
    print(f"  probability on the option letters: median {sorted(mass)[len(mass) // 2]:.3f}, min {min(mass):.3f}")
    ok = any(told >= 60 and d is not None and d[1] > 0 for _, told, d in gate)
    print(f"  GATE (Told conflict >= 60% and Told-Image interval above zero on a set): {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for p in sys.argv[1:]:
        report(p)
