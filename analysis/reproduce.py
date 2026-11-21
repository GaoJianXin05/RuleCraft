"""Recompute the paper's main results from the released model answers (no API call).

  Table 1  accuracy by condition (Text, Told, Image) on both Minecraft sets, six models, with the gain from naming
           the game (Told - Image, 95% CI) and the gain in balanced accuracy
  Table 5  Terraria and Stardew Valley
  Table 7  reasoning settings on hard conflict rules (DeepSeek thinking off / on, GPT-6.1-Sol low / high)
  plus     the share of wrong bare-image answers on conflict rules that pick the real-world outcome

Inputs (after `python scripts/link_data.py <dataset folder>`): rulecraft/data/items.json, rulecraft/results/r2/,
rulecraft/terraria/, rulecraft/stardew/. Confidence intervals come from a two-level bootstrap (rules, then items within
rules; 2,000 resamples, seed 0), the procedure of the paper.

Usage:  python analysis/reproduce.py            readable tables
        python analysis/reproduce.py --latex    the table rows exactly as they are typeset in the paper
"""
import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RC = Path(__file__).resolve().parent.parent / "rulecraft"
R2 = RC / "results" / "r2"
B = 2000
SETS = {"main": ("test2", "test3", "test4", "test5"), "hard": ("test6",)}
DS_PREFIX = {"test2": "", "test3": "t3_", "test4": "t4_", "test5": "t5_", "test6": "t6_"}
# table order; profile = folder suffix of the model's runs (DeepSeek's runs sit in rep<k>/ and t<n>_rep<k>/)
MODELS = [("DeepSeek", "deepseek"), ("Qwen-Max", "qwenmax"), ("Qwen-Flash", "qwenflash"), ("Doubao-Pro", "doubaopro"),
          ("Doubao-Lite", "doubaolite"), ("GPT-6.1-Sol", "solrun")]


# ------------------------------------------------------------------------------------------------ statistics
def cluster_ci(values_by_rule, seed=0):
    """{rule: [value, ...]} -> (mean, lo, hi): mean over all values; CI resampling rules, then values within rules."""
    rules = [r for r, v in values_by_rule.items() if v]
    if not rules:
        return None
    flat = [x for r in rules for x in values_by_rule[r]]
    mean = sum(flat) / len(flat)
    rng = random.Random(seed)
    stats = []
    for _ in range(B):
        sample = []
        for r in rng.choices(rules, k=len(rules)):
            v = values_by_rule[r]
            sample += rng.choices(v, k=len(v))
        stats.append(sum(sample) / len(sample))
    stats.sort()
    return mean, stats[int(0.025 * B)], stats[int(0.975 * B) - 1]


def shift_ci(d):
    """The same for values that may be negative (paired differences)."""
    ci = cluster_ci({k: [x + 1 for x in v] for k, v in d.items()})
    return None if ci is None else (ci[0] - 1, ci[1] - 1, ci[2] - 1)


def boot_two(da, db, n=B, seed=0):
    """CI of the average of two independent groups' means (balanced accuracy), rules resampled within each group."""
    rng = random.Random(seed)
    ra, rb = list(da), list(db)
    out = []
    for _ in range(n):
        a = [x for r in rng.choices(ra, k=len(ra)) for x in rng.choices(da[r], k=len(da[r]))]
        b = [x for r in rng.choices(rb, k=len(rb)) for x in rng.choices(db[r], k=len(db[r]))]
        out.append((statistics.mean(a) + statistics.mean(b)) / 2)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n) - 1]


def acc(items, m):
    """Accuracy (%) over the items that have answers; m: {item id: share of runs answered correctly}."""
    d = defaultdict(list)
    for i in items:
        if i["id"] in m:
            d[i["rule"]].append(m[i["id"]])
    ci = cluster_ci(d)
    return None if ci is None else 100 * ci[0]


def dci(items, a, b):
    """Paired difference a - b in points, with its 95% CI."""
    d = defaultdict(list)
    for i in items:
        if i["id"] in a and i["id"] in b:
            d[i["rule"]].append(a[i["id"]] - b[i["id"]])
    ci = shift_ci(d)
    return None if ci is None else tuple(100 * x for x in ci)


def per_rule_diff(items, a, b):
    d = defaultdict(list)
    for it in items:
        if it["id"] in a and it["id"] in b:
            d[it["rule"]].append(100 * (a[it["id"]] - b[it["id"]]))
    return d


# ------------------------------------------------------------------------------------------------ answers
def read(path):
    rows = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("error"):
                    rows[r["id"]] = r
    return rows


def collect(paths):
    """{item id: [answer row per run]} over the given files."""
    out = defaultdict(list)
    for p in paths:
        for k, r in read(p).items():
            out[k].append(r)
    return out


