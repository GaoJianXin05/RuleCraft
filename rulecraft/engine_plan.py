"""Write data/engine_plan.json: for every scene variant, how to build it, which action to perform on a vanilla
1.20.1 server, and which block states the vanilla outcome implies."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DY = -64          # scene y=3 (ground surface) -> superflat grass at y=-61


def W(site, x, y, z):
    return [site[0] + x, y + DY, site[1] + z]


def plan_for(v, scene):
    r, t, s = v["rule"], v["target"], v["support"]
    act, checks, wait = {}, [], 40
    if r in ("G1", "T1", "D1"):
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks = [((0, 5, 0), t), ((0, 4, 0), "air")]
    elif r in ("S1", "S2"):
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks, wait = [((0, 4, 0), t), ((0, 5, 0), "air")], 80
    elif r == "D2":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks, wait = [((0, 4, 0), "#minecraft:anvil"), ((0, 5, 0), "air")], 80
    elif r == "G2":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks = [((0, 4, 0), "air"), ((0, 5, 0), f"{t}_log"), ((0, 7, 0), f"{t}_log"), ((0, 8, 0), f"{t}_leaves")]
    elif r == "A1":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), t)]}
        checks = [((0, 4, 0), "air"), ((0, 5, 0), "air"), ((1, 4, 0), t)]
    elif r == "L1":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "ice")]
    elif r == "L2":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 5, 0), t), ((-1, 5, 0), t), ((0, 5, 1), "wall_torch")]
    elif r == "R4":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "water")]}
        checks = [((0, 4, 0), t.replace("_concrete_powder", "_concrete"))]
    elif r == "R5":
        act = {"type": "dig", "pos": (0, 5, 0)}
        checks = [((0, 5, 0), "water")]
    elif r == "S3":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "air")]}
        checks = [((0, 6, 0), "air")]
    elif r == "S4":
        act = {"type": "cmd", "cmds": [("setblock", (0, 6, 0), "air")]}
        checks = [((0, 6, 1), "air")]
    elif r == "N1":      # the cane is only re-checked on a block update, so it stands until something else disturbs it
        act = {"type": "cmd", "cmds": [("setblock", (1, 3, 0), "air")], "pre": ["gamerule randomTickSpeed 0"],
               "post": ["gamerule randomTickSpeed 3"]}
        checks = [((0, 4, 0), "sugar_cane"), ((0, 5, 0), "sugar_cane")]
    elif r == "H1":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((1, 4, 0), t), ((0, 4, 0), "campfire")]
    elif r in ("H2", "H3"):
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), t)]
    elif r in ("H4", "H5", "H6"):
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 5, 0), t), ((0, 4, 0), "magma_block")]
    elif r == "H7":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "tnt"), ((1, 4, 0), "torch")]
    elif r == "H8":
        act = {"type": "ticks", "speed": 3, "seconds": 20}
        checks = [((1, 5, 0), "cobweb"), ((0, 5, 0), "fire")]
    elif r == "H9":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), t)]
    elif r == "H10":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "cake")]
    elif r == "V1":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks = [((0, 5, 0), "air"), ((0, 6, 0), "air")]
    elif r == "V2":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks = [((0, 5, 0), "air"), ((0, 4, 0), "air")]
    elif r == "V3":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "water")]}
        checks, wait = [((0, 4, 0), "water"), ((0, 4, -2), "air"), ((0, 4, -1), t)], 80
    elif r == "V4":
        act = {"type": "cmd", "cmds": [("setblock", (-1, 4, 0), "redstone_block")]}
        checks, wait = [((2, 4, 0), t), ((1, 4, 0), "piston_head")], 10
    elif r == "V5":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "redstone_block")]}
        checks, wait = [((0, 4, 0), "redstone_lamp[lit=true]")], 10
    elif r == "V6":
        act = {"type": "dig", "pos": (0, 5, 0)}
        checks = [((0, 5, 0), "air"), {"entity": "item", "pos": (0, 5, 0), "r": 4, "absent": True}]
    elif r == "V7":
        act = {"type": "cmd", "cmds": [("setblock", (0, 6, 0), "air")]}
        checks, wait = [((0, 4, 0), "stone_slab"), ((0, 5, 0), "air"), ((0, 7, 0), "air")], 80
    elif r == "V8":      # the trunk goes first, then leaves left without a log decay on random ticks
        act = {"type": "cmd", "cmds": [("setblock", (0, y, 0), "air") for y in (4, 5, 6, 7)],
               "after": ["gamerule randomTickSpeed 1000"], "post": ["gamerule randomTickSpeed 3"]}
        checks, wait = [((0, 8, 0), "air"), ((1, 7, 0), "air"), ((0, 9, 0), "air")], 300
    elif r == "V9":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), t)]}
        checks, wait = [((0, 3, 0), "dirt"), ((0, 4, 0), t)], 20
    elif r == "Q5":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks, wait = [((0, 4, 0), t), ((0, 5, 0), t), ((0, 6, 0), "air")], 80
    elif r == "Q6":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "lava")]}
        checks, wait = [((1, 4, 0), "lava"), ((0, 5, 0), "lava")], 240
    elif r == "Q7":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "air")]}
        checks = [((0, 5, 1), "air"), ((0, 5, 0), "air")]
    elif r == "Q8":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "air")]}
        checks = [((0, 6, 0), "air"), ((0, 5, 0), "air")]
    elif r == "Q9":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "air")]
    elif r == "F1":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), t), ((0, 8, 0), t)]
    elif r == "F2":
        act = {"type": "cmd", "cmds": [("setblock", (0, 7, 0), "air")]}
        checks = [((0, 6, 0), "chain"), ((0, 5, 0), "chain"), ((0, 7, 0), "air")]
    elif r == "F3":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "air")]}
        checks = [((0, 5, 1), "oak_trapdoor"), ((0, 5, 0), "air")]
    elif r == "F4":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks = [((0, 5, 0), "air"), ((0, 4, 0), "air"), {"entity": "item", "pos": (0, 4, 0), "r": 4, "absent": True}]
    elif r == "F5":
        act = {"type": "ticks", "speed": 1000, "seconds": 15}
        checks = [((0, 6, 0), "cactus"), ((0, 7, 0), "air")]
    elif r == "F6":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 7, 0), f"{t}_log"), ((0, 8, 0), f"{t}_leaves"), ((0, 9, 0), f"{t}_leaves"), ((0, 10, 0), "air"), ((2, 7, 0), "air")]
    elif r == "F7":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 3, 0), t), ((0, 4, 0), t)]
    elif r == "F8":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "water")]}
        checks, wait = [((0, 4, 0), t), ((1, 4, 0), "water"), ((1, 4, 1), "water")], 40
    elif r == "F9":      # a redstone block primes the TNT; the check waits past its four-second fuse
        act = {"type": "cmd", "cmds": [("setblock", (1, 3, 0), "redstone_block")]}
        checks, wait = [((2, 3, 0), "grass_block"), ((-2, 3, 0), "grass_block"), ((0, 2, 0), "dirt"), ((-1, 2, 0), "dirt"), ((0, 3, -1), "water")], 140
    elif r == "F10":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "ice"), ((1, 4, 0), t)]
    elif r == "F11":     # fire works on its own scheduled ticks, so this one needs real time
        act = {"type": "ticks", "speed": 3, "seconds": 45}
        checks = [((0, 4, 0), "air"), ((0, 5, 0), "air")]
    elif r == "F12":
        act = {"type": "cmd", "cmds": [("setblock", (-1, 4, 0), "redstone_block")]}
        checks, wait = [((1, 4, 0), t), ((2, 4, 0), "air"), ((0, 4, 0), "piston[extended=false]")], 10
    elif r == "F13":
        act = {"type": "ticks", "speed": 1000, "seconds": 8, "pre": ["weather rain 1000000"], "post": ["weather clear 1000000"]}
        checks = [((0, 4, 0), t)]
    elif r == "F14":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "lava")]}
        checks, wait = [((0, 3, 0), "stone")], 40
    elif r == "F15":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")], "pre": ["gamerule randomTickSpeed 0"],
               "post": ["gamerule randomTickSpeed 3"]}
        checks = [((0, 5, 0), "air"), ((0, 6, 0), "air")]
    elif r == "Q10":     # a redstone block primes the TNT, standing in for flint and steel
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "redstone_block")]}
        checks, wait = [((0, 4, 0), "air"), {"pos": (0, 3, 0), "block": "grass_block", "negate": True}], 120
    elif r == "Q11":
        act = {"type": "ticks", "speed": 1000, "seconds": 45}     # 20 seconds left one plot short of full growth
        checks = [((1, 4, 0), "wheat[age=7]"), ((-1, 4, 1), "wheat[age=7]")]
    elif r == "Q12":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), t)]
    elif r == "Q13":     # flipping a lever by hand tells the blocks around its support; setblock does not, so the block above the piston nudges it
        act = {"type": "cmd", "cmds": [("setblock", (-1, 5, 0), "lever[face=floor,facing=east,powered=true]"),
                                       ("setblock", (0, 5, 0), "stone"), ("setblock", (0, 5, 0), "air")]}
        checks, wait = [((2, 4, 0), t), ((1, 4, 0), "piston_head")], 10
    elif r == "Q14":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "water")]}
        checks, wait = [((0, 4, -1), "water"), ((0, 4, -2), "water")], 80
    elif r == "M1":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "water"), ((1, 4, 0), t)]
    elif r == "M2":      # at this tick speed the dirt soon grows grass from the field around it, so test "no longer farmland"
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [{"pos": (0, 3, 0), "block": "farmland", "negate": True}]
    elif r == "M3":
        act = {"type": "ticks_only", "seconds": 12}
        checks, wait = [((0, 4, 0), "lava[level=0]"), ((3, 4, 0), "lava"), ((4, 4, 0), "air")], 20
    elif r == "M4":
        act = {"type": "ticks", "speed": 3, "seconds": 60}
        checks = [((0, 4, 0), "air"), ((1, 4, 0), "air"), ((1, 3, 0), "grass_block"), ((0, 3, 0), "grass_block")]
    elif r == "M5":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), t)]
    elif r == "M6":
        act = {"type": "dig", "pos": (0, 4, 0)}
        checks = [((0, 4, 0), "air"), {"entity": "item", "pos": (0, 4, 0), "r": 4, "absent": True}]
    elif r == "M7":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "water")]}
        checks, wait = [((0, 4, 0), t), ((1, 4, 0), "water")], 60
    elif r == "M8":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "wet_sponge")]
    elif r == "Q1":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "air")]}
        checks = [((0, 5, 1), "air"), ((0, 5, 0), "air")]
    elif r == "Q2":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "water")]}
        checks, wait = [((0, 4, 0), "water")], 60
    elif r == "Q3":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [{"pos": (0, 4, 0), "block": "ice", "negate": True}]
    elif r == "Q4":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 3, 0), "grass_block")]
    elif r == "N7":
        act = {"type": "cmd", "cmds": [("setblock", (0, y, 0), "air") for y in (4, 5, 6)]}
        checks, wait = [((1, 6, 0), t), ((4, 6, 0), t), ((1, 4, 0), "air")], 40
    elif r == "N8":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "air")]}
        checks, wait = [((0, 4, 0), t), ((0, 5, 0), "#minecraft:anvil"), ((0, 6, 0), "air")], 60
    elif r == "N9":
        act = {"type": "cmd", "cmds": [("setblock", (0, 6, 0), t)]}
        checks, wait = [((0, 6, 0), t), ((0, 5, 0), s), ((0, 4, 0), s)], 40
    elif r == "N10":
        act = {"type": "cmd", "cmds": [("setblock", (0, 2, 0), t)]}
        checks, wait = [((0, 2, 0), t), ((0, 3, 0), "water")], 60
    elif r == "N11":
        act = {"type": "cmd", "cmds": [("setblock", (0, 3, 0), t)]}
        checks, wait = [((0, 3, 0), t), ((0, 2, 0), "water")], 60
    elif r == "N12":
        act = {"type": "ticks_only", "seconds": 8}
        checks, wait = [((0, 4, 0), "water[level=0]"), ((7, 4, 0), "water"), ((8, 4, 0), "air")], 20
    elif r == "N13":
        act = {"type": "cmd", "cmds": [("setblock", (0, 3, 0), "air")]}
        checks, wait = [((0, 3, 0), "water[level=0]"), ((1, 3, 0), "water[level=0]")], 60
    elif r == "N14":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "water")]}
        checks, wait = [((0, 4, 0), "water")], 60
    elif r == "N15":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 3, 0), "water[level=0]"), ((1, 3, 1), "water[level=0]")]
    elif r == "N16":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "snow_block")]
    elif r == "N17":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), t)]
    elif r == "N18":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "snow"), ((1, 4, 1), "snow")]
    elif r == "N19":
        act = {"type": "cmd", "cmds": [("setblock", (0, 3, 0), "air")]}
        checks = [((0, 4, 0), "air"), ((0, 3, 0), "air")]
    elif r in ("N20", "N21"):
        act = {"type": "dig", "pos": (0, 4, 0)}
        checks = [((0, 4, 0), "air")]
        if r == "N20":   # glass leaves nothing behind: no dropped item may exist around the block
            checks.append({"entity": "item", "pos": (0, 4, 0), "r": 4, "absent": True})
    elif r == "N22":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "redstone_torch")], "post": ["kill @e[type=tnt]"]}
        checks, wait = [((0, 4, 0), "air")], 4
    elif r in ("N24", "N25"):
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), t)]
    elif r == "N23":
        act = {"type": "cmd", "cmds": [("setblock", (0, 6, 0), "air")]}
        checks, wait = [((0, 4, 0), "torch"), ((0, 5, 0), "air"), ((0, 7, 0), "air")], 80
    elif r == "N26":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "water")]}
        checks = [((0, 3, 0), "obsidian")]
    elif r == "K5":      # fire ages on its own scheduled ticks, not random ticks, so this one needs real time
        act = {"type": "ticks", "speed": 3, "seconds": 60}
        checks = [((0, 5, 0), "air"), ((0, 4, 0), t)]
    elif r == "K6":
        act = {"type": "ticks", "speed": 1000, "seconds": 20}
        checks = [{"pos": (0, 4, 0), "block": "copper_block", "negate": True}]
    elif r == "K7":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "dirt"), ((0, 5, 0), t)]
    elif r == "K8":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "water")]}
        checks, wait = [((0, 4, 0), "water"), ((0, 4, -2), "air")], 80
    elif r == "K9":
        act = {"type": "cmd", "cmds": [("setblock", (1, 4, 0), "water")]}
        checks, wait = [((0, 4, 0), "water")], 60
    elif r == "K10":
        act = {"type": "cmd", "cmds": [("setblock", (0, 3, 0), "wet_sponge")]}
        checks, wait = [((0, 3, 0), "wet_sponge"), ((1, 3, 0), "water"), ((-1, 3, -1), "water")], 40
    elif r == "K11":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "air")]
    elif r == "K12":
        act = {"type": "cmd", "cmds": [("setblock", (0, 6, 0), "air")]}
        checks = [((0, 5, 0), "air")]
    elif r == "K13":
        act = {"type": "cmd", "cmds": [("setblock", (2, 4, 0), t)]}
        checks = [((0, 4, 0), "cactus"), ((0, 5, 0), "cactus"), ((2, 4, 0), t)]
    elif r == "N2":
        act = {"type": "cmd", "cmds": [("setblock", (0, y, 0), "air") for y in (4, 5, 6, 7)]}
        checks, wait = [((0, 8, 0), f"{t}_leaves"), ((1, 7, 0), f"{t}_leaves")], 20
    elif r == "N3":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks, wait = [((1, 4, 0), "air"), ((2, 4, 0), "air"), ((1, 4, 1), "air")], 120
    elif r == "N4":
        act = {"type": "cmd", "cmds": [("setblock", (0, 3, 0), "sponge")]}
        checks = [((0, 3, 0), "wet_sponge"), ((1, 3, 0), "air"), ((-1, 3, -1), "air")]
    elif r == "N5":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "lava")]
    elif r == "N6":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 5, 0), "fire"), ((0, 4, 0), "netherrack")]
    elif r == "K1":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 4, 0), "water")]
    elif r == "K2":
        act = {"type": "cmd", "cmds": [("setblock", (0, 5, 0), "water")]}
        checks, wait = [((1, 4, 0), "water")], 60
    elif r == "K3":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), t)]}
        checks, wait = [((0, 2, 0), t), ((0, 4, 0), "air")], 80
    elif r == "K4":
        act = {"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}
        checks, wait = [((0, 4, 0), t), ((0, 5, 0), "air")], 80
    # ------------------------------------------------------------------ harder batch, development pool
    elif r == "X1":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 3, 0), "mud"), ((1, 3, 1), "mud")]
    elif r in ("X2", "X8"):
        act = {"type": "ticks", "speed": 1000, "seconds": 10, "pre": ["weather rain 1000000"], "post": ["weather clear 1000000"]}
        checks = [((0, 4, 0), t)]
    elif r == "X3":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 3, 0), t), ((0, 4, 0), t), ((1, 3, 0), "water")]
    elif r == "X4":
        act = {"type": "ticks", "speed": 1000, "seconds": 10, "pre": ["weather rain 1000000"], "post": ["weather clear 1000000"]}
        checks = [((0, 4, 0), "hay_block")]
    elif r == "X5":
        act = {"type": "ticks", "speed": 1000, "seconds": 10, "pre": ["weather rain 1000000"], "post": ["weather clear 1000000"]}
        checks = [((0, 3, 0), "lava"), ((1, 3, 0), t)]
    elif r == "X7":
        act = {"type": "ticks", "speed": 1000, "seconds": 10}
        checks = [((0, 9, 0), f"{t}_leaves"), ((1, 7, 0), f"{t}_leaves"), ((-1, 8, -1), f"{t}_leaves")]
    elif r == "X9":
        act = {"type": "ticks", "speed": 1000, "seconds": 10, "pre": ["weather rain 1000000"], "post": ["weather clear 1000000"]}
        checks = [((0, 6, 0), t), ((-2, 6, 0), t), ((2, 6, 0), t)]
    elif r == "X10":     # coral dies on a scheduled tick a few seconds after it is placed without water
        act = {"type": "ticks_only", "seconds": 12}
        checks = [((0, 4, 0), "dead_" + t)]
    elif r == "X11":     # the sapling grows on random ticks; whatever tree comes out, the sapling block is gone
        act = {"type": "ticks", "speed": 1000, "seconds": 20}
        checks = [{"pos": (0, 4, 0), "block": t, "negate": True}, {"pos": (0, 4, 0), "block": "air", "negate": True}]
    # ------------------------------------------------------------------ batch 5 (rules_round7.py)
    elif r.startswith("Y"):
        act, checks, wait = plan_round7(r, t)
    else:
        raise ValueError(r)
    return act, checks, wait


RAIN = {"pre": ["weather rain 1000000"], "post": ["weather clear 1000000"]}


def plan_round7(r, t):
    """Batch 5: the action and the checks that the vanilla outcome implies."""
    tick = {"type": "ticks", "speed": 1000, "seconds": 10}
    rain = dict(tick, **RAIN)
    same = [((0, 4, 0), t)]
    table = {
        "Y1": (rain, same), "Y2": (tick, same), "Y3": (rain, same), "Y4": (tick, [((0, 4, 0), t), ((1, 4, 0), t)]),
        "Y5": (tick, same), "Y6": (tick, [((0, 4, 0), "lily_pad"), ((1, 4, 1), "lily_pad")]),
        "Y7": (tick, [((0, 3, 0), "water"), ((1, 2, 1), "water")]),
        "Y8": (tick, [((0, 3, 0), "ice"), ((1, 3, 1), "ice")]),
        "Y9": (dict(tick, seconds=20), [((0, 4, 0), "wheat"), {"pos": (0, 4, 0), "block": "wheat[age=1]", "negate": True},
                                        ((1, 4, 1), "wheat")]),
        "Y10": (tick, [((1, 4, 0), "wheat[age=7]"), ((-1, 4, 1), "wheat[age=7]")]),
        "Y11": (tick, same), "Y12": (tick, [((0, 4, 0), "campfire[lit=true]")]),
        "Y13": (rain, [((0, 4, 0), "campfire[lit=true]")]),
        "Y14": (dict(type="ticks", speed=3, seconds=40, **RAIN), [((0, 5, 0), "fire"), ((0, 4, 0), "netherrack")]),
        "Y15": (tick, [((0, 5, 0), "torch"), ((0, 4, 0), t)]),
        "Y16": (rain, [((0, 4, 0), "magma_block")]), "Y17": (rain, [((0, 4, 0), "snow_block")]),
        "Y18": (tick, [((0, 4, 0), "water_cauldron[level=3]")]), "Y19": (tick, [((0, 3, 0), "water")]),
        "Y20": (rain, [((0, 3, 0), "water"), ((1, 3, 1), "water"), ((2, 4, 0), "air"), ((0, 4, 2), "air")]),
        "Y21": (rain, same), "Y22": (rain, [((0, 4, 0), "sponge")]),
        "Y23": (tick, [((1, 4, 0), "wet_sponge"), ((0, 4, 0), "campfire[lit=true]")]),
        "Y24": (rain, [((0, 3, 0), "dirt_path"), ((1, 3, 1), "dirt_path")]),
        "Y25": (tick, [((0, 6, 0), "sugar_cane"), ((0, 7, 0), "air")]),
        "Y26": (tick, [((0, 5, 1), "vine"), ((1, 4, 1), "vine")]), "Y27": (tick, [((0, 4, 0), "sea_pickle")]),
        "Y28": (rain, [((0, 5, 0), "cobweb")]), "Y29": (rain, same), "Y30": (rain, same), "Y31": (tick, same),
        "Y32": (rain, same),
        "Y33": (tick, [((0, 7, 0), f"{t}_log"), ((1, 7, 0), f"{t}_leaves"), ((0, 9, 0), f"{t}_leaves")]),
        "Y34": (tick, same), "Y35": (tick, [((0, 4, 0), t), ((2, 5, 0), t)]), "Y36": (rain, same),
        "Y37": (rain, [((0, 4, 0), "anvil")]),
        # action
        "Y38": ({"type": "dig", "pos": (0, 4, 0)}, [((0, 4, 0), "air")]),
        "Y39": ({"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}, [((0, 5, 0), "barrel"), ((0, 4, 0), "air")]),
        "Y40": ({"type": "cmd", "cmds": [("setblock", (0, 4, 0), "air")]}, [((0, 5, 0), t)]),
        "Y41": ({"type": "cmd", "cmds": [("setblock", (1, 4, 0), "water")]},
                [((0, 4, 0), "campfire[lit=true]"), ((1, 4, 0), "water")]),
        "Y42": ({"type": "cmd", "cmds": [("setblock", (0, 5, 0), "water")]},
                [((0, 4, 0), "magma_block"), {"pos": (0, 5, 0), "block": "air", "negate": True}]),
        "Y43": ({"type": "cmd", "cmds": [("setblock", (0, 4, 0), "ice")]}, [((0, 4, 0), "ice")]),
        "Y44": ({"type": "cmd", "cmds": [("setblock", (0, 5, 0), "air")]}, [((0, 5, 1), "air"), ((0, 4, 0), t)]),
        "Y45": ({"type": "cmd", "cmds": [("setblock", (2, 4, 0), "water")]}, [((0, 4, 0), "water"), ((-1, 4, 0), "water")]),
        "Y46": ({"type": "dig", "pos": (0, 4, 0)}, [((0, 4, 0), "water")]),
        "Y47": ({"type": "cmd", "cmds": [("setblock", (0, 5, 0), "torch")]}, [((0, 4, 0), "hay_block"), ((0, 5, 0), "torch")]),
        # consistent
        "Y48": (tick, [((0, 5, 0), "sugar_cane")]), "Y49": (tick, [((0, 5, 1), "cocoa[age=2]")]),
        "Y50": (tick, [((0, 4, 0), "sweet_berry_bush[age=3]")]), "Y51": (dict(tick, seconds=15), [((0, 5, 0), "bamboo")]),
        "Y52": (dict(tick, seconds=30), [((1, 4, 0), "carrots[age=7]"), ((-1, 4, 1), "carrots[age=7]")]),
        "Y53": ({"type": "cmd", "cmds": [("setblock", (0, 7, 0), "air")]},
                [((0, 6, 0), "air"), ((0, 5, 0), "air"), ((0, 4, 0), "air")]),
        "Y54": ({"type": "dig", "pos": (0, 3, 0)}, [((0, 3, 0), "water")]),
        "Y55": ({"type": "ticks", "speed": 3, "seconds": 30}, [{"pos": (1, 5, 0), "block": "tnt", "negate": True}]),
        "Y56": (tick, [((1, 4, 0), "water")]),
        "Y57": ({"type": "ticks", "speed": 3, "seconds": 45}, [{"pos": (1, 5, 0), "block": t, "negate": True}]),
        "Y58": (dict(tick, seconds=40), [((1, 4, 0), "pumpkin"), ((0, 4, 0), "attached_pumpkin_stem")]),
        "Y59": ({"type": "ticks", "speed": 3, "seconds": 90}, [{"pos": (1, 5, 0), "block": "hay_block", "negate": True}]),
        "Y60": ({"type": "cmd", "cmds": [("setblock", (-2, 4, 0), "water")]}, [((0, 4, 0), "water")]),
    }
    waits = {"Y38": 20, "Y41": 80, "Y42": 60, "Y43": 60, "Y45": 80, "Y46": 20, "Y47": 400, "Y53": 80, "Y54": 40,
             "Y55": 120, "Y60": 80}
    act, checks = table[r]
    return dict(act), list(checks), waits.get(r, 40)


def main():
    scenes = {s["id"]: s for s in json.loads((DATA / "scenes_pre.json").read_text(encoding="utf-8"))}
    variants = json.loads((DATA / "variants.json").read_text(encoding="utf-8"))
    plan = []
    for k, v in enumerate(variants):
        site = (24 * (k % 11) + 8, 24 * (k // 11) + 8)
        sc = scenes[v["variant"]]
        act, checks, wait = plan_for(v, sc)
        if act["type"] == "cmd":
            act["cmds"] = [f"setblock {' '.join(map(str, W(site, *p)))} minecraft:{b}" for _, p, b in act["cmds"]]
        if act["type"] == "dig":
            act["pos"] = W(site, *act["pos"])
        blocks = []
        for b in sc["blocks"]:
            props = ",".join(f"{a}={val}" for a, val in b["props"].items())
            blocks.append(f"setblock {' '.join(map(str, W(site, b['x'], b['y'], b['z'])))} minecraft:{b['name']}"
                          + (f"[{props}]" if props else ""))
        plan_checks = []
        for c in checks:
            if isinstance(c, tuple):
                c = {"pos": c[0], "block": c[1]}
            if "entity" in c:
                plan_checks.append({"entity": c["entity"], "pos": W(site, *c["pos"]), "r": c["r"], "absent": c["absent"]})
            else:
                name = c["block"]
                plan_checks.append({"pos": W(site, *c["pos"]), "negate": c.get("negate", False),
                                    "block": name if name.startswith("#") else f"minecraft:{name}"})
        plan.append({
            "id": v["variant"], "rule": v["rule"], "split": v["split"], "site": site,
            "bot": [2, 2] if v["rule"] in ("R5", "N20", "N21", "M6", "V6", "Y38", "Y46", "Y54") else [9, 9] if v["rule"] in ("F9", "Q10", "Y55") else [6, 6],
            "ground": sc["ground"], "biome": sc["biome"],
            "build": blocks, "action": act, "wait_ticks": wait, "checks": plan_checks,
        })
    (DATA / "engine_plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"engine plan: {len(plan)} scenes, {sum(len(p['checks']) for p in plan)} checks")


if __name__ == "__main__":
    main()
