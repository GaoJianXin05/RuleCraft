"""Pilot experiments: diagnosis ladder, three-context matrix, baselines, MDR and its ablations.

Usage (from the pilot folder):
  python pilot.py items              # build data/items.json from rules + rendered images (+ external sets if present)
  python pilot.py run [--only NAMES] # run conditions; results/<condition>.jsonl (cached, safe to re-run)
  MOCK=1 python pilot.py run         # dry run without API calls
"""
import argparse
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import llm
from rules import RULE_BY_ID, pretty

ROOT = Path(__file__).parent
DATA = ROOT / "data"
RES = llm.RESULTS
WORKERS = int(os.environ.get("WORKERS", 24))

CONTEXT = {
    "C0": "",
    "C1": "Suppose the scene in this image were a real-world scene built from real materials (real soil, wood, sand, "
          "ice, plants and so on) that obey real-world physics.\n",
    "C2": "This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1). Answer according to the rules of "
          "vanilla Minecraft.\n",
    "C3": "This image is a screenshot from a modded Minecraft server. On this server, {mod}. Everything else follows "
          "vanilla Minecraft (Java Edition 1.20.1).\n",
}
FIXED_GAME = "Answer according to the rules of the video game shown in the image, not according to real-world physics.\n"
TAIL = "Reply with a single letter."
COT_TAIL = "Think step by step, then end your reply with 'Answer: <letter>'."


# ----------------------------------------------------------------------------- items
def fill(s, v):
    return s.format(target_name=v["target_name"], support_name=v.get("support_name") or "")


