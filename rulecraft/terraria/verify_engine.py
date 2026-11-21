"""Post each item's scene to the TShock TileVerify plugin and check every expected tile state.

Usage: python verify_engine.py [ids_file] [extra_id ...]
Writes verify_<date>.jsonl with the engine's raw reply per item.
"""
import json, sys, urllib.request
from datetime import date

URL = "http://localhost:7779/tv/run"
items = {i["id"]: i for i in json.load(open("items_terraria.json", encoding="utf-8"))["items"]}

ids = []
if len(sys.argv) > 1:
    ids += [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
ids += sys.argv[2:]
ids = ids or list(items)


def clear(scene):
    """Remove every tile the scene touches, so one item cannot leak into the next."""
    pts = {(t["x"], t["y"]) for t in scene["tiles"]}
    body = {"tiles": [{"x": x, "y": y, "type": -1} for x, y in pts], "ticks": 0}
    post(body)


def post(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=40).read())


out = open(f"verify_{date.today():%m%d}.jsonl", "w", encoding="utf-8")
npass = 0
for k in ids:
    sc = items[k]["scene"]
    clear(sc)
    r = post(sc)
    checks = r.get("checks", [])
    ok = r.get("ok") and checks and all(c.get("match_active", True) and c.get("match_type", True) for c in checks)
    npass += bool(ok)
    out.write(json.dumps({"id": k, "pass": bool(ok), "reply": r}, ensure_ascii=False) + "\n")
    if not ok:
        print("FAIL", k, json.dumps(checks)[:300])
    clear(sc)
print(f"PASS {npass}/{len(ids)}")
