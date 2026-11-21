"""Build and audit a model's own departure card with the frozen card prompts (lists and merge without reasoning, the audit
with reasoning on, as for DeepSeek). No test item is shown at any step; no human edits the card.

Usage: LLM_PROFILE=qwenflash WORKERS=6 python card_model.py
Writes results/card_<profile>.json and results/card_<profile>_audited.json.
"""
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot
import own_card as s
from tune2 import AUDIT_PROMPT


def audit(card):
    _, path = s.card_paths()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["departures"]

    def check(d):
        exc = f" (except {', '.join(d.get('except', []))})" if d.get("except") else ""
        prompt = AUDIT_PROMPT.format(objects=", ".join(d.get("objects", [])), exc=exc, trigger=d.get("trigger", ""),
                                     minecraft=d.get("minecraft", ""))
        for attempt in range(3):
            try:
                r = llm.chat([llm.user(prompt)], max_tokens=s.CARD_TOKENS, thinking=True, tag="audit", seed=attempt)
            except (RuntimeError, OSError):
                continue
            v = llm.parse_json(r["text"])
            if v:
                return v
        return {"verdict": "unparsed", "reason": "", "corrected": ""}

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
    print(f"card audited: kept {len(kept)}/{len(card)}, verdicts {dict(counts)}; spend {llm.profile_spend()}", flush=True)
    return kept


_chat = llm.chat


def _chat_merge_greedy(messages, **kw):
    """As for DeepSeek's card: lists sampled at temperature 0.7, merges at temperature 0."""
    if str(kw.get("tag", "")).startswith("cardmerge"):
        kw["temperature"] = 0.0
    return _chat(messages, **kw)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    llm.chat = _chat_merge_greedy
    llm.set_sampling(temperature=0.7, seed=0)        # the list prompts sample like DeepSeek's (temperature 0.7)
    card = s.build_card()
    print(f"raw card: {len(card)} entries", flush=True)
    kept = audit(card)
    print(Counter("".join(ch for ch in d["id"] if ch.isalpha()) for d in kept), flush=True)


if __name__ == "__main__":
    main()
