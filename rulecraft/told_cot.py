"""Told + chain of thought: the told wording of C2 with the chain-of-thought tail, on every item.

This is the second call of GateTold whenever the gate named Minecraft, so those rows are reused as they are. An item
whose gate did not name Minecraft took GateOnly's row there; it is asked here with the same request, sampling and
labels as GateTold. Writes ToldCoT.jsonl next to every GateTold.jsonl of the current model.

Usage (Git Bash, from rulecraft/):
  python told_cot.py                                            # DeepSeek: reuse only
  LLM_PROFILE=solrun python told_cot.py                         # GPT-6.1-Sol: reuse only
  LLM_PROFILE=qwenflash WORKERS=8 SPEND_CAP_CNY=<cap> python told_cot.py
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import gdc
import llm
import pilot
from gate_told import OUT, load, save
from pilot import CONTEXT, COT_TAIL, ask


def files():
    if llm.PROFILE_CFG:
        return sorted(OUT.glob(f"*nothink_{llm.PROFILE}/rep*/GateTold.jsonl"))
    return sorted(OUT.glob("*final_rep*/GateTold.jsonl"))


def run():
    items = {i["id"]: i for i in pilot.load_items()}
    for f in files():
        rep = int(f.parent.name[-1])
        src, out_f = load(f), f.with_name("ToldCoT.jsonl")
        rows = load(out_f)
        todo = []
        for i, r in src.items():
            if not r.get("copied") and not r.get("error"):
                assert r["path"] == "told", (f, i)
                rows[i] = dict(r, reused="GateTold")
            elif i not in rows or rows[i].get("error"):
                todo.append(items[i])
        asked = len(todo)
        for attempt in range(4):
            if not todo:
                break
            seed = rep + 1 + (0 if attempt == 0 else 2000 + 100 * attempt)
            llm.set_sampling(temperature=1.0 if llm.PROFILE_CFG else gdc.TEMPERATURE, seed=seed)

            def one(it, a=attempt, s=seed):
                llm.LABEL.item = f"{it['id']}#ToldCoT#{rep}#{a}"
                try:
                    pred, text = ask(it, CONTEXT["C2"], tail=COT_TAIL, max_tokens=700, tag="ToldCoT")
                except llm.BudgetExceeded:
                    raise
                except (RuntimeError, OSError) as e:
                    return dict(id=it["id"], pred=None, correct=False, error=str(e)[:300])
                return dict(id=it["id"], pred=pred, correct=pred == it["answer"]["C0"], path="told", seed=s, text=text)

            with ThreadPoolExecutor(pilot.WORKERS) as ex:
                got = list(ex.map(one, todo))
            for r in got:
                rows[r["id"]] = r
            todo = [it for it, r in zip(todo, got) if r.get("error")]
        rows = {i: rows[i] for i in src if i in rows}
        save(out_f, rows)
        ok = [r for r in rows.values() if not r.get("error")]
        print(f"{llm.PROFILE} {f.parent.parent.name}/{f.parent.name}: {asked} asked, {len(ok)}/{len(src)} rows, "
              f"acc={sum(bool(r['correct']) for r in ok) / max(1, len(ok)):.3f}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run()
