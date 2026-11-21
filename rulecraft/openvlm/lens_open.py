"""Stage 2, logit lens on the saved hidden states (Minecraft and PhysBench rows only).

For every saved prompt and layer, the hidden state at the answer position goes through the model's final norm and
output head. Kept per layer: log-probabilities of the option letters A-D, and the rank and log-probability of the
"Minecraft" token (best over its spellings) in the full vocabulary.

Usage (server, GPU free): python lens_open.py --model ~/models/Qwen3.5-9B --name qwen35_9b
Output: out/<name>/lens.npz
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

HERE = Path(__file__).parent
KEEP = {"mc", "physbench"}


def find_norm(model):
    names = [n for n, _ in model.named_modules() if n.endswith("language_model.norm") or n.endswith("language_model.model.norm")]
    assert names, "final norm not found"
    return model.get_submodule(names[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    out = HERE / "out" / a.name
    proc = AutoProcessor.from_pretrained(a.model, trust_remote_code=True)
    tok = proc.tokenizer
    model = AutoModelForImageTextToText.from_pretrained(a.model, dtype=torch.bfloat16, device_map="cuda",
                                                        trust_remote_code=True).eval()
    norm, head = find_norm(model), model.get_output_embeddings()
    letters = [tok.encode(l, add_special_tokens=False)[0] for l in "ABCD"]
    mc_ids = sorted({t[0] for s in ("Minecraft", " Minecraft", "minecraft", " minecraft")
                     for t in [tok.encode(s, add_special_tokens=False)] if len(t) == 1})   # whole-word tokens only
    assert mc_ids, "no single-token spelling of Minecraft"
    print("Minecraft first tokens:", [(i, tok.decode([i])) for i in mc_ids], flush=True)

    index = json.loads((out / "hs_index.json").read_text(encoding="utf-8"))
    hs = np.load(out / "hs.npy", mmap_mode="r")
    saved = {}
    for d in map(json.loads, open(out / "answers.jsonl", encoding="utf-8")):
        if "row" in d:
            saved[d["row"]] = d["logp"]
    rows = [k for k, (g, _, _) in enumerate(index) if g in KEEP]
    L = hs.shape[1]
    lp_letters = np.zeros((len(rows), L, 4), np.float32)
    mc_rank = np.zeros((len(rows), L), np.int32)
    mc_logp = np.zeros((len(rows), L), np.float32)

    # is the last saved layer already normed? pick the reading that reproduces the saved answer log-probs
    k0 = rows[0]
    h_last = torch.tensor(hs[k0, -1], device="cuda", dtype=torch.bfloat16)
    want = np.array([saved[k0][l] for l in sorted(saved[k0])])
    with torch.inference_mode():
        def read(h):
            lp = torch.log_softmax(head(h).float(), -1)
            return np.array([float(lp[letters["ABCD".index(l)]]) for l in sorted(saved[k0])])
        err_raw, err_norm = np.abs(read(h_last) - want).max(), np.abs(read(norm(h_last)) - want).max()
    last_normed = err_raw < err_norm
    print(f"last layer check: raw err {err_raw:.3f}, normed err {err_norm:.3f} -> last layer already normed: {last_normed}", flush=True)

    with torch.inference_mode():
        for n, k in enumerate(rows):
            h = torch.tensor(hs[k], device="cuda", dtype=torch.bfloat16)          # [L, dim]
            z = norm(h)
            if last_normed:
                z[-1] = h[-1]
            lp = torch.log_softmax(head(z).float(), -1)                           # [L, vocab]
            lp_letters[n] = lp[:, letters].cpu().numpy()
            mc = lp[:, mc_ids].max(-1).values
            mc_logp[n] = mc.cpu().numpy()
            mc_rank[n] = (lp > mc[:, None]).sum(-1).cpu().numpy()
            if (n + 1) % 1000 == 0:
                print(f"{n + 1}/{len(rows)}", flush=True)
    np.savez_compressed(out / "lens.npz", rows=np.array(rows), lp_letters=lp_letters, mc_rank=mc_rank, mc_logp=mc_logp,
                        index=np.array([index[k] for k in rows]))
    print("saved", out / "lens.npz", flush=True)


if __name__ == "__main__":
    main()
