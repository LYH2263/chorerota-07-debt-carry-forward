"""欠班债纯逻辑引擎：不触碰数据库，输入/输出均为 list/dict。

记号约定（signed balance）：
- debt 为正 = 欠债（本周负荷低于活跃成员均值，少做）；
- debt 为负 = 结余/预付（多做），可冲抵下一周。
"""

from app.engines.rota import build_week_slots


def assign_with_debt(member_ids, tasks, days=7, debt_before=None):
    """按债务优先派格位，返回网格序（day 升序、同 day 内 task_id 升序）。

    member_ids: 当周活跃成员 id，升序
    tasks:      [(task_id, weight), ...]，clean 且 weight>0，按 id 升序
    debt_before: {member_id: float}，缺视为 0

    重格位先派（LPT）；每格选当前「调整负荷」最低者：
    adjusted = load - debt_before —— 欠债越多分越低，越优先得格（含重格）；
    次键为已占格位数（少派者优先），末键 member_id 保证确定性。
    """
    if not member_ids or not tasks:
        return []
    debt_before = debt_before or {}
    weight = {tid: w for tid, w in tasks}

    # 复用 round-robin 引擎铺出 day×task 网格位置，只取其位置不取其派位
    positions = build_week_slots(member_ids, [tid for tid, _ in tasks], days)
    load = {m: 0 for m in member_ids}
    count = {m: 0 for m in member_ids}

    def key(m):
        adjusted = load[m] - debt_before.get(m, 0.0)
        return (round(adjusted, 9), count[m], m)

    for p in sorted(positions, key=lambda x: (-weight[x["task_id"]], x["day"], x["task_id"])):
        mid = min(member_ids, key=key)
        p["member_id"] = mid
        p["task_weight"] = weight[p["task_id"]]
        load[mid] += p["task_weight"]
        count[mid] += 1
    return positions


def settle(member_ids, slots, debt_before, frozen=False):
    """结算一周：占格统计 + 均值 + 债前/债后余额。

    返回按 member_ids 顺序的 dict 列表；member_ids 为空时返回 []（不除零）。
    冻结周不结算：debt_after 原样等于 debt_before（余额结转，后续正常周继续累加）。
    """
    if not member_ids:
        return []
    debt_before = debt_before or {}
    slots_count = {m: 0 for m in member_ids}
    load = {m: 0 for m in member_ids}
    for s in slots:
        mid = s["member_id"]
        if mid in load:
            slots_count[mid] += 1
            load[mid] += s["task_weight"]
    avg = sum(load.values()) / len(member_ids)
    rows = []
    for mid in member_ids:
        before = debt_before.get(mid, 0.0)
        after = before if frozen else before + (avg - load[mid])
        rows.append({
            "member_id": mid,
            "slots": slots_count[mid],
            "load": load[mid],
            "avg_load": avg,
            "debt_before": before,
            "debt_after": after,
            "frozen": 1 if frozen else 0,
        })
    return rows
