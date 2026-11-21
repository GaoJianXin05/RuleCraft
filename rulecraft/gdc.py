"""Gated departure card (GDC) and the full experiment runner.

GDC, in plain terms: first ask which world the image shows (the gate). If it is Minecraft, answer with the departure card
in the system message; otherwise answer exactly as the direct prompt does. The card lists only how the world differs
from reality and is written by the model itself, once, before any test item is seen.

Ablations: GateOnly (gate, no card), NoGate (card always), GateRetr (gate, only the entries matching the scene's objects).
Baselines: C0 (direct), CoT, GKP, FixedGame.

Usage: python gdc.py card
       python gdc.py tune                    # one repeat on the tuning rules (round-1 rules and round-1 GlitchBench sample)
       python gdc.py run --reps 2            # the frozen test set; results/r2/rep<k>/<condition>.jsonl
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot
from pilot import CONTEXT, ask, departure_lines, question_block, retrieve

RES = llm.RESULTS
OUT = RES / "r2"
TEMPERATURE = 1.0                       # default sampling, the only setting all three formal models share
# The account is shared with another experiment, so its balance says nothing about this project's spend (see
# results/usage.jsonl for that). The floor only stops the run before the account empties.
FLOOR_CNY = 1.0

# Generic topics only: they must not name anything that a test rule is about.
FAMILIES = {
    "GRV": "gravity and support: which blocks and objects fall, stay in place or drop when what holds them up is removed",
    "FLU": "liquids: how water and lava flow, spread and interact with blocks and objects",
    "PLA": "plants: what they need to survive, when they break and how they grow",
    "LHF": "light, heat and fire: melting, freezing, burning and what catches fire",
    "RXN": "materials and tools: what happens when blocks are broken, combined, or exposed to water, lava, weather or time",
}
FAMILY_PROMPT = ("List the ways in which the following aspect of vanilla Minecraft (Java Edition 1.20.1) DIFFERS from "
                 "real-world physics: {desc}. Only list differences, not similarities. Return JSON: {{\"departures\": "
                 "[{{\"id\": \"short-id\", \"objects\": [affected blocks or items, lowercase; use \"all blocks\" if "
                 "general], \"except\": [blocks excluded, if any], \"trigger\": \"when it happens\", \"real_world\": "
                 "\"what would happen in reality\", \"minecraft\": \"what happens in Minecraft\"}}]}}. "
                 "Give 8 to 20 entries.")
CARD_HEAD = ("Notes on how vanilla Minecraft differs from real-world physics. Use a note only if it applies to the image. "
             "If the user's text states a rule change for this world, the stated rule overrides these notes.\n")
GATE_PROMPT = ("Look at the image and read the question.\n{q}\nDo not answer the question. Return JSON with fields:\n"
               " world: one of \"real_world\", \"minecraft_vanilla\", \"minecraft_modded\", \"other_game\", \"unknown\";\n"
               " game_name: the name of the game if the image is from a game, else \"\";\n"
               " objects: the objects or blocks involved in the action or question (lowercase names).")


def entries(js):
    js = js or {}
    return js.get("departures") or next((v for v in js.values() if isinstance(v, list)), [])


def build_card_v2(n=5):
    path = RES / ("card_v2_mock.json" if llm.MOCK else "card_v2.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    card, raw = [], {}
    for fam, desc in FAMILIES.items():
        samples = []
        for s in range(n):
            r = llm.chat([llm.user(FAMILY_PROMPT.format(desc=desc))], max_tokens=3000, json_mode=True,
                         temperature=0.7, tag=f"card2_{fam}", seed=s)
            samples.append(entries(llm.parse_json(r["text"])))
        merge = (f"Here are {n} lists of differences between vanilla Minecraft and real-world physics about {desc}, "
                 "produced independently. Merge entries that describe the same difference. Keep only differences that "
                 f"appear in at least {n // 2 + 1} of the {n} lists. Return JSON: {{\"departures\": [...]}} using the same "
                 "entry format.\n" + json.dumps(samples, ensure_ascii=False))
        merged = entries(llm.parse_json(llm.chat([llm.user(merge)], max_tokens=5000, json_mode=True, temperature=0.0,
                                                 tag=f"card2_merge_{fam}", seed=0)["text"]))
        for i, d in enumerate(merged):
            d["id"] = f"{fam}{i + 1}"
            card.append(d)
        raw[fam] = samples
    path.write_text(json.dumps({"departures": card, "samples": raw}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"departures": card, "samples": raw}


def card_system(deps):
    return CARD_HEAD + departure_lines(deps)


def gate(item):
    r = llm.chat([llm.user(GATE_PROMPT.format(q=question_block(item)), [item["image"]])], max_tokens=150, json_mode=True,
                 tag="GATE")
    g = llm.parse_json(r["text"]) or {}
    if isinstance(g, list):     # a few Qwen replies come as a list: [{...}] or a flat ["world", "minecraft_vanilla"]
        dicts = [x for x in g if isinstance(x, dict)]
        g = dicts[0] if dicts else (dict(zip(g[::2], g[1::2])) if len(g) % 2 == 0
                                    and all(isinstance(x, str) for x in g[::2]) else {})
    world = str(g.get("world", "unknown"))
    return {"world": world, "game_name": str(g.get("game_name") or ""), "objects": g.get("objects") or [],
            "is_mc": world.startswith("minecraft")}


def answer(item, g, card, system_all, ctx="C0", use_gate=True, use_card=True, mode="whole", tag="GDC"):
    """Answer one item with a GDC variant, given the gate result g of this repeat."""
    context = CONTEXT[ctx].format(mod=item.get("mod", ""))
    if use_gate and not g["is_mc"]:
        pred, _ = ask(item, context, tag=ctx)
        path = "direct"
    elif not use_card:
        hint = f"This scene is from {g['game_name'] or 'Minecraft'}. Answer according to the rules of that game.\n"
        pred, _ = ask(item, context + hint, tag=tag)
        path = "hint"
    elif mode == "whole":
        pred, _ = ask(item, context, system=system_all, tag=tag)
        path = "card"
    else:
        deps = retrieve(card, g["objects"])
        pred, _ = ask(item, context, system=card_system(deps) if deps else None, tag=tag)
        path = f"retrieved:{len(deps)}"
    return {"pred": pred, "correct": pred == item["answer"][ctx], "world": g["world"], "path": path}


def par(fn, xs):
    with ThreadPoolExecutor(pilot.WORKERS) as ex:
        return list(ex.map(fn, xs))


def warm_cache(system_all, image):
    """One call before the parallel ones, so that they find the card in the prompt cache instead of all missing it."""
    llm.chat([{"role": "system", "content": system_all}, llm.user("Reply with the single letter A.", [image])],
             max_tokens=3, tag="warm")
    if not llm.MOCK:
        time.sleep(15)


def run_conditions(items, out_dir, only=None, diagnostics=True):
    out_dir.mkdir(parents=True, exist_ok=True)
    mc = [i for i in items if i["set"] == "mc"]
    conflict = [i for i in mc if i["kind"] == "conflict"]
    s1 = mc + [i for i in items if i["set"] != "mc"]
    card = build_card_v2()["departures"]
    system_all = card_system(card)

    def save(name, xs, rows):
        with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for i, r in zip(xs, rows):
                f.write(json.dumps(dict(id=i["id"], **r), ensure_ascii=False) + "\n")
        acc = sum(bool(r.get("correct")) for r in rows) / max(1, len(rows))
        print(f"{out_dir.name}/{name}: {len(rows)} rows, acc={acc:.3f}", flush=True)

    def want(n):
        return only is None or n in only

    if diagnostics:
        if want("R"):
            save("R", mc, par(pilot.run_R, mc))
        if want("K"):
            rules = sorted({i["rule"] for i in mc})
            save("K", [{"id": r} for r in rules], par(pilot.run_K_rule, rules))
        if want("P"):
            save("P", mc, par(pilot.run_P, mc))
        if want("T"):
            save("T", mc, par(pilot.run_T, mc))
    for ctx, xs in (("C0", s1), ("C1", conflict), ("C2", mc), ("C3", mc)):
        if want(ctx):
            save(ctx, xs, par(lambda it, c=ctx: pilot.run_context(it, c), xs))
    for name, fn in (("CoT", pilot.run_cot), ("GKP", pilot.run_gkp), ("FixedGame", pilot.run_fixed)):
        if want(name):
            save(name, s1, par(fn, s1))
    if only is not None and not only & {"GATE", "GDC", "GateOnly", "NoGate", "GateRetr", "GDC_C3"}:
        print("spend so far:", llm.spend_report(), flush=True)      # a phenomenon-only run needs no gate and no card
        return
    gates = dict(zip([i["id"] for i in s1], par(gate, s1)))
    save("GATE", s1, [gates[i["id"]] for i in s1])
    warm_cache(system_all, mc[0]["image"])
    variants = {"GDC": dict(),"GateOnly": dict(use_card=False, tag="GateOnly"), "NoGate": dict(use_gate=False, tag="NoGate"),
                "GateRetr": dict(mode="retrieved", tag="GateRetr")}
    for name, kw in variants.items():
        if want(name):
            save(name, s1, par(lambda it, k=kw: answer(it, gates[it["id"]], card, system_all, **k), s1))
    if want("GDC_C3"):
        save("GDC_C3", mc, par(lambda it: answer(it, gates[it["id"]], card, system_all, ctx="C3", tag="GDC_C3"), mc))
    print("spend so far:", llm.spend_report(), flush=True)


def run(reps, prefix, only=None, split="test2"):
    items = [i for i in pilot.load_items() if i["split"] == split]
    start = time.time()
    for rep in range(reps):
        llm.set_sampling(temperature=TEMPERATURE, seed=rep + 1)
        run_conditions(items, OUT / f"{prefix}rep{rep}", only)
        print(f"after repeat {rep}: {llm.spend_report(start)}", flush=True)


def tune(rep=0):
    items = [i for i in pilot.load_items() if i["split"] in ("test", "dev")]
    llm.set_sampling(temperature=TEMPERATURE, seed=100 + rep)
    run_conditions(items, OUT / f"tune{rep}", only={"C0", "C3", "GDC", "NoGate", "GateRetr", "GateOnly", "GDC_C3"},
                   diagnostics=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["card", "tune", "run"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--only", default=None)
    ap.add_argument("--split", default="test2")
    a = ap.parse_args()
    if not llm.MOCK:
        # ALLOW_PEAK=1 runs during DeepSeek's peak hours at double price instead of waiting
        llm.set_guard(floor_cny=FLOOR_CNY, wait_off_peak=os.environ.get("ALLOW_PEAK") != "1")
    t0 = time.time()
    if a.cmd == "card":
        c = build_card_v2()["departures"]
        print(len(c), "entries;", llm.spend_report(t0))
    elif a.cmd == "tune":
        tune()
        print("tuning:", llm.spend_report(t0))
    else:
        run(a.reps, a.prefix, set(a.only.split(",")) if a.only else None, a.split)
