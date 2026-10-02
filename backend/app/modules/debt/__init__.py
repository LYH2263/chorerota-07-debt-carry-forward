"""欠班债跨周结转模块：纯引擎 / 生成挂钩 / 读模型投影。"""

from app.modules.debt.engine import assign_with_debt, settle
from app.modules.debt.hooks import (
    WeekSettledError, BadDaysError,
    active_clean_member_ids, clean_positive_tasks, prior_balances, pin_generation,
)
from app.modules.debt.projection import week_ledger, members_debt_view

__all__ = [
    "assign_with_debt", "settle",
    "WeekSettledError", "BadDaysError",
    "active_clean_member_ids", "clean_positive_tasks", "prior_balances", "pin_generation",
    "week_ledger", "members_debt_view",
]
