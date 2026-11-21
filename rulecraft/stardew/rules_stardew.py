"""Stardew Valley rules for the second-game extension (same format as rulecraft/terraria).

Each rule fixes its type, question and three options before any model answers it. Its four variants change the object
and the place on the farm. The SceneLab mod builds every variant in the game, performs the action or lets the days pass
through the game's own sleep, and reads back the state; check() says whether the game produced the outcome labelled
"game". Rules whose game outcome is not the one expected are dropped before any model sees them.

  python rules_stardew.py job   [--only R1,R2] [--variants 1] [--resume]   writes the SceneLab job (verification run)
  python rules_stardew.py check                                   reads the run, prints pass/fail per variant
  python rules_stardew.py items                                   writes items_stardew.json from the passing rules
"""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Stardew Valley\Mods\SceneLab\jobs\job.json")
RUN = HERE / "verify"
ORIGINS = [(50, 28), (56, 33), (45, 37), (61, 39)]       # four open patches of the standard farm (the "camera" of a variant)

SPRING_SEEDS = {"parsnip": "472", "potato": "475", "kale": "477", "cauliflower": "474", "garlic": "476", "green bean": "473"}
FALL_SEEDS = {"pumpkin": "490", "eggplant": "488", "bok choy": "491", "beet": "494"}


def at(d, **kw):
    return {"d": list(d), **kw}


def crop_state(s, d="0,0"):
    return (s.get(d) or {}).get("crop")


def obj(s, d="0,0"):
    return (s.get(d) or {}).get("obj")


def debris_ids(s):
    """Items dropped on the ground, plus items the farmer standing next to the scene picked up at once."""
    return [x.split("x")[0] for x in s.get("debris", []) + s.get("gained", [])]


# ------------------------------------------------------------------------------------------------------------ rules
# Each rule: id, category, question, options (game / real or over_departure / neither), variants: list of scene kwargs,
# build(v) -> scene dict (tiles, steps, season, day, rain_today, watch), check(before, after) -> bool for the game option.
RULES = []


def rule(**kw):
    RULES.append(kw)


# ---- passive conflict: only time or weather acts; the game leaves the scene as it is
rule(id="S_P01", category="passive_conflict",
     question="Nobody waters the young plants in the tilled soil, and three hot, sunny days pass. What do the plants look like at the end?",
     options={"game": "They look exactly the same as now.", "real": "They wilt, droop and start to dry out.",
              "neither": "They grow to full size and ripen."},
     variants=["parsnip", "potato", "kale", "cauliflower"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, crop=SPRING_SEEDS[v], phase=2), at((1, 0), hoe=True, crop=SPRING_SEEDS[v], phase=2)],
                          steps=[{"op": "days", "n": 3, "rain_all": False}]),
     check=lambda b, a: all(crop_state(a, k) and not crop_state(a, k)["dead"] and crop_state(a, k)["phase"] == crop_state(b, k)["phase"] for k in ("0,0", "1,0")))

rule(id="S_P02", category="passive_conflict",
     question="The vegetables in the image are ripe. Nobody picks them, and a week of sunny weather passes. What do they look like at the end of the week?",
     options={"game": "They are still ripe and ready to pick, just as now.", "real": "They become overripe and start to rot in the ground.",
              "neither": "They shrink back into small seedlings."},
     variants=["parsnip", "potato", "kale", "cauliflower"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, crop=SPRING_SEEDS[v], phase="grown"), at((1, 0), hoe=True, crop=SPRING_SEEDS[v], phase="grown")],
                          steps=[{"op": "days", "n": 7, "rain_all": False}]),
     check=lambda b, a: all(crop_state(a, k) and crop_state(a, k)["ready"] and not crop_state(a, k)["dead"] for k in ("0,0", "1,0")))

