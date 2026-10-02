"""读模型投影：看板占格/按周回看 与 成员页债表，同源于钉死的 debt_entries。"""


def week_ledger(c, week_id):
    """某周的钉账快照。无台账行（旧版周/未生成）时 pinned=False，不编造数字。"""
    week = c.execute("SELECT frozen FROM weeks WHERE id=?", (week_id,)).fetchone()
    rows = [dict(r) for r in c.execute(
        """SELECT de.member_id, m.name AS member_name, de.slots, de.load,
                  de.avg_load, de.debt_before, de.debt_after, de.frozen
           FROM debt_entries de JOIN members m ON m.id = de.member_id
           WHERE de.week_id = ? ORDER BY de.member_id""",
        (week_id,))]
    return {
        "pinned": bool(rows),
        "frozen": week["frozen"] if week else 0,
        "mean": rows[0]["avg_load"] if rows else None,
        "rows": rows,
    }


def members_debt_view(c):
    """成员页投影：每成员最新余额（含停用成员、无历史=0）+ 逐周台账 + 周表头。"""
    members = [dict(r) for r in c.execute("SELECT * FROM members ORDER BY id")]
    weeks = [dict(r) for r in c.execute(
        "SELECT id AS week_id, label, status, frozen FROM weeks ORDER BY id")]
    entries = [dict(r) for r in c.execute(
        """SELECT de.week_id, de.member_id, de.slots, de.load, de.avg_load,
                  de.debt_before, de.debt_after, de.frozen
           FROM debt_entries de ORDER BY de.week_id, de.member_id""")]

    latest = {}
    for e in entries:
        latest[e["member_id"]] = e  # entries 已按 week_id 升序，最后一条即最新
    for m in members:
        e = latest.get(m["id"])
        m["current_balance"] = e["debt_after"] if e else 0.0
        m["last_week_id"] = e["week_id"] if e else None
        m["last_frozen"] = e["frozen"] if e else 0
    return {"members": members, "weeks": weeks, "entries": entries}
