"""Score the human baseline from the exported answer files (answers/*.json), offline.

Two file formats are read:
  version 2 (the 95-rule page of 2026-11-09): {"version": "2", "pid", "session", "offset", "items", "answers": [{id,
            choice, rt_ms, ...}], "profile", "post"}; one variant of every main-set rule.
  version 5 (the site of 2026-11-13): {"v": 5, "pid", "session", "offset", "n", "items", "a": [[id, choice, rt_ms,
            seconds since start], ...], "profile", "post"}; 100 of the 155 rules, drawn within rule types (sampling.py).
Every file is checked against the page's assignment (version 2: the id's variant of every main rule; version 5: one
item per rule, the id's variant of each, every rule-type quota held). Per id, mid-way exports and final results are
merged by keeping the most complete file; an id started in two different sessions (two people picked the same id) is
reported and only the most complete is scored. Only finished files count. Each choice is mapped to the outcome kind of
its option (game, real-world, third, over-departure) through the answer keys in rulecraft/data/items.json; pooled accuracy
uses the paper's two-level rule-clustered bootstrap. A participant counts for a set if their answers include that set.

Usage: python score.py [--min-hours 10-100] [--answers DIR] [--tex FILE]
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import sampling as S  # noqa: E402

sys.path.insert(0, str(S.PILOT))
from analyze import cluster_ci  # noqa: E402
from rules import RULE_BY_ID  # noqa: E402

HOURS = ["0", "lt10", "10-100", "100-500", "gt500"]
DASH = r"\textendash"
BLANK = r"\underline{\hspace{1.5em}}"     # a visible blank to fill in (main set, which already has answers)


def normalize(r, name):
    if r.get("v") == 5:
        return {"pid": r["pid"], "session": r["session"], "offset": r["offset"], "items": r["items"],
                "answers": [{"id": a[0], "choice": a[1], "rt_ms": a[2]} for a in r["a"]], "profile": r["profile"],
                "post": r.get("post"), "version": 5, "file": name}
    if str(r.get("version")) == "2":
        return {"pid": r["pid"], "session": r["session"], "offset": r["offset"], "items": r["items"],
                "answers": r["answers"], "profile": r["profile"], "post": r.get("post"), "version": 2, "file": name}
    raise SystemExit(f"{name}: unknown answer-file format")


def check(r, items, plan, rj, rules):
    if r["version"] == 2:
        offset = S.fnv1a(r["pid"]) % 8
        want = {f"{rule}_v{(offset + j) % 8}" for j, rule in enumerate(rules["main"])}
        problem = None if r["offset"] == offset and set(r["items"]) == want else "item list does not match the id"
    else:
        # released files carry a pseudonym in place of the id that seeded the draw; each draw was
        # checked against its original id before release
        problem = None if r["pid"].startswith("P") else S.check(r["pid"], r["offset"], r["items"],
                                                                 items, plan, rj)
    assert problem is None, f"{r['file']}: {problem} ({r['pid']!r})"
    assert [a["id"] for a in r["answers"]] == r["items"][:len(r["answers"])], f"{r['file']}: answers out of order"


def load(items, folder):
    plan, rj, rules = S.plan(items), S.rule_index(items), S.rule_lists(items)
    runs, sessions = {}, defaultdict(set)
    for f in sorted(list(folder.glob("*.json")) + list(folder.glob("*.txt"))):
        text = f.read_text(encoding="utf-8-sig")
        text = text[text.find("{"):text.rfind("}") + 1]          # pasted text may carry a few extra words around it
        r = normalize(json.loads(text), f.name)
        check(r, items, plan, rj, rules)
        key = (r["pid"], r["version"])
        sessions[key].add(r["session"])
        rank = lambda x: (x.get("post") is not None, len(x["answers"]))   # a finished file beats a mid-way export
        if key not in runs or rank(r) > rank(runs[key]):
            runs[key] = r
    for (pid, v), s in sessions.items():
        if len(s) > 1:
            print(f"warning: id {pid!r} (version {v}) was used in {len(s)} different sessions (possibly two people); "
                  "only the most complete is scored")
    return runs


RUN_FLAG, FAST_FLAG_MS = 15, 1500


def attention(r):
    """Signs of answering without looking: the longest run of one letter in answering order (options are shuffled per
    item, so long runs are unlikely by chance) and the median time on screen. Reported only; files are set aside by hand
    (answers_excluded/)."""
    run = best = 0
    prev = None
    for a in r["answers"]:
        run = run + 1 if a["choice"] == prev else 1
        prev, best = a["choice"], max(best, run)
    rts = sorted(a["rt_ms"] for a in r["answers"]) or [0]
    med = rts[len(rts) // 2]
    why = []
    if best >= RUN_FLAG:
        why.append(f"{best} answers in a row with the same letter")
    if med < FAST_FLAG_MS:
        why.append(f"median {med / 1000:.1f} s per question")
    return why


def measures(items, keep, part):
    """Pooled accuracy (rule-clustered bootstrap), fallback rate and per-person lines, on one set."""
    groups = {"conflict": defaultdict(list), "consistent": defaultdict(list), "passive": defaultdict(list),
              "action": defaultdict(list)}
    picks, cover, lines, n_ans, n_people = Counter(), Counter(), [], 0, 0
    for (pid, v), r in sorted(keep.items()):
        right, rts = Counter(), []
        for ans in r["answers"]:
            it = items[ans["id"]]
            if it["split"] not in S.SPLITS[part]:
                continue
            ok = ans["choice"] == it["answer"]["C0"]
            groups[it["kind"]][it["rule"]].append(float(ok))
            if part == "hard" and it["kind"] == "conflict":
                groups[RULE_BY_ID[it["rule"]]["act"]][it["rule"]].append(float(ok))
            right[it["kind"], ok] += 1
            rts.append(ans["rt_ms"])
            cover[ans["id"]] += 1
            n_ans += 1
            if it["kind"] == "conflict" and not ok:
                picks[next(k for k, val in it["keys"].items() if val == ans["choice"])] += 1
        if not rts:
            continue
        n_people += 1
        acc = {k: 100 * right[k, True] / max(1, right[k, True] + right[k, False]) for k in ("conflict", "consistent")}
        rts.sort()
        lines.append(f"{pid} (v{v}): {len(rts)} answers, conflict {acc['conflict']:.1f}, consistent {acc['consistent']:.1f}, "
                     f"median {rts[len(rts) // 2] / 1000:.1f} s, profile {r['profile']}, basis {(r.get('post') or {}).get('basis')}")
    pooled = {k: [100 * x for x in cluster_ci(d)] for k, d in groups.items() if d}
    wrong = sum(picks.values())
    return {"n": n_people, "pooled": pooled, "fallback": 100 * picks["real"] / wrong if wrong else None,
            "picks": dict(picks), "cover": len(cover), "lines": lines, "answers": n_ans}


def write_tex(path, main_all, main_exp, hard_all, done):
    """LaTeX macros for the paper. Main set: a visible blank until answers exist; hard set: a dash until answers exist."""
    def acc(m, k, empty):
        return empty if k not in m["pooled"] else f"{m['pooled'][k][0]:.1f}"

    def ci(m, k, empty):
        return empty if k not in m["pooled"] else f"[{m['pooled'][k][1]:.1f}, {m['pooled'][k][2]:.1f}]"

    have, hhave = main_all["n"] > 0, hard_all["n"] > 0
    hours = Counter(r["profile"]["hours"] for r in done.values())
    macros = {
        "HumanN": str(main_all["n"]) if have else BLANK,
        "HumanConf": acc(main_all, "conflict", BLANK), "HumanConfCI": ci(main_all, "conflict", BLANK),
        "HumanCons": acc(main_all, "consistent", BLANK), "HumanConsCI": ci(main_all, "consistent", BLANK),
        "HumanFallback": f"{main_all['fallback']:.0f}" if main_all["fallback"] is not None else BLANK,
        "HumanCover": str(main_all["cover"]) if have else BLANK,
        "HumanAnswers": f"{main_all['answers']:,}" if have else BLANK,
        "HumanExpN": str(main_exp["n"]) if have else BLANK,
        "HumanExpConf": acc(main_exp, "conflict", BLANK), "HumanExpConfCI": ci(main_exp, "conflict", BLANK),
        "HumanExpCons": acc(main_exp, "consistent", BLANK),
        "HumanExpFallback": f"{main_exp['fallback']:.0f}" if main_exp["fallback"] is not None else BLANK,
        "HumanHN": str(hard_all["n"]) if hhave else DASH,
        "HumanHConf": acc(hard_all, "conflict", DASH), "HumanHConfCI": ci(hard_all, "conflict", DASH),
        "HumanHCons": acc(hard_all, "consistent", DASH), "HumanHConsCI": ci(hard_all, "consistent", DASH),
        "HumanHPas": acc(hard_all, "passive", DASH), "HumanHAct": acc(hard_all, "action", DASH),
        "HumanHFallback": f"{hard_all['fallback']:.0f}" if hard_all["fallback"] is not None else DASH,
        "HumanHCover": str(hard_all["cover"]) if hhave else DASH,
    }
    for h in HOURS:
        name = {"0": "None", "lt10": "Few", "10-100": "Some", "100-500": "Many", "gt500": "Most"}[h]
        macros["HumanHours" + name] = str(hours[h]) if have else BLANK
    label = {"0": "none", "lt10": "under 10 hours", "10-100": "10--100 hours", "100-500": "100--500 hours",
             "gt500": "over 500 hours"}
    parts = [f"{label[h]} ({hours[h]})" for h in HOURS if hours[h]]
    macros["HumanHoursText"] = ", ".join(parts) if have else BLANK
    text = ["% generated by human_baseline/score.py --tex"]
    text += [rf"\providecommand{{\n{k}}}{{{v}}}" for k, v in sorted(macros.items())]
    Path(path).write_text("\n".join(text) + "\n", encoding="utf-8")


def report(title, m, total):
    print(f"\n== {title}: {m['n']} participants")
    print("\n".join(m["lines"]))
    for k, v in m["pooled"].items():
        print(f"pooled {k}: {v[0]:.1f} [{v[1]:.1f}, {v[2]:.1f}]")
    if m["fallback"] is not None:
        print(f"conflict errors pick the real-world outcome: {m['fallback']:.0f}% {m['picks']}")
    print(f"items answered at least once: {m['cover']} of {total}; answers scored: {m['answers']}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-hours", default="0", choices=HOURS)
    ap.add_argument("--answers", default=str(HERE / "answers"), help="folder of answer files")
    ap.add_argument("--tex", default=None, help="also write the paper's macros to this file")
    a = ap.parse_args()
    items = S.load_items()
    folder = Path(a.answers)
    runs = load(items, folder) if folder.exists() else {}
    done = {k: r for k, r in runs.items() if len(r["answers"]) == len(r["items"])}
    at_least = lambda h: {k: r for k, r in done.items() if HOURS.index(r["profile"]["hours"]) >= HOURS.index(h)}
    if a.tex:
        write_tex(a.tex, measures(items, done, "main"), measures(items, at_least("10-100"), "main"),
                  measures(items, done, "hard"), done)
        return
    unfinished = sorted(f"{p} (v{v}): {len(r['answers'])}/{len(r['items'])}" for (p, v), r in runs.items() if (p, v) not in done)
    print(f"{len(done)} finished files; unfinished: {unfinished}")
    flags = {f"{p} ({r['file']})": attention(r) for (p, v), r in sorted(done.items()) if attention(r)}
    for who, why in flags.items():
        print(f"check {who}: {'; '.join(why)} -- if it looks careless, move the file to answers_excluded/ with the reason")
    keep = at_least(a.min_hours)
    report(f"main set, play time at least {a.min_hours}", measures(items, keep, "main"), 760)
    report(f"hard set, play time at least {a.min_hours}", measures(items, keep, "hard"), 480)


if __name__ == "__main__":
    main()