def rows(part, profile, cond):
    """Answers of one model in one condition (C0 = Image, C2 = Told, T = Text) on one set, every run."""
    if profile == "deepseek":
        return collect([R2 / f"{DS_PREFIX[s]}rep{k}" / f"{cond}.jsonl" for s in SETS[part] for k in range(3)])
    folder = "nothink_" if part == "main" else "t6_nothink_"
    return collect(sorted((R2 / f"{folder}{profile}").glob(f"rep*/{cond}.jsonl")))


def means(rws, items):
    return {i["id"]: sum(bool(r.get("correct")) for r in rws[i["id"]]) / len(rws[i["id"]])
            for i in items if rws.get(i["id"])}


def groups(part):
    items = json.loads((RC / "data" / "items.json").read_text(encoding="utf-8"))
    items = [i for i in items if i["set"] == "mc" and i["split"] in SETS[part]]
    return {"conflict": [i for i in items if i["kind"] == "conflict"],
            "consistent": [i for i in items if i["kind"] == "consistent"]}


def real_share(rws, items):
    """Wrong answers (all runs) and how many of them pick the real-world outcome."""
    hit = wrong = 0
    for it in items:
        key = {o[0]: o[2] for o in it["options"]}
        for r in rws.get(it["id"], []):
            if not r.get("correct") and r.get("pred"):
                wrong += 1
                hit += key.get(r["pred"]) == "real"
    return hit, wrong


# ------------------------------------------------------------------------------------------------ tables
def phenomenon():
    out = {}
    for part in ("main", "hard"):
        g = groups(part)
        for name, prof in MODELS:
            r = {a: rows(part, prof, a) for a in ("T", "C2", "C0")}
            conf = {a: means(r[a], g["conflict"]) for a in r}
            cons = {a: means(r[a], g["consistent"]) for a in r}
            res = {"text": acc(g["conflict"], conf["T"]), "told": acc(g["conflict"], conf["C2"]),
                   "image": acc(g["conflict"], conf["C0"]), "gap": dci(g["conflict"], conf["C2"], conf["C0"]),
                   "cons_told": acc(g["consistent"], cons["C2"]), "cons_image": acc(g["consistent"], cons["C0"])}
            bal = (res["told"] + res["cons_told"]) / 2 - (res["image"] + res["cons_image"]) / 2
            res["bal_gain"] = (bal,) + boot_two(per_rule_diff(g["conflict"], conf["C2"], conf["C0"]),
                                                per_rule_diff(g["consistent"], cons["C2"], cons["C0"]))
            res["real_share"] = real_share(r["C0"], g["conflict"])
            out[(part, name)] = res
    return out


def one_game(folder, items_file, as_consistent=()):
    """Image, Told and Text on a game's engine-checked questions, one run each for three models."""
    T = RC / folder
    raw = json.loads((T / items_file).read_text(encoding="utf-8"))["items"]
    cat = {i["id"]: ("consistent" if i["base_rule"] in as_consistent else i["category"]) for i in raw}
    items = [{"id": i["id"], "rule": i["base_rule"]} for i in raw]
    conf = [x for x in items if cat[x["id"]] != "consistent"]
    cons = [x for x in items if cat[x["id"]] == "consistent"]
    out = {}
    for name, prof in (("DeepSeek", "deepseek"), ("Qwen-Max", "qwenmax"), ("Doubao-Pro", "doubaopro")):
        sc = {}
        for a in ("Image", "Told", "Text"):
            rws = [json.loads(l) for l in (T / "results" / prof / f"{a}.jsonl").read_text(encoding="utf-8").splitlines()
                   if l.strip()]
            sc[a] = {r["id"]: float(bool(r["correct"])) for r in rws}
        out[name] = {"text": acc(conf, sc["Text"]), "told": acc(conf, sc["Told"]), "image": acc(conf, sc["Image"]),
                     "gap": dci(conf, sc["Told"], sc["Image"]),
                     "cons_image": acc(cons, sc["Image"]), "cons_told": acc(cons, sc["Told"])}
    return out


def games():
    # Terraria's T_A04 (sand falls) is filed as an action conflict, but sand falls in the real world as well, so it is
    # scored as a consistent rule
    return {"Terraria": one_game("terraria", "items_terraria.json", as_consistent=("T_A04",)),
            "Stardew Valley": one_game("stardew", "items_stardew.json")}


