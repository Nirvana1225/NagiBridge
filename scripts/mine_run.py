"""
挖矿脚本：进入矿洞 → 逐层挖掘 → 低血量自动撤退

用法:
    python mine_run.py [--hp-threshold 30] [--max-levels 5]

参数:
    --hp-threshold  血量百分比低于此值时撤退（默认 30）
    --max-levels    最多挖几层就返回（默认 5）
"""

import sys
import time
import argparse
import stardew_api as api

# ── 配置 ──
TOOL_DELAY = 0.7
SCAN_RADIUS = 8
RETREAT_EMOTE = 52  # angry emote 表示撤退

# 矿石/石头的物品名（surroundings 返回的 object 字段）
MINEABLE_OBJECTS = {"Stone", "Copper Node", "Iron Node", "Gold Node", "Iridium Node",
                    "Mystic Stone", "Gem Node", "Diamond Node", "Amethyst Node",
                    "Topaz Node", "Emerald Node", "Aquamarine Node", "Jade Node",
                    "Ruby Node", "Geode Node", "Frozen Geode Node",
                    "Magma Geode Node", "Omni Geode Node"}


def check_health(threshold_pct):
    """检查血量，返回 True 表示安全。"""
    hp, max_hp = api.player_health()
    pct = (hp / max_hp) * 100 if max_hp > 0 else 0
    api.log(f"  血量: {hp}/{max_hp} ({pct:.0f}%)")
    return pct >= threshold_pct


def check_stamina(threshold=10):
    """检查体力是否足够。"""
    sta, max_sta = api.player_stamina()
    return sta >= threshold


def find_minable_tiles():
    """扫描周围，返回可挖掘的 (x, y, name) 列表，按距离排序。"""
    data = api.surroundings(SCAN_RADIUS)
    px, py = data["center"]["x"], data["center"]["y"]
    targets = []

    for tile in data.get("tiles", []):
        obj = tile.get("object")
        if obj and obj in MINEABLE_OBJECTS:
            dist = abs(tile["x"] - px) + abs(tile["y"] - py)
            targets.append((tile["x"], tile["y"], obj, dist))

    targets.sort(key=lambda t: t[3])
    return [(x, y, name) for x, y, name, _ in targets]


def find_ladder():
    """扫描周围，寻找梯子（Ladder / Shaft）。"""
    data = api.surroundings(SCAN_RADIUS)
    for tile in data.get("tiles", []):
        obj = tile.get("object", "")
        if "Ladder" in obj or "Shaft" in obj:
            return tile["x"], tile["y"]
    return None


def find_passable_neighbor(tx, ty):
    """找到目标格旁边一个可通行的格子用于站立。"""
    data = api.surroundings(SCAN_RADIUS)
    blocked = set()
    for tile in data.get("tiles", []):
        if not tile.get("passable", True):
            blocked.add((tile["x"], tile["y"]))

    # 上下左右四个邻居
    for dx, dy, face_dir in [(0, -1, 2), (0, 1, 0), (-1, 0, 1), (1, 0, 3)]:
        nx, ny = tx + dx, ty + dy
        if (nx, ny) not in blocked:
            return nx, ny, face_dir
    return None


def mine_tile(tx, ty, name):
    """移动到石头旁，面向它，用镐敲碎。"""
    neighbor = find_passable_neighbor(tx, ty)
    if neighbor is None:
        api.log(f"  无法靠近 ({tx},{ty}) {name}，跳过")
        return False

    nx, ny, face_dir = neighbor
    api.move_to(nx, ny)
    api.face(face_dir)
    time.sleep(0.15)

    # 多敲几下（大石头可能需要）
    for _ in range(3):
        api.use_tool("Pickaxe")
        api.wait_tool_animation(TOOL_DELAY)

    return True


def go_to_mine_entrance():
    """尝试前往矿洞入口。"""
    loc = api.current_location()
    api.log(f"当前位置: {loc}")

    if loc == "Mine":
        api.log("已在矿洞中")
        return True

    if loc == "Mountain":
        api.log("在山区，走向矿洞入口...")
        api.move_to(54, 5)  # 矿洞入口大致位置
        time.sleep(0.5)
        api.interact()
        time.sleep(1.5)
        return api.current_location() != "Mountain"

    if loc == "Farm":
        api.log("在农场，先去山区...")
        api.move_to(69, 2)  # 农场北出口大致位置
        time.sleep(2)
        if api.current_location() == "Mountain":
            return go_to_mine_entrance()

    api.log(f"从 {loc} 出发可能无法自动到矿洞，请手动走到 Mountain 或 Mine 再运行")
    return False


