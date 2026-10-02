"""生成挂钩：在周生成落定时把占格与债务台账钉死（不可变）。

只操作路由传入的 sqlite 连接；week 是否存在、commit/close 由路由负责。
钉后不可重新生成（WeekSettledError -> 409）；对调永不重算台账。
"""

from app.modules.debt.engine import assign_with_debt, settle

MIN_DAYS, MAX_DAYS = 1, 31
# 活跃成员不足此数（含全员 skip 的 0 人）时冻结：照常生成占格但不结算债
MIN_ACTIVE_TO_SETTLE = 2


class WeekSettledError(Exception):
    """该周已钉台账，不可重新生成。"""


class BadDaysError(Exception):
    """days 超出允许范围。"""


def active_clean_member_ids(c):
    return [r["id"] for r in c.execute(
        "SELECT id FROM members WHERE active=1 AND data_quality='clean' ORDER BY id")]


def clean_positive_tasks(c):
    """返回 [(task_id, weight), ...]，clean 且 weight>0，按 id 升序。"""
    return [(r["id"], r["weight"]) for r in c.execute(
        "SELECT id, weight FROM tasks WHERE data_quality='clean' AND weight>0 ORDER BY id")]


def prior_balances(c, week_id, member_ids):
    """每成员截至本周之前最近一次钉账后的余额；冻结周也串联（after==before）。"""
    balances = {}
    for mid in member_ids:
        row = c.execute(
            "SELECT debt_after FROM debt_entries "
            "WHERE member_id=? AND week_id<? ORDER BY week_id DESC LIMIT 1",
            (mid, week_id)).fetchone()
        balances[mid] = row["debt_after"] if row else 0.0
    return balances


def pin_generation(c, week_id, days=7):
    """生成并落钉一周。成功返回生成回包（含 debts 钉账行）；不 commit。"""
    if days < MIN_DAYS or days > MAX_DAYS:
        raise BadDaysError(f"days must be in [{MIN_DAYS},{MAX_DAYS}]")
    pinned = c.execute(
        "SELECT 1 FROM debt_entries WHERE week_id=? LIMIT 1", (week_id,)).fetchone()
    if pinned:
        raise WeekSettledError(f"week {week_id} already settled")

    mids = active_clean_member_ids(c)
    tasks = clean_positive_tasks(c)
    frozen = 1 if len(mids) < MIN_ACTIVE_TO_SETTLE else 0
    balances = prior_balances(c, week_id, mids)

    slots = assign_with_debt(mids, tasks, days=days, debt_before=balances)
    rows = settle(mids, slots, balances, frozen=bool(frozen))

    # 尚未落钉才可清空重建；格位携带任务权重快照，事后改 tasks.weight 不回刷
    c.execute("DELETE FROM assignments WHERE week_id=?", (week_id,))
    c.executemany(
        "INSERT INTO assignments(week_id,day,task_id,member_id,task_weight) "
        "VALUES (?,?,?,?,?)",
        [(week_id, s["day"], s["task_id"], s["member_id"], s["task_weight"]) for s in slots])

    c.executemany(
        "INSERT INTO debt_entries(week_id,member_id,slots,load,avg_load,debt_before,debt_after,frozen) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [(week_id, r["member_id"], r["slots"], r["load"], r["avg_load"],
          r["debt_before"], r["debt_after"], r["frozen"]) for r in rows])

    c.execute("UPDATE weeks SET status='ready', frozen=? WHERE id=?", (frozen, week_id))

    names = {r["id"]: r["name"] for r in c.execute("SELECT id,name FROM members")}
    debts = []
    for r in rows:
        debts.append({**r, "member_name": names.get(r["member_id"], "?")})
    return {"count": len(slots), "frozen": frozen, "slots": slots, "debts": debts}
