"""Render Terraria scenes using real tile sprites extracted from the game's XNB files.

Tile sheets: 18px stride (16px tile + 2px gutter). Frame chosen from 4-neighbour
mask following Terraria's standard block framing; variant 0..2 picked per position.
Output: images_real/<id>.png, 768x480.
"""
import json, os, sys
from PIL import Image

SP = "sprites_real"
OUT = sys.argv[1] if len(sys.argv) > 1 else "images_real"
W, H, S = 768, 480, 2          # final size, pixel scale
CW, CH = W // S, H // S        # native canvas 384x240 = 24x15 tiles
NONSOLID = {19, 51}            # platforms, cobweb: do not merge

sheets = {}
def sheet(tid):
    if tid not in sheets:
        sheets[tid] = Image.open(f"{SP}/tiles_sheet_{tid}.png").convert("RGBA")
    return sheets[tid]

def frame(up, dn, lf, rt, v):
    """Return (fx, fy) in 18px units for Terraria standard block framing."""
    key = (up, dn, lf, rt)
    table = {
        (1,1,1,1): (1+v, 1), (0,1,1,1): (1+v, 0), (1,0,1,1): (1+v, 2),
        (1,1,0,1): (0, v),   (1,1,1,0): (4, v),
        (0,1,0,1): (0+2*v%6, 3), (0,1,1,0): (1+2*v%6, 3),
        (1,0,0,1): (0+2*v%6, 4), (1,0,1,0): (1+2*v%6, 4),
        (0,0,1,1): (6+v, 4), (1,1,0,0): (5, v),
        (0,1,0,0): (6+v, 0), (1,0,0,0): (6+v, 3),
        (0,0,0,1): (9, v),   (0,0,1,0): (12, v),
        (0,0,0,0): (9+v, 3),
    }
    return table[key]

def crop(tid, fx, fy):
    sh = sheet(tid)
    x, y = fx * 18, fy * 18
    if x + 16 > sh.width or y + 16 > sh.height:
        x, y = 18, 18
    return sh.crop((x, y, x + 16, y + 16))

def tile_img(grid, gx, gy):
    tid = grid[gy][gx]
    if tid == 19:                          # wood platform
        return crop(19, 0, 0)
    if tid == 51:                          # cobweb
        return crop(51, (gx * 7 + gy) % 5, 0)
    def solid(x, y):
        if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
            return 1
        t = grid[y][x]
        return int(t >= 0 and t not in NONSOLID)
    v = (gx * 3 + gy * 7) % 3
    fx, fy = frame(solid(gx, gy-1), solid(gx, gy+1), solid(gx-1, gy), solid(gx+1, gy), v)
    return crop(tid, fx, fy)

# --- background + HUD assets ---
SKY = Image.open(f"{SP}/Background_0.png").convert("RGBA")
HILLS = Image.open(f"{SP}/Background_7.png").convert("RGBA")
HEART = Image.open(f"{SP}/Heart.png").convert("RGBA")
MANA = Image.open(f"{SP}/Mana.png").convert("RGBA")
SLOT = Image.open(f"{SP}/Inventory_Back.png").convert("RGBA")
SLOT_SEL = Image.open(f"{SP}/Inventory_Back14.png").convert("RGBA")

def background():
    sky = SKY.crop((0, 0, SKY.width, 700)).resize((W, H), Image.BILINEAR)
    bg = sky.copy()
    hills = HILLS.resize((W, int(HILLS.height * W / HILLS.width)), Image.BILINEAR)
    bg.alpha_composite(hills, (0, H - hills.height - 60))
    return bg

def hud(img):
    # hotbar top-left (Terraria default layout)
    x0, y0, step = 16, 16, 42
    a, b = SLOT.resize((40, 40)), SLOT_SEL.resize((40, 40))
    for i in range(10):
        img.alpha_composite(b if i == 0 else a, (x0 + i * step, y0))
    # hearts + mana top-right
    for i in range(10):
        img.alpha_composite(HEART, (W - 290 + i * 25, 18))
    for i in range(6):
        img.alpha_composite(MANA, (W - 34, 60 + i * 28))

def render(scene):
    tiles = scene["tiles"]
    xs = [t["x"] for t in tiles]; ys = [t["y"] for t in tiles]
    cols, rows = CW // 16, CH // 16                       # 24 x 15
    cx = (min(xs) + max(xs)) // 2; ox = cx - cols // 2
    ground = max(ys) + 1                                  # first ground row
    oy = ground - (rows - 4)                              # 4 ground rows visible
    grid = [[-1] * cols for _ in range(rows)]
    for gy in range(rows):
        wy = oy + gy
        if wy >= ground:
            d = wy - ground
            for gx in range(cols):
                grid[gy][gx] = 2 if d == 0 else (0 if d < 3 else 1)
    for t in tiles:
        gx, gy = t["x"] - ox, t["y"] - oy
        if 0 <= gx < cols and 0 <= gy < rows and t["type"] >= 0:
            grid[gy][gx] = t["type"]
    layer = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    for gy in range(rows):
        for gx in range(cols):
            if grid[gy][gx] >= 0:
                layer.alpha_composite(tile_img(grid, gx, gy), (gx * 16, gy * 16))
    img = background()
    img.alpha_composite(layer.resize((W, H), Image.NEAREST))
    hud(img)
    return img.convert("RGB")

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    items = json.load(open("items_terraria.json", encoding="utf-8"))["items"]
    only = sys.argv[2:]
    n = 0
    for it in items:
        if only and it["id"] not in only:
            continue
        render(it["scene"]).save(f"{OUT}/{it['id']}.png"); n += 1
    print(f"rendered {n} -> {OUT}/")