def build_items():
    variants = json.loads((DATA / "variants.json").read_text(encoding="utf-8"))
    items = []
    for v in variants:
        rule = RULE_BY_ID[v["rule"]]
        img = DATA / v["image"]
        if not img.exists():
            continue
        rng = random.Random(v["variant"])
        keys = list(rule["options"].keys())
        rng.shuffle(keys)
        letters = "ABC"
        opts = [(letters[i], fill(rule["options"][k], v), k) for i, k in enumerate(keys)]
        by_key = {k: l for l, _, k in opts}
        if rule["kind"] == "conflict":
            answer = {"C0": by_key["vanilla"], "C1": by_key["real"], "C2": by_key["vanilla"], "C3": by_key["third"],
                      "T": by_key["vanilla"]}
        else:
            answer = {"C0": by_key["correct"], "C2": by_key["correct"], "C3": by_key[rule["mod_answer"]],
                      "T": by_key["correct"]}
        items.append({
            "id": v["variant"], "set": "mc", "rule": v["rule"], "kind": rule["kind"], "split": v["split"],
            "family": rule["family"], "familiarity": rule["familiarity"], "trap": bool(rule.get("trap_of")),
            "image": str(img), "action": fill(rule["action"], v),
            "question": "What happens immediately after this action? (If the action describes time passing, "
                        "answer for the end of that period.)",
            "options": opts, "keys": by_key, "answer": answer, "mod": fill(rule["mod"], v),
            "world": "minecraft_vanilla", "gold_departure": rule["departure"],
            "target_name": v["target_name"], "support_name": v.get("support_name"),
            "text_scene": fill(rule["text_scene"], v),
            "p_pair": [fill(s, v) for s in rule["p_pair"]],
        })
    for extra in ("items_glitch.json", "items_glitch2.json", "items_physbench.json"):
        p = DATA / extra
        if p.exists():
            items += json.loads(p.read_text(encoding="utf-8"))
    (DATA / "items.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"items: {len(items)} ({sum(i['set'] == 'mc' for i in items)} Minecraft)")


def load_items():
    items = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
    for it in items:            # image paths are stored relative to this folder
        it["image"] = str(ROOT / it["image"])
    return items


def options_text(item):
    return "\n".join(f"{l}. {t}" for l, t, _ in item["options"])


def letters_of(item):
    return "".join(l for l, _, _ in item["options"])


def question_block(item):
    lines = []
    if item.get("action"):
        lines.append(f"Action: {item['action']}")
    lines.append(item["question"])
    lines.append(options_text(item))
    return "\n".join(lines)


def ask(item, context="", tail=TAIL, extra="", max_tokens=20, tag="", seed=None, images=None, system=None):
    prompt = f"{context}{extra}Look at the image.\n{question_block(item)}\n{tail}"
    # a system message comes first in the request, so a long fixed card is served from the prompt cache
    head = [{"role": "system", "content": system}] if system else []
    r = llm.chat(head + [llm.user(prompt, images if images is not None else [item["image"]])],
                 max_tokens=max_tokens, tag=tag, seed=seed)
    return llm.parse_letter(r["text"], letters_of(item)), r["text"]


# ----------------------------------------------------------------------------- diagnosis
def run_R(item):
    r = llm.chat([llm.user("Which video game is this screenshot from? Reply with the name of the game only.",
                           [item["image"]])], max_tokens=20, tag="R")
    return {"pred": r["text"].strip(), "correct": "minecraft" in r["text"].lower()}


def true_false(statement, images=(), tag=""):
    prompt = f"True or false: {statement}\nReply with 'true' or 'false' only."
    r = llm.chat([llm.user(prompt, list(images))], max_tokens=5, tag=tag)
    t = r["text"].strip().lower()
    return True if t.startswith("true") else False if t.startswith("false") else None


def run_P(item):
    t = true_false(item["p_pair"][0], [item["image"]], tag="P")
    f = true_false(item["p_pair"][1], [item["image"]], tag="P")
    return {"pred": [t, f], "correct": t is True and f is False}


def run_K_rule(rule_id):
    rule = RULE_BY_ID[rule_id]
    v = {"target_name": pretty(rule["target_choices"][0]),
         "support_name": pretty(rule.get("support") or (rule.get("support_choices") or [""])[0])}
    passes = []
    for tr, fa in rule["k_pairs"]:
        t = true_false(fill(tr, v), tag="K")
        f = true_false(fill(fa, v), tag="K")
        passes.append(t is True and f is False)
    return {"pred": passes, "correct": all(passes)}


def run_T(item):
    prompt = (f"In vanilla Minecraft (Java Edition 1.20.1): {item['text_scene']}\n{question_block(item)}\n{TAIL}")
    r = llm.chat([llm.user(prompt)], max_tokens=20, tag="T")
    pred = llm.parse_letter(r["text"], letters_of(item))
    return {"pred": pred, "correct": pred == item["answer"]["T"]}


def run_context(item, ctx):
    context = CONTEXT[ctx].format(mod=item.get("mod", ""))
    pred, raw = ask(item, context, tag=ctx)
    return {"pred": pred, "correct": pred == item["answer"][ctx], "raw": raw}


# ----------------------------------------------------------------------------- baselines
def run_cot(item):
    pred, raw = ask(item, tail=COT_TAIL, max_tokens=700, tag="CoT")
    return {"pred": pred, "correct": pred == item["answer"]["C0"], "raw": raw}


def run_gkp(item):
    k = llm.chat([llm.user("Before answering, list 3-5 facts or rules that are relevant for predicting the answer to "
                           f"the question below. Do not answer the question yet.\n{question_block(item)}",
                           [item["image"]])], max_tokens=300, tag="GKP1")["text"]
    pred, raw = ask(item, extra=f"Relevant knowledge:\n{k}\n\n", tag="GKP2")
    return {"pred": pred, "correct": pred == item["answer"]["C0"], "knowledge": k}


def run_fixed(item):
    pred, raw = ask(item, FIXED_GAME, tag="FixedGame")
    return {"pred": pred, "correct": pred == item["answer"]["C0"]}


# ----------------------------------------------------------------------------- MDR
CARD_PROMPT = (
    "List the ways in which the behavior of blocks, liquids, plants, light, heat and other physical phenomena in vanilla "
    "Minecraft (Java Edition 1.20.1) DIFFERS from real-world physics. Only list differences, not similarities. "
    "Return JSON: {\"departures\": [{\"id\": \"short-id\", \"objects\": [affected blocks or items, lowercase; use "
    "\"all blocks\" if general], \"except\": [blocks excluded, if any], \"trigger\": \"when it happens\", "
    "\"real_world\": \"what would happen in reality\", \"minecraft\": \"what happens in Minecraft\"}]}. "
    "Give 20 to 40 entries.")


def build_card(n_samples=5):
    path = RES / "card.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    samples = []
    for s in range(n_samples):
        r = llm.chat([llm.user(CARD_PROMPT)], max_tokens=4000, json_mode=True, temperature=0.7, tag="card", seed=s)
        samples.append((llm.parse_json(r["text"]) or {}).get("departures", []))
    merge = (f"Here are {n_samples} lists of differences between vanilla Minecraft and real-world physics, produced "
             "independently. Merge entries that describe the same difference. Keep only differences that appear in at "
             f"least {n_samples // 2 + 1} of the {n_samples} lists. Return JSON in the same format, with ids D1, D2, ...\n"
             + json.dumps(samples, ensure_ascii=False))
    r = llm.chat([llm.user(merge)], max_tokens=6000, json_mode=True, tag="card_merge")
    merged = llm.parse_json(r["text"]) or {}
    # the model sometimes renames the top-level key; take the first list of entries it returned
    card = merged.get("departures") or next((v for v in merged.values() if isinstance(v, list)), [])
    for i, d in enumerate(card):
        d.setdefault("id", f"D{i + 1}")
    path.write_text(json.dumps({"departures": card, "samples": samples}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"departures": card, "samples": samples}


STOP = {"block", "blocks", "a", "the", "of"}
GENERAL = {"all", "most", "any", "solid", "non", "other", "normal", "regular", "every"}


def tokens(name):
    words = re.findall(r"[a-z]+", str(name).lower().replace("_", " "))
    return {w[:-1] if w.endswith("s") and len(w) > 3 and not w.endswith("ss") else w for w in words}


def same_thing(scene_obj, card_name):
    """Token match: 'red sand' matches 'sand', but 'sandstone' does not match 'sand'."""
    a, b = tokens(scene_obj) - STOP, tokens(card_name) - STOP
    return bool(a and b) and (b <= a or a <= b)


def retrieve(card, objects):
    """Code retrieval: keep entries whose objects match a scene object, or general entries minus their exceptions."""
    hits = []
    for d in card:
        names = d.get("objects", [])
        general = any(("block" in tokens(n) and tokens(n) & GENERAL) or tokens(n) <= {"block"} for n in names)
        excl = d.get("except", []) or []
        match = any(same_thing(o, n) for o in objects for n in names)
        if general and any(not any(same_thing(o, e) for e in excl) for o in objects):
            match = True
        if match:
            hits.append(d)
    return hits


def ground(item, context=""):
    prompt = (f"{context}Look at the image and read the question.\n{question_block(item)}\n"
              "Do not answer the question. Return JSON with fields:\n"
              " world: one of \"real_world\", \"minecraft_vanilla\", \"minecraft_modded\", \"other_game\", \"unknown\";\n"
              " game_name: the name of the game if the image is from a game, else \"\";\n"
              " evidence: a short list of visual cues for your choice of world;\n"
              " declared_changes: rule changes explicitly stated in the text above (empty list if none);\n"
              " objects: the objects or blocks involved in the action or question (lowercase names);\n"
              " state: one or two sentences describing the relevant arrangement (what rests on what, what touches what).")
    r = llm.chat([llm.user(prompt, [item["image"]])], max_tokens=400, json_mode=True, tag="MDR1")
    g = llm.parse_json(r["text"]) or {}
    g.setdefault("world", "unknown")
    g.setdefault("objects", [])
    g.setdefault("declared_changes", [])
    g.setdefault("state", "")
    return g


def departure_lines(deps):
    out = []
    for d in deps:
        exc = f" (except {', '.join(d.get('except', []))})" if d.get("except") else ""
        out.append(f"- {d['id']}: applies to {', '.join(d.get('objects', [])) or 'the stated objects'}{exc}; "
                   f"when: {d.get('trigger', '')}; in this world: {d.get('minecraft', '')}")
    return "\n".join(out)


def scene_text(g, item):
    return (f"Scene: {g.get('state', '')} (objects: {', '.join(g.get('objects', []))})\nWorld: {g.get('world')}"
            f"{' (' + g['game_name'] + ')' if g.get('game_name') else ''}\n{question_block(item)}")


def declared_applies(d, objects):
    """Code-level scope check for a rule stated in the prompt: it names a scene object, or it is stated for any block."""
    words = tokens(d["minecraft"])
    if {"any", "block"} <= words or {"all", "block"} <= words or {"every", "block"} <= words:
        return True
    return any((tokens(o) - STOP) and (tokens(o) - STOP) <= words for o in objects)


def default_then_depart(item, g, deps):
    declared = [d for d in deps if d["id"].startswith("DECL") and declared_applies(d, g.get("objects", []))]
    general = [d for d in deps if not d["id"].startswith("DECL")]
    blocks = []
    if declared:
        blocks.append("Rules explicitly stated for this specific world. They DO apply to this scene and take priority "
                      "over the general rules below; if a stated rule and a general rule conflict, the stated rule wins:\n"
                      + "\n".join(f"- {d['id']}: {d['minecraft']}" for d in declared))
    if general:
        blocks.append("General rules on how this world differs from real-world physics:\n" + departure_lines(general))
    prompt = (f"{scene_text(g, item)}\n\nAnswer in three stages.\n"
              "Stage 1 (default): which option would happen under real-world physics?\n"
              "Stage 2 (departures): for each rule below, decide whether it applies to the objects and the action in this "
              "scene (yes or no).\n"
              + "\n\n".join(blocks) + "\n"
              "Stage 3 (final): starting from the default outcome, apply every rule that applies. Which option "
              "happens in this world?\n"
              "Return JSON: {\"default\": \"<letter>\", \"applies\": {\"<id>\": \"yes\" or \"no\"}, \"final\": \"<letter>\"}")
    r = llm.chat([llm.user(prompt)], max_tokens=400, json_mode=True, tag="MDR3")
    out = llm.parse_json(r["text"]) or {}
    applies = out.get("applies") or {}
    for d in declared:                      # stated rules are applied by code, not by the model's yes/no
        applies[d["id"]] = "yes"
    out["applies"] = applies
    return out


def mdr(item, card, context="", ctx="C0", direct_pred=None, gate=True, default_stage=True):
    """MDR. gate=False -> ablation A1 (always use the Minecraft card); default_stage=False -> ablation A2."""
    g = ground(item, context)
    world = g.get("world", "unknown")
    declared = [{"id": f"DECL{i + 1}", "objects": ["(as stated)"], "trigger": "as stated", "minecraft": c}
                for i, c in enumerate(g.get("declared_changes") or [])]
    if gate:
        deps = (retrieve(card, g["objects"]) if world.startswith("minecraft") else []) + declared
    else:
        deps = retrieve(card, g["objects"]) + declared
    rec = {"world": world, "objects": g["objects"], "state": g.get("state"), "retrieved": [d["id"] for d in deps]}
    if not deps:
        # nothing to apply: MDR answers exactly like the direct prompt
        pred = direct_pred if direct_pred is not None else ask(item, context, tag=ctx)[0]
        rec.update(path="direct", pred=pred)
    elif default_stage:
        out = default_then_depart(item, g, deps)
        applies = {k: str(v).lower().startswith("y") for k, v in (out.get("applies") or {}).items()}
        rec.update(path="mdr", default=out.get("default"), applies=applies, final_model=out.get("final"))
        rec["pred"] = out.get("final") if any(applies.values()) else out.get("default")
    else:
        prompt = (f"{scene_text(g, item)}\n\nThis world differs from real-world physics as follows:\n"
                  f"{departure_lines(deps)}\nUsing the rules of this world, which option happens? "
                  "Return JSON: {\"final\": \"<letter>\"}")
        out = llm.parse_json(llm.chat([llm.user(prompt)], max_tokens=60, json_mode=True, tag="A2")["text"]) or {}
        rec.update(path="no_default", pred=out.get("final"))
    rec["correct"] = rec["pred"] == item["answer"][ctx]
    return rec


def run_A3(item, card, ctx="C0", context=""):
    notes = departure_lines(card)
    pred, raw = ask(item, context, extra=f"Notes on how vanilla Minecraft differs from real-world physics (use a note "
                                         f"only if it applies to this image):\n{notes}\n\n", tag="A3")
    return {"pred": pred, "correct": pred == item["answer"][ctx]}


# ----------------------------------------------------------------------------- runner
def run_all(only=None, split=None):
    items = load_items()
    if split:
        items = [i for i in items if i["split"] == split]
    mc = [i for i in items if i["set"] == "mc"]
    conflict = [i for i in mc if i["kind"] == "conflict"]
    locality = [i for i in items if i["set"] != "mc"]
    s1 = mc + locality                      # implicit setting (C0) on all streams
    card = None

    def save(name, rows):
        with open(RES / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows, acc={sum(bool(r.get('correct')) for r in rows) / max(1, len(rows)):.3f}")

    def par(fn, xs):
        with ThreadPoolExecutor(WORKERS) as ex:
            return list(ex.map(fn, xs))

    def want(name):
        return only is None or name in only

    if want("R"):
        save("R", [dict(id=i["id"], **r) for i, r in zip(mc, par(run_R, mc))])
    if want("K"):
        rules = sorted({i["rule"] for i in mc})
        save("K", [dict(rule=r, **k) for r, k in zip(rules, par(run_K_rule, rules))])
    if want("P"):
        save("P", [dict(id=i["id"], **r) for i, r in zip(mc, par(run_P, mc))])
    if want("T"):
        save("T", [dict(id=i["id"], **r) for i, r in zip(mc, par(run_T, mc))])
    c0 = {}
    for ctx in ("C0", "C1", "C2", "C3"):
        if ctx == "C0":
            xs = s1
        elif ctx == "C1":
            xs = conflict
        else:
            xs = mc
        if want(ctx) or (ctx == "C0" and want("MDR")):
            rows = [dict(id=i["id"], **r) for i, r in zip(xs, par(lambda it: run_context(it, ctx), xs))]
            if ctx == "C0":
                c0 = {r["id"]: r["pred"] for r in rows}
            if want(ctx):
                save(ctx, rows)
    if want("CoT"):
        save("CoT", [dict(id=i["id"], **r) for i, r in zip(s1, par(run_cot, s1))])
    if want("GKP"):
        save("GKP", [dict(id=i["id"], **r) for i, r in zip(s1, par(run_gkp, s1))])
    if want("FixedGame"):
        save("FixedGame", [dict(id=i["id"], **r) for i, r in zip(s1, par(run_fixed, s1))])
    if any(want(n) for n in ("MDR", "MDR_C3", "A1", "A2", "A3")):
        card = build_card()["departures"]
    if want("MDR"):
        save("MDR", [dict(id=i["id"], **r) for i, r in
                     zip(s1, par(lambda it: mdr(it, card, direct_pred=c0.get(it["id"])), s1))])
    if want("MDR_C3"):
        save("MDR_C3", [dict(id=i["id"], **r) for i, r in
                        zip(mc, par(lambda it: mdr(it, card, CONTEXT["C3"].format(mod=it["mod"]), "C3"), mc))])
    if want("A1"):
        save("A1", [dict(id=i["id"], **r) for i, r in zip(s1, par(lambda it: mdr(it, card, gate=False,
                                                                             direct_pred=c0.get(it["id"])), s1))])
    if want("A2"):
        save("A2", [dict(id=i["id"], **r) for i, r in zip(s1, par(lambda it: mdr(it, card, default_stage=False,
                                                                             direct_pred=c0.get(it["id"])), s1))])
    if want("A3"):
        save("A3", [dict(id=i["id"], **r) for i, r in zip(s1, par(lambda it: run_A3(it, card), s1))])
    print("spend:", llm.spend_report())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["items", "run"])
    ap.add_argument("--only", default=None, help="comma-separated condition names")
    ap.add_argument("--split", default=None, choices=["dev", "test"], help="run only dev or test items")
    a = ap.parse_args()
    if a.cmd == "items":
        build_items()
    else:
        run_all(set(a.only.split(",")) if a.only else None, a.split)
