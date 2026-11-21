"""Open-weight models on the RuleCraft prompts (bundle/prompts.jsonl, built by build_prompts.py), thinking off.

Letter prompts: one forward pass; the answer is the most probable option letter at the first answer position, and the
hidden state of that position is kept for every layer (hs.npy, float16, [prompt, layer, dim]; row order in hs_index.json).
R prompts: greedy generation of up to 20 tokens.

Usage (server): python run_open.py --model ~/models/Qwen3.5-9B --name qwen35_9b [--limit 20]
Output: out/<name>/answers.jsonl (resumable), out/<name>/hs.npy, out/<name>/hs_index.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

HERE = Path(__file__).parent
BUNDLE = HERE / "bundle"


def load(model_path):
    proc = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(model_path, torch_dtype=torch.bfloat16, device_map="cuda",
                                                        trust_remote_code=True).eval()
    return proc, model


def inputs_for(proc, row, device):
    content = []
    if row["image"]:
        content.append({"type": "image", "image": Image.open(BUNDLE / row["image"]).convert("RGB")})
    content.append({"type": "text", "text": row["text"]})
    msgs = [{"role": "user", "content": content}]
    return proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True, return_dict=True,
                                    return_tensors="pt", enable_thinking=False).to(device)


def letter_ids(tok, letters="ABCD"):
    ids = {}
    for l in letters:
        t = tok.encode(l, add_special_tokens=False)
        assert len(t) == 1, (l, t)
        ids[l] = t[0]
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--groups", nargs="+")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(BUNDLE / "prompts.jsonl", encoding="utf-8")]
    if a.groups:
        rows = [r for r in rows if r["group"] in a.groups]
    if a.limit:
        rows = rows[:a.limit]
    out = HERE / "out" / a.name
    out.mkdir(parents=True, exist_ok=True)
    proc, model = load(a.model)
    tok = proc.tokenizer
    LID = letter_ids(tok)
    dev = model.device

    letter_rows = [i for i, r in enumerate(rows) if r["mode"] == "letter"]
    pos = {i: k for k, i in enumerate(letter_rows)}
    n_layers = model.config.get_text_config().num_hidden_layers + 1
    dim = model.config.get_text_config().hidden_size
    hs_path = out / "hs.npy"
    hs = (np.lib.format.open_memmap(hs_path, mode="r+") if hs_path.exists() else
          np.lib.format.open_memmap(hs_path, mode="w+", dtype=np.float16, shape=(len(letter_rows), n_layers, dim)))
    assert hs.shape == (len(letter_rows), n_layers, dim), hs.shape
    (out / "hs_index.json").write_text(json.dumps([[rows[i]["group"], rows[i]["id"], rows[i]["arm"]]
                                                   for i in letter_rows]), encoding="utf-8")

    ans_path = out / "answers.jsonl"
    done = set()
    if ans_path.exists():
        done = {(d["group"], d["id"], d["arm"]) for d in map(json.loads, open(ans_path, encoding="utf-8"))}
    t0, n = time.time(), 0
    with open(ans_path, "a", encoding="utf-8") as f, torch.inference_mode():
        for i, r in enumerate(rows):
            key = (r["group"], r["id"], r["arm"])
            if key in done:
                continue
            x = inputs_for(proc, r, dev)
            rec = dict(group=r["group"], id=r["id"], arm=r["arm"], split=r["split"], rule=r["rule"], kind=r["kind"],
                       n_tokens=int(x["input_ids"].shape[1]))
            if r["mode"] == "letter":
                o = model(**x, output_hidden_states=True)
                logp = torch.log_softmax(o.logits[0, -1].float(), -1)
                lp = {l: float(logp[LID[l]]) for l in r["letters"]}
                pred = max(lp, key=lp.get)
                hs[pos[i]] = torch.stack([h[0, -1] for h in o.hidden_states]).float().cpu().numpy().astype(np.float16)
                rec.update(pred=pred, answer=r["answer"], correct=pred == r["answer"], logp=lp,
                           letter_mass=float(sum(np.exp(v) for v in lp.values())), row=pos[i])
            else:
                g = model.generate(**x, max_new_tokens=20, do_sample=False)
                rec.update(reply=tok.decode(g[0, x["input_ids"].shape[1]:], skip_special_tokens=True).strip())
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
            if n % 200 == 0:
                f.flush()
                hs.flush()
                print(f"{n} done, {(time.time() - t0) / n:.2f}s each", flush=True)
    hs.flush()
    print(f"finished {n} new prompts in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
