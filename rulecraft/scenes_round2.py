"""Scene templates for the test rules. scene_blocks2 returns (blocks, ground, biome, focus_y) or None.

state: pre (shown to the model), legal / illegal (judge after-frames: vanilla outcome / real-physics outcome).
"""


def b(x, y, z, name, **props):
    return {"x": x, "y": y, "z": z, "name": name, "props": props}


def patch(name, r=2, y=3):
    return [b(x, y, z, name) for x in range(-r, r + 1) for z in range(-r, r + 1)]


def flow_ring(fluid, center_level, ring1, ring2, y=4):
    out = [b(0, y, 0, fluid, level=center_level)] if center_level is not None else []
    for x, z in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.append(b(x, y, z, fluid, level=ring1))
    for x, z in ((2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        out.append(b(x, y, z, fluid, level=ring2))
    return out


def pool(y_levels=(3,), r=1, center=None):
    out = [b(x, y, z, "water", level=0) for x in range(-r, r + 1) for z in range(-r, r + 1) for y in y_levels
           if not (center and (x, z, y) == (0, 0, max(y_levels)))]
    return out


CAM2 = {  # distance multiplier, max yaw, extra eye height
    "sugar_cane": (0.95, 50, 0.2), "water_flow": (1.15, 60, 0.9), "sponge_pool": (1.05, 60, 1.1),
    "lava_pool": (1.15, 60, 0.9), "netherrack_fire": (0.95, 50, 0.3), "ice_torch": (0.9, 45, 0.2),
    "water_step": (1.0, 50, 0.4), "deep_pool": (1.05, 60, 1.1), "desert_pool": (1.05, 60, 1.1), "beam": (2.0, 40, 0.6),
    "anvil_glass": (1.0, 50, 0.4), "leaves_stack": (0.95, 60, 0.3), "sand_over_torch": (1.25, 40, 0.5),
    "flower_ground": (0.75, 60, 0.0), "lily_pad": (0.85, 60, 0.9), "snow_layer": (1.0, 60, 0.8),
    "lava_hole": (0.9, 60, 0.9), "stone_fire": (0.95, 50, 0.3), "covered_grass": (0.95, 60, 0.3),
    "glass_wall": (1.9, 25, 0.8), "torch_ground": (0.7, 45, 0.1), "snow_torch": (0.85, 45, 0.5),
    "lantern": (0.95, 40, 0.2), "cactus_gap": (1.15, 60, 0.3),
    "lamp_ice": (0.95, 45, 0.3), "farmland": (0.95, 60, 0.9), "fire_ground": (0.85, 50, 0.3), "wooden_lava": (1.0, 45, 0.5),
    "desert_block": (0.95, 60, 0.3), "ladder": (0.95, 30, 0.2), "fire_rock": (0.9, 50, 0.4), "ice_lava": (1.0, 45, 0.7),
    "dirt_patch": (0.8, 60, 0.9),
    "campfire_wood": (0.95, 45, 0.3), "on_magma": (0.95, 60, 0.3), "tnt_torch": (0.9, 45, 0.2), "cobweb_fire": (0.95, 40, 0.3),
    "door_on_block": (1.05, 40, 0.3), "carpet_on_block": (0.9, 60, 0.4), "bars_row": (1.9, 25, 0.8), "piston_line": (1.05, 35, 0.4),
    "lamp_block": (0.9, 60, 0.3), "ice_ledge": (1.0, 35, 0.3), "sand_over_slab": (1.25, 40, 0.5), "tree_natural": (1.7, 60, 0.3),
    "path_ground": (0.95, 60, 0.9), "falling_stack": (0.95, 60, 0.3), "lever_block": (0.95, 30, 0.2), "sapling_block": (0.9, 60, 0.2),
    "snow_lava": (1.0, 45, 0.7),
    "sand_tower": (1.5, 50, 0.6), "chain_hang": (1.15, 40, 0.5), "trapdoor_side": (0.95, 30, 0.2), "cake_on_block": (0.85, 50, 0.3),
    "cactus_young": (0.8, 60, 0.3), "stone_pool": (0.95, 60, 0.7), "lantern_ground": (0.75, 60, 0.3), "tnt_pool": (0.9, 60, 0.9),
    "torch_open": (0.7, 45, 0.1), "lava_on_pool": (1.05, 60, 1.1), "tall_cane": (1.15, 50, 0.3), "wheat_plot": (0.9, 60, 0.8),
    "piston_lever": (1.1, 35, 0.5), "wall_gap": (1.9, 25, 0.8),
    "mud_desert": (1.05, 60, 1.1), "block_plain": (1.0, 50, 0.4), "hay_ground": (1.0, 50, 0.4), "dirt_bridge": (2.0, 40, 0.6),
    "sapling_ground": (0.75, 60, 0.0),
    # batch 5 (rules_round7.py)
    "fence_row": (1.25, 40, 0.4), "pond_lily": (1.05, 60, 1.1), "pond_plain": (1.05, 60, 1.1), "pond_ice": (1.05, 60, 1.1),
    "wheat_dry": (1.0, 60, 0.8), "wheat_ripe": (1.0, 60, 0.8), "pumpkin_face": (0.9, 35, 0.3), "campfire_open": (0.85, 50, 0.3),
    "campfire_patch": (0.95, 50, 0.4), "torch_top": (0.9, 45, 0.3), "cauldron_desert": (0.9, 50, 0.6), "sand_hole": (0.85, 60, 0.9),
    "pool_full": (1.05, 60, 1.1), "pool_rim": (1.15, 60, 1.2), "campfire_sponge": (1.0, 45, 0.4), "vine_wall": (1.2, 30, 0.6),
    "pickles_ground": (0.7, 60, 0.1), "cobweb_posts": (1.05, 30, 0.4), "tree_desert": (1.7, 60, 0.3), "pot_desert": (0.75, 50, 0.2),
    "brick_wall": (1.6, 30, 0.5), "leaves_pile": (0.95, 60, 0.3), "anvil_plain": (0.9, 50, 0.3), "barrel_on_block": (1.0, 50, 0.4),
    "pot_on_block": (0.9, 50, 0.4), "vine_pillar": (1.0, 30, 0.4), "wheat_row": (1.1, 30, 0.6), "cane_young": (0.85, 50, 0.3),
    "cocoa_log": (0.95, 30, 0.4), "berry_bush": (0.75, 60, 0.1), "bamboo_shoot": (0.7, 60, 0.0), "kelp_pool": (1.0, 60, 1.4),
    "dripstone_hang": (1.25, 35, 0.6), "pond_ice_center": (1.05, 60, 1.1), "fire_tnt": (1.05, 40, 0.4), "fire_leaves": (1.05, 40, 0.4),
    "campfire_ice": (1.0, 45, 0.4), "pumpkin_stem": (0.95, 45, 0.5), "water_film": (0.9, 60, 0.9),
    "carrot_plot": (1.0, 60, 0.8), "fire_hay": (1.05, 40, 0.4),
}


def beam_blocks(target, pillar=True):
    out = [b(x, 6, 0, target) for x in range(1, 5)]
    if pillar:
        out += [b(0, y, 0, "stone") for y in (4, 5, 6)]
    return out


def scene_blocks2(rule, target, support, state="pre"):
    s = rule["scene"]
    if s == "sugar_cane":
        base = [b(0, 3, 0, target)]
        cane = [b(0, 4, 0, "sugar_cane"), b(0, 5, 0, "sugar_cane")]
        return base + [b(1, 3, 0, "water", level=0)] + cane, "grass", "plains", 4.6
    if s == "water_flow":
        ground = patch(support, r=3)
        if state == "pre":
            return ground + flow_ring("water", 0, 1, 2), "grass", "plains", 4.1
        if state == "legal":
            return ground, "grass", "plains", 4.1
        return ground + flow_ring("water", 3, 3, 4), "grass", "plains", 4.1
    if s == "sponge_pool":
        ground = patch(support, r=2)
        water = pool()
        if state == "pre":
            return ground + water, "grass", "plains", 3.6
        center = [b(0, 3, 0, "wet_sponge")]
        if state == "legal":
            return ground + [b(x, 3, z, "air") for x in (-1, 0, 1) for z in (-1, 0, 1)] + center, "grass", "plains", 3.6
        return ground + water + center, "grass", "plains", 3.6
    if s == "lava_pool":
        ground = patch(target, r=3)
        if state in ("pre", "legal"):
            return ground + flow_ring("lava", 0, 2, 4), "grass", "plains", 4.1
        return ground + [b(0, 4, 0, "basalt", axis="y")], "grass", "plains", 4.1
    if s == "netherrack_fire":
        ground = patch(support, r=1)
        rack = [b(0, 4, 0, "netherrack")]
        if state in ("pre", "legal"):
            return ground + rack + [b(0, 5, 0, "fire", age=0)], "grass", "plains", 5.0
        return ground + rack, "grass", "plains", 5.0
    if s == "stone_fire":
        return [b(0, 4, 0, target), b(0, 5, 0, "fire", age=0)], "grass", "plains", 5.0
    if s == "ice_torch":
        ground = patch(support, r=1)
        if state == "illegal":
            return ground + [b(0, 4, 0, "water", level=0), b(1, 4, 0, "torch")], "grass", "plains", 4.5
        return ground + [b(0, 4, 0, target), b(1, 4, 0, "torch")], "grass", "plains", 4.5
    if s == "water_step":
        return [b(0, 4, 0, target)], "grass", "plains", 4.6
    if s == "deep_pool":
        water = pool(y_levels=(2, 3))
        if rule["id"] == "N10":
            if state == "legal":
                return water + [b(0, 2, 0, target)], "grass", "plains", 3.4
            if state == "illegal":
                return water + [b(0, 3, 0, target)], "grass", "plains", 3.4
        if rule["id"] == "N11":
            if state == "legal":
                return water + [b(0, 3, 0, target)], "grass", "plains", 3.4
            if state == "illegal":
                return water + [b(0, 2, 0, target)], "grass", "plains", 3.4
        return water, "grass", "plains", 3.4
    if s == "desert_pool":
        deco = [b(6, 4, -5, "dead_bush"), b(-7, 4, -6, "cactus"), b(-7, 5, -6, "cactus")]
        return pool() + deco, "sand", "desert", 3.6
    if s == "beam":
        if state == "legal":
            return beam_blocks(target, pillar=False), "grass", "plains", 5.2
        if state == "illegal":
            return [b(x, 4, 0, target) for x in range(1, 5)], "grass", "plains", 5.2
        return beam_blocks(target), "grass", "plains", 5.2
    if s == "anvil_glass":
        if state == "legal":
            return [b(0, 4, 0, target), b(0, 5, 0, "anvil", facing="north")], "grass", "plains", 5.0
        if state == "illegal":
            return [b(0, 4, 0, "anvil", facing="north")], "grass", "plains", 5.0
        return [b(0, 4, 0, target), b(0, 5, 0, "oak_log", axis="y"), b(0, 6, 0, "anvil", facing="north")], "grass", "plains", 5.0
    if s == "leaves_stack":
        return [b(0, 4, 0, support, persistent="true"), b(0, 5, 0, support, persistent="true")], "grass", "plains", 5.0
    if s == "sand_over_torch":
        pillar = [b(1, y, 0, "stone") for y in (4, 5, 6)]
        return pillar + [b(0, 4, 0, "torch"), b(0, 6, 0, "oak_log", axis="x"), b(0, 7, 0, target)], "grass", "plains", 5.5
    if s == "flower_ground":
        if state == "legal":
            return flow_ring("water", None, 1, 2), "grass", "plains", 4.4
        if state == "illegal":
            return [b(0, 4, 0, target)] + flow_ring("water", None, 1, 2), "grass", "plains", 4.4
        return [b(0, 4, 0, target)], "grass", "plains", 4.4
    if s == "lily_pad":
        return patch(support, r=2) + [b(0, 3, 0, "water", level=0), b(0, 4, 0, "lily_pad")], "grass", "plains", 3.8
    if s == "snow_layer":
        return [b(x, 4, z, "snow", layers=1) for x in (-1, 0, 1) for z in (-1, 0, 1)], "grass", "plains", 4.0
    if s == "lava_hole":
        return patch(target, r=2) + [b(0, 3, 0, "lava", level=0)], "grass", "plains", 3.6
    if s == "covered_grass":
        return [b(0, 4, 0, "grass_block", snowy="false"), b(0, 5, 0, target)], "grass", "plains", 4.9
    if s == "glass_wall":     # the wall runs across the view, behind the spot where the water is poured
        wall = [b(x, y, -1, target) for y in (4, 5) for x in range(-4, 5)]
        return wall, "grass", "plains", 4.5
    if s == "torch_ground":
        return patch(support, r=1) + [b(0, 4, 0, "torch")], "grass", "plains", 4.3
    if s == "snow_torch":
        return [b(0, 4, 0, "snow", layers=1), b(1, 4, 0, "torch"), b(0, 4, 1, "snow", layers=1),
                b(0, 4, -1, "snow", layers=1)], "grass", "plains", 4.3
    if s == "lantern":
        pillar = [b(-1, y, 0, "stone") for y in (4, 5, 6)]
        return pillar + [b(0, 6, 0, target), b(0, 5, 0, "lantern", hanging="true")], "grass", "plains", 5.2
    if s == "cactus_gap":
        sand = [b(x, 3, z, "sand") for x in (-1, 0, 1) for z in (-1, 0, 1)]
        return sand + [b(0, 4, 0, "cactus"), b(0, 5, 0, "cactus")], "grass", "plains", 5
    # ------------------------------------------------------------------ confirmation rules (rules_round3.py)
    if s == "lamp_ice":
        return [b(0, 4, 0, "ice"), b(1, 4, 0, target)], "grass", "plains", 4.5
    if s == "farmland":
        return [b(x, 3, z, "farmland", moisture=0) for x in (-1, 0, 1) for z in (-1, 0, 1)], "grass", "plains", 3.6
    if s == "fire_ground":
        return [b(0, 4, 0, "fire", age=0)], "grass", "plains", 4.4
    if s == "wooden_lava":
        return [b(0, 4, 0, target), b(1, 4, 0, "lava", level=0)], "grass", "plains", 4.5
    if s == "desert_block":
        deco = [b(6, 4, -5, "dead_bush"), b(-7, 4, -6, "cactus"), b(-7, 5, -6, "cactus")]
        return [b(0, 4, 0, target)] + deco, "sand", "desert", 4.5
    if s == "ladder":
        return [b(0, 4, 0, "stone"), b(0, 5, 0, target), b(0, 5, 1, "ladder", facing="south")], "grass", "plains", 5.0
    if s == "fire_rock":
        return patch(target, r=1) + [b(0, 4, 0, "fire", age=0)], "grass", "plains", 4.4
    if s == "ice_lava":
        return patch(target, r=2) + [b(0, 4, 0, "ice"), b(1, 3, 0, "lava", level=0)], "grass", "plains", 4.2
    if s == "dirt_patch":
        return [b(0, 3, 0, "dirt")], "grass", "plains", 3.6
    # ------------------------------------------------------------------ pre-registered rules (rules_round4.py)
    if s == "campfire_wood":
        return [b(0, 4, 0, "campfire", lit="true", signal_fire="false", waterlogged="false", facing="north"),
                b(1, 4, 0, target)], "grass", "plains", 4.5
    if s == "on_magma":
        extra = {"layers": 1} if target == "snow" else {}
        return [b(0, 4, 0, "magma_block"), b(0, 5, 0, target, **extra)], "grass", "plains", 5.0
    if s == "tnt_torch":
        return [b(0, 4, 0, "tnt"), b(1, 4, 0, "torch")], "grass", "plains", 4.5
    if s == "cobweb_fire":
        return [b(0, 4, 0, "netherrack"), b(0, 5, 0, "fire", age=0), b(1, 4, 0, "stone"), b(1, 5, 0, "cobweb")], "grass", "plains", 5.0
    if s == "door_on_block":
        door = dict(facing="south", hinge="left", open="false", powered="false")
        return [b(0, 4, 0, target), b(0, 5, 0, "oak_door", half="lower", **door),
                b(0, 6, 0, "oak_door", half="upper", **door)], "grass", "plains", 5.4
    if s == "carpet_on_block":
        return [b(0, 4, 0, support), b(0, 5, 0, target)], "grass", "plains", 4.8
    if s == "bars_row":
        joined = dict(east="true", west="true", north="false", south="false", waterlogged="false")
        return [b(x, y, -1, target, **joined) for y in (4, 5) for x in range(-4, 5)], "grass", "plains", 4.5
    if s == "piston_line":
        return [b(0, 4, 0, "piston", facing="east", extended="false"), b(1, 4, 0, target)], "grass", "plains", 4.5
    if s == "lamp_block":
        return [b(0, 4, 0, "redstone_lamp", lit="false")], "grass", "plains", 4.5
    if s == "ice_ledge":
        return [b(1, y, 0, "stone") for y in (4, 5)] + [b(0, 5, 0, "ice")], "grass", "plains", 5.0
    if s == "sand_over_slab":
        pillar = [b(1, y, 0, "stone") for y in (4, 5, 6)]
        return pillar + [b(0, 4, 0, "stone_slab", type="bottom", waterlogged="false"), b(0, 6, 0, "oak_log", axis="x"),
                         b(0, 7, 0, target)], "grass", "plains", 5.5
    if s == "tree_natural":
        log, leaves = f"{target}_log", f"{target}_leaves"
        out = [b(0, y, 0, log, axis="y") for y in range(4, 8)]
        for y in (7, 8):
            for x in (-1, 0, 1):
                for z in (-1, 0, 1):
                    if (x, z) != (0, 0) or y == 8:
                        out.append(b(x, y, z, leaves, persistent="false", distance=2, waterlogged="false"))
        return out + [b(0, 9, 0, leaves, persistent="false", distance=2, waterlogged="false")], "grass", "plains", 6.5
    if s == "path_ground":
        return [b(x, 3, z, "dirt_path") for x in (-1, 0, 1) for z in (-1, 0, 1)], "grass", "plains", 3.6
    if s == "falling_stack":
        return [b(0, 4, 0, "oak_log", axis="y"), b(0, 5, 0, target), b(0, 6, 0, target)], "grass", "plains", 5.2
    if s == "lever_block":
        return [b(0, 4, 0, "stone"), b(0, 5, 0, target), b(0, 5, 1, "lever", face="wall", facing="south", powered="false")], "grass", "plains", 5.0
    if s == "sapling_block":
        return [b(0, 4, 0, "oak_log", axis="y"), b(0, 5, 0, "dirt"), b(0, 6, 0, target, stage=0)], "grass", "plains", 5.5
    if s == "snow_lava":
        return patch(target, r=2) + [b(0, 4, 0, "snow", layers=1), b(1, 3, 0, "lava", level=0)], "grass", "plains", 4.0
    # ------------------------------------------------------------------ last batch (rules_round5.py)
    if s == "sand_tower":
        return [b(0, y, 0, target) for y in range(4, 9)], "grass", "plains", 6.3
    if s == "chain_hang":
        pillar = [b(1, y, 0, "stone") for y in (4, 5, 6, 7)]
        chain = [b(0, y, 0, "chain", axis="y", waterlogged="false") for y in (5, 6)]
        return pillar + [b(0, 7, 0, target)] + chain, "grass", "plains", 5.9
    if s == "trapdoor_side":
        return [b(0, 4, 0, "stone"), b(0, 5, 0, target),
                b(0, 5, 1, "oak_trapdoor", facing="south", half="bottom", open="true", powered="false", waterlogged="false")], "grass", "plains", 5.0
    if s == "cake_on_block":
        return [b(0, 4, 0, target), b(0, 5, 0, "cake", bites=0)], "grass", "plains", 4.9
    if s == "cactus_young":
        return patch("sand", r=1) + [b(0, 4, 0, "cactus", age=0)], "grass", "plains", 4.3
    if s == "stone_pool":
        return pool() + [b(0, 3, 0, target), b(0, 4, 0, target)], "grass", "plains", 4.0
    if s == "lantern_ground":
        return patch("stone", r=2) + [b(0, 4, 0, target, hanging="false", waterlogged="false")], "grass", "plains", 4.3
    if s == "tnt_pool":
        return pool() + [b(0, 3, 0, "tnt")], "grass", "plains", 3.7
    if s == "torch_open":
        return [b(0, 4, 0, target)], "grass", "plains", 4.3
    if s == "lava_on_pool":
        return patch(support, r=2) + pool(), "grass", "plains", 3.6
    if s == "tall_cane":
        return [b(0, 3, 0, target), b(1, 3, 0, "water", level=0)] + [b(0, y, 0, "sugar_cane") for y in (4, 5, 6)], "grass", "plains", 5.0
    if s == "wheat_plot":
        ring = [(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1) if (x, z) != (0, 0)]
        return ([b(0, 3, 0, "water", level=0)] + [b(x, 3, z, "farmland", moisture=7) for x, z in ring]
                + [b(x, 4, z, "wheat", age=0) for x, z in ring]), "grass", "plains", 3.9
    if s == "piston_lever":
        return [b(0, 4, 0, "piston", facing="east", extended="false"), b(1, 4, 0, target), b(-1, 4, 0, "stone"),
                b(-1, 5, 0, "lever", face="floor", facing="east", powered="false")], "grass", "plains", 4.6
    if s == "wall_gap":
        return [b(x, y, -1, target) for y in (4, 5) for x in range(-4, 5) if x != 0], "grass", "plains", 4.5
    # ------------------------------------------------------------------ harder batch, development pool (rules_round6.py)
    if s == "mud_desert":
        deco = [b(6, 4, -5, "dead_bush"), b(-7, 4, -6, "cactus"), b(-7, 5, -6, "cactus")]
        return patch(target, r=1) + deco, "sand", "desert", 3.6
    if s == "block_plain":
        return [b(0, 4, 0, target)], "grass", "plains", 4.5
    if s == "hay_ground":
        return [b(0, 4, 0, target, axis="y")], "grass", "plains", 4.5
    if s == "dirt_bridge":
        pillars = [b(x, y, 0, "stone") for x in (-3, 3) for y in (4, 5, 6)]
        return pillars + [b(x, 6, 0, target) for x in range(-2, 3)], "grass", "plains", 5.2
    if s == "sapling_ground":
        return [b(0, 4, 0, target, stage=0)], "grass", "plains", 4.4
    # ------------------------------------------------------------------ batch 5 (rules_round7.py)
    camp = dict(lit="true", signal_fire="false", waterlogged="false", facing="north")
    desert = [b(6, 4, -5, "dead_bush"), b(-7, 4, -6, "cactus"), b(-7, 5, -6, "cactus")]
    if s == "fence_row":
        sides = [dict(east="true", west="false"), dict(east="true", west="true"), dict(east="false", west="true")]
        return [b(x, 4, 0, target, north="false", south="false", waterlogged="false", **sd)
                for x, sd in zip((-1, 0, 1), sides)], "grass", "plains", 4.6
    if s in ("pond_plain", "pond_lily"):
        lily = [b(0, 4, 0, "lily_pad"), b(1, 4, 1, "lily_pad")] if s == "pond_lily" else []
        return pool(y_levels=(2, 3)) + lily, "grass", "plains", 3.6
    if s == "pond_ice":
        return pool(y_levels=(2,)) + [b(x, 3, z, "ice") for x in (-1, 0, 1) for z in (-1, 0, 1)], "grass", "plains", 3.6
    if s == "pond_ice_center":
        water = [w for w in pool(y_levels=(2, 3)) if (w["x"], w["y"], w["z"]) != (0, 3, 0)]
        return water + [b(0, 3, 0, "ice")], "grass", "plains", 3.6
    if s == "wheat_dry":
        cells = [(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1)]
        return ([b(x, 3, z, "farmland", moisture=0) for x, z in cells]
                + [b(x, 4, z, "wheat", age=1) for x, z in cells]), "grass", "plains", 3.9
    if s == "wheat_ripe":
        ring = [(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1) if (x, z) != (0, 0)]
        return ([b(0, 3, 0, "water", level=0)] + [b(x, 3, z, "farmland", moisture=7) for x, z in ring]
                + [b(x, 4, z, "wheat", age=7) for x, z in ring]), "grass", "plains", 3.9
    if s == "wheat_row":
        return ([b(x, 3, 0, "farmland", moisture=7) for x in (-1, 0, 1)]
                + [b(x, 4, 0, "wheat", age=3) for x in (-1, 0, 1)]), "grass", "plains", 3.9
    if s == "pumpkin_face":
        return [b(0, 4, 0, target, facing="south")], "grass", "plains", 4.5
    if s == "campfire_open":
        return [b(0, 4, 0, "campfire", **camp)], "grass", "plains", 4.3
    if s == "campfire_patch":
        return patch(support, r=1) + [b(0, 4, 0, "campfire", **camp)], "grass", "plains", 4.3
    if s == "campfire_sponge":
        return [b(0, 4, 0, "campfire", **camp), b(1, 4, 0, target)], "grass", "plains", 4.5
    if s == "campfire_ice":
        return [b(0, 4, 0, "campfire", **camp), b(1, 4, 0, "ice")], "grass", "plains", 4.5
    if s == "torch_top":
        return [b(0, 4, 0, target), b(0, 5, 0, "torch")], "grass", "plains", 5.0
    if s == "cauldron_desert":
        return [b(0, 4, 0, "water_cauldron", level=3)] + desert, "sand", "desert", 4.5
    if s == "sand_hole":
        return [b(0, 3, 0, "water", level=0)], "sand", "beach", 3.6
    if s == "pool_full":
        return pool(), "grass", "plains", 3.6
    if s == "pool_rim":
        rim = [b(x, 3, z, target) for x in range(-2, 3) for z in range(-2, 3) if max(abs(x), abs(z)) == 2]
        return pool() + rim, "grass", "plains", 3.8
    if s == "vine_wall":
        wall = [b(x, y, 0, target) for x in (-1, 0, 1) for y in (4, 5, 6)]
        vines = [b(x, y, 1, "vine", north="true", east="false", south="false", west="false", up="false")
                 for x in (-1, 0, 1) for y in (4, 5, 6)]
        return wall + vines, "grass", "plains", 5.5
    if s == "pickles_ground":
        return [b(0, 4, 0, "sea_pickle", pickles=3, waterlogged="false")], "grass", "plains", 4.2
    if s == "cobweb_posts":
        posts = [b(x, y, 0, support) for x in (-1, 1) for y in (4, 5)]
        return posts + [b(0, 5, 0, "cobweb")], "grass", "plains", 5.0
    if s == "tree_desert":
        log, leaves = f"{target}_log", f"{target}_leaves"
        out = [b(0, y, 0, log, axis="y") for y in range(4, 8)]
        for y in (7, 8):
            for x in (-1, 0, 1):
                for z in (-1, 0, 1):
                    if (x, z) != (0, 0) or y == 8:
                        out.append(b(x, y, z, leaves, persistent="false", distance=2, waterlogged="false"))
        out.append(b(0, 9, 0, leaves, persistent="false", distance=2, waterlogged="false"))
        return out + desert, "sand", "desert", 6.5
    if s == "pot_desert":
        return [b(0, 4, 0, target)] + desert, "sand", "desert", 4.4
    if s == "brick_wall":
        return [b(x, y, 0, target) for x in range(-2, 3) for y in (4, 5)], "grass", "plains", 5.0
    if s == "leaves_pile":
        return [b(0, 4, 0, target, persistent="true", distance=7, waterlogged="false")], "grass", "plains", 4.5
    if s == "anvil_plain":
        return [b(0, 4, 0, "anvil", facing="north")], "grass", "plains", 4.5
    if s == "barrel_on_block":
        return [b(0, 4, 0, support), b(0, 5, 0, "barrel", facing="up", open="false")], "grass", "plains", 5.0
    if s == "pot_on_block":
        return [b(0, 4, 0, support), b(0, 5, 0, target)], "grass", "plains", 5.0
    if s == "vine_pillar":
        return [b(0, 4, 0, target), b(0, 5, 0, target),
                b(0, 5, 1, "vine", north="true", east="false", south="false", west="false", up="false")], "grass", "plains", 5.0
    if s == "cane_young":
        return [b(0, 3, 0, target), b(1, 3, 0, "water", level=0), b(0, 4, 0, "sugar_cane", age=0)], "grass", "plains", 4.4
    if s == "cocoa_log":
        return ([b(0, y, 0, "jungle_log", axis="y") for y in (4, 5, 6)]
                + [b(0, 5, 1, "cocoa", age=0, facing="north")]), "grass", "plains", 5.4
    if s == "berry_bush":
        return [b(0, 4, 0, "sweet_berry_bush", age=1)], "grass", "plains", 4.3
    if s == "bamboo_shoot":
        return [b(0, 4, 0, "bamboo_sapling")], "grass", "plains", 4.2
    if s == "kelp_pool":
        water = [b(x, y, z, "water", level=0) for x in (-1, 0, 1) for z in (-1, 0, 1) for y in (1, 2, 3)
                 if (x, y, z) != (0, 1, 0)]
        return water + [b(0, 1, 0, "kelp", age=0)], "grass", "plains", 2.6
    if s == "dripstone_hang":
        pillar = [b(1, y, 0, "stone") for y in (4, 5, 6, 7)]
        tip = b(0, 6, 0, "pointed_dripstone", thickness="tip", vertical_direction="down", waterlogged="false")
        return pillar + [b(0, 7, 0, target), tip], "grass", "plains", 6.0
    if s == "carrot_plot":
        ring = [(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1) if (x, z) != (0, 0)]
        return ([b(0, 3, 0, "water", level=0)] + [b(x, 3, z, "farmland", moisture=7) for x, z in ring]
                + [b(x, 4, z, "carrots", age=0) for x, z in ring]), "grass", "plains", 3.9
    if s in ("fire_tnt", "fire_leaves", "fire_hay"):
        if s == "fire_tnt":
            right = b(1, 5, 0, "tnt", unstable="false")
        elif s == "fire_hay":
            right = b(1, 5, 0, "hay_block", axis="y")
        else:
            right = b(1, 5, 0, target, persistent="true", distance=7, waterlogged="false")
        return [b(0, 4, 0, "netherrack"), b(0, 5, 0, "fire", age=0), b(1, 4, 0, "stone"), right], "grass", "plains", 5.0
    if s == "pumpkin_stem":
        return [b(0, 3, 0, "farmland", moisture=7), b(0, 3, 1, "water", level=0), b(0, 4, 0, "pumpkin_stem", age=7),
                b(-1, 4, 0, "stone"), b(0, 4, -1, "stone")], "grass", "plains", 4.3
    if s == "water_film":
        return patch(target, r=1) + [b(0, 4, 0, "water", level=3)], "grass", "plains", 3.8
    return None
