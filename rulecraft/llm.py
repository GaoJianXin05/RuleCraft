"""OpenAI-compatible chat client with an on-disk cache, retries, a spending guard and usage logging.

Keys and endpoints are read from rulecraft/Key.env (copy Key.env.example; never commit it). LLM_PROFILE picks the
model; without it the client talks to DeepSeek:
  DEEPSEEK_API_KEY=...                            (or DEEPSEEK_API_KEY1, DEEPSEEK_API_KEY2, ...: later keys are fallbacks)
  DEEPSEEK_BASE_URL=https://api.deepseek.com      (optional)
  DEEPSEEK_MODEL=deepseek-flash                    (optional)
Set MOCK=1 in the environment to run the whole pipeline without network calls.
"""
import base64
import hashlib
import json
import os
import random
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def load_env():
    env = {}
    for name in (".env", "Key.env"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
PROFILE = os.environ.get("LLM_PROFILE", "deepseek")
DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
ARK_BASE = "https://ark.cn-beijing.volces.com/api/v3"
OPENAI_BASE = ENV.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
# Every profile other than the default (DeepSeek). Fields: model id, name of the max-tokens field, list price per 1M
# tokens (input, cached input, output; used only by the spend cap), base and key_prefix (endpoint and the Key.env
# entries holding its keys), extra (merged into every request, here to turn thinking off), think_extra (merged when a
# step asks for reasoning), send_effort=False (never send reasoning_effort), effort (the reasoning_effort of every
# answer call), send_temperature=True (send the run's temperature). All answer calls run with thinking off, or at the
# lowest reasoning setting a model accepts.
PROFILES = {
    # GPT-6.1-Sol at its lowest accepted reasoning setting, and at the high setting (Table "reasoning")
    "solrun": dict(model=ENV.get("OPENAI_MODEL", "gpt-6.1-sol"), max_field="max_completion_tokens",
                   price=(2.0, 0.2, 10.0), base=OPENAI_BASE, key_prefix="OPENAI_API_KEY", effort="low"),
    "qwenmax": dict(model="qwen3.8-max", max_field="max_tokens", price=(6.0, 0.6, 24.0), base=DASHSCOPE_BASE,
                    key_prefix="DASHSCOPE_API_KEY", extra={"enable_thinking": False}, send_effort=False,
                    send_temperature=True, think_extra={"enable_thinking": True}),
    "qwenflash": dict(model="qwen3.8-flash", max_field="max_tokens", price=(1.5, 0.15, 15.0), base=DASHSCOPE_BASE,
                      key_prefix="DASHSCOPE_API_KEY", extra={"enable_thinking": False}, send_effort=False,
                      send_temperature=True, think_extra={"enable_thinking": True}),
    "doubaopro": dict(model="doubao-seed-2-1-pro-260915", max_field="max_tokens", price=(3.2, 0.64, 16.0),
                      base=ARK_BASE, key_prefix="ARK_API_KEY", extra={"thinking": {"type": "disabled"}},
                      send_effort=False, send_temperature=True),
    "doubaolite": dict(model="doubao-seed-2-1-lite-260915", max_field="max_tokens", price=(0.8, 0.16, 8.0),
                       base=ARK_BASE, key_prefix="ARK_API_KEY", extra={"thinking": {"type": "disabled"}},
                       send_effort=False, send_temperature=True),
}
PROFILES["solhigh"] = dict(PROFILES["solrun"], effort="high")
PROFILE_CFG = PROFILES.get(PROFILE)
# REASONING_EFFORT overrides the profile's reasoning_effort for every answer call ("omit" sends none).
REASONING_EFFORT = os.environ.get("REASONING_EFFORT")
MIN_TOKENS = 4000 if REASONING_EFFORT == "low" else 8000   # reasoning counts toward the limit, so short answers need room
LABEL = threading.local()     # the item a thread is working on, recorded with each call's token counts
_KEY_PREFIX = PROFILE_CFG["key_prefix"] if PROFILE_CFG else "DEEPSEEK_API_KEY"
API_KEYS = [ENV[k] for k in sorted(ENV) if k.startswith(_KEY_PREFIX) and ENV[k]]
_key_idx = 0
MOCK = os.environ.get("MOCK") == "1"
BASE_URL = PROFILE_CFG["base"] if PROFILE_CFG else ENV.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = PROFILE_CFG["model"] if PROFILE_CFG else ENV.get("DEEPSEEK_MODEL", "deepseek-flash")
PRICE = {"in_miss": 0.30, "in_hit": 0.006, "out": 1.20}   # DeepSeek, USD / 1M tokens, peak rates (off-peak is half)
# Defaults for every chat() call. A run sets them once per repeat, so repeats differ only by sampling noise.
SAMPLING = {"temperature": 0.0, "seed": 0}
# Budget guard: stop when the DeepSeek balance falls to floor_cny; wait out peak hours instead of paying double.
GUARD = {"floor_cny": None, "wait_off_peak": False, "calls": 0, "check_every": 150}
_guard_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def set_sampling(temperature=0.0, seed=0):
    SAMPLING.update(temperature=temperature, seed=seed)


def set_guard(floor_cny=None, wait_off_peak=True):
    GUARD.update(floor_cny=floor_cny, wait_off_peak=wait_off_peak)


def balance_cny():
    req = urllib.request.Request(f"{BASE_URL}/user/balance", headers={"Authorization": f"Bearer {API_KEYS[_key_idx]}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return float(json.loads(r.read())["balance_infos"][0]["total_balance"])


def peak_priced_usd(since):
    """DeepSeek spend since a time, from the usage log, counting every call at peak prices."""
    path = RESULTS / "usage.jsonl"
    usd = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line) if line.strip() else None
        if r and r["t"] >= since:
            miss = r["prompt_tokens"] - r["cache_hit"]
            usd += (miss * PRICE["in_miss"] + r["cache_hit"] * PRICE["in_hit"] + r["completion_tokens"] * PRICE["out"]) / 1e6
    return usd


def profile_usage_path():
    return RESULTS / f"usage_{PROFILE}.jsonl"


def profile_spend():
    """(calls, cost, cost) of this profile from its own usage log, at the profile's list prices."""
    path = profile_usage_path()
    if not PROFILE_CFG or not path.exists():
        return 0, 0.0, 0.0
    p_in, p_hit, p_out = PROFILE_CFG["price"]
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    cost = sum((r["prompt_tokens"] - r["cache_hit"]) * p_in + r["cache_hit"] * p_hit + r["completion_tokens"] * p_out
               for r in rows) / 1e6
    return len(rows), cost, cost


_keys_ready = False


def _pick_keys():
    """Keep only the keys that can use this model. Keys are never printed."""
    global _keys_ready
    with _guard_lock:
        if _keys_ready:
            return
        good = []
        for k in API_KEYS:
            req = urllib.request.Request(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {k}"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    ids = {m["id"] for m in json.loads(r.read())["data"]}
                    ids |= {i.split("/")[-1] for i in ids}       # some hosts list ids as "models/<id>"
            except (OSError, ValueError, KeyError):
                good.append(k)                                   # a host without a model list: keep the key
                continue
            if MODEL in ids:
                good.append(k)
        if not good:
            raise RuntimeError(f"none of the {len(API_KEYS)} {_KEY_PREFIX} keys can use {MODEL}")
        API_KEYS[:] = good
        _keys_ready = True


def _before_call():
    while GUARD["wait_off_peak"] and is_peak():
        time.sleep(30)
    with _guard_lock:
        GUARD["calls"] += 1
        due = GUARD["calls"] % GUARD["check_every"] == 1
    # SPEND_CAP_USD (or SPEND_CAP_CNY for the profiles priced in CNY) stops a run at a total for this profile
    for var in ("SPEND_CAP_USD", "SPEND_CAP_CNY"):
        if PROFILE_CFG and due and var in os.environ:
            spent = profile_spend()[1]
            if spent >= float(os.environ[var]):
                raise BudgetExceeded(f"{PROFILE} spend {spent:.2f} reached the cap {os.environ[var]}")
    # PEAK_CAP_USD and PEAK_CAP_SINCE set a DeepSeek spending limit that holds across scripts
    if due and "PEAK_CAP_USD" in os.environ:
        spent = peak_priced_usd(float(os.environ["PEAK_CAP_SINCE"]))
        if spent >= float(os.environ["PEAK_CAP_USD"]):
            raise BudgetExceeded(f"peak-priced spend ${spent:.2f} reached the cap ${os.environ['PEAK_CAP_USD']}")
    if GUARD["floor_cny"] is None:
        return
    if due:
        try:
            left = balance_cny()
        except (OSError, ValueError, KeyError):
            return                              # a failed balance check is not a reason to stop; the next one decides
        if left <= GUARD["floor_cny"]:
            raise BudgetExceeded(f"balance {left} CNY reached the floor {GUARD['floor_cny']} CNY")


_db_lock = threading.Lock()
_db = sqlite3.connect(RESULTS / "cache.sqlite", check_same_thread=False, timeout=120)   # two models may run side by side
_db.execute("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, v TEXT)")
_db.commit()


def image_part(path):
    data = base64.b64encode(Path(path).read_bytes()).decode()
    mime = "image/png" if str(path).lower().endswith(".png") else "image/jpeg"
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def user(text, images=()):
    if not images:
        return {"role": "user", "content": text}
    return {"role": "user", "content": [image_part(p) for p in images] + [{"type": "text", "text": text}]}


def is_peak(now=None):
    now = now or datetime.now(timezone.utc)
    return now.weekday() < 5 and (1 <= now.hour < 4 or 6 <= now.hour < 10)


def _mock_reply(body):
    text = json.dumps(body["messages"], ensure_ascii=False)
    rng = random.Random(hashlib.sha256(text.encode()).hexdigest())
    if body.get("response_format", {}).get("type") == "json_object":
        if "List the ways" in text or "Merge entries" in text:
            return json.dumps({"departures": [{"id": "MOCK1", "objects": ["all blocks"], "except": ["sand", "gravel"],
                                               "trigger": "support removed", "real_world": "falls", "minecraft": "stays floating"}]})
        if "Return JSON with fields" in text:
            return json.dumps({"world": rng.choice(["minecraft_vanilla", "minecraft_vanilla", "real_world", "other_game"]), "game_name": "",
                               "evidence": ["mock"], "declared_changes": [], "objects": ["dirt", "oak log"], "state": "mock state"})
        return json.dumps({"default": rng.choice("ABC"), "applies": {"MOCK1": rng.choice(["yes", "no"])}, "final": rng.choice("ABC")})
    if "true or false" in text.lower():
        return rng.choice(["true", "false"])
    if "Which video game" in text:
        return rng.choice(["Minecraft", "Terraria"])
    return "Answer: " + rng.choice("ABCD")


def chat(messages, *, max_tokens=300, json_mode=False, thinking=False, temperature=None, tag="", seed=None, effort=None):
    """Return dict(text, reasoning, usage, model, cached). `seed` only changes the cache key (for repeated samples)."""
    temperature = SAMPLING["temperature"] if temperature is None else temperature
    seed = SAMPLING["seed"] if seed is None else seed
    if SAMPLING.get("thinking") and not PROFILE_CFG:     # a run can turn thinking on for every call
        thinking = True
        max_tokens = max(max_tokens, 8000)
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "stream": False}
    if PROFILE_CFG:
        del body["max_tokens"]
        body[PROFILE_CFG["max_field"]] = max(max_tokens, MIN_TOKENS)
        chosen = "high" if thinking else (effort or REASONING_EFFORT or PROFILE_CFG.get("effort"))
        if chosen and chosen != "omit" and PROFILE_CFG.get("send_effort", True):
            body["reasoning_effort"] = chosen
        body.update(PROFILE_CFG.get("extra", {}))
        if thinking and PROFILE_CFG.get("think_extra"):      # offline steps that ask for reasoning (the card audit)
            body.update(PROFILE_CFG["think_extra"])
        if PROFILE_CFG.get("send_temperature"):
            body["temperature"] = temperature
    elif thinking:
        body["thinking"] = {"type": "enabled"}
        body["reasoning_effort"] = "high"
    else:
        body["thinking"] = {"type": "disabled"}
        body["temperature"] = temperature
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    key = hashlib.sha256(json.dumps([body, seed, MOCK], sort_keys=True).encode()).hexdigest()
    with _db_lock:
        row = _db.execute("SELECT v FROM cache WHERE k=?", (key,)).fetchone()
    if row:
        out = json.loads(row[0])
        out["cached"] = True
        return out

    if MOCK:
        out = {"text": _mock_reply(body), "reasoning": "", "usage": {}, "model": "mock"}
    else:
        global _key_idx
        if not API_KEYS:
            raise RuntimeError(f"no key found: put {_KEY_PREFIX}...=... in rulecraft/Key.env")
        if PROFILE_CFG:
            _pick_keys()
        _before_call()
        for attempt in range(6):
            req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {API_KEYS[_key_idx]}"})
            try:
                with urllib.request.urlopen(req, timeout=600 if thinking else 180) as r:   # reasoning calls can run minutes
                    resp = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:500]
                if e.code == 402 and _key_idx + 1 < len(API_KEYS):   # insufficient balance: move to the next key
                    _key_idx += 1
                    continue
                if e.code in (429, 500, 502, 503, 504, 524) and attempt < 5:
                    time.sleep(2 ** attempt + random.random())
                    continue
                raise RuntimeError(f"HTTP {e.code}: {detail}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                if attempt < 5:
                    time.sleep(2 ** attempt + random.random())
                    continue
                raise
        msg = resp["choices"][0]["message"]
        out = {"text": msg.get("content") or "", "reasoning": msg.get("reasoning_content") or "",
               "usage": resp.get("usage", {}), "model": resp.get("model", MODEL)}
    with _db_lock:
        _db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)", (key, json.dumps(out, ensure_ascii=False)))
        _db.commit()
        u = out["usage"]
        log = RESULTS / "usage_mock.jsonl" if MOCK else profile_usage_path() if PROFILE_CFG else RESULTS / "usage.jsonl"
        hit = u.get("prompt_cache_hit_tokens") or (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "tag": tag, "item": getattr(LABEL, "item", None), "peak": is_peak(),
                                "model": out["model"], "prompt_tokens": u.get("prompt_tokens", 0), "cache_hit": hit,
                                "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                                "completion_tokens": u.get("completion_tokens", 0)}) + "\n")
    out["cached"] = False
    return out


def parse_letter(text, letters="ABC"):
    """The chosen option. Case matters past the first checks: in prose, "a" and "A torch" are words, not answers."""
    m = re.search(r"answer\s*[:：]\s*\**\s*\(?([%s])\b" % letters, text, re.I)
    if m:
        return m.group(1).upper()
    bold = re.findall(r"\*\*\s*\(?([%s])\)?[.:]?\s*\*\*" % letters, text)
    if bold:
        return bold[-1]
    text = text.strip()
    if len(text) <= 4:                  # a bare reply, whatever its case: "B", "b.", "(C)"
        m = re.search(r"([%s])" % letters, text.upper())
        return m.group(1) if m else None
    m = re.match(r"\(?([%s])\b" % letters, text)   # the reply opens with its answer: "B. The ice melts ..."
    if m:
        return m.group(1)
    m = re.findall(r"\b([%s])\b(?!\s+[a-z])" % letters, text)   # otherwise the last capital that is not starting a sentence
    return m[-1] if m else None


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def spend_report(since=0.0):
    path = RESULTS / "usage.jsonl"
    if not path.exists():
        return "no calls yet"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["t"] >= since]
    usd = 0.0
    for r in rows:
        f = 1.0 if r["peak"] else 0.5
        miss = r["prompt_tokens"] - r["cache_hit"]
        usd += f * (miss * PRICE["in_miss"] + r["cache_hit"] * PRICE["in_hit"] + r["completion_tokens"] * PRICE["out"]) / 1e6
    return f"{len(rows)} calls, {sum(r['prompt_tokens'] for r in rows):,} prompt tok, {sum(r['completion_tokens'] for r in rows):,} completion tok, ~${usd:.2f}"
