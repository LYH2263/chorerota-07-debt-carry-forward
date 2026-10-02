"""欠班债：记债、优先偿还（含多做贷项冲下周）、冻结，以及旧周债不回刷。"""

import pytest

from app.engines.debt import build_week_slots_balanced, settle_week
from app.db import connect
from app import seed
from app.modules import debt_rollover


# ---------- 纯引擎 ----------

def _run_week(active, weights, days, before):
    slots = build_week_slots_balanced(active, weights, days, before=before)
    return slots, settle_week(active, slots, weights, before=before)


def _by_member(settlement):
    return {r["member_id"]: r for r in settlement["members"]}


def test_records_debt_below_mean_and_credit_above():
    # 3 人、单任务权重 1、7 天 = 7 格，均值 7/3。占 3 格者多做（贷项），占 2 格者欠班。
    _, s = _run_week([1, 2, 3], {10: 1}, 7, {})
    rows = _by_member(s)
    assert s["frozen"] is False
    assert rows[1]["load"] == 3 and rows[1]["delta"] < 0          # 多做 -> 负（贷项）
    assert rows[2]["load"] == 2 and rows[2]["delta"] > 0          # 少做 -> 欠班
    assert rows[3]["delta"] > 0
    assert abs(sum(r["delta"] for r in s["members"])) < 1e-6      # 守恒


def test_debtor_gets_priority_slots_and_debt_clears():
    # 2 人、权重 1、3 天 = 3 格，均值 1.5。
    _, w1 = _run_week([1, 2], {10: 1}, 3, {})
    before = {m: r["after"] for m, r in _by_member(w1).items()}
    assert before[2] == 0.5 and before[1] == -0.5                 # 2 欠班，1 多做

    slots, w2 = _run_week([1, 2], {10: 1}, 3, before)
    loads = _by_member(w2)
    # 欠债的 2 号在第二周被优先多派：拿到 2 格（1 号 1 格）。
    counts = {}
    for sl in slots:
        counts[sl["member_id"]] = counts.get(sl["member_id"], 0) + 1
    assert counts[2] == 2 and counts[1] == 1
    # 优先偿还 + 1 号的多做贷项冲抵后，两边债清零。
    assert loads[2]["before"] == 0.5 and loads[2]["after"] == 0
    assert loads[1]["before"] == -0.5 and loads[1]["after"] == 0


def test_frozen_when_active_insufficient():
    # 1 人活跃：即便独占全部格位也冻结，不记新债，余额原样结转。
    slots, s = _run_week([1], {10: 1}, 7, {1: 2.0})
    assert s["frozen"] is True
    row = s["members"][0]
    assert row["delta"] == 0 and row["after"] == 2.0 and row["before"] == 2.0
    assert row["load"] == 7                                        # 活照干，但不结算

    # 0 活跃（全员 skip）：无格、冻结。
    empty, s0 = _run_week([], {10: 1}, 7, {})
    assert empty == [] and s0["frozen"] is True and s0["members"] == []


# ---------- 数据库：结转 + 旧周不回刷 + 冻结 ----------

@pytest.fixture()
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    seed.init_db()
    c = connect()
    yield c
    c.close()


def _debt_rows(c, week_id):
    return {r["member_id"]: dict(r) for r in c.execute(
        "SELECT * FROM week_member_debt WHERE week_id=? ORDER BY member_id", (week_id,))}


def test_carryover_and_weight_change_does_not_rewrite_old_week(db):
    c = db
    debt_rollover.generate_week(c, 1, days=7)                     # 第1周落定
    w1_before_change = {m: r["after_debt"] for m, r in _debt_rows(c, 1).items()}
    w1_load = {m: r["load"] for m, r in _debt_rows(c, 1).items()}

    # 只改现行任务权重，并生成下一周；旧周快照必须原样（不回刷）。
    c.execute("UPDATE tasks SET weight=100 WHERE id=3")
    c.execute("INSERT INTO weeks(label,status) VALUES ('第13周','draft')")
    debt_rollover.generate_week(c, 2, days=7)

    w1_after = _debt_rows(c, 1)
    assert {m: r["after_debt"] for m, r in w1_after.items()} == w1_before_change
    assert {m: r["load"] for m, r in w1_after.items()} == w1_load

    # 第2周的债前 = 第1周的债后（跨周结转）。
    for m, r in _debt_rows(c, 2).items():
        assert r["before_debt"] == w1_before_change[m]


def test_regenerate_current_week_does_not_touch_older(db):
    c = db
    debt_rollover.generate_week(c, 1, days=7)
    c.execute("INSERT INTO weeks(label,status) VALUES ('第13周','draft')")
    debt_rollover.generate_week(c, 2, days=7)
    w1 = {m: r["after_debt"] for m, r in _debt_rows(c, 1).items()}
    # 重新生成第2周（重钉本周）：第1周债不变。
    debt_rollover.generate_week(c, 2, days=5)
    assert {m: r["after_debt"] for m, r in _debt_rows(c, 1).items()} == w1


def test_frozen_week_carries_balance_unchanged(db):
    c = db
    debt_rollover.generate_week(c, 1, days=7)
    carried = _debt_rows(c, 1)[1]["after_debt"]
    # 只留 1 个活跃成员（其余 skip），活跃不足 -> 冻结。
    c.execute("UPDATE members SET active=0 WHERE id IN (2,3)")
    c.execute("INSERT INTO weeks(label,status) VALUES ('第13周','draft')")
    debt_rollover.generate_week(c, 2, days=7)
    row = _debt_rows(c, 2)[1]
    assert row["frozen"] == 1 and row["delta"] == 0.0
    assert row["before_debt"] == carried and row["after_debt"] == carried
