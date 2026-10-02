"""只读投影：把已落定的周债快照投给看板与成员页。

不做任何计算/回刷，只读 week_member_debt —— 所以"钉"在哪里，页面就显示在哪里，
改现行任务权重不会改变这里读出的旧周数字。
"""

from __future__ import annotations


def week_debt(c, week_id: int) -> dict:
    """某周看板/回包的债视图：债前、本周占格(load/slots)、增量、债后、冻结。"""
    rows = c.execute("""
        SELECT d.member_id AS member_id, m.name AS name,
               d.load AS load, d.slots AS slots, d.before_debt AS before,
               d.delta AS delta, d.after_debt AS after, d.frozen AS frozen
        FROM week_member_debt d JOIN members m ON m.id = d.member_id
        WHERE d.week_id = ? ORDER BY d.member_id
    """, (week_id,)).fetchall()
    frozen_row = c.execute(
        "SELECT MAX(frozen) AS f FROM week_member_debt WHERE week_id=?", (week_id,)).fetchone()
    return {
        "week_id": week_id,
        "frozen": bool(frozen_row["f"]) if frozen_row and frozen_row["f"] is not None else False,
        "members": [dict(r) for r in rows],
    }


def member_debts(c) -> list[dict]:
    """成员页债表：每个成员最近一次落定周的债后余额（即当前结欠）。"""
    members = c.execute("SELECT id,name,active FROM members ORDER BY id").fetchall()
    latest = {r["member_id"]: r for r in c.execute("""
        SELECT d.member_id AS member_id, d.after_debt AS current_debt,
               d.week_id AS week_id, w.label AS label
        FROM week_member_debt d
        JOIN weeks w ON w.id = d.week_id
        JOIN (SELECT member_id, MAX(week_id) AS max_week FROM week_member_debt GROUP BY member_id) p
          ON p.member_id = d.member_id AND p.max_week = d.week_id
    """)}
    out = []
    for m in members:
        row = latest.get(m["id"])
        out.append({
            "member_id": m["id"],
            "name": m["name"],
            "active": bool(m["active"]),
            "current_debt": float(row["current_debt"]) if row else 0.0,
            "week_id": row["week_id"] if row else None,
            "label": row["label"] if row else None,
        })
    return out


def member_history(c, member_id: int) -> dict:
    """按周回看：某成员逐周的债前/占格/增量/债后（顺序按周）。"""
    m = c.execute("SELECT id,name,active FROM members WHERE id=?", (member_id,)).fetchone()
    rows = c.execute("""
        SELECT d.week_id AS week_id, w.label AS label, d.load AS load, d.slots AS slots,
               d.before_debt AS before, d.delta AS delta, d.after_debt AS after,
               d.frozen AS frozen
        FROM week_member_debt d JOIN weeks w ON w.id = d.week_id
        WHERE d.member_id = ? ORDER BY d.week_id
    """, (member_id,)).fetchall()
    return {
        "member_id": member_id,
        "name": m["name"] if m else None,
        "active": bool(m["active"]) if m else False,
        "weeks": [dict(r) for r in rows],
    }
