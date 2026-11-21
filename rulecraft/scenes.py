"""Build scene specs (pre-state images and judge after-frames) for every rule variant."""
import json
import math
import random
from pathlib import Path

from rules import RULES, pretty
from scenes_round2 import CAM2, scene_blocks2

ROOT = Path(__file__).parent
DATA = ROOT / "data"
N_VARIANTS = {"test": 8, "dev": 4, "test2": 8, "test3": 8, "test4": 8, "test5": 8, "dev6": 8, "test6": 8}
JUDGE_RULES = ["G1", "T1", "G2", "A1", "L1",                       # tuning rules (round 1)
               "N3", "N4", "N5", "N6", "N7", "N8", "N10", "N11", "N16", "N17", "N2"]
# a two-block reference pillar beside unsupported blocks, so "floating" is not mistaken for "farther away"
REF_PILLAR = [{"x": -2, "y": 4, "z": 0, "name": "stone_bricks", "props": {}},
              {"x": -2, "y": 5, "z": 0, "name": "stone_bricks", "props": {}}]
JUDGE_VARIANTS = 4

# camera: (yaw offset in degrees around the target, distance, eye height above ground top)
CAMERAS = [(0, 3.8, 0.6), (-35, 4.2, 0.9), (35, 3.8, 0.4), (55, 4.5, 1.2)]
# per-scene tweaks: distance multiplier and the largest yaw offset allowed (small objects need frontal views)
SCENE_CAM = {"tree": (1.7, 60), "torch_wall": (0.85, 30), "torch_on_block": (0.9, 35), "flower_on_block": (0.9, 60),
             "ice_desert": (1.0, 60), "cactus": (1.0, 60)}


def b(x, y, z, name, **props):
    return {"x": x, "y": y, "z": z, "name": name, "props": props}


def tree_blocks(kind, with_bottom=True, fallen=False):
    log, leaves = f"{kind}_log", f"{kind}_leaves"
    out = []
    if fallen:
        for x in range(1, 5):
            out.append(b(x, 4, 0, log, axis="x"))
        for x in range(5, 7):
            for z in (-1, 0, 1):
                out.append(b(x, 4, z, leaves, persistent="true"))
                if z == 0:
                    out.append(b(x, 5, z, leaves, persistent="true"))
        return out
    for y in range(4 if with_bottom else 5, 8):
        out.append(b(0, y, 0, log, axis="y"))
    for y in (7, 8):
        for x in (-1, 0, 1):
            for z in (-1, 0, 1):
                if (x, z) != (0, 0) or y == 8:
                    out.append(b(x, y, z, leaves, persistent="true"))
    out.append(b(0, 9, 0, leaves, persistent="true"))
    return out


def scene_blocks(rule, target, support, state="pre"):
    """Return (blocks, ground, biome, focus_y). state: pre | legal | illegal (judge after-frames)."""
    s = rule["scene"]
    r2 = scene_blocks2(rule, target, support, state)
    if r2 is not None:
        return r2
    if s == "block_on_pillar":
        if state == "pre":
            return REF_PILLAR + [b(0, 4, 0, support, **({"axis": "y"} if support.endswith("_log") else {})), b(0, 5, 0, target)], "grass", "plains", 5
        if state == "legal":   # support removed, block stays
            return REF_PILLAR + [b(0, 5, 0, target)], "grass", "plains", 5
        return REF_PILLAR + [b(0, 4, 0, target)], "grass", "plains", 5   # illegal: block fell
    if s == "block_on_ground":
        if state == "pre":
            return [b(0, 4, 0, target)], "grass", "plains", 4.5
        hardened = target.replace("_concrete_powder", "_concrete")
        water = b(1, 4, 0, "water", level=0)
        if state == "legal":
            return [b(0, 4, 0, hardened), water], "grass", "plains", 4.5
        return [b(0, 4, 0, target), water], "grass", "plains", 4.5
    if s == "tree":
        if state == "pre":
            return tree_blocks(target), "grass", "plains", 6.5
        if state == "legal":
            return tree_blocks(target, with_bottom=False), "grass", "plains", 6.5
        return tree_blocks(target, fallen=True), "grass", "plains", 5
    if s == "cactus":
        sand = [b(x, 3, z, "sand") for x in (-1, 0, 1) for z in (-1, 0, 1)]
        base = sand + [b(0, 4, 0, "cactus"), b(0, 5, 0, "cactus")]
        if state == "pre":
            return base, "grass", "plains", 5
        placed = b(1, 4, 0, target)
        if state == "legal":   # cactus broke
            return sand + [placed], "grass", "plains", 5
        return base + [placed], "grass", "plains", 5
    if s == "ice_desert":
        deco = [b(6, 4, -5, "dead_bush"), b(-7, 4, -6, "cactus"), b(-7, 5, -6, "cactus"), b(9, 4, 3, "dead_bush")]
        if state == "illegal":   # melted into water (real-world outcome)
            return [b(0, 4, 0, "water", level=0)] + deco, "sand", "desert", 4.5
        return [b(0, 4, 0, "ice")] + deco, "sand", "desert", 4.5   # pre, and legal (unchanged)
    if s == "torch_wall":
        wall = [b(x, y, 0, target) for x in (-1, 0, 1) for y in (4, 5, 6)]
        return wall + [b(0, 5, 1, "wall_torch", facing="south")], "grass", "plains", 5.5
    if s == "flower_on_block":
        return [b(0, 4, 0, "oak_log", axis="y"), b(0, 5, 0, "grass_block"), b(0, 6, 0, target)], "grass", "plains", 5.5
    if s == "torch_on_block":
        return [b(0, 4, 0, "stone"), b(0, 5, 0, "stone"), b(0, 6, 0, target), b(0, 6, 1, "wall_torch", facing="south")], "grass", "plains", 6
    raise ValueError(s)


