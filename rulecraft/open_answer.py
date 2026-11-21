"""Open answers on the hard set's passive conflict rules: the same image, action and question, without the options.
The closing line names the thing asked about (a first version did not, and answers drifted to other objects in the
scene; its DeepSeek answers are kept as v1_Open*.jsonl).

Tests whether the bare-image gap is made by the multiple-choice format (or by the wording of the real-world option).
The model answers in one or two sentences, on the bare image (OpenC0) and when told the game (OpenC2); a judge model
that sees neither the condition nor the answer key then says which of the item's three outcomes the answer matches.

  LLM_PROFILE=<answerer> python open_answer.py run            answers -> results/r2/t6_open_<answerer>/rep0/Open*.jsonl
  [LLM_PROFILE=<judge>] python open_answer.py judge --model <answerer>      -> .../judge_<judge>_Open*.jsonl
One run per model, temperature 1.0, seed 1, as the first run of the other conditions. The judge runs at temperature 0.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot
from analyze import cluster_ci
from analyze2 import shift_ci
from rules import RULE_BY_ID

OUT = llm.RESULTS / "r2"
ARMS = {"OpenC0": "C0", "OpenC2": "C2"}
TAIL = "Describe what happens to {subject} in one or two sentences."
SUBJECT = re.compile(r"^The (.+?) (?:is|are|looks?|look|stays?|keeps?|still|has|have) ")
MODELS = {"deepseek": "DeepSeek-V4.1-Flash", "solrun": "GPT-6.1-Sol", "qwenflash": "Qwen3.8-Flash"}
MCQ = {"deepseek": lambda arm, k: OUT / f"t6_rep{k}" / f"{arm}.jsonl",
       "solrun": lambda arm, k: OUT / f"t6_nothink_solrun/rep{k}" / f"{arm}.jsonl",
       "qwenflash": lambda arm, k: OUT / f"t6_nothink_qwenflash/rep{k}" / f"{arm}.jsonl"}
JUDGE = ("A scene changes as described below, and there are three candidate outcomes. Someone looked at the scene and "
         "wrote a prediction. Decide which candidate outcome the prediction matches.\n\n"
         "What happens to the scene: {action}\nCandidate outcomes:\n{options}\n\nPrediction: \"{answer}\"\n\n"
         "Reply with one letter only. A, B or C: the prediction matches that outcome; if it mentions several outcomes "
         "but settles on one, choose the one it settles on. D: it leaves two or more of the outcomes open, for "
         "example by saying that the result depends on whether the scene is real or a game. E: it matches none of "
         "the outcomes.")


def items():
    return [i for i in pilot.load_items() if i.get("split") == "test6" and i["set"] == "mc" and i["kind"] == "conflict"
            and RULE_BY_ID[i["rule"]]["act"] == "passive"]


def subject(it):
    """The thing the question is about, read off the game option ("The moss is still green ..." -> "the moss").
    The options name it in the multiple-choice form; without them the action alone often leaves it open."""
    game = next(o[1] for o in it["options"] if o[2] == "vanilla")
    return "the " + SUBJECT.match(game).group(1)


def folder(model):
    return OUT / f"t6_open_{model}" / "rep0"


def load(path):
    if not path.exists():
        return {}
    return {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def guarded(fn):
    def wrapped(it):
        try:
            return fn(it)
        except llm.BudgetExceeded:
            raise
        except (RuntimeError, OSError) as e:        # recorded as missing; asked again on the next run
            return {"id": it["id"], "error": str(e)[:300]}
    return wrapped


def run(limit=None):
    xs = items()[:limit] if limit else items()
    llm.set_sampling(temperature=1.0, seed=1)
    for arm, ctx in ARMS.items():
        def one(it, a=arm, c=ctx):
            llm.LABEL.item = f"{it['id']}#{a}#0"
            prompt = f"{pilot.CONTEXT[c]}Look at the image.\nAction: {it['action']}\n{it['question']}\n{TAIL.format(subject=subject(it))}"
            assert "{" not in prompt and subject(it) in prompt
            r = llm.chat([llm.user(prompt, [it["image"]])], max_tokens=200, tag=a)
            return {"id": it["id"], "raw": r["text"].strip()}
        with ThreadPoolExecutor(pilot.WORKERS) as ex:
            rows = list(ex.map(guarded(one), xs))
        if not limit:
            save(folder(llm.PROFILE) / f"{arm}.jsonl", rows)
        print(f"{llm.PROFILE} {arm}: {sum('raw' in r for r in rows)}/{len(rows)} answered; e.g. {rows[0].get('raw', rows[0])!r}", flush=True)


def judge(model):
    by_id = {i["id"]: i for i in items()}
    llm.set_sampling(temperature=0.0, seed=0)
    for arm in ARMS:
        answers = [r for r in load(folder(model) / f"{arm}.jsonl").values() if r.get("raw")]

        def one(r, a=arm):
            it = by_id[r["id"]]
            llm.LABEL.item = f"{it['id']}#judge{a}#{model}"
            prompt = JUDGE.format(action=it["action"], options=pilot.options_text(it), answer=r["raw"].replace('"', "'"))
            out = llm.chat([llm.user(prompt)], max_tokens=5, tag="OpenJudge")
            letter = llm.parse_letter(out["text"], "ABCDE")
            kind = {o[0]: o[2] for o in it["options"]}.get(letter) or {"D": "open", "E": "none"}.get(letter)
            return {"id": it["id"], "letter": letter, "kind": kind}      # kind: vanilla, real, third, open, none
        with ThreadPoolExecutor(pilot.WORKERS) as ex:
            rows = list(ex.map(guarded(lambda r: one(r)), answers))
        save(folder(model) / f"judge_{llm.PROFILE}_{arm}.jsonl", rows)
        print(f"judge {llm.PROFILE} on {model} {arm}: {dict(Counter(r.get('kind') for r in rows))}", flush=True)


def mcq(model, arm):
    per = defaultdict(list)
    for k in range(3):
        for r in load(MCQ[model](arm, k)).values():
            if not r.get("error"):
                per[r["id"]].append(float(bool(r["correct"])))
    return {i: sum(v) / len(v) for i, v in per.items()}




if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "judge"])
    ap.add_argument("--model", help="judge: the profile whose answers are judged")
    ap.add_argument("--limit", type=int, help="run: ask only the first N items and save nothing")
    a = ap.parse_args()
    if a.cmd == "run":
        if not llm.PROFILE_CFG:
            llm.set_guard(floor_cny=1.0, wait_off_peak=True)
        run(a.limit)
        print("spend:", llm.profile_spend() if llm.PROFILE_CFG else llm.spend_report(), flush=True)
    elif a.cmd == "judge":
        if not llm.PROFILE_CFG:
            llm.set_guard(floor_cny=1.0, wait_off_peak=True)
        judge(a.model)
