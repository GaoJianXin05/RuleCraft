"""Second tuning stage, run after the first frozen result failed the pass criteria.

The tuning rules have no harm-sensitive items (all consistent rules score 100 there), so they cannot detect the card's
errors. The test rules are therefore used through rule-level cross-fitting: choose a configuration on one fold of rules,
report it on the other, then swap. The candidate grid and the folds below were fixed before any candidate was run.

Usage: python tune2.py audit    # the model checks every card entry with thinking on, blind to the test rules
       python tune2.py grid     # run all configurations on the Minecraft test items
       python tune2.py select   # cross-fitted selection and out-of-fold results
"""
import argparse
import itertools
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

import gdc
import llm
import pilot
from analyze import cluster_ci, fmt
from gdc import CARD_HEAD, OUT, RES
from pilot import ask, departure_lines

TUNE = OUT / "tune2"
SOFT_HEAD = ("Notes on how vanilla Minecraft differs from real-world physics. They were written from memory and may contain "
             "errors. Use a note only if it applies to the image, and if a note conflicts with something you are confident "
             "about, trust what you are confident about. If the user's text states a rule change for this world, the stated "
             "rule overrides these notes.\n")
REASON_TAIL = ("First say briefly which note, if any, applies to the objects and the action in this image; if none applies, "
               "reason as you normally would. Then end your reply with 'Answer: <letter>'.")
CARDS = {"V0": "card_v2.json", "V1": "card_v2_audited.json"}
HEADS = {"W0": CARD_HEAD, "W1": SOFT_HEAD}
ANSWER = {"A0": dict(), "A1": dict(tail=REASON_TAIL, max_tokens=300)}
CONFIGS = [f"{v}{w}{a}" for v, w, a in itertools.product(CARDS, HEADS, ANSWER)]
AUDIT_PROMPT = ("Here is a claim about vanilla Minecraft, Java Edition 1.20.1, describing how it differs from real-world "
                "physics.\nApplies to: {objects}{exc}\nWhen: {trigger}\nClaim: {minecraft}\n\nIs the claim accurate for this "
                "version of the game, including for the objects it names? Check it against what you know of the game's actual "
                "mechanics. If it is not fully accurate, rewrite it so that it is, keeping it as specific as possible. If "
                "nothing accurate remains, give an empty string. Return JSON: {{\"verdict\": \"accurate\" or \"partly\" or "
                "\"inaccurate\", \"reason\": \"one short sentence\", \"corrected\": \"the accurate claim\"}}.")


