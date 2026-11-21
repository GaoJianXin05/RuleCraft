"""A model writes its own card of departures from real-world physics and audits it (used by card_model.py,
method_sol.py and note_use.py). Five independent lists per topic are merged into the entries that appear in at least
three; the audit asks the model to check each entry against the game and keeps or corrects it.
"""
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot
from gdc import FAMILIES, FAMILY_PROMPT, entries
from tune2 import AUDIT_PROMPT

RES = llm.RESULTS
OUT = RES / "r2"
CARD_TOKENS = 16000
LIST_EFFORT = None   # reasoning setting of the list calls


def choose_items():
    items = pilot.load_items()
    mc = [i for i in items if i["split"] in ("test2", "test3") and i["set"] == "mc" and i["id"].endswith(("_v0", "_v1"))]
    ext = []
    for name in ("glitch", "physbench"):
        pool = sorted((i for i in items if i["set"] == name and i["split"] == "test2"), key=lambda i: i["id"])
        ext += pool[::4][:20]
    return mc, ext


def card_paths(prefix=""):
    tag = "mock" if llm.MOCK else llm.PROFILE
    return RES / f"{prefix}card_{tag}.json", RES / f"{prefix}card_{tag}_audited.json"


def build_card(prefix=""):
    raw_path, _ = card_paths(prefix)
    if raw_path.exists():
        return json.loads(raw_path.read_text(encoding="utf-8"))["departures"]
    card, raw = [], {}

    def sample(args):
        fam, s = args
        r = llm.chat([llm.user(FAMILY_PROMPT.format(desc=FAMILIES[fam]))], max_tokens=CARD_TOKENS, json_mode=True,
                     tag=f"card_{fam}", seed=s, effort=LIST_EFFORT)
        return entries(llm.parse_json(r["text"]))

    for fam, desc in FAMILIES.items():
        with ThreadPoolExecutor(5) as ex:
            samples = list(ex.map(sample, [(fam, s) for s in range(5)]))
        merge = ("Here are 5 lists of differences between vanilla Minecraft and real-world physics about " + desc +
                 ", produced independently. Merge entries that describe the same difference. Keep only differences that "
                 "appear in at least 3 of the 5 lists. Return JSON: {\"departures\": [...]} using the same entry format.\n"
                 + json.dumps(samples, ensure_ascii=False))
        merged = entries(llm.parse_json(llm.chat([llm.user(merge)], max_tokens=CARD_TOKENS, json_mode=True,
                                                 tag=f"cardmerge_{fam}", seed=0, effort=LIST_EFFORT)["text"]))
        for k, d in enumerate(merged):
            d["id"] = f"{fam}{k + 1}"
            card.append(d)
        raw[fam] = samples
        print(f"{fam}: samples {[len(s) for s in samples]}, merged {len(merged)}; {llm.profile_spend()}", flush=True)
    if not card:
        raise RuntimeError("the card came back empty")
    raw_path.write_text(json.dumps({"departures": card, "samples": raw}, indent=1, ensure_ascii=False), encoding="utf-8")
    return card


def audit_card(card, prefix=""):
    _, path = card_paths(prefix)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["departures"]

    def check(d):
        exc = f" (except {', '.join(d.get('except', []))})" if d.get("except") else ""
        prompt = AUDIT_PROMPT.format(objects=", ".join(d.get("objects", [])), exc=exc, trigger=d.get("trigger", ""),
                                     minecraft=d.get("minecraft", ""))
        r = llm.chat([llm.user(prompt)], max_tokens=CARD_TOKENS, json_mode=True, tag="audit", seed=0)
        return llm.parse_json(r["text"]) or {"verdict": "unparsed", "reason": "", "corrected": ""}

    with ThreadPoolExecutor(pilot.WORKERS) as ex:
        verdicts = list(ex.map(check, card))
    kept, counts = [], Counter()
    for d, v in zip(card, verdicts):
        verdict = str(v.get("verdict", "unparsed")).lower()
        counts[verdict] += 1
        if verdict in ("accurate", "unparsed"):
            kept.append(d)
        elif str(v.get("corrected") or "").strip():
            kept.append(dict(d, minecraft=v["corrected"].strip()))
    log = [dict(id=d["id"], claim=d.get("minecraft"), **v) for d, v in zip(card, verdicts)]
    path.write_text(json.dumps({"departures": kept, "audit": log}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"card audited: kept {len(kept)}/{len(card)}, verdicts {dict(counts)}; {llm.profile_spend()}", flush=True)
    return kept