rule(id="S_P03", category="passive_conflict",
     question="The vegetables in the image are ripe. Nobody picks them, and it rains every day for a week. What do they look like at the end of the week?",
     options={"game": "They are still ripe and ready to pick, just as now.", "real": "They become waterlogged and start to rot.",
              "neither": "They are washed out of the soil."},
     variants=["garlic", "parsnip", "cauliflower", "potato"],
     build=lambda v: dict(season="spring", day=5, rain_today=True, tiles=[at((0, 0), hoe=True, crop=SPRING_SEEDS[v], phase="grown"), at((1, 0), hoe=True, crop=SPRING_SEEDS[v], phase="grown")],
                          steps=[{"op": "days", "n": 7, "rain_all": True}]),
     check=lambda b, a: all(crop_state(a, k) and crop_state(a, k)["ready"] and not crop_state(a, k)["dead"] for k in ("0,0", "1,0")))

rule(id="S_P04", category="passive_conflict",
     question="The torch stuck in the ground is lit. Nobody touches it for a week. What does it look like at the end of the week?",
     options={"game": "It is still burning, just as now.", "real": "It has burned down and gone out.", "neither": "It has turned into a small tree."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj="(O)93")] + ([at((2, 0), obj="(O)93")] if v % 2 else []),
                          steps=[{"op": "days", "n": 7, "rain_all": False}]),
     check=lambda b, a: obj(a) is not None and obj(a)["id"] == "(O)93" and obj(a)["on"])

rule(id="S_P05", category="passive_conflict",
     question="It is raining, and it keeps raining for three days. What does the lit torch look like at the end?",
     options={"game": "It is still burning, just as now.", "real": "The rain has put the flame out.", "neither": "It has grown taller."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, rain_today=True, tiles=[at((0, 0), obj="(O)93")] + ([at((-2, 0), obj="(O)93")] if v % 2 else []),
                          steps=[{"op": "days", "n": 3, "rain_all": True}]),
     check=lambda b, a: obj(a) is not None and obj(a)["on"])

rule(id="S_P06", category="passive_conflict",
     question="The campfire is burning. Nobody adds any wood, and a week passes. What does it look like at the end of the week?",
     options={"game": "It is still burning, just as now.", "real": "It has burned out, leaving a pile of ash.", "neither": "It has spread into a large blaze."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj="(BC)146", on=True)], steps=[{"op": "days", "n": 7, "rain_all": False}]),
     check=lambda b, a: obj(a) is not None and obj(a)["on"])

rule(id="S_P07", category="passive_conflict",
     question="The fruit on the tree is ripe. Nobody picks it, and a week passes. What does the tree look like at the end of the week?",
     options={"game": "The fruit is still hanging on the tree.", "real": "The fruit has fallen to the ground and started to rot.",
              "neither": "The tree has lost all its leaves."},
     variants=["628", "629", "628", "629"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), fruittree=v, stage=4, fruit=2)], steps=[{"op": "days", "n": 7, "rain_all": False}],
                          watch=[[0, 1], [1, 0], [-1, 0], [0, -1]]),
     check=lambda b, a: (a.get("0,0") or {}).get("fruittree", {}).get("fruit", 0) >= (b.get("0,0") or {}).get("fruittree", {}).get("fruit", 0) > 0)

rule(id="S_P08", category="passive_conflict",
     question="Nobody waters the young plants in the tilled soil, and a whole week of hot, sunny weather passes. What do the plants look like at the end?",
     options={"game": "They look exactly the same as now.", "real": "They have withered and died.", "neither": "They are covered in flowers."},
     variants=["garlic", "green bean", "parsnip", "kale"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, crop=SPRING_SEEDS[v], phase=1)], steps=[{"op": "days", "n": 7, "rain_all": False}]),
     check=lambda b, a: crop_state(a) and not crop_state(a)["dead"] and crop_state(a)["phase"] == crop_state(b)["phase"])

rule(id="S_P09", category="passive_conflict",
     question="It rains every day for a week, and nobody tends the seedlings in the tilled soil. What do they look like at the end of the week?",
     options={"game": "They are fully grown and ready to harvest.", "real": "They are a little taller, but still young plants.",
              "neither": "They have been washed away."},
     variants=["parsnip", "garlic", "parsnip", "garlic"],
     build=lambda v: dict(season="spring", day=5, rain_today=True, tiles=[at((0, 0), hoe=True, crop=SPRING_SEEDS[v], phase=1), at((1, 0), hoe=True, crop=SPRING_SEEDS[v], phase=1)],
                          steps=[{"op": "days", "n": 7, "rain_all": True}]),
     check=lambda b, a: all(crop_state(a, k) and crop_state(a, k)["ready"] for k in ("0,0", "1,0")))

