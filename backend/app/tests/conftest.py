"""测试隔离：每个用例使用独立 DATA_DIR 的全新 seed 库。

db.db_path() 每次连接都重新读 DATA_DIR，因此 monkeypatch 后无需重导入；
纯引擎用例（test_rota/test_debt_engine）不碰数据库，fixture 对它们无副作用。
"""

import pytest


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app import seed
    seed.init_db()
    yield
