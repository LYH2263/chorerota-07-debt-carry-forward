"""纯债引擎测试：记债、优先偿还、多做冲抵、冻结、确定性、空输入。"""

from app.modules.debt.engine import assign_with_debt, settle

TASKS = [(1, 1), (2, 1), (3, 2)]  # 洗碗 / 倒垃圾 / 扫地
MEMBERS = [1, 2, 3]


def test_balanced_weighted_load_and_grid_order():
    # seed 场景：3 人 × (1,1,2) × 7 天 = 总负荷 28，贪心派位逼近均分
    slots = assign_with_debt(MEMBERS, TASKS, days=7, debt_before={})
    assert len(slots) == 21
    # 返回保持网格序：day 升序、同 day 内 task_id 升序
    assert [(s["day"], s["task_id"]) for s in slots] == \
        [(d, t) for d in range(7) for (t, _) in TASKS]
    loads = {m: 0 for m in MEMBERS}
    counts = {m: 0 for m in MEMBERS}
    for s in slots:
        loads[s["member_id"]] += s["task_weight"]
        counts[s["member_id"]] += 1
    assert loads == {1: 10, 2: 9, 3: 9}
    assert counts == {1: 7, 2: 7, 3: 7}
    # 每个格位都带权重快照
    assert all(s["task_weight"] in (1, 2) for s in slots)


def test_settle_records_signed_debt():
    slots = assign_with_debt(MEMBERS, TASKS, days=7, debt_before={})
    rows = settle(MEMBERS, slots, {})
    by = {r["member_id"]: r for r in rows}
    assert by[1]["load"] == 10 and by[1]["slots"] == 7
    assert by[1]["debt_after"] < 0          # 多做 → 结余（负）
    assert by[2]["debt_after"] > 0          # 少做 → 欠债（正）
    assert by[3]["debt_after"] > 0
    assert by[1]["avg_load"] == 28 / 3
    assert abs(sum(r["debt_after"] for r in rows)) < 1e-9  # 同周活跃集合内零和


def test_priority_repayment():
    # 第 1 周落钉后，欠债 +0.33 的成员下周优先拿重格位还债
    first = settle(MEMBERS, assign_with_debt(MEMBERS, TASKS, 7, {}), {})
    before = {r["member_id"]: r["debt_after"] for r in first}
    second = assign_with_debt(MEMBERS, TASKS, days=7, debt_before=before)
    loads = {m: 0 for m in MEMBERS}
    for s in second:
        loads[s["member_id"]] += s["task_weight"]
    # 两名欠债者（2、3）之一本周多扛重格位，负荷达到 10；债权人 1 降到 9
    assert loads[2] == 10 or loads[3] == 10
    assert loads[1] == 9
    rows = settle(MEMBERS, second, before)
    # 优先受偿的欠债者本周翻过均值，转为小额结余
    repayer = 2 if loads[2] == 10 else 3
    assert rows[repayer - 1]["debt_after"] < 0


def test_credit_holder_gets_fewer_heavy_slots():
    # 单方预付很多（debt_before 负得多）→ 下周明显少扛
    slots = assign_with_debt([1, 2], [(10, 1), (20, 3)], days=4,
                             debt_before={1: -6.0, 2: 6.0})
    loads = {1: 0, 2: 0}
    for s in slots:
        loads[s["member_id"]] += s["task_weight"]
    assert loads[1] < loads[2]


def test_freeze_passthrough():
    slots = assign_with_debt([1], TASKS, days=7)
    rows = settle([1], slots, {1: 2.5}, frozen=True)
    assert len(rows) == 1
    assert rows[0]["debt_after"] == 2.5 == rows[0]["debt_before"]
    assert rows[0]["frozen"] == 1
    assert rows[0]["avg_load"] == rows[0]["load"]


def test_deterministic_tie_break():
    a = assign_with_debt(MEMBERS, TASKS, 7, {})
    b = assign_with_debt(MEMBERS, TASKS, 7, {})
    assert [(s["day"], s["task_id"], s["member_id"]) for s in a] == \
           [(s["day"], s["task_id"], s["member_id"]) for s in b]
    # 完全同态时低 id 先得格
    slots = assign_with_debt([7, 8], [(1, 1)], days=2, debt_before={})
    assert slots[0]["member_id"] == 7 and slots[1]["member_id"] == 8


def test_empty_inputs():
    assert assign_with_debt([], TASKS, 7) == []
    assert assign_with_debt(MEMBERS, [], 7) == []
    assert settle([], [], {}) == []
