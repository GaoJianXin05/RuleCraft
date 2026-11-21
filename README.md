# 🎮 RuleCraft

**Code for the paper *Multimodal LLMs Know the Game but Assume the Real World*.**

[![Dataset](https://img.shields.io/badge/🤗%20Dataset-RuleCraft-yellow)](https://huggingface.co/datasets/GGjx/RuleCraft)
[![Code license: MIT](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Data license: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)

Show a multimodal model a Minecraft screenshot of a block of dirt floating in mid-air and ask what happens next. The
model knows that in Minecraft the dirt stays put, and it recognizes the game, yet it answers that the dirt falls. It
predicts what reality would do. **RuleCraft** measures this gap between *knowing* a game's rules and *using* them.

## ✨ Highlights

- 🧱 **1,240 image questions over 155 Minecraft rules.** Every outcome is checked in the game engine. Each question
  is asked three ways: in **Text**, on the image with the game named (**Told**), and on the bare **Image**.
- 📉 **Naming the game raises accuracy a lot.** Six widely used models know the rules (Text) and recognize the game,
  yet naming it raises their accuracy by 8.2–19.8 points on the main set and by 33.8–52.7 points on the hard set.
- 🌍 **Errors follow real-world physics.** The gap is largest where the game leaves a scene unchanged, for example
  when only time or weather acts.
- 🕹️ **Two more games, same pattern.** It recurs in Terraria and Stardew Valley. It also holds with reasoning turned
  on, and with open models whose layers can be inspected.
- 🔁 **Reproducible without an API key.** Every model answer is released, and one script recomputes the main tables
  from them.

## 📦 What is in this repository

```
RuleCraft/
├── analysis/reproduce.py     🔁 recompute Tables 1, 5 and 7 of the paper from the released answers
├── scripts/link_data.py      🔗 put the downloaded dataset where the code expects it
├── rulecraft/                🧪 benchmark construction and every experiment (run scripts from this folder)
│   ├── rules*.py             the rules: rules_round2-5.py = main set, rules_round7.py = hard set,
│   │                         rules_round6.py = development pool (not evaluated)
│   ├── scenes*.py, engine_plan.py   scene of every variant and the commands that check it in the engine
│   ├── engine/verify.js      engine check on a vanilla Minecraft Java Edition 1.20.1 server (Mineflayer bot)
│   ├── render/render.js      renders the question images (prismarine-viewer, headless browser)
│   ├── pilot.py              questions and answer conditions: Image (C0), Told (C2), Text (T), CoT, GKP, ...
│   ├── llm.py                API client: profiles of the six models, cache, retries, spend cap, answer parser
│   ├── item_sets.py          question groups and the two-level bootstrap used by the analyses
│   ├── *_run.py, nothink.py, ...   one script per experiment (see the table below)
│   ├── data/items.json       all 1,240 questions with options, answer keys and text scenes
│   ├── terraria/, stardew/   the two extra games: rules, question builders, server plugin and game mod (source)
│   ├── openvlm/              open models: answers, logit lens and steering
│   └── Key.env.example       template for your API keys
├── human_study/              🧑‍🤝‍🧑 the answer page builder, question sampling, translations and the scorer
├── PROMPTS.md                💬 every prompt constant, verbatim
├── requirements.txt
└── LICENSE
```

The data (questions, images, model answers, engine checks and human answers) is on Hugging Face:
🤗 [`GGjx/RuleCraft`](https://huggingface.co/datasets/GGjx/RuleCraft).

## 🧱 The benchmark at a glance

| Set | Rules | Questions | Conflict / consistent rules | What makes it hard |
|---|---:|---:|---|---|
| Main | 95 | 760 | 67 / 28 | Rules where Minecraft departs from reality, mixed with rules where both agree |
| Hard | 60 | 480 | 47 / 13 | Mostly *passive* rules, where only time or weather acts and the game changes nothing |
| Terraria | 40 | 160 | 28 / 12 | The same design, checked on a TShock server |
| Stardew Valley | 36 | 142 | 25 / 11 | The same design, checked inside the game with a SMAPI mod |

Every Minecraft rule has eight variants, which vary materials, supports and camera positions; every Terraria and
Stardew Valley rule has up to four. Each question
has three options: the **game** outcome, the **real-world** outcome and a third one. For a consistent rule, game
and reality agree, and the third option *over-departs*: it changes something neither world changes.

| Condition | Code | The model gets |
|---|---|---|
| Text | `T` | the scene in words, with the game named |
| Told | `C2` | the image plus *"This image is a screenshot from vanilla Minecraft (Java Edition 1.20.1). Answer according to the rules of vanilla Minecraft."* |
| Image | `C0` | the bare image |

## 🚀 Quick start: reproduce the main results

No API key is needed, only Python 3.10+ (standard library).

```bash
git clone https://github.com/GaoJianXin05/RuleCraft.git
cd RuleCraft
pip install -U "huggingface_hub[cli]"
huggingface-cli download GGjx/RuleCraft --repo-type dataset --local-dir RuleCraft-data
python scripts/link_data.py RuleCraft-data
python analysis/reproduce.py
```

> 💡 If huggingface.co is slow or unreachable where you are, set a mirror before downloading:
> `export HF_ENDPOINT=https://hf-mirror.com` (PowerShell: `$env:HF_ENDPOINT="https://hf-mirror.com"`).

The script prints accuracy by condition for both sets and the six models, with 95% bootstrap intervals. It also
prints the two other games and the reasoning settings. `--latex` prints the rows exactly as typeset in the paper.
Before release, each row it printed was checked against the paper.

```
Hard set (60 rules, 480 questions): accuracy (%) on conflict rules, consistent rules, and the gain from naming the game
Model           Text   Told  Image  Told-Image [95% CI]    Cons.Told Cons.Image  ...
DeepSeek        85.2   80.9   28.9  +52.0 [40.0, 63.4]          76.0       96.5  ...
GPT-6.1-Sol     98.7   98.2   47.0  +51.2 [38.1, 64.5]          96.2       99.0  ...
```

To score the human study as well: `cd human_study && python score.py`.

## 🤖 Evaluate a model

1. Copy `rulecraft/Key.env.example` to `rulecraft/Key.env` and fill in the keys you have. `Key.env` is git-ignored.
2. Run the scripts from `rulecraft/`. Choose the model with `LLM_PROFILE`:

| `LLM_PROFILE` | Model | Key in `Key.env` |
|---|---|---|
| *(unset)* | DeepSeek-V4.1-Flash | `DEEPSEEK_API_KEY` |
| `solrun` / `solhigh` | GPT-6.1-Sol, lowest / high reasoning setting | `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`) |
| `qwenmax`, `qwenflash` | Qwen3.8-Max, Qwen3.8-Flash | `DASHSCOPE_API_KEY` |
| `doubaopro`, `doubaolite` | Doubao-Seed-2.1-Pro, Doubao-Seed-2.1-Lite | `ARK_API_KEY` |

Every answer call runs with thinking off, or at the lowest reasoning setting the model accepts. To add a new model,
add one entry to `PROFILES` in `rulecraft/llm.py`; any OpenAI-compatible endpoint works.

```bash
cd rulecraft
# Text, Told and Image on the hard set, one run, spending capped at 5 (in the profile's list-price units)
LLM_PROFILE=qwenflash SPEND_CAP_USD=5 python nothink.py run --reps 1 --prefix t6_ --splits test6 --arms T,C2,C0
# the same three conditions for DeepSeek (default profile), three runs
python gdc.py run --reps 3 --prefix t6_ --split test6 --only C0,C2,T
```

Each call is cached in `rulecraft/results/cache.sqlite` when it returns, so an interrupted run resumes where it
stopped. Answers go to `rulecraft/results/r2/<run folder>/rep<k>/<condition>.jsonl`, the layout of the released
answers.

## 🔬 Experiments and their scripts

| Paper | Script (in `rulecraft/`) | Answers (in the dataset, `answers/minecraft/r2/`) |
|---|---|---|
| Text, Told, Image: six models (Table 1) | `nothink.py` (DeepSeek: `gdc.py run`) | `nothink_*`, `t6_nothink_*`, `rep*`, `t3-t6_rep*` |
| Recognition: which game is this? | `world_open.py`, `run_world_open.sh` | `worldopen_*` |
| Which world, gameplay tool | `interp_run.py` | `interp_*` |
| Cues: a video game, the world shown, the game named | `pilot.py` (FixedGame), `neutral_run.py`, `name_split_run.py`, `review_runs.py` | `*rep*/FixedGame`, `*neutral_*`, `t6_namesplit`, `review_ds` |
| Chain of thought, generated knowledge | `gdc.py run --only CoT,GKP` | `*rep*/CoT`, `*rep*/GKP` |
| Reasoning on (Table 7) and its traces | `think_hard.py`, `think_trace_classify.py`; `LLM_PROFILE=solhigh` | `t6_think_deepseek`, `t6_nothink_solhigh` |
| Open answers without options and their judges | `open_answer.py` | `t6_open_*` |
| Self-named world and the model's own notes | `gdc.py`, `gdc2.py`, `gate_told.py`, `told_cot.py`, `card_model.py`, `method_sol.py`, `note_use.py` | `*final_rep*`, `GATE`, `GateTold`, `ToldCoT`, `../cards/` |
| Terraria and Stardew Valley (Table 5) | `terraria/run_terraria.py`, `stardew/run_stardew.py` | `answers/terraria/`, `answers/stardew/` |
| Open models: answers, logit lens, steering | `openvlm/*.py` | `answers/open_models/` |
| Human study | `human_study/` | `human_study/answers/` |

## 🏗️ Rebuild the benchmark

1. **Scenes**: `python scenes.py && python engine_plan.py` write every scene and the plan of its engine check.
2. **Engine check**: put a vanilla Minecraft Java Edition 1.20.1 server (`server.jar`, EULA accepted, superflat
   world) in `rulecraft/engine/server/`. Then run `cd engine && node verify.js test6`, one batch at a time. Progress
   is saved per scene.
3. **Images**: `cd render && npm install && node render.js ../data/scenes_pre.json ../data/images` renders all
   1,240 images. Or take them from the dataset.
4. **Questions**: `python pilot.py items` rebuilds `data/items.json`.

🕹️ **Terraria and Stardew Valley** need a local install of each game. `terraria/plugin/` is a TShock plugin that
places each scene and reports the tile states. `stardew/mod/SceneLab/` is a SMAPI mod that builds each scene, runs its
steps and saves the state before and after. Set the game folder at the top of `stardew/rules_stardew.py`,
`stardew/run_game.ps1`, `stardew/mod/SceneLab/SceneLab.csproj` and `terraria/lzx_xnb.py`. Use `lzx_xnb.py` to
extract the sprites the Terraria renderer needs from your own copy of the game. Game files are not redistributed
here.

🧠 **Open models**: `openvlm/build_prompts.py` exports the prompts and images. `run_open.py` answers them and keeps
the hidden states. `lens_open.py` and `steer_open.py` run the logit lens and the steering. The `analyze_*.py` scripts
summarize the outputs. One GPU with 24 GB is enough for both models in bfloat16.

## 📝 Citation

```bibtex
@article{rulecraft2026,
  title   = {Multimodal {LLMs} Know the Game but Assume the Real World},
  author  = {Gao, Jianxin},
  journal = {arXiv preprint},
  year    = {2026}
}
```

## 📄 License

Code: [MIT](LICENSE). Data on Hugging Face: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Minecraft,
Terraria and Stardew Valley are trademarks of their respective owners. This project is not affiliated with them.
