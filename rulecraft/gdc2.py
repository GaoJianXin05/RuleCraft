"""The final GDC, chosen by cross-fitting in tune2.py (configuration V1W1A1), and its ablations.

Gate: which world does the image show? If Minecraft, answer with the audited card in the system message, say which note
applies, then answer. Otherwise answer with plain chain of thought, the default reasoner (chosen on the tuning sample).
Ablations: GateOnly (gate, no card), NoGate (card always), GateRetr (gate, only entries matching the scene's objects).

Baselines stay in results/r2/rep<k>; this script writes results/r2/final_rep<k>. Usage: python gdc2.py [--reps 2]
"""
import argparse
import json
import os
import time

import gdc
import llm
import pilot
from gdc import OUT, RES, par
from pilot import CONTEXT, COT_TAIL, ask, departure_lines, retrieve
from tune2 import REASON_TAIL, SOFT_HEAD


def load_card():
    return json.loads((RES / "card_v2_audited.json").read_text(encoding="utf-8"))["departures"]


def system_of(deps):
    return SOFT_HEAD + departure_lines(deps)


def answer(item, g, card, system_all, ctx="C0", use_gate=True, use_card=True, mode="whole", tag="GDC2"):
    context = CONTEXT[ctx].format(mod=item.get("mod", ""))
    if use_gate and not g["is_mc"]:
        pred, _ = ask(item, context, tail=COT_TAIL, max_tokens=700, tag="CoT")
        path = "default"
    elif not use_card:
        hint = f"This scene is from {g['game_name'] or 'Minecraft'}. Answer according to the rules of that game.\n"
        pred, _ = ask(item, context + hint, tail=COT_TAIL, max_tokens=700, tag=tag)
        path = "hint"
    elif mode == "whole":
        pred, _ = ask(item, context, tail=REASON_TAIL, max_tokens=300, system=system_all, tag=tag)
        path = "card"
    else:
        deps = retrieve(card, g["objects"])
        if deps:
            pred, _ = ask(item, context, tail=REASON_TAIL, max_tokens=300, system=system_of(deps), tag=tag)
        else:
            pred, _ = ask(item, context, tail=COT_TAIL, max_tokens=700, tag=tag)
        path = f"retrieved:{len(deps)}"
    return {"pred": pred, "correct": pred == item["answer"][ctx], "world": g["world"], "path": path}


def gates_of(rep, prefix=""):
    rows = (OUT / f"{prefix}rep{rep}" / "GATE.jsonl").read_text(encoding="utf-8").splitlines()
    return {json.loads(l)["id"]: json.loads(l) for l in rows if l.strip()}


def run(reps, prefix="", split="test2", arms=None):
    items = [i for i in pilot.load_items() if i["split"] == split]
    mc = [i for i in items if i["set"] == "mc"]
    s1 = mc + [i for i in items if i["set"] != "mc"]
    card = load_card()
    system_all = system_of(card)
    t0 = time.time()
    for rep in range(reps):
        llm.set_sampling(temperature=gdc.TEMPERATURE, seed=rep + 1)
        out = OUT / f"{prefix}final_rep{rep}"
        out.mkdir(parents=True, exist_ok=True)
        gates = gates_of(rep, prefix)
        gdc.warm_cache(system_all, mc[0]["image"])

        def save(name, xs, rows):
            with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
                for i, r in zip(xs, rows):
                    f.write(json.dumps(dict(id=i["id"], **r), ensure_ascii=False) + "\n")
            print(f"{out.name}/{name}: {len(rows)} rows, acc={sum(bool(r['correct']) for r in rows) / len(rows):.3f}", flush=True)

        variants = {"GDC": dict(), "GateOnly": dict(use_card=False, tag="GateOnly2"), "NoGate": dict(use_gate=False, tag="NoGate2"),
                    "GateRetr": dict(mode="retrieved", tag="GateRetr2")}
        for name, kw in variants.items():
            if arms is None or name in arms:
                save(name, s1, par(lambda it, k=kw: answer(it, gates[it["id"]], card, system_all, **k), s1))
        if arms is None or "GDC_C3" in arms:
            save("GDC_C3", mc, par(lambda it: answer(it, gates[it["id"]], card, system_all, ctx="C3", tag="GDC2_C3"), mc))
        print(f"after final repeat {rep}: {llm.spend_report(t0)}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--split", default="test2")
    ap.add_argument("--arms", default=None, help="comma-separated arms; all by default")
    a = ap.parse_args()
    if not llm.MOCK:
        llm.set_guard(floor_cny=gdc.FLOOR_CNY, wait_off_peak=os.environ.get("ALLOW_PEAK") != "1")
    run(a.reps, a.prefix, a.split, set(a.arms.split(",")) if a.arms else None)
