"""Rule library for the pilot.

Each rule describes one scene template, one action, and the outcome options. Outcomes follow the
Minecraft Wiki (Java Edition 1.20.1); they are construction labels until the engine check confirms them.

Option keys:
  vanilla - what vanilla Minecraft does
  real    - what real-world physics predicts
  third   - an outcome that is neither; it becomes correct only under the declared mod (context C3)
For consistent rules vanilla == real, and "over" is the Minecraft-flavoured wrong answer.
"""

# Block lists used by variants. Every name must exist in minecraft-data 1.20.1.
NON_GRAVITY = ["dirt", "stone", "oak_planks", "cobblestone"]

RULES = [
    # ---------------- conflict rules (test) ----------------
    dict(
        id="G1", split="test", kind="conflict", family="gravity", familiarity="high",
        departure="MC-GRAVITY-FLOAT",
        scene="block_on_pillar", target_choices=NON_GRAVITY, support="oak_log",
        action="The {support_name} under the {target_name} is broken and removed.",
        options=dict(
            vanilla="The {target_name} stays exactly where it was, floating in mid-air.",
            real="The {target_name} falls down onto the ground.",
            third="The {target_name} breaks apart and disappears.",
        ),
        mod="any block that loses the block supporting it breaks apart and disappears",
        k_pairs=[
            ("In Minecraft, when the block under a {target_name} block is removed, the {target_name} block stays where it was.",
             "In Minecraft, when the block under a {target_name} block is removed, the {target_name} block falls down."),
            ("In Minecraft, a {target_name} block can float in mid-air with nothing beneath it.",
             "In Minecraft, a {target_name} block cannot stay in mid-air with nothing beneath it."),
        ],
        p_pair=("The {target_name} is resting directly on top of a {support_name}.",
                "The {target_name} is resting directly on the grass ground."),
        text_scene="A single {target_name} block sits on top of a single {support_name} block, which stands on a flat grass field.",
    ),
    dict(
        id="G2", split="test", kind="conflict", family="gravity", familiarity="high",
        departure="MC-GRAVITY-FLOAT",
        scene="tree", target_choices=["oak", "birch", "spruce"], support=None,
        action="The bottom log of the {target_name} tree's trunk is chopped and removed.",
        options=dict(
            vanilla="The rest of the trunk and the leaves stay where they were, floating above the ground.",
            real="The tree topples over and falls to the ground.",
            third="The whole tree instantly disappears.",
        ),
        mod="when the bottom log of a tree is removed, the entire tree instantly disappears",
        k_pairs=[
            ("In Minecraft, if you chop only the bottom log of a tree, the logs above it stay floating in place.",
             "In Minecraft, if you chop only the bottom log of a tree, the tree falls over."),
            ("In Minecraft, tree trunks do not fall when their lowest log is removed.",
             "In Minecraft, tree trunks fall when their lowest log is removed."),
        ],
        p_pair=("The tree trunk stands directly on the ground.",
                "The tree is lying on its side on the ground."),
        text_scene="A small {target_name} tree stands on a flat grass field: a vertical trunk of four logs topped with leaves.",
    ),
    dict(
        id="A1", split="test", kind="conflict", family="attachment", familiarity="mid",
        departure="MC-CACTUS-BREAK",
        scene="cactus", target_choices=["cobblestone", "stone", "oak_planks", "dirt"], support="sand",
        action="A {target_name} block is placed on the ground directly next to the cactus, touching its side.",
        options=dict(
            vanilla="The cactus breaks and pops off as a dropped item.",
            real="Nothing happens to the cactus; it stays standing.",
            third="The newly placed {target_name} block breaks, and the cactus stays.",
        ),
        mod="a block placed next to a cactus breaks immediately, while the cactus is not affected",
        k_pairs=[
            ("In Minecraft, placing a solid block right next to a cactus makes the cactus break.",
             "In Minecraft, placing a solid block right next to a cactus does not affect the cactus."),
            ("In Minecraft, a cactus cannot have a solid block touching its sides.",
             "In Minecraft, a cactus can have a solid block touching its sides."),
        ],
        p_pair=("The cactus is growing out of sand.",
                "The cactus is growing out of grass."),
        text_scene="A two-block-tall cactus grows on a sand block in an otherwise flat grass field; no other blocks touch it.",
    ),
    dict(
        id="L1", split="test", kind="conflict", family="light_heat", familiarity="low",
        departure="MC-ICE-SKYLIGHT",
        scene="ice_desert", target_choices=["ice"], support="sand",
        action="A whole day passes under bright, direct sunlight. There are no torches or other light sources nearby.",
        options=dict(
            vanilla="The ice block stays completely unchanged.",
            real="The ice block melts into water.",
            third="The ice block vanishes without leaving any water.",
        ),
        mod="sunlight makes ice vanish without leaving any water",
        k_pairs=[
            ("In Minecraft, sunlight alone does not melt ice.",
             "In Minecraft, ice placed in bright sunlight melts."),
            ("In Minecraft, ice only melts from nearby block light such as torches, not from the sun.",
             "In Minecraft, ice melts in hot sunny biomes such as deserts."),
        ],
        p_pair=("The ice block is sitting on sand.",
                "The ice block is sitting on snow."),
        text_scene="A single block of ice sits on the sand of a hot desert at noon, far from any torches or other light sources.",
    ),
    dict(
        id="L2", split="test", kind="conflict", family="light_heat", familiarity="mid",
        departure="MC-TORCH-NO-FIRE",
        scene="torch_wall", target_choices=["oak_planks", "spruce_planks", "birch_planks"], support=None,
        action="Several days pass with the torch burning against the wooden wall.",
        options=dict(
            vanilla="The wooden wall stays undamaged and the torch keeps burning.",
            real="The wood around the torch gets scorched or catches fire.",
            third="The torch burns out and drops to the ground, and the wall is undamaged.",
        ),
        mod="wall torches burn out and drop after a few days",
        k_pairs=[
            ("In Minecraft, a torch placed on a wooden wall never sets the wood on fire.",
             "In Minecraft, a torch placed on a wooden wall eventually sets the wood on fire."),
            ("In Minecraft, torches are not a source of fire for nearby blocks.",
             "In Minecraft, torches can ignite nearby flammable blocks."),
        ],
        p_pair=("The torch is attached to the side of a wooden wall.",
                "The torch is standing on the ground away from any wall."),
        text_scene="A lit torch is attached to the side of a wall made of {target_name}.",
    ),
    dict(
        id="R4", split="test", kind="conflict", family="reaction", familiarity="low",
        departure="MC-CONCRETE-HARDEN",
        scene="block_on_ground", target_choices=["white_concrete_powder", "red_concrete_powder", "blue_concrete_powder", "lime_concrete_powder"], support=None,
        action="A bucket of water is poured so that water flows directly against the side of the {target_name} block.",
        options=dict(
            vanilla="The {target_name} instantly hardens into a solid concrete block.",
            real="The {target_name} gets soaked and partly washes away; it does not instantly become solid.",
            third="The {target_name} turns into a block of sand.",
        ),
        mod="concrete powder turns into sand when it touches water",
        k_pairs=[
            ("In Minecraft, concrete powder turns into solid concrete as soon as it touches water.",
             "In Minecraft, concrete powder needs hours of curing after touching water before it becomes concrete."),
            ("In Minecraft, touching water instantly converts concrete powder into concrete.",
             "In Minecraft, touching water washes concrete powder away."),
        ],
        p_pair=("There is a single block of concrete powder on the ground.",
                "There is a single block of glass on the ground."),
        text_scene="A single {target_name} block sits on a flat grass field, with nothing next to it.",
    ),
    dict(
        id="R5", split="test", kind="conflict", family="reaction", familiarity="mid",
        departure="MC-ICE-BREAK-WATER",
        scene="block_on_pillar", target_choices=["ice"], support_choices=["stone", "cobblestone", "dirt", "oak_planks"],
        action="The ice block is broken by hand (no special enchantments).",
        options=dict(
            vanilla="A block of water appears where the ice block was.",
            real="Broken pieces of ice are left lying on the {support_name}.",
            third="Nothing at all is left where the ice block was.",
        ),
        mod="broken ice leaves nothing behind",
        k_pairs=[
            ("In Minecraft, breaking an ice block that has a block under it leaves a water block in its place.",
             "In Minecraft, breaking an ice block leaves ice fragments behind."),
            ("In Minecraft, ice turns into water when it is broken by hand above a solid block.",
             "In Minecraft, ice broken by hand simply disappears and leaves nothing."),
        ],
        p_pair=("The ice block is resting on top of a {support_name} block.",
                "The ice block is resting directly on the grass ground."),
        text_scene="A single ice block sits on top of a {support_name} block on a flat grass field.",
    ),
    dict(
        id="T1", split="test", kind="conflict", family="gravity", familiarity="mid", trap_of="S1",
        departure="MC-GRAVITY-FLOAT",
        scene="block_on_pillar", target_choices=["sandstone", "smooth_sandstone", "red_sandstone", "cut_sandstone"], support="oak_log",
        action="The {support_name} under the {target_name} is broken and removed.",
        options=dict(
            vanilla="The {target_name} stays exactly where it was, floating in mid-air.",
            real="The {target_name} falls down onto the ground.",
            third="The {target_name} breaks apart and disappears.",
        ),
        mod="any block that loses the block supporting it breaks apart and disappears",
        k_pairs=[
            ("In Minecraft, sandstone is not affected by gravity, unlike sand.",
             "In Minecraft, sandstone falls when unsupported, just like sand."),
            ("In Minecraft, a sandstone block with nothing under it stays in place.",
             "In Minecraft, a sandstone block with nothing under it falls down."),
        ],
        p_pair=("The block on top of the log is sandstone.",
                "The block on top of the log is sand."),
        text_scene="A single {target_name} block sits on top of a single {support_name} block, which stands on a flat grass field.",
    ),
    # ---------------- consistent rules (test) ----------------
    dict(
        id="S1", split="test", kind="consistent", family="gravity", familiarity="high",
        departure=None,
        scene="block_on_pillar", target_choices=["sand", "red_sand"], support="oak_log",
        action="The {support_name} under the {target_name} is broken and removed.",
        options=dict(
            correct="The {target_name} falls down onto the ground.",
            over="The {target_name} stays exactly where it was, floating in mid-air.",
            third="The {target_name} breaks apart and disappears.",
        ),
        mod="sand is not affected by gravity and stays where it is",
        mod_answer="over",
        k_pairs=[
            ("In Minecraft, a sand block falls when the block under it is removed.",
             "In Minecraft, a sand block stays floating when the block under it is removed."),
            ("In Minecraft, sand is affected by gravity.",
             "In Minecraft, sand is not affected by gravity."),
        ],
        p_pair=("The {target_name} is resting directly on top of a {support_name}.",
                "The {target_name} is resting directly on the grass ground."),
        text_scene="A single {target_name} block sits on top of a single {support_name} block, which stands on a flat grass field.",
    ),
    dict(
        id="S2", split="test", kind="consistent", family="gravity", familiarity="mid",
        departure=None,
        scene="block_on_pillar", target_choices=["gravel"], support_choices=["oak_log", "stone", "cobblestone", "oak_planks"],
        action="The {support_name} under the {target_name} is broken and removed.",
        options=dict(
            correct="The {target_name} falls down onto the ground.",
            over="The {target_name} stays exactly where it was, floating in mid-air.",
            third="The {target_name} breaks apart and disappears.",
        ),
        mod="gravel is not affected by gravity and stays where it is",
        mod_answer="over",
        k_pairs=[
            ("In Minecraft, gravel falls when the block under it is removed.",
             "In Minecraft, gravel stays floating when the block under it is removed."),
            ("In Minecraft, gravel is affected by gravity.",
             "In Minecraft, gravel is not affected by gravity."),
        ],
        p_pair=("The gravel is resting directly on top of a {support_name}.",
                "The gravel is resting directly on the grass ground."),
        text_scene="A single gravel block sits on top of a single {support_name} block, which stands on a flat grass field.",
    ),
    dict(
        id="S3", split="test", kind="consistent", family="attachment", familiarity="mid",
        departure=None,
        scene="flower_on_block", target_choices=["poppy", "dandelion", "cornflower", "oxeye_daisy"], support="grass_block",
        action="The grass block under the {target_name} is broken and removed.",
        options=dict(
            correct="The {target_name} drops down; it does not stay in the air.",
            over="The {target_name} stays exactly where it was, floating in mid-air.",
            third="The {target_name} turns into a sapling.",
        ),
        mod="flowers stay in place even when the block under them is removed",
        mod_answer="over",
        k_pairs=[
            ("In Minecraft, a flower drops when the block it is planted on is removed.",
             "In Minecraft, a flower keeps floating when the block it is planted on is removed."),
            ("In Minecraft, flowers need a block under them to stay in place.",
             "In Minecraft, flowers can stay in place with nothing under them."),
        ],
        p_pair=("The {target_name} is planted on top of a grass block that sits on a log.",
                "The {target_name} is planted directly in the ground."),
        text_scene="A {target_name} is planted on a grass block that sits on top of an oak log standing on a flat grass field.",
    ),
    dict(
        id="S4", split="test", kind="consistent", family="attachment", familiarity="mid",
        departure=None,
        scene="torch_on_block", target_choices=["stone", "cobblestone", "oak_planks", "dirt"], support=None,
        action="The {target_name} block that the torch is attached to is broken and removed.",
        options=dict(
            correct="The torch drops down; it does not stay in the air.",
            over="The torch stays exactly where it was, floating in mid-air.",
            third="The torch goes out but stays where it was.",
        ),
        mod="torches stay in place even when the block they are attached to is removed",
        mod_answer="over",
        k_pairs=[
            ("In Minecraft, a torch drops when the block it is attached to is removed.",
             "In Minecraft, a torch keeps floating when the block it is attached to is removed."),
            ("In Minecraft, a torch needs a block to be attached to.",
             "In Minecraft, a torch can hang in mid-air on its own."),
        ],
        p_pair=("The torch is attached to the side of a {target_name} block.",
                "The torch is standing on the ground."),
        text_scene="A lit torch is attached to the side of a single {target_name} block that sits on a pillar of two stone blocks.",
    ),
    # ---------------- dev rules (prompt tuning only) ----------------
    dict(
        id="D1", split="dev", kind="conflict", family="gravity", familiarity="mid",
        departure="MC-GRAVITY-FLOAT",
        scene="block_on_pillar", target_choices=["glass", "bricks"], support="oak_log",
        action="The {support_name} under the {target_name} is broken and removed.",
        options=dict(
            vanilla="The {target_name} stays exactly where it was, floating in mid-air.",
            real="The {target_name} falls down onto the ground.",
            third="The {target_name} breaks apart and disappears.",
        ),
        mod="any block that loses the block supporting it breaks apart and disappears",
        k_pairs=[
            ("In Minecraft, a glass block with nothing under it stays in place.",
             "In Minecraft, a glass block with nothing under it falls down."),
        ],
        p_pair=("The {target_name} is resting directly on top of a {support_name}.",
                "The {target_name} is resting directly on the grass ground."),
        text_scene="A single {target_name} block sits on top of a single {support_name} block, which stands on a flat grass field.",
    ),
    dict(
        id="D2", split="dev", kind="consistent", family="gravity", familiarity="mid",
        departure=None,
        scene="block_on_pillar", target_choices=["anvil"], support="oak_log",
        action="The {support_name} under the anvil is broken and removed.",
        options=dict(
            correct="The anvil falls down onto the ground.",
            over="The anvil stays exactly where it was, floating in mid-air.",
            third="The anvil breaks apart and disappears.",
        ),
        mod="anvils are not affected by gravity and stay where they are",
        mod_answer="over",
        k_pairs=[
            ("In Minecraft, an anvil falls when the block under it is removed.",
             "In Minecraft, an anvil stays floating when the block under it is removed."),
        ],
        p_pair=("The anvil is resting directly on top of a {support_name}.",
                "The anvil is resting directly on the grass ground."),
        text_scene="An anvil sits on top of a single {support_name} block, which stands on a flat grass field.",
    ),
]

from rules_round2 import ROUND2  # noqa: E402
from rules_round3 import ROUND3  # noqa: E402
from rules_round4 import ROUND4  # noqa: E402
from rules_round5 import ROUND5  # noqa: E402
from rules_round6 import ROUND6_DEV  # noqa: E402
from rules_round7 import ROUND7  # noqa: E402

RULES += ROUND2 + ROUND3 + ROUND4 + ROUND5 + ROUND6_DEV + ROUND7     # new rules are only ever appended: scenes and sites follow this order
RULE_BY_ID = {r["id"]: r for r in RULES}


def pretty(block_name):
    """minecraft id -> readable name used in prompts."""
    return block_name.replace("_", " ")