rule(id="S_P10", category="passive_conflict",
     question="The weeds in the image are left alone for two weeks of warm, rainy spring weather. What do they look like at the end?",
     options={"game": "They look exactly the same as now.", "real": "They have grown taller and spread.", "neither": "They have turned into flowers."},
     variants=["(O)674", "(O)675", "(O)784", "(O)785"],
     build=lambda v: dict(season="spring", day=5, rain_today=True, tiles=[at((0, 0), obj=v), at((1, 0), obj=v)], steps=[{"op": "days", "n": 14, "rain_all": True}],
                          watch=[[0, 1], [1, 1], [-1, 0], [2, 0]]),
     check=lambda b, a: obj(a) is not None and obj(a)["id"] == obj(b)["id"])

rule(id="S_P11", category="passive_conflict",
     question="The wild plant growing in the grass is left alone for a week. What does it look like at the end of the week?",
     options={"game": "It looks exactly the same as now.", "real": "It has wilted and withered.", "neither": "It has turned into a bush."},
     variants=["(O)16", "(O)18", "(O)20", "(O)22"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj=v, spawned=True)], steps=[{"op": "days", "n": 7, "rain_all": False}]),
     check=lambda b, a: obj(a) is not None and obj(a)["id"] == obj(b)["id"])

rule(id="S_P12", category="passive_conflict",
     question="The pieces of wood lying on the ground are left out in the rain for three days. What has happened to them at the end?",
     options={"game": "They have disappeared from the ground.", "real": "They are still there, soaked and darker.", "neither": "They have sprouted into saplings."},
     variants=["(O)388", "(O)388", "(O)388", "(O)388"],
     build=lambda v: dict(season="spring", day=5, rain_today=True, tiles=[at((0, 0), drop=v, count=3)], steps=[{"op": "days", "n": 3, "rain_all": True}]),
     check=lambda b, a: len(b.get("debris", [])) > 0 and len(a.get("debris", [])) == 0)

rule(id="S_P13", category="passive_conflict",
     question="The tree stump in the image is left alone for a whole spring. What does it look like at the end?",
     options={"game": "It looks exactly the same as now.", "real": "New shoots have sprouted from it.", "neither": "It has grown back into a full tree."},
     variants=["1", "2", "3", "1"],
     build=lambda v: dict(season="spring", day=1, tiles=[at((0, 0), tree=v, stage=5, stump=True)],
                          steps=[{"op": "days", "n": 27, "rain_all": False}]),
     check=lambda b, a: (a.get("0,0") or {}).get("tree", {}).get("stump") is True)

rule(id="S_P14", category="passive_conflict",
     question="The wooden chest stands outdoors and it rains every day for two weeks. What does the chest look like at the end?",
     options={"game": "It looks exactly the same as now.", "real": "The wood has darkened and started to swell and warp.", "neither": "It has sunk into the ground."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, rain_today=True, tiles=[at((0, 0), obj="(BC)130", chest_items=[["(O)24", 5]])],
                          steps=[{"op": "days", "n": 14, "rain_all": True}]),
     check=lambda b, a: obj(a) is not None and obj(a)["id"] == "(BC)130")

# ---- action conflict: something is done to the scene
rule(id="S_A01", category="action_conflict",
     question="Someone chops the tree with an axe until it falls. What is left where the tree stood right afterwards?",
     options={"game": "A stump, with small pieces of wood scattered around it.", "real": "A stump, with the whole trunk lying on the ground beside it.",
              "neither": "Nothing at all; the ground is bare."},
     variants=["1", "2", "3", "1"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), tree=v, stage=5)], steps=[{"op": "tool", "tool": "axe", "d": [0, 0], "hits": 14, "settle": 300}]),
     check=lambda b, a: (a.get("0,0") or {}).get("tree", {}).get("stump") is True and "(O)388" in debris_ids(a))

