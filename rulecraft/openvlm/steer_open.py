"""Stage 3: steering and activation patching on the Minecraft prompts (open-weight models, thinking off).

The steering direction at hidden-state index l is the mean of (Told - Image) answer-position hidden states over the
dev6 items only (saved by run_open.py in hs.npy). Hidden-state index l is the output of decoder layer l-1.

  sweep  : dev6 Image prompts, add alpha * v_l at layer l (answer position only, or every position); grid over l, alpha.
  test   : test Image prompts (test2-test6) with the chosen (l, alpha, pos); also a random direction of the same norm,
           and Told prompts with the direction subtracted.
  patch  : test conflict items that are right under Told and wrong under Image; for every layer, the Image run's
           answer-position state is replaced by the saved Told state; records the option-letter log-probs.

Usage (server): python steer_open.py --model ~/models/Qwen3.5-9B --name qwen35_9b sweep
                python steer_open.py --model ... --name ... test --layer 22 --alpha 2 --pos last
                python steer_open.py --model ... --name ... patch
Output: out/<name>/steer_<mode>.jsonl
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from run_open import BUNDLE, inputs_for, letter_ids, load

HERE = Path(__file__).parent
TEST = {"test2", "test3", "test4", "test5", "test6"}


def find_layers(model):
    for n, m in model.named_modules():
        if n.endswith("language_model.layers") or n.endswith("language_model.model.layers"):
            return m
    raise RuntimeError("decoder layers not found")


class Hook:
    """Adds `add` (or writes `put`) at the answer position (or every position) of one decoder layer's output."""

    def __init__(self, layers):
        self.layers, self.h, self.add, self.put, self.all = layers, None, None, None, False

    def set(self, l=None, add=None, put=None, every=False):
        if self.h:
            self.h.remove()
            self.h = None
        self.add, self.put, self.all = add, put, every
        if l is not None:
            self.h = self.layers[l - 1].register_forward_hook(self.fn)

    def fn(self, mod, inp, out):
        x = out[0] if isinstance(out, tuple) else out
        if self.put is not None:
            x[:, -1] = self.put.to(x.dtype)
        elif self.all:
            x += self.add.to(x.dtype)
        else:
            x[:, -1] += self.add.to(x.dtype)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("mode", choices=["sweep", "test", "patch"])
    ap.add_argument("--layer", type=int)
    ap.add_argument("--alpha", type=float)
    ap.add_argument("--pos", choices=["last", "all"], default="last")
    a = ap.parse_args()

    out = HERE / "out" / a.name
    rows = [json.loads(l) for l in open(BUNDLE / "prompts.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["group"] == "mc" and r["mode"] == "letter"]
    index = {tuple(k): n for n, k in enumerate(json.loads((out / "hs_index.json").read_text(encoding="utf-8")))}
    hs = np.load(out / "hs.npy", mmap_mode="r")
    L = hs.shape[1]
    dev = [r for r in rows if r["split"] == "dev6"]
    ids = sorted({r["id"] for r in dev})
    v = np.mean([hs[index[("mc", i, "Told")]].astype(np.float32) - hs[index[("mc", i, "Image")]].astype(np.float32)
                 for i in ids], 0)                                                    # [L, dim]
    proc, model = load(a.model)
    tok = proc.tokenizer
    LID = letter_ids(tok)
    hook = Hook(find_layers(model))
    devc = model.device
    V = torch.tensor(v, device=devc)

    def ask(r):
        with torch.inference_mode():
            o = model(**inputs_for(proc, r, devc))
        lp = torch.log_softmax(o.logits[0, -1].float(), -1)
        lp = {l: float(lp[LID[l]]) for l in r["letters"]}
        pred = max(lp, key=lp.get)
        return dict(id=r["id"], arm=r["arm"], split=r["split"], kind=r["kind"], rule=r["rule"], pred=pred,
                    correct=pred == r["answer"], logp=lp)

    f = open(out / f"steer_{a.mode}.jsonl", "a", encoding="utf-8")

    def emit(rec):
        f.write(json.dumps(rec) + "\n")
        f.flush()

    if a.mode == "sweep":
        img = [r for r in dev if r["arm"] == "Image"]
        for r in img:
            emit(dict(ask(r), layer=0, alpha=0.0, pos="none"))
        for l in range(L // 4, L - 1, 2):
            for alpha in (1.0, 2.0, 3.0):
                for pos in ("last", "all"):
                    hook.set(l, add=alpha * V[l], every=pos == "all")
                    for r in img:
                        emit(dict(ask(r), layer=l, alpha=alpha, pos=pos))
            print("layer", l, "done", flush=True)
    elif a.mode == "test":
        img = [r for r in rows if r["split"] in TEST and r["arm"] == "Image"]
        told = [r for r in rows if r["split"] in TEST and r["arm"] == "Told"]
        g = torch.Generator(device="cpu").manual_seed(0)
        rnd = torch.randn(V.shape[1], generator=g).to(devc)
        rnd = rnd / rnd.norm() * V[a.layer].norm()
        for tag, rs, add in (("steer", img, a.alpha * V[a.layer]), ("random", img, a.alpha * rnd),
                             ("minus", told, -a.alpha * V[a.layer])):
            hook.set(a.layer, add=add, every=a.pos == "all")
            for r in rs:
                emit(dict(ask(r), cond=tag, layer=a.layer, alpha=a.alpha, pos=a.pos))
            print(tag, "done", flush=True)
    else:
        ans = {(d["id"], d["arm"]): d for d in map(json.loads, open(out / "answers.jsonl", encoding="utf-8"))
               if d["group"] == "mc" and "correct" in d}
        img = [r for r in rows if r["split"] in TEST and r["arm"] == "Image" and r["kind"] == "conflict"
               and ans[(r["id"], "Told")]["correct"] and not ans[(r["id"], "Image")]["correct"]]
        print(len(img), "flip items", flush=True)
        for r in img:
            told = torch.tensor(hs[index[("mc", r["id"], "Told")]].astype(np.float32), device=devc)
            for l in range(1, L - 1):                          # the last saved state is already normed
                hook.set(l, put=told[l])
                emit(dict(ask(r), layer=l))
        hook.set()
    print("finished", a.mode, flush=True)


if __name__ == "__main__":
    main()
