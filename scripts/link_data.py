"""Put the downloaded RuleCraft dataset where the code expects it (files are copied; the dataset folder is untouched).

  <dataset>/minecraft/images/            -> rulecraft/data/images/
  <dataset>/minecraft/engine_checks/     -> rulecraft/results/
  <dataset>/answers/minecraft/r2/        -> rulecraft/results/r2/
  <dataset>/answers/minecraft/cards/     -> rulecraft/results/
  <dataset>/terraria/images/             -> rulecraft/terraria/images_real/
  <dataset>/stardew/images/              -> rulecraft/stardew/images/
  <dataset>/stardew/engine_check/        -> rulecraft/stardew/verify/
  <dataset>/answers/terraria|stardew/    -> rulecraft/terraria|stardew/results/
  <dataset>/answers/open_models/         -> rulecraft/openvlm/out/
  <dataset>/human_study/answers/         -> human_study/answers/

Usage (in the repository folder):
  huggingface-cli download GGjx/RuleCraft --repo-type dataset --local-dir RuleCraft-data
  python scripts/link_data.py RuleCraft-data
"""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAP = [("minecraft/images", "rulecraft/data/images"), ("minecraft/engine_checks", "rulecraft/results"),
       ("answers/minecraft/r2", "rulecraft/results/r2"), ("answers/minecraft/cards", "rulecraft/results"),
       ("terraria/images", "rulecraft/terraria/images_real"), ("stardew/images", "rulecraft/stardew/images"),
       ("stardew/engine_check", "rulecraft/stardew/verify"), ("answers/terraria", "rulecraft/terraria/results"),
       ("answers/stardew", "rulecraft/stardew/results"), ("answers/open_models", "rulecraft/openvlm/out"),
       ("human_study/answers", "human_study/answers")]


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    data = Path(sys.argv[1]).resolve()
    if not (data / "minecraft" / "questions.jsonl").exists():
        raise SystemExit(f"{data} does not look like the RuleCraft dataset (no minecraft/questions.jsonl)")
    for src, dst in MAP:
        n = 0
        for f in (data / src).rglob("*"):
            if f.is_file():
                out = REPO / dst / f.relative_to(data / src)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, out)
                n += 1
        print(f"{src:<26} -> {dst:<32} {n:>5} files")


if __name__ == "__main__":
    main()