def camera(cam_idx, focus_y, jitter, scene_kind=None):
    yaw_off, dist, eye = CAMERAS[cam_idx % len(CAMERAS)]
    mult, max_yaw = SCENE_CAM.get(scene_kind, (1.0, 60))
    if scene_kind in CAM2:
        mult, max_yaw, extra = CAM2[scene_kind]
        eye += extra
    dist *= mult
    if scene_kind == "tree":
        eye += 0.3
    yaw_off = max(-max_yaw, min(max_yaw, yaw_off))
    yaw = math.radians(yaw_off + jitter)
    tx, tz = 0.5, 0.5
    px, pz = tx + dist * math.sin(yaw), tz + dist * math.cos(yaw)
    return {"pos": [round(px, 3), round(3.0 + eye, 3), round(pz, 3)], "target": [tx, focus_y, tz]}


def clutter(rng, scene_kind):
    if scene_kind in ("tree", "ice_desert"):
        return []
    picks = []
    for _ in range(rng.randint(0, 2)):
        x, z = rng.choice([-9, -8, 8, 9]), rng.choice([-9, -7, -6])
        name = rng.choice(["cobblestone", "mossy_cobblestone", "oak_leaves"])
        picks.append(b(x, 4, z, name, **({"persistent": "true"} if name == "oak_leaves" else {})))
        if rng.random() < 0.5:
            picks.append(b(x + 1, 4, z, name, **({"persistent": "true"} if name == "oak_leaves" else {})))
    return picks


def build():
    DATA.mkdir(exist_ok=True)
    rng = random.Random(20261104)
    pre, judge, variants = [], [], []
    for rule in RULES:
        n = N_VARIANTS[rule["split"]]
        for v in range(n):
            target = rule["target_choices"][v % len(rule["target_choices"])]
            supports = rule.get("support_choices")
            support = supports[(v // len(rule["target_choices"])) % len(supports)] if supports else rule.get("support")
            blocks, ground, biome, focus = scene_blocks(rule, target, support)
            cam_idx = v % len(CAMERAS)
            jitter = rng.uniform(-8, 8)
            cam = camera(cam_idx, focus, jitter, rule["scene"])
            extra = clutter(rng, rule["scene"])
            vid = f"{rule['id']}_v{v}"
            pre.append({"id": vid, "ground": ground, "biome": biome, "blocks": blocks + extra, "camera": cam, "viewDistance": 2})
            variants.append({
                "variant": vid, "rule": rule["id"], "split": rule["split"], "kind": rule["kind"],
                "target": target, "support": support,
                "target_name": pretty(target) if rule["scene"] != "tree" else target,
                "support_name": pretty(support) if support else None,
                "image": f"images/{vid}.png", "camera_idx": cam_idx,
            })
            if rule["id"] in JUDGE_RULES and v < JUDGE_VARIANTS:
                for state in ("legal", "illegal"):
                    jb, jg, jbio, jf = scene_blocks(rule, target, support, state)
                    judge.append({"id": f"{vid}_{state}", "ground": jg, "biome": jbio, "blocks": jb + extra,
                                  "camera": camera(cam_idx, focus, jitter, rule["scene"]), "viewDistance": 2})
    (DATA / "scenes_pre.json").write_text(json.dumps(pre, indent=1), encoding="utf-8")
    (DATA / "scenes_judge.json").write_text(json.dumps(judge, indent=1), encoding="utf-8")
    (DATA / "variants.json").write_text(json.dumps(variants, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"pre-state scenes: {len(pre)}, judge after-frames: {len(judge)}")


if __name__ == "__main__":
    build()