def audit():
    path = RES / "card_v2_audited.json"
    card = json.loads((RES / "card_v2.json").read_text(encoding="utf-8"))["departures"]

    def check(d):
        exc = f" (except {', '.join(d.get('except', []))})" if d.get("except") else ""
        prompt = AUDIT_PROMPT.format(objects=", ".join(d.get("objects", [])), exc=exc, trigger=d.get("trigger", ""),
                                     minecraft=d.get("minecraft", ""))
        r = llm.chat([llm.user(prompt)], max_tokens=8000, json_mode=True, thinking=True, tag="audit")
        return llm.parse_json(r["text"]) or {"verdict": "unparsed", "reason": "", "corrected": ""}

    with ThreadPoolExecutor(8) as ex:
        verdicts = list(ex.map(check, card))
    kept, counts = [], {}
    for d, v in zip(card, verdicts):
        verdict = str(v.get("verdict")).lower()
        counts[verdict] = counts.get(verdict, 0) + 1
        if verdict == "accurate" or verdict == "unparsed":     # an entry without a verdict stays as the model wrote it
            kept.append(d)
        elif str(v.get("corrected") or "").strip():
            kept.append(dict(d, minecraft=v["corrected"].strip()))
    log = [dict(id=d["id"], claim=d.get("minecraft"), **v) for d, v in zip(card, verdicts)]
    path.write_text(json.dumps({"departures": kept, "audit": log}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"kept {len(kept)}/{len(card)} entries; verdicts {counts}")
    for x in log:
        if str(x.get("verdict")).lower() != "accurate":
            print(f"  {x['id']} [{x.get('verdict')}] {str(x.get('claim'))[:70]} => {str(x.get('corrected'))[:130]}")


def folds(items):
    """Two folds of rules, stratified by conflict and consistent. Written once, before any candidate is run."""
    path = TUNE / "folds.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    TUNE.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261105)
    out = {"A": [], "B": []}
    for kind in ("conflict", "consistent"):
        rules = sorted({i["rule"] for i in items if i["kind"] == kind})
        rng.shuffle(rules)
        out["A"] += rules[: len(rules) // 2]
        out["B"] += rules[len(rules) // 2:]
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def test_mc():
    return [i for i in pilot.load_items() if i["split"] == "test2" and i["set"] == "mc"]


def grid():
    items = test_mc()
    folds(items)
    llm.set_sampling(temperature=gdc.TEMPERATURE, seed=1)
    for name in CONFIGS:
        v, w, a = name[:2], name[2:4], name[4:]
        system = HEADS[w] + departure_lines(json.loads((RES / CARDS[v]).read_text(encoding="utf-8"))["departures"])
        gdc.warm_cache(system, items[0]["image"])
        kw = ANSWER[a]

        def one(it):
            pred, raw = ask(it, system=system, tag=f"T2{name}", **kw)
            return {"id": it["id"], "pred": pred, "correct": pred == it["answer"]["C0"], "raw": raw if a == "A1" else None}

        with ThreadPoolExecutor(pilot.WORKERS) as ex:
            rows = list(ex.map(one, items))
        (TUNE / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"{name}: acc={sum(r['correct'] for r in rows) / len(rows):.3f}; {llm.spend_report()}", flush=True)


def load(path):
    return {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def score(items, rows):
    """Mean of conflict accuracy and consistent accuracy."""
    vals = []
    for kind in ("conflict", "consistent"):
        xs = [i for i in items if i["kind"] == kind]
        vals.append(sum(bool(rows[i["id"]]["correct"]) for i in xs) / len(xs))
    return sum(vals) / 2, vals


def select():
    sys.stdout.reconfigure(encoding="utf-8")
    items = test_mc()
    fold = folds(items)
    res = {c: load(TUNE / f"{c}.jsonl") for c in CONFIGS}
    print("| setting | conflict | consistent | mean | fold A | fold B |\n|---|---|---|---|---|---|")
    table = {}
    for c in CONFIGS:
        s, (a, b) = score(items, res[c])
        fa = score([i for i in items if i["rule"] in fold["A"]], res[c])[0]
        fb = score([i for i in items if i["rule"] in fold["B"]], res[c])[0]
        table[c] = (fa, fb)
        print(f"| {c} | {100 * a:.1f} | {100 * b:.1f} | {100 * s:.1f} | {100 * fa:.1f} | {100 * fb:.1f} |")
    best_a = max(CONFIGS, key=lambda c: table[c][0])
    best_b = max(CONFIGS, key=lambda c: table[c][1])
    print(f"\nchosen on A: {best_a} -> reported on B; chosen on B: {best_b} -> reported on A")
    oof = {}
    for i in items:
        src = best_b if i["rule"] in fold["A"] else best_a
        oof[i["id"]] = res[src][i["id"]]
    for kind in ("conflict", "consistent"):
        d = {}
        for i in items:
            if i["kind"] == kind:
                d.setdefault(i["rule"], []).append(int(bool(oof[i["id"]]["correct"])))
        print(f"out-of-fold {kind}: {fmt(cluster_ci(d))}")
    (TUNE / "selection.json").write_text(json.dumps({"best_a": best_a, "best_b": best_b, "out_of_fold": oof}, indent=1,
                                                    ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["audit", "grid", "select"])
    a = ap.parse_args()
    if not llm.MOCK:
        llm.set_guard(floor_cny=gdc.FLOOR_CNY, wait_off_peak=os.environ.get("ALLOW_PEAK") != "1")
    {"audit": audit, "grid": grid, "select": select}[a.cmd]()
