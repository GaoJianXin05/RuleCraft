"""Two probes of how the bare-image question is read. Designs fixed before any run.

Meta    The bare image, the action, the question and its three options, exactly as in the image condition (C0), but the
        model is asked which world the question is about instead of answering it:
            G. what happens in the video game that the image comes from
            R. what would happen to such a scene in the real world
        The order of G and R alternates with the item (even index: G first), so neither reading is always first.
        Answer key: none; the reply is the reading. It is paired per item with the model's saved C0 answers.
Deploy  The image condition (C0) word for word, after a system message that sets a deployment context without naming a
        game or ruling out real-world physics:
            "You are the assistant of a tool that analyses gameplay recordings. Users send a frame from a gameplay
             video and ask what happens next in the scene."
        Answer key: the game outcome, as in every condition.

Items: the 1,240 Minecraft test items (main set test2-test5, hard set test6), or the 80 development items (dev6) with
--dev for a format check. Thinking off, temperature 1.0, seed 1, one run, as for the first run of C0 and C2.
Writes results/r2/interp_<profile>/rep0/<arm>.jsonl (dev: results/r2/probe_interp/<profile>/); finished calls come
from the cache.

Usage: LLM_PROFILE=qwenflash WORKERS=8 SPEND_CAP_CNY=... python interp_run.py --arms Meta,Deploy
       LLM_PROFILE=solrun python interp_run.py --arms Meta,Deploy --dev
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import llm
import pilot

OUT = llm.RESULTS / "r2"
G = "G. what happens in the video game that the image comes from"
R = "R. what would happen to such a scene in the real world"
DEPLOY = ("You are the assistant of a tool that analyses gameplay recordings. Users send a frame from a gameplay video "
          "and ask what happens next in the scene.")


def meta_tail(index):
    first, second = (G, R) if index % 2 == 0 else (R, G)
    return ("Do not answer the question. Instead, say which world the question is about:\n"
            f"{first}\n{second}\nReply with a single letter, G or R.")


def parse_gr(text):
    m = re.search(r"\b([GR])\b", text.strip().upper()[:40])
    return m.group(1) if m else None


def meta(it, index):
    prompt = f"Look at the image.\n{pilot.question_block(it)}\n{meta_tail(index)}"
    r = llm.chat([llm.user(prompt, [it["image"]])], max_tokens=20, tag="Meta")
    return {"pred": parse_gr(r["text"]), "raw": r["text"][:80], "g_first": index % 2 == 0}


def deploy(it, index):
    pred, raw = pilot.ask(it, system=DEPLOY, tag="Deploy")
    return {"pred": pred, "raw": raw[:80], "correct": pred == it["answer"]["C0"]}


ARMS = {"Meta": meta, "Deploy": deploy}


def one(fn, it, index, arm):
    llm.LABEL.item = f"{it['id']}#{arm}#0"
    try:
        return dict(id=it["id"], kind=it["kind"], split=it["split"], **fn(it, index))
    except llm.BudgetExceeded:
        raise
    except (RuntimeError, OSError) as e:       # a rejected request is recorded as missing and re-asked on the next run
        return {"id": it["id"], "kind": it["kind"], "split": it["split"], "pred": None, "error": str(e)[:300]}


def main(arms, dev):
    sys.stdout.reconfigure(encoding="utf-8")
    splits = {"dev6"} if dev else {"test2", "test3", "test4", "test5", "test6"}
    items = sorted((i for i in pilot.load_items() if i["set"] == "mc" and i["split"] in splits), key=lambda i: i["id"])
    llm.set_sampling(temperature=1.0, seed=1)
    out = (OUT / "probe_interp" / llm.PROFILE) if dev else (OUT / f"interp_{llm.PROFILE}" / "rep0")
    out.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        with ThreadPoolExecutor(pilot.WORKERS) as ex:
            rows = list(ex.map(lambda p: one(ARMS[arm], p[1], p[0], arm), enumerate(items)))
        (out / f"{arm}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        good = [r for r in rows if r.get("pred")]
        msg = f"{llm.PROFILE} {arm}: {len(good)}/{len(rows)} parsed"
        if arm == "Meta":
            msg += f", G {sum(r['pred'] == 'G' for r in good) / max(1, len(good)):.3f}"
        else:
            conf = [r for r in good if r["kind"] == "conflict"]
            msg += f", conflict acc {sum(r['correct'] for r in conf) / max(1, len(conf)):.3f} ({len(conf)})"
        print(msg, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="Meta,Deploy")
    ap.add_argument("--dev", action="store_true", help="format check on the 80 development items")
    a = ap.parse_args()
    if not llm.PROFILE_CFG:
        llm.set_guard(floor_cny=1.0, wait_off_peak=False)
    main([x for x in a.arms.split(",") if x], a.dev)
    print("spend:", llm.profile_spend() if llm.PROFILE_CFG else llm.spend_report(), flush=True)
