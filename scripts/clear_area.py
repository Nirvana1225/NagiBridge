"""
开垦skill：扫描区域 → 按工具分组 → 批量清除障碍物

用法:
    python clear_area.py <x1> <y1> <x2> <y2> [options]

参数:
    x1,y1  左上角坐标
    x2,y2  右下角坐标

选项:
    --port PORT   NagiBridge端口（默认 7843）
    --hits N      硬目标额外敲击次数（默认 2）

示例:
    python clear_area.py 50 20 70 30 --port 7843
    → 清除 (50,20)-(70,30) 区域内所有杂草、石头、树枝、树
"""

import argparse
import os
import time
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument("x1", type=int)
parser.add_argument("y1", type=int)
parser.add_argument("x2", type=int)
parser.add_argument("y2", type=int)
parser.add_argument("--port", type=int, default=7843)
parser.add_argument("--hits", type=int, default=2)
args = parser.parse_args()

os.environ["NAGI_URL"] = f"http://localhost:{args.port}"
import stardew_api as api

TOOL_DELAY = 0.55

TOOL_MAP = {
    "Weeds": ("Scythe", 1),
    "Grass": ("Scythe", 1),
    "Stone": ("Pickaxe", 2),
    "Twig": ("Axe", 1),
    "Tree": ("Axe", 3),
    "LargeStump": ("Axe", 4),
    "LargeLog": ("Axe", 4),
    "LargeBoulder": ("Pickaxe", 4),
    "MeteoriteOre": ("Pickaxe", 4),
}

TOOL_ORDER = ["Scythe", "Pickaxe", "Axe"]


def scan_area():
    cx = (args.x1 + args.x2) // 2
    cy = (args.y1 + args.y2) // 2
    radius = max(args.x2 - args.x1, args.y2 - args.y1) // 2 + 5

    api.move_to(cx, cy)
    data = api.surroundings(min(radius, 30))

    targets = []
    for t in data.get("tiles", []):
        x, y = t["x"], t["y"]
        if x < args.x1 or x > args.x2 or y < args.y1 or y > args.y2:
            continue

        obj = t.get("object", "")
        terrain = t.get("terrain", "")
        resource = t.get("resource", "")

        if obj in TOOL_MAP:
            name = obj
        elif resource in TOOL_MAP:
            name = resource
        elif terrain and terrain.startswith("Tree:"):
            name = "Tree"
        elif terrain == "Grass":
            name = "Grass"
        else:
            continue

        tool, hits = TOOL_MAP[name]
        targets.append((x, y, tool, name, hits))

    return targets


def clear_targets(targets):
    by_tool = defaultdict(list)
    for x, y, tool, name, hits in targets:
        by_tool[tool].append((x, y, name, hits))

    for tool in TOOL_ORDER:
        items = by_tool.get(tool, [])
        if not items:
            continue

        items.sort(key=lambda t: (t[1], t[0]))
        api.log(f"--- {tool}: {len(items)} targets ---")
        api.select(tool)
        time.sleep(0.15)

        for x, y, name, hits in items:
            api.move_to(x, y - 1)
            api.face(2)
            time.sleep(0.1)
            for h in range(hits):
                api.use_item()
                time.sleep(TOOL_DELAY)


def run():
    api.log(f"=== clear skill: ({args.x1},{args.y1})-({args.x2},{args.y2}) ===")

    targets = scan_area()
    by_tool = defaultdict(int)
    for _, _, tool, name, _ in targets:
        by_tool[tool] += 1
    api.log(f"found: {dict(by_tool)}, total={len(targets)}")

    if not targets:
        api.log("nothing to clear!")
        return

    clear_targets(targets)
    api.log(f"=== done: {len(targets)} obstacles cleared ===")


if __name__ == "__main__":
    try:
        st = api.status()
        if not st.get("worldReady"):
            print("game not ready")
            exit(1)
    except Exception as e:
        print(f"cannot connect: {e}")
        exit(1)
    run()
