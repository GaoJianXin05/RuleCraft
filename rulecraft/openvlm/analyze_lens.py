"""Stage 2 summary from out/<name>/lens.npz (Minecraft conflict rules, main + hard sets; PhysBench as the real-photo control).

Per layer:
  game - real   mean log-prob margin of the game option over the real-world option, for Image / Told / Text,
                on the items the model gets right when told and wrong from the image alone ("flip" items);
  Minecraft     median rank of the "Minecraft" token, flip items under Image vs Told vs PhysBench photos,
                and the share of prompts where it sits in the top 100.

Usage (in rulecraft/): python openvlm/analyze_lens.py openvlm/out/qwen35_9b
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import item_sets as S  # noqa: E402


def main(d):
    d = Path(d)
    z = np.load(d / "lens.npz")
    index = [tuple(x) for x in z["index"]]
    pos = {k: n for n, k in enumerate(index)}
    ans = {(r["group"], r["id"], r["arm"]): r for r in map(json.loads, open(d / "answers.jsonl", encoding="utf-8"))}
    conf = S.groups("main")["conflict, all"] + S.groups("hard")["conflict, all"]
    flip = [it for it in conf if ans[("mc", it["id"], "Told")]["correct"] and not ans[("mc", it["id"], "Image")]["correct"]]
    phys = [n for k, n in pos.items() if k[0] == "physbench"]
    L = z["mc_rank"].shape[1]
    print(f"{d.name}: {len(flip)} flip items on {len({i['rule'] for i in flip})} rules; {len(phys)} PhysBench photos; {L} layers")

    def margin(arm):
        m = []
        for it in flip:
            keys = {o[2]: "ABCD".index(o[0]) for o in it["options"]}
            m.append(z["lp_letters"][pos[("mc", it["id"], arm)]][:, keys["vanilla"]] -
                     z["lp_letters"][pos[("mc", it["id"], arm)]][:, keys["real"]])
        return np.array(m)                                                    # [items, L]

    def ranks(arm):
        return z["mc_rank"][[pos[("mc", it["id"], arm)] for it in flip]]

    M = {a: margin(a) for a in ("Image", "Told", "Text")}
    R = {a: ranks(a) for a in ("Image", "Told", "Text")}
    R["Photo"] = z["mc_rank"][phys]
    print(f"{'layer':>5} | game-real  Image   Told   Text | Minecraft median rank  Image   Told   Photo | top100 Image Photo")
    for l in range(L):
        print(f"{l:5d} | {'':9s}{M['Image'][:, l].mean():6.2f} {M['Told'][:, l].mean():6.2f} {M['Text'][:, l].mean():6.2f} | "
              f"{'':21s}{np.median(R['Image'][:, l]):6.0f} {np.median(R['Told'][:, l]):6.0f} {np.median(R['Photo'][:, l]):7.0f} | "
              f"{'':6s}{(R['Image'][:, l] < 100).mean():5.2f} {(R['Photo'][:, l] < 100).mean():5.2f}")
    best = int(np.argmin(np.median(R["Image"], 0)))
    print(f"best layer for Minecraft under Image: {best}, median rank {np.median(R['Image'][:, best]):.0f} "
          f"vs photos {np.median(R['Photo'][:, best]):.0f}")
    gap = M["Told"] - M["Image"]
    first = next((l for l in range(L) if gap[:, l].mean() > 0.5), None)
    print(f"first layer where Told - Image margin exceeds 0.5 nats: {first}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for p in sys.argv[1:]:
        main(p)