def reasoning(phen):
    conf = groups("hard")["conflict"]
    out = {}
    for label, src in (("DeepSeek, off", None), ("DeepSeek, on", "think"), ("GPT-6.1-Sol, low", None),
                       ("GPT-6.1-Sol, high", "solhigh")):
        if src is None:                 # the runs of Table 1
            p = phen[("hard", label.split(",")[0])]
            out[label] = {"image": p["image"], "told": p["told"], "gap": p["gap"]}
            continue
        if src == "think":              # DeepSeek with thinking on, one run (rulecraft/think_hard.py)
            r = {a: collect([R2 / "t6_think_deepseek" / f"{a}.jsonl"]) for a in ("C0", "C2")}
        else:
            r = {a: rows("hard", src, a) for a in ("C0", "C2")}
        m = {a: means(r[a], conf) for a in r}
        out[label] = {"image": acc(conf, m["C0"]), "told": acc(conf, m["C2"]), "gap": dci(conf, m["C2"], m["C0"])}
    return out


# ------------------------------------------------------------------------------------------------ output
def f1(x):
    return f"{x:.1f}"


def fs(x):
    return f"{x:+.1f}".replace("-", "$-$")


def ci_tex(c):
    return f"[{c[1]:.1f}, {c[2]:.1f}]".replace("-", "$-$")


def latex(phen, gm, rs):
    for name, _ in MODELS:
        cells = []
        for part in ("main", "hard"):
            r = phen[(part, name)]
            b = r["bal_gain"]
            dagger = "$^{\\dagger}$" if b[1] > 0 or b[2] < 0 else "\\phantom{$^{\\dagger}$}"
            cells += [f1(r["text"]), f1(r["told"]), f1(r["image"]), f"{fs(r['gap'][0])} {{\\scriptsize{ci_tex(r['gap'])}}}",
                      f1(r["cons_told"]), f1(r["cons_image"]), fs(b[0]) + dagger]
        print(" & ".join([name] + cells) + " \\\\")
    for game, rows_ in gm.items():
        for name, r in rows_.items():
            print(f"{name} & {f1(r['text'])} & {f1(r['told'])} & {f1(r['image'])} & {fs(r['gap'][0])} "
                  f"{{\\scriptsize{ci_tex(r['gap'])}}} & {f1(r['cons_image'])} & {f1(r['cons_told'])} \\\\")
    for label, r in rs.items():
        print(f"{label} & {f1(r['image'])} & {f1(r['told'])} & {fs(r['gap'][0])} {{\\scriptsize{ci_tex(r['gap'])}}} \\\\")


def plain(phen, gm, rs):
    gap = lambda g: f"{g[0]:+.1f} [{g[1]:.1f}, {g[2]:.1f}]"
    for part, title in (("main", "Main set (95 rules, 760 questions)"), ("hard", "Hard set (60 rules, 480 questions)")):
        print(f"\n{title}: accuracy (%) on conflict rules, consistent rules, and the gain from naming the game")
        print(f"{'Model':<13}{'Text':>7}{'Told':>7}{'Image':>7}  {'Told-Image [95% CI]':<22}{'Cons.Told':>10}"
              f"{'Cons.Image':>11}  {'Bal. gain':<20}{'real-world share of errors':>27}")
        for name, _ in MODELS:
            r = phen[(part, name)]
            h, w = r["real_share"]
            print(f"{name:<13}{r['text']:>7.1f}{r['told']:>7.1f}{r['image']:>7.1f}  {gap(r['gap']):<22}"
                  f"{r['cons_told']:>10.1f}{r['cons_image']:>11.1f}  {gap(r['bal_gain']):<20}"
                  f"{100 * h / w:>20.0f}% of {w}")
    for game, rows_ in gm.items():
        print(f"\n{game}: accuracy (%), one run per model")
        print(f"{'Model':<13}{'Text':>7}{'Told':>7}{'Image':>7}  {'Told-Image [95% CI]':<22}{'Cons.Image':>11}{'Cons.Told':>10}")
        for name, r in rows_.items():
            print(f"{name:<13}{r['text']:>7.1f}{r['told']:>7.1f}{r['image']:>7.1f}  {gap(r['gap']):<22}"
                  f"{r['cons_image']:>11.1f}{r['cons_told']:>10.1f}")
    print("\nReasoning settings, hard conflict rules: accuracy (%)")
    print(f"{'Model, setting':<20}{'Image':>7}{'Told':>7}  Told-Image [95% CI]")
    for label, r in rs.items():
        print(f"{label:<20}{r['image']:>7.1f}{r['told']:>7.1f}  {gap(r['gap'])}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--latex", action="store_true", help="print the table rows as typeset in the paper")
    a = ap.parse_args()
    if not (R2 / "rep0").exists():
        raise SystemExit("no model answers found: download the dataset and run  python scripts/link_data.py <folder>")
    phen = phenomenon()
    gm, rs = games(), reasoning(phen)
    (latex if a.latex else plain)(phen, gm, rs)


if __name__ == "__main__":
    main()
