"""Stage 3 summary: dev6 sweep (choice of layer, strength, positions), test-set steering with controls, and patching.

Usage (in rulecraft/): python openvlm/analyze_steer.py openvlm/out/qwen35_9b [sweep|test|patch]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import item_sets as S  # noqa: E402

mt = S.mt


def read(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


def bal(rs):
    c = [r["correct"] for r in rs if r["kind"] == "conflict"]
    k = [r["correct"] for r in rs if r["kind"] == "consistent"]
    return 100 * np.mean(c), 100 * np.mean(k), 50 * (np.mean(c) + np.mean(k))


def sweep(d):
    g = defaultdict(list)
    for r in read(d / "steer_sweep.jsonl"):
        g[(r["layer"], r["alpha"], r["pos"])].append(r)
    base = bal(g.pop((0, 0.0, "none")))
    print(f"dev6 Image, no steering: conflict {base[0]:.1f}  consistent {base[1]:.1f}  balanced {base[2]:.1f}")
    res = sorted(((bal(v), k) for k, v in g.items() if len(v) == 80), key=lambda x: -x[0][2])
    for (c, k, b), key in res[:8]:
        print(f"  layer {key[0]:2d} alpha {key[1]:.0f} {key[2]:4s}: conflict {c:5.1f}  consistent {k:5.1f}  balanced {b:5.1f}")
    return res[0][1] if res else None


def table(rows_by, label):
    print(f"  {label:22s}", end="")
    for part in ("main", "hard"):
        g = S.groups(part)
        acc = {}
        for kind in ("conflict, all", "consistent"):
            m = mt.means(rows_by, g[kind])
            acc[kind] = mt.acc(g[kind], m)
        print(f" | {part}: conflict {acc['conflict, all']:5.1f} consistent {acc['consistent']:5.1f}"
              f" balanced {(acc['conflict, all'] + acc['consistent']) / 2:5.1f}", end="")
    print()


def test(d):
    base = defaultdict(lambda: defaultdict(list))
    for r in read(d / "answers.jsonl"):
        if r["group"] == "mc" and "correct" in r:
            base[r["arm"]][r["id"]].append(r)
    st = defaultdict(lambda: defaultdict(list))
    for r in read(d / "steer_test.jsonl"):
        st[r["cond"]][r["id"]].append(r)
    table(base["Image"], "Image")
    table(st["steer"], "Image + direction")
    table(st["random"], "Image + random")
    table(base["Told"], "Told")
    table(st["minus"], "Told - direction")


def patch(d):
    rs = read(d / "steer_patch.jsonl")
    by = defaultdict(list)
    for r in rs:
        it = mt.ITEMS[r["id"]]
        keys = {o[0]: o[2] for o in it["options"]}
        inv = {v: k for k, v in keys.items()}
        r["margin"] = r["logp"][inv["vanilla"]] - r["logp"][inv["real"]]
        by[r["layer"]].append(r)
    n = len(by[1])
    print(f"patching the Told state into the Image run, {n} items right under Told and wrong under Image")
    for l in sorted(by):
        v = by[l]
        print(f"  layer {l:2d}: answer flips to the game outcome {100 * np.mean([r['correct'] for r in v]):5.1f}%"
              f"   game - real margin {np.mean([r['margin'] for r in v]):+.2f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    d = Path(sys.argv[1])
    for what in sys.argv[2:] or ["sweep", "test", "patch"]:
        {"sweep": sweep, "test": test, "patch": patch}[what](d)
