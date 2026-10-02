"""欠班债（chore debt）跨周结转引擎。

无状态纯函数：只管"算"，不碰数据库。落定与快照由 modules/debt_rollover 负责，
因此改现行任务权重只会影响之后新生成的周，已钉旧周债不会被回刷。

约定
----
* 每个格位 (day, task) 的权重负荷 = 该任务的 weight（int）。
* 成员当周负荷 load = 其分到格位的权重之和。
* 当周活跃成员均值 mean = 全部格位权重 / 活跃成员数。
* 债余额 balance 带符号、跨周结转：
    delta = mean - load （>0 少做→新增欠班；<0 多做→贷项）
    after = before + delta
  即多做形成的贷项（负债）会自动冲抵下一周，守恒：sum(delta) == 0。
* 活跃成员不足（< 2 人，含全员 skip / 0 活跃）时无法形成均值比较，
  当周冻结：不记新债也不冲销，余额原样结转。
"""

from __future__ import annotations

# 活跃成员数低于该阈值时冻结债结算（0 人除零、1 人无比较意义）。
MIN_ACTIVE_TO_SETTLE = 2
_EPS = 1e-9


def _r(x: float) -> float:
    """去掉浮点尾噪，便于快照与断言。"""
    x = round(float(x), 6)
    return 0.0 if abs(x) < _EPS else x


def member_loads(slots: list[dict], weights: dict[int, int]) -> dict[int, dict]:
    """汇总每个成员的本周占格：权重负荷 load 与格位数 slots。"""
    acc: dict[int, dict] = {}
    for s in slots:
        m = s["member_id"]
        row = acc.setdefault(m, {"member_id": m, "load": 0.0, "slots": 0})
        row["load"] += float(weights.get(s["task_id"], 0))
        row["slots"] += 1
    for row in acc.values():
        row["load"] = _r(row["load"])
    return acc


def build_week_slots_balanced(
    member_ids: list[int],
    task_weights: dict[int, int],
    days: int,
    before: dict[int, float] | None = None,
) -> list[dict]:
    """在 round-robin 网格上，让有欠债的成员优先多派格位偿还。

    逐格（day 外、task 内，与 build_week_slots 同序）贪心挑选当前综合欠账最大的成员：
        key(m) = before[m] + (target - load[m])
        target = 格位总权重 / 活跃人数
    key 越大越该补做；平局按 member_ids 原顺序，保证结果确定且与 round-robin 同样稳定。
    成员不足 2 人时退化为普通顺序分配（0 人返回空），由结算层判定冻结。
    """
    if not member_ids or not task_weights:
        return []
    before = before or {}
    order = list(member_ids)
    idx = {m: i for i, m in enumerate(order)}
    n = len(order)
    tasks = list(task_weights.keys())
    total_weight = sum(float(w) for w in task_weights.values()) * float(days)
    target = total_weight / n if n else 0.0

    load = {m: 0.0 for m in order}
    balance = True if n >= MIN_ACTIVE_TO_SETTLE else False
    slots: list[dict] = []
    for day in range(days):
        for tid in tasks:
            if balance:
                def key(m: int) -> tuple[float, int]:
                    return (_r(before.get(m, 0.0) + (target - load[m])), -idx[m])
                m = max(order, key=key)
            else:
                m = order[len(slots) % n]
            slots.append({"day": day, "task_id": tid, "member_id": m})
            load[m] += float(task_weights[tid])
    return slots


def settle_week(
    active_ids: list[int],
    slots: list[dict],
    weights: dict[int, int],
    before: dict[int, float] | None = None,
) -> dict:
    """结算一周。返回 frozen 标志、均值、每个成员的债前/增量/债后/本周占格。

    frozen=True 时（活跃 < 2 人）：delta 一律 0，after=before，余额原样结转。
    返回的 members 以 active_ids 顺序排列；before 中含但本周不活跃的成员不在此结算，
    其余额由调用方在结转时原样保留。
    """
    before = before or {}
    loads = member_loads(slots, weights)
    active = list(active_ids)
    frozen = len(active) < MIN_ACTIVE_TO_SETTLE

    total = sum(float(weights.get(s["task_id"], 0)) for s in slots)
    mean = _r(total / len(active)) if not frozen else 0.0

    # 先各自四舍五入，再让增量绝对值最大的一行吸收舍入残差，保证 sum(delta)==0
    # （独立四舍五入会产生 ±1e-6 的守恒误差）。
    raw_deltas = [0.0 if frozen else (mean - loads.get(m, {}).get("load", 0.0)) for m in active]
    rounded = [_r(d) for d in raw_deltas]
    if rounded:
        residual = _r(-sum(rounded))
        if abs(residual) > _EPS:
            k = max(range(len(rounded)), key=lambda i: abs(rounded[i]))
            rounded[k] = _r(rounded[k] + residual)

    rows = []
    for m, delta in zip(active, rounded):
        load = loads.get(m, {}).get("load", 0.0)
        count = loads.get(m, {}).get("slots", 0)
        b = _r(before.get(m, 0.0))
        after = _r(b + delta)  # 用已守恒的舍入增量，保证 after == before + delta
        rows.append({
            "member_id": m,
            "load": load,          # 本周占格权重
            "slots": count,        # 本周占格数
            "before": b,           # 债前（上周结转）
            "delta": delta,        # 本周新增（正=新欠，负=多做贷项）
            "after": after,        # 债后（结转下周）
        })
    return {"frozen": frozen, "mean": mean, "members": rows}
