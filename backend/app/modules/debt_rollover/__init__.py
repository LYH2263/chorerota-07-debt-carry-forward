"""生成挂钩：把欠班债引擎挂到周生成流程上，并落定不可变周快照。

职责
----
* 周生成时取每个成员"上一次落定周"的债后余额作为本周债前（跨周结转，允许中间有空档周）。
* 用债引擎做优先偿还分配，生成 assignments 后结算并写入 week_member_debt。
* 同一周重新生成只删除并重钉"本周"快照，结转源始终来自更早的周，
  因此改现行任务权重 / 重钉本周都不会回刷已钉的旧周债。
* 活跃成员不足（< 2，含全员 skip / 0 活跃）时整周冻结：delta=0，余额原样结转。
"""

from __future__ import annotations

from app.engines.debt import build_week_slots_balanced, settle_week


def active_member_ids(c) -> list[int]:
    """本周实际参与派格的成员：在岗且数据干净（skip/停用/脏数据被排除）。"""
    return [r["id"] for r in c.execute(
        "SELECT id FROM members WHERE active=1 AND data_quality='clean' ORDER BY id")]


def task_weights(c) -> dict[int, int]:
    """现行可用任务权重（落定当周时的当前值；改它不影响已落定旧周，因旧周已钉 load）。"""
    return {r["id"]: r["weight"] for r in c.execute(
        "SELECT id,weight FROM tasks WHERE data_quality='clean' AND weight>0")}


def carried_balances(c, week_id: int) -> dict[int, float]:
    """每个成员在本周之前最近一次落定周的债后余额（没有则 0）。

    按成员取 week_id < 当前的最大周，因此停用/skip 形成的空档周不会断链。
    """
    rows = c.execute("""
        SELECT d.member_id AS member_id, d.after_debt AS after_debt
        FROM week_member_debt d
        JOIN (
            SELECT member_id, MAX(week_id) AS max_week
            FROM week_member_debt WHERE week_id < ? GROUP BY member_id
        ) p ON p.member_id = d.member_id AND p.max_week = d.week_id
    """, (week_id,))
    return {r["member_id"]: float(r["after_debt"]) for r in rows}


def generate_week(c, week_id: int, days: int) -> dict:
    """在已打开的连接上生成一周（含债分配）、落定 assignments 与债快照。

    返回 {"count","slots","debt": settle_week 结果}。week 不存在时抛 LookupError。
    """
    week = c.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not week:
        raise LookupError("week not found")

    mids = active_member_ids(c)
    weights = task_weights(c)
    before = carried_balances(c, week_id)

    slots = build_week_slots_balanced(mids, weights, days, before=before)

    c.execute("DELETE FROM assignments WHERE week_id=?", (week_id,))
    for s in slots:
        c.execute("INSERT INTO assignments(week_id,day,task_id,member_id) VALUES (?,?,?,?)",
                  (week_id, s["day"], s["task_id"], s["member_id"]))

    settlement = settle_week(mids, slots, weights, before=before)

    # 重钉本周：只清本周快照；结转源来自更早的周，旧周债纹丝不动。
    c.execute("DELETE FROM week_member_debt WHERE week_id=?", (week_id,))
    pinned = settlement["members"]
    if settlement["frozen"] and not pinned:
        # 全员 skip（0 活跃）：没有活跃成员可结算，但要为有历史余额的成员钉一条冻结行，
        # 使冻结在看板可见、余额沿同一周链原样结转。
        pinned = [
            {"member_id": m, "load": 0.0, "slots": 0,
             "before": float(b), "delta": 0.0, "after": float(b)}
            for m, b in before.items()
        ]
    for row in pinned:
        c.execute("""INSERT INTO week_member_debt
            (week_id,member_id,load,slots,before_debt,delta,after_debt,frozen)
            VALUES (?,?,?,?,?,?,?,?)""",
            (week_id, row["member_id"], row["load"], row["slots"],
             row["before"], row["delta"], row["after"], 1 if settlement["frozen"] else 0))

    c.execute("UPDATE weeks SET status='ready' WHERE id=?", (week_id,))
    return {"count": len(slots), "slots": slots, "debt": settlement}