rule(id="S_A02", category="action_conflict",
     question="Someone chops the tree with an axe until it falls. What happens to the plants growing right next to the tree?",
     options={"game": "They are untouched.", "real": "They are crushed by the falling tree.", "neither": "They are pulled out of the ground and replanted elsewhere."},
     variants=["parsnip", "cauliflower", "kale", "potato"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), tree="1", stage=5)] + [at(d, hoe=True, crop=SPRING_SEEDS[v], phase="grown") for d in ((-1, 0), (1, 0), (-1, 1), (1, 1))],
                          steps=[{"op": "tool", "tool": "axe", "d": [0, 0], "hits": 14, "settle": 300}]),
     check=lambda b, a: all(crop_state(a, k) and not crop_state(a, k)["dead"] and crop_state(a, k)["ready"] for k in ("-1,0", "1,0", "-1,1", "1,1")))

rule(id="S_A03", category="action_conflict",
     question="Someone hits the rock once with a pickaxe. What happens to the rock right afterwards?",
     options={"game": "It disappears, and a few loose stones pop out where it was.", "real": "It cracks, but stays in place.",
              "neither": "It rolls away across the field."},
     variants=["(O)343", "(O)450", "(O)343", "(O)450"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj=v)], steps=[{"op": "tool", "tool": "pickaxe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None and "(O)390" in debris_ids(a))

rule(id="S_A04", category="action_conflict",
     question="Someone hits the fallen branch once with an axe. What happens to the branch right afterwards?",
     options={"game": "It disappears, and a few small pieces of wood pop out where it was.", "real": "It is split, and the two halves stay on the ground.",
              "neither": "It bounces back up into a tree."},
     variants=["(O)294", "(O)295", "(O)294", "(O)295"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj=v)], steps=[{"op": "tool", "tool": "axe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None and "(O)388" in debris_ids(a))

rule(id="S_A05", category="action_conflict",
     question="Someone waters the seedlings in the tilled soil every morning for one week of sunny weather. What do they look like at the end of the week?",
     options={"game": "They are fully grown and ready to harvest.", "real": "They are a little taller, but still young plants.",
              "neither": "They have dried out and died."},
     variants=["parsnip", "garlic", "parsnip", "garlic"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, water=True, crop=SPRING_SEEDS[v], phase=1), at((1, 0), hoe=True, water=True, crop=SPRING_SEEDS[v], phase=1)],
                          steps=[{"op": "days", "n": 7, "rain_all": False, "water": [[0, 0], [1, 0]]}]),
     check=lambda b, a: all(crop_state(a, k) and crop_state(a, k)["ready"] for k in ("0,0", "1,0")))

rule(id="S_A06", category="action_conflict",
     question="Someone hits the wooden chest once with a pickaxe. What happens to the chest right afterwards?",
     options={"game": "It pops off the ground in one piece, completely intact.", "real": "Its wood splinters and cracks where it was hit.",
              "neither": "It sinks into the ground."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj="(BC)130")], steps=[{"op": "tool", "tool": "pickaxe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None and "(BC)130" in debris_ids(a))

rule(id="S_A07", category="action_conflict",
     question="Someone hits the lit torch once with a pickaxe. What happens to the torch right afterwards?",
     options={"game": "It pops out of the ground whole, and the flame is gone.", "real": "It snaps in two, and the burning end falls to the ground.",
              "neither": "It flies up into the sky."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj="(O)93")], steps=[{"op": "tool", "tool": "pickaxe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None and "(O)93" in debris_ids(a))

rule(id="S_A08", category="action_conflict",
     question="Someone hits the fence post once with an axe. What happens to the fence post right afterwards?",
     options={"game": "It pops out of the ground in one piece, completely intact.", "real": "It gets a deep cut, but stays standing.",
              "neither": "It turns to stone."},
     variants=["(O)322", "(O)298", "(O)322", "(O)298"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj=v)], steps=[{"op": "tool", "tool": "axe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None and any(x == obj(b)["id"] for x in debris_ids(a)))

rule(id="S_A09", category="action_conflict",
     question="Someone hits the burning campfire once with a pickaxe. What happens right afterwards?",
     options={"game": "The whole campfire pops off the ground in one piece, and the fire is gone.", "real": "The burning logs are knocked apart and scattered.",
              "neither": "The fire grows twice as large."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj="(BC)146", on=True)], steps=[{"op": "tool", "tool": "pickaxe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None and "(BC)146" in debris_ids(a))

rule(id="S_A10", category="action_conflict",
     question="Someone cuts the weeds with a scythe. What is left where the weeds were right afterwards?",
     options={"game": "Nothing but a few loose fibers on the bare ground.", "real": "Short cut stems still rooted in the ground.",
              "neither": "Taller weeds than before."},
     variants=["(O)674", "(O)675", "(O)784", "(O)785"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj=v)], steps=[{"op": "tool", "tool": "scythe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None)

rule(id="S_A11", category="action_conflict",
     question="Someone chops the small sapling once with an axe. What happens to it right afterwards?",
     options={"game": "It disappears completely, leaving nothing on the ground.", "real": "It is cut off, and the cut stem lies on the ground.",
              "neither": "It grows into a full tree."},
     variants=["1", "2", "3", "1"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), tree=v, stage=2)], steps=[{"op": "tool", "tool": "axe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: (b.get("0,0") or {}).get("tf") == "Tree" and (a.get("0,0") or {}).get("tf") is None and not debris_ids(a))

rule(id="S_A12", category="action_conflict",
     question="Someone chops the tree with an axe until it falls. What happens to the wooden chest standing right next to it?",
     options={"game": "It is untouched.", "real": "It is smashed by the falling tree.", "neither": "It is thrown over the fence."},
     variants=["1", "2", "3", "1"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), tree=v, stage=5), at((1, 0), obj="(BC)130"), at((-1, 0), obj="(BC)130")],
                          steps=[{"op": "tool", "tool": "axe", "d": [0, 0], "hits": 14, "settle": 300}]),
     check=lambda b, a: obj(a, "1,0") is not None and obj(a, "-1,0") is not None)

# ---- consistent: the game simulates the change, and reality agrees
rule(id="S_C01", category="consistent",
     question="The tilled soil was watered this morning. A hot, sunny day passes and nobody waters it again. What does the soil look like the next morning?",
     options={"game": "It has dried out and turned lighter.", "over_departure": "It looks exactly as wet as now.", "neither": "It has turned into grass."},
     variants=[1, 2, 3, 4],
     build=lambda v: dict(season="spring", day=5, tiles=[at((k, 0), hoe=True, water=True) for k in range(v)], steps=[{"op": "days", "n": 1, "rain_all": False}]),
     check=lambda b, a: (a.get("0,0") or {}).get("watered") is False and (b.get("0,0") or {}).get("watered") is True)

rule(id="S_C02", category="consistent",
     question="The tilled soil is dry. It rains all night. What does the soil look like the next morning?",
     options={"game": "It is dark and wet.", "over_departure": "It looks exactly as dry as now.", "neither": "It has turned into a puddle of mud that covers the field."},
     variants=[1, 2, 3, 4],
     build=lambda v: dict(season="spring", day=5, tiles=[at((k, 0), hoe=True) for k in range(v)], steps=[{"op": "days", "n": 1, "rain_all": True}]),
     check=lambda b, a: (a.get("0,0") or {}).get("watered") is True)

rule(id="S_C03", category="consistent",
     question="It is the last day of autumn. Overnight, winter arrives with freezing cold. What do the crops in the tilled soil look like the next morning?",
     options={"game": "They have died from the cold.", "over_departure": "They look exactly the same as now.", "neither": "They are ripe and twice as large."},
     variants=["pumpkin", "eggplant", "bok choy", "beet"],
     build=lambda v: dict(season="fall", day=28, tiles=[at((0, 0), hoe=True, water=True, crop=FALL_SEEDS[v], phase=2), at((1, 0), hoe=True, water=True, crop=FALL_SEEDS[v], phase=2)],
                          steps=[{"op": "days", "n": 1, "rain_all": False}]),
     check=lambda b, a: all((crop_state(a, k) or {}).get("dead") for k in ("0,0", "1,0")))

rule(id="S_C04", category="consistent",
     question="Someone chops the tree with an axe many times. What happens to the tree?",
     options={"game": "It is cut down.", "over_departure": "It stays standing, without a scratch.", "neither": "It turns into stone."},
     variants=["1", "2", "3", "1"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), tree=v, stage=5)], steps=[{"op": "tool", "tool": "axe", "d": [0, 0], "hits": 14, "settle": 300}]),
     check=lambda b, a: (a.get("0,0") or {}).get("tree", {}).get("stump") is True)

rule(id="S_C05", category="consistent",
     question="Someone waters the young plants in the tilled soil every morning for three sunny days. What do they look like at the end?",
     options={"game": "They have grown bigger.", "over_departure": "They look exactly the same as now.", "neither": "They have dried out and died."},
     variants=["cauliflower", "kale", "potato", "green bean"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, water=True, crop=SPRING_SEEDS[v], phase=1), at((1, 0), hoe=True, water=True, crop=SPRING_SEEDS[v], phase=1)],
                          steps=[{"op": "days", "n": 3, "rain_all": False, "water": [[0, 0], [1, 0]]}]),
     check=lambda b, a: all(crop_state(a, k) and crop_state(a, k)["phase"] > crop_state(b, k)["phase"] and not crop_state(a, k)["dead"] for k in ("0,0", "1,0")))

rule(id="S_C06", category="consistent",
     question="Someone pulls up one of the ripe vegetables by hand. What is left in that spot right afterwards?",
     options={"game": "Bare tilled soil.", "over_departure": "The same ripe vegetable, still growing there.", "neither": "A small tree."},
     variants=["parsnip", "potato", "cauliflower", "kale"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, crop=SPRING_SEEDS[v], phase="grown"), at((1, 0), hoe=True, crop=SPRING_SEEDS[v], phase="grown")],
                          steps=[{"op": "harvest", "d": [0, 0]}]),
     check=lambda b, a: (a.get("0,0") or {}).get("tf") == "HoeDirt" and crop_state(a) is None)

rule(id="S_C07", category="consistent",
     question="Seeds were just planted in the tilled soil. Nobody waters them, and three hot, sunny days pass. What does the soil look like at the end?",
     options={"game": "Still bare, with no sprouts.", "over_departure": "Covered in fully grown plants.", "neither": "Covered in snow."},
     variants=["parsnip", "potato", "kale", "cauliflower"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, crop=SPRING_SEEDS[v], phase=0), at((1, 0), hoe=True, crop=SPRING_SEEDS[v], phase=0)],
                          steps=[{"op": "days", "n": 3, "rain_all": False}]),
     check=lambda b, a: all(crop_state(a, k) and crop_state(a, k)["phase"] == 0 for k in ("0,0", "1,0")))

rule(id="S_C08", category="consistent",
     question="Someone pours water from a watering can onto the dry tilled soil. What does the soil look like right afterwards?",
     options={"game": "It is dark and wet.", "over_departure": "It looks exactly as dry as now.", "neither": "It has turned into a pond."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True)] + ([at((1, 0), hoe=True)] if v % 2 else []),
                          steps=[{"op": "tool", "tool": "can", "d": [0, 0], "hits": 1, "settle": 60}]),
     check=lambda b, a: (a.get("0,0") or {}).get("watered") is True)

