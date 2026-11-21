# Prompts

Exported verbatim from the scripts in `rulecraft/`. `{...}` marks a slot filled per question. The model replies with one letter, parsed by `llm.parse_letter`.

## The three conditions

**Image (C0): the bare image, then**

```text
Look at the image.
Action: {action}
{question}
A. {option A}
B. {option B}
C. {option C}
Reply with a single letter.
```

**Told (C2): the image, then**

```text
This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1). Answer according to the rules of vanilla Minecraft.
Look at the image.
Action: {action}
{question}
A. {option A}
B. {option B}
C. {option C}
Reply with a single letter.
```

**Text (T): no image**

```text
In vanilla Minecraft (Java Edition 1.20.1): {text_scene}
Action: {action}
{question}
A. {option A}
B. {option B}
C. {option C}
Reply with a single letter.
```

## Every other prompt kept as a constant

Module and name in each heading; prompts assembled inside a function are in the script the heading names.

### `pilot.FIXED_GAME`

```text
Answer according to the rules of the video game shown in the image, not according to real-world physics.
```

### `pilot.TAIL`

```text
Reply with a single letter.
```

### `pilot.COT_TAIL`

```text
Think step by step, then end your reply with 'Answer: <letter>'.
```

### `pilot.CARD_PROMPT`

```text
List the ways in which the behavior of blocks, liquids, plants, light, heat and other physical phenomena in vanilla Minecraft (Java Edition 1.20.1) DIFFERS from real-world physics. Only list differences, not similarities. Return JSON: {"departures": [{"id": "short-id", "objects": [affected blocks or items, lowercase; use "all blocks" if general], "except": [blocks excluded, if any], "trigger": "when it happens", "real_world": "what would happen in reality", "minecraft": "what happens in Minecraft"}]}. Give 20 to 40 entries.
```

### `gdc.FAMILIES`

```text
[GRV]
gravity and support: which blocks and objects fall, stay in place or drop when what holds them up is removed

[FLU]
liquids: how water and lava flow, spread and interact with blocks and objects

[PLA]
plants: what they need to survive, when they break and how they grow

[LHF]
light, heat and fire: melting, freezing, burning and what catches fire

[RXN]
materials and tools: what happens when blocks are broken, combined, or exposed to water, lava, weather or time
```

### `gdc.FAMILY_PROMPT`

```text
List the ways in which the following aspect of vanilla Minecraft (Java Edition 1.20.1) DIFFERS from real-world physics: {desc}. Only list differences, not similarities. Return JSON: {{"departures": [{{"id": "short-id", "objects": [affected blocks or items, lowercase; use "all blocks" if general], "except": [blocks excluded, if any], "trigger": "when it happens", "real_world": "what would happen in reality", "minecraft": "what happens in Minecraft"}}]}}. Give 8 to 20 entries.
```

### `gdc.CARD_HEAD`

```text
Notes on how vanilla Minecraft differs from real-world physics. Use a note only if it applies to the image. If the user's text states a rule change for this world, the stated rule overrides these notes.
```

### `gdc.GATE_PROMPT`

```text
Look at the image and read the question.
{q}
Do not answer the question. Return JSON with fields:
 world: one of "real_world", "minecraft_vanilla", "minecraft_modded", "other_game", "unknown";
 game_name: the name of the game if the image is from a game, else "";
 objects: the objects or blocks involved in the action or question (lowercase names).
```

### `gdc2.REASON_TAIL`

```text
First say briefly which note, if any, applies to the objects and the action in this image; if none applies, reason as you normally would. Then end your reply with 'Answer: <letter>'.
```

### `gdc2.SOFT_HEAD`

```text
Notes on how vanilla Minecraft differs from real-world physics. They were written from memory and may contain errors. Use a note only if it applies to the image, and if a note conflicts with something you are confident about, trust what you are confident about. If the user's text states a rule change for this world, the stated rule overrides these notes.
```

### `tune2.HEADS`

```text
[W0]
Notes on how vanilla Minecraft differs from real-world physics. Use a note only if it applies to the image. If the user's text states a rule change for this world, the stated rule overrides these notes.


[W1]
Notes on how vanilla Minecraft differs from real-world physics. They were written from memory and may contain errors. Use a note only if it applies to the image, and if a note conflicts with something you are confident about, trust what you are confident about. If the user's text states a rule change for this world, the stated rule overrides these notes.
```

### `tune2.AUDIT_PROMPT`

```text
Here is a claim about vanilla Minecraft, Java Edition 1.20.1, describing how it differs from real-world physics.
Applies to: {objects}{exc}
When: {trigger}
Claim: {minecraft}

Is the claim accurate for this version of the game, including for the objects it names? Check it against what you know of the game's actual mechanics. If it is not fully accurate, rewrite it so that it is, keeping it as specific as possible. If nothing accurate remains, give an empty string. Return JSON: {{"verdict": "accurate" or "partly" or "inaccurate", "reason": "one short sentence", "corrected": "the accurate claim"}}.
```

### `neutral_run.NEUTRAL`

```text
Answer according to the rules that govern the world shown in the image.
```

### `review_runs.NAME_ARMS`

```text
[NameOnly]
This image is a screenshot from Minecraft.


[NameVer]
This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1).
```

### `world_open.ASK`

```text
Which video game is this screenshot from? Reply with the name of the game only.
```

### `interp_run.G`

```text
G. what happens in the video game that the image comes from
```

### `interp_run.R`

```text
R. what would happen to such a scene in the real world
```

### `interp_run.DEPLOY`

```text
You are the assistant of a tool that analyses gameplay recordings. Users send a frame from a gameplay video and ask what happens next in the scene.
```

### `open_answer.TAIL`

```text
Describe what happens to {subject} in one or two sentences.
```

### `open_answer.JUDGE`

```text
A scene changes as described below, and there are three candidate outcomes. Someone looked at the scene and wrote a prediction. Decide which candidate outcome the prediction matches.

What happens to the scene: {action}
Candidate outcomes:
{options}

Prediction: "{answer}"

Reply with one letter only. A, B or C: the prediction matches that outcome; if it mentions several outcomes but settles on one, choose the one it settles on. D: it leaves two or more of the outcomes open, for example by saying that the result depends on whether the scene is real or a game. E: it matches none of the outcomes.
```

### `think_trace_classify.PROMPT`

```text
Below is a model's private reasoning about a question on an image. The image is a Minecraft screenshot, but the question did not say so. Two outcomes matter:
GAME outcome (what vanilla Minecraft does): {game}
REAL-WORLD outcome: {real}

Reasoning:
"""
{reasoning}
"""

Which description fits the reasoning best? Reply with one digit only.
1: It works out or states that in Minecraft the GAME outcome would hold, and it answers with the GAME outcome.
2: It states or concedes that in Minecraft the GAME outcome would hold (or that Minecraft does not simulate the change), but decides to answer by real-world logic or common sense instead.
3: It claims that Minecraft's own mechanics produce the REAL-WORLD outcome (a mistaken game rule).
4: It uses the word Minecraft only to describe the image or its style, and reasons about the outcome with real-world logic alone, without considering what the game's rules would give.
5: None of these.
```
