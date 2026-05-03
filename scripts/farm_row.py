"""
种田skill：逐格完成 翻地→播种→浇水（蛇形走位，带体力/水量检测）

用法:
    python farm_row.py <start_x> <start_y> <length> [options]

选项:
    --seed NAME        种子名（默认 Parsnip Seeds）
    --dir DIR          种植方向: right/left/down/up（默认 right）
    --rows N           种几排（默认 1）
    --row-spacing N    排间距（默认 1）
    --skip-water       跳过浇水
    --port PORT        NagiBridge端口（默认 7843）
"""

import sys
import time
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("start_x", type=int)
parser.add_argument("start_y", type=int)
parser.add_argument("length", type=int)
parser.add_argument("--seed", default="Parsnip Seeds")
parser.add_argument("--dir", default="right", choices=["right", "left", "down", "up"])
parser.add_argument("--rows", type=int, default=1)
parser.add_argument("--row-spacing", type=int, default=1)
parser.add_argument("--skip-water", action="store_true")
parser.add_argument("--port", type=int, default=7843)
args = parser.parse_args()

os.environ["NAGI_URL"] = f"http://localhost:{args.port}"
import stardew_api as api

TOOL_DELAY = 0.55
STAMINA_THRESHOLD = 0.15

DIR_MAP = {
    "right": (1, 0),
    "left":  (-1, 0),
    "down":  (0, 1),
    "up":    (0, -1),
}

ROW_OFFSET = {
    "right": (0, 1),
    "left":  (0, 1),
    "down":  (1, 0),
    "up":    (1, 0),
}

# facing direction when approaching from different sides
FACE_FORWARD = {"right": 1, "left": 3, "down": 2, "up": 0}
FACE_REVERSE = {"right": 3, "left": 1, "down": 0, "up": 2}

# offset to stand adjacent to tile based on facing
STAND_OFFSET_FORWARD = {"right": (-1, 0), "left": (1, 0), "down": (0, -1), "up": (0, 1)}
STAND_OFFSET_REVERSE = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}


def calc_tiles(sx, sy, length, direction, rows, row_spacing):
    dx, dy = DIR_MAP[direction]
    rdx, rdy = ROW_OFFSET[direction]
    tiles = []
    for r in range(rows):
        row = []
        for i in range(length):
            tx = sx + dx * i + rdx * r * row_spacing
            ty = sy + dy * i + rdy * r * row_spacing
            row.append((tx, ty))
        is_reverse = (r % 2 == 1)
        if is_reverse:
            row.reverse()
        tiles.append((row, is_reverse))
    return tiles


def check_stamina():
    cur, mx = api.player_stamina()
    if cur / mx < STAMINA_THRESHOLD:
        api.log(f"stamina low: {cur}/{mx} ({cur/mx:.0%}), stopping")
        return False
    return True


def refill_water():
    api.log("watering can empty, refilling...")
    result = api.refill_water()
    if result.get("ok"):
        api.log(f"refilled: {result.get('water')}/{result.get('max')}")
        return True
    api.log("could not refill")
    return False


def use_tool_at(tx, ty, tool_or_item, is_reverse, direction):
    if is_reverse:
        ox, oy = STAND_OFFSET_REVERSE[direction]
        face = FACE_REVERSE[direction]
    else:
        ox, oy = STAND_OFFSET_FORWARD[direction]
        face = FACE_FORWARD[direction]

    api.move_to(tx + ox, ty + oy)
    api.face(face)
    time.sleep(0.1)
    api.select(tool_or_item)
    time.sleep(0.1)
    api.use_item()
    time.sleep(TOOL_DELAY)


def run():
    direction = args.dir
    tiles = calc_tiles(args.start_x, args.start_y, args.length,
                       direction, args.rows, args.row_spacing)
    total = sum(len(row) for row, _ in tiles)
    api.log(f"=== farm skill: {total} tiles, dir={direction}, rows={args.rows}, seed={args.seed} ===")

    for row, is_reverse in tiles:
        for tx, ty in row:
            if not check_stamina():
                api.log(f"stopped at ({tx},{ty}) due to low stamina")
                return

            # till
            use_tool_at(tx, ty, "Hoe", is_reverse, direction)

            # plant
            use_tool_at(tx, ty, args.seed, is_reverse, direction)

            # water
            if not args.skip_water:
                water, _ = api.watering_can_water()
                if water is not None and water <= 0:
                    if not refill_water():
                        return
                use_tool_at(tx, ty, "Watering Can", is_reverse, direction)

    api.log(f"=== done ===")


if __name__ == "__main__":
    try:
        st = api.status()
        if not st.get("worldReady"):
            print("game not ready")
            sys.exit(1)
    except Exception as e:
        print(f"cannot connect: {e}")
        sys.exit(1)
    run()