rule(id="S_C09", category="consistent",
     question="Someone picks the ripe strawberries from one of the plants by hand. What is left in that spot right afterwards?",
     options={"game": "The strawberry plant, still growing there.", "over_departure": "Bare tilled soil.", "neither": "A small tree."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), hoe=True, crop="745", phase="grown"), at((1, 0), hoe=True, crop="745", phase="grown")],
                          steps=[{"op": "harvest", "d": [0, 0]}]),
     check=lambda b, a: crop_state(a) is not None and not crop_state(a)["ready"])

rule(id="S_C10", category="consistent",
     question="Someone hits the rock with a pickaxe again and again. What happens to the rock?",
     options={"game": "It breaks apart.", "over_departure": "It stays in place, without a scratch.", "neither": "It melts."},
     variants=["(O)343", "(O)450", "(O)343", "(O)450"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj=v)], steps=[{"op": "tool", "tool": "pickaxe", "d": [0, 0], "hits": 4, "settle": 120}]),
     check=lambda b, a: obj(a) is None)

rule(id="S_C11", category="consistent",
     question="Someone cuts the weeds with a scythe. What happens to the weeds?",
     options={"game": "They are cut down.", "over_departure": "They stay standing, untouched.", "neither": "They burst into flames."},
     variants=["(O)674", "(O)675", "(O)784", "(O)785"],
     build=lambda v: dict(season="spring", day=5, tiles=[at((0, 0), obj=v), at((1, 0), obj=v)], steps=[{"op": "tool", "tool": "scythe", "d": [0, 0], "hits": 1, "settle": 120}]),
     check=lambda b, a: obj(a) is None)

