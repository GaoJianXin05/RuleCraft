"""Chinese translations of every action and option text of the 1,240 test items, for the bilingual human baseline.

Main set (760 items): DeepSeek-V4.1-Flash translated each unique English string once (thinking off, temperature 0).
Hard set (480 items, 298 new strings): translated under the same rules (literal, standard Simplified Chinese
Minecraft names, no added game words) and checked for consistent block names. Results are cached in translations.json,
so rerunning only asks DeepSeek for strings that are still missing (none at present). The answer keys are never sent.
Usage (Git Bash, from this folder): ALLOW_PEAK=1 python translate.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
PILOT = HERE.parent / "rulecraft"
sys.path.insert(0, str(PILOT))
import llm  # noqa: E402

OUT = HERE / "translations.json"
QUESTION = "What happens immediately after this action? (If the action describes time passing, answer for the end of that period.)"
QUESTION_ZH = "这个动作之后会立刻发生什么？（如果动作描述的是一段时间过去，请回答这段时间结束时的情况。）"
PROMPT = """Translate each English sentence below into natural Simplified Chinese for a picture-based quiz.
Rules:
- Translate faithfully and literally: keep every detail, quantity and qualifier (immediately, completely, slowly, several hours, etc.); add nothing.
- For block and item names use the standard Simplified Chinese names used in Minecraft (e.g. snow block = 雪块, trapdoor = 活板门, sponge = 海绵, farmland = 耕地, slab = 台阶, lever = 拉杆, piston = 活塞), but do not add the word Minecraft or any game term that the English does not contain.
- Do not judge which sentence is true; only translate.
Return a JSON object mapping each number to its translation, e.g. {"1": "...", "2": "..."}.

"""


def items():
    data = json.loads((PILOT / "data" / "items.json").read_text(encoding="utf-8"))
    return [i for i in data if i["set"] == "mc" and i["split"] in ("test2", "test3", "test4", "test5", "test6")]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    its = items()
    assert {i["question"] for i in its} == {QUESTION}
    strings = sorted({i["action"] for i in its} | {o[1] for i in its for o in i["options"]})
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {QUESTION: QUESTION_ZH}
    todo = [s for s in strings if s not in done]
    print(f"{len(strings)} strings, {len(todo)} to translate", flush=True)
    llm.set_sampling(temperature=0.0, seed=1)
    for k in range(0, len(todo), 40):
        chunk = todo[k:k + 40]
        body = "\n".join(f"{n + 1}. {s}" for n, s in enumerate(chunk))
        out = llm.chat([{"role": "user", "content": PROMPT + body}], max_tokens=4000, json_mode=True, tag="HUMAN_ZH")
        got = json.loads(out["text"])
        for n, s in enumerate(chunk):
            zh = got.get(str(n + 1))
            if isinstance(zh, str) and zh.strip():
                done[s] = zh.strip()
        OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{min(k + 40, len(todo))}/{len(todo)}", flush=True)
    missing = [s for s in strings if s not in done]
    print("missing:", len(missing))


if __name__ == "__main__":
    main()