def retreat():
    """撤退：离开矿洞。"""
    api.log("!!! 血量过低，撤退 !!!")
    api.emote(RETREAT_EMOTE)
    api.chat("血量不行了，先撤！")

    loc = api.current_location()
    if "Mine" in loc or "UndergroundMine" in loc:
        # 尝试找梯子向上走，或者用回城杖
        # 最简单的方式：使用 Return Scepter 或 Farm Warp Totem
        for escape_item in ["Return Scepter", "Farm Warp Totem", "Warp Totem: Farm"]:
            result = api.select(escape_item)
            if result.get("ok"):
                api.log(f"使用 {escape_item} 回城")
                api.use_item()
                time.sleep(2)
                return True

        # 没有传送道具，尝试找到楼梯向上
        api.log("没有传送道具，尝试向矿洞入口移动...")
        # MineShaft 入口通常在左上角附近
        api.move_to(6, 3)
        time.sleep(1)
        api.interact()
        time.sleep(1.5)

    return True


def mine_current_level(hp_threshold):
    """在当前层挖矿，返回 True 表示安全完成，False 表示需要撤退。"""
    api.log(f"--- 开始挖掘 [{api.current_location()}] ---")

    max_attempts = 30
    attempt = 0

    while attempt < max_attempts:
        attempt += 1

        # 血量检查
        if not check_health(hp_threshold):
            return False

        # 体力检查
        if not check_stamina():
            api.log("体力不足，停止挖掘")
            return False

        # 先看有没有梯子
        ladder = find_ladder()
        if ladder:
            api.log(f"  发现梯子 ({ladder[0]},{ladder[1]})，下楼！")
            api.move_to(ladder[0], ladder[1])
            time.sleep(0.3)
            api.interact()
            time.sleep(1.5)
            return True

        # 扫描可挖目标
        targets = find_minable_tiles()
        if not targets:
            api.log("  没有可挖的石头了，扫描更大范围...")
            time.sleep(0.5)
            # 扩大搜索或随机移动
            break

        # 挖最近的几个
        mined = 0
        for tx, ty, name in targets[:5]:
            if not check_health(hp_threshold):
                return False

            api.log(f"  挖掘 {name} ({tx},{ty})")
            if mine_tile(tx, ty, name):
                mined += 1

        if mined == 0:
            break

    # 最后再检查一次梯子
    ladder = find_ladder()
    if ladder:
        api.log(f"  发现梯子 ({ladder[0]},{ladder[1]})")
        api.move_to(ladder[0], ladder[1])
        time.sleep(0.3)
        api.interact()
        time.sleep(1.5)
        return True

    api.log("  本层没找到梯子，可能需要继续敲石头")
    return True


def run(hp_threshold, max_levels):
    api.log("=== 挖矿脚本启动 ===")
    api.log(f"血量撤退阈值: {hp_threshold}%，最大层数: {max_levels}")

    # 确保手持镐子
    result = api.select("Pickaxe")
    if not result.get("ok"):
        api.log("背包里没有镐子！")
        return

    # 前往矿洞
    if not go_to_mine_entrance():
        return

    levels_done = 0
    while levels_done < max_levels:
        if not check_health(hp_threshold):
            retreat()
            break

        safe = mine_current_level(hp_threshold)
        if not safe:
            retreat()
            break

        levels_done += 1
        api.log(f"=== 已完成 {levels_done}/{max_levels} 层 ===")

    api.log(f"=== 挖矿结束，共挖了 {levels_done} 层 ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="星露谷自动挖矿脚本")
    parser.add_argument("--hp-threshold", type=int, default=30, help="血量百分比撤退阈值")
    parser.add_argument("--max-levels", type=int, default=5, help="最多挖几层")
    args = parser.parse_args()

    try:
        st = api.status()
        if not st.get("worldReady"):
            api.log("游戏世界未就绪，请先进入游戏")
            sys.exit(1)
    except Exception as e:
        api.log(f"无法连接 NagiBridge: {e}")
        sys.exit(1)

    run(args.hp_threshold, args.max_levels)