rule(id="S_C12", category="consistent",
     question="Someone turns the grassy ground over with a hoe. What does that spot look like right afterwards?",
     options={"game": "Freshly tilled, bare soil.", "over_departure": "The same untouched ground as before.", "neither": "A deep hole full of water."},
     variants=[0, 1, 2, 3],
     build=lambda v: dict(season="spring", day=5, tiles=[], watch=[[0, 0]], steps=[{"op": "tool", "tool": "hoe", "d": [0, 0], "hits": 1, "settle": 60}]),
     check=lambda b, a: (a.get("0,0") or {}).get("tf") == "HoeDirt")


# ------------------------------------------------------------------------------------------------------------ job and checks
def scene(r, k):
    v = r["variants"][k]
    s = r["build"](v)
    sc = {"id": f"{r['id']}_V{k + 1}", "season": s["season"], "day": s["day"], "origin": list(ORIGINS[k]),
          "rain_today": s.get("rain_today", False), "tiles": s["tiles"], "steps": s["steps"], "watch": s.get("watch", [])}
    if not sc["tiles"] and not sc["watch"]:
        sc["watch"] = [[0, 0]]
    return sc


def job(only=None, variants=4, resume=False, shots=False):
    items = [scene(r, k) for r in RULES if not only or r["id"] in only for k in range(variants)]
    out = RUN
    if shots:                                    # question images only: the verified scenes, built again with no steps
        keep = {i["id"] for i in json.loads((HERE / "items_stardew.json").read_text(encoding="utf-8"))["items"]}
        items = [dict(s, steps=[]) for s in items if s["id"] in keep]
        out = HERE / "shots"
    if resume:                                   # skip scenes whose engine record is already on disk
        items = [s for s in items if not (RUN / f"{s['id']}.json").exists()]
    out.mkdir(exist_ok=True)
    GAME.write_text(json.dumps({"out": str(out).replace("\\", "/"), "exit": True, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"job: {len(items)} scenes -> {GAME}")


def check():
    ok_rules, rows = {}, []
    for r in RULES:
        res = []
        for k in range(len(r["variants"])):
            f = RUN / f"{r['id']}_V{k + 1}.json"
            if not f.exists():
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("error"):
                res.append((k + 1, "ERROR " + d["error"][:120]))
                continue
            try:
                ok = bool(r["check"](d["before"], d["after"]))
            except (KeyError, TypeError) as e:
                ok = f"check failed: {e!r}"
            res.append((k + 1, ok))
        ok_rules[r["id"]] = res
        print(r["id"], r["category"], res)
    return ok_rules


def items():
    """Questions for the passing variants; option order shuffled with a fixed seed per item (as in the other games)."""
    out = []
    for r in RULES:
        for k in range(len(r["variants"])):
            iid = f"{r['id']}_V{k + 1}"
            f = RUN / f"{iid}.json"
            if not f.exists():
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("error") or not r["check"](d["before"], d["after"]):
                continue
            keys = list(r["options"])
            random.Random(iid).shuffle(keys)
            out.append({"id": iid, "base_rule": r["id"], "variant": k + 1, "category": r["category"], "question_en": r["question"],
                        "options": r["options"], "options_ordered": keys, "correct_key": "game", "correct_letter": "ABC"[keys.index("game")],
                        "image": f"{iid}_before.png"})
    (HERE / "items_stardew.json").write_text(json.dumps({"items": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"items_stardew.json: {len(out)} items")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["job", "check", "items"])
    ap.add_argument("--only", default="")
    ap.add_argument("--variants", type=int, default=4)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--shots", action="store_true")
    a = ap.parse_args()
    if a.cmd == "job":
        job([x for x in a.only.split(",") if x], a.variants, a.resume, a.shots)
    elif a.cmd == "check":
        check()
    else:
        items()
