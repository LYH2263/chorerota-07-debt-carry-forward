from app.db import connect

def init_db():
    c = connect()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY, name TEXT, active INT, data_quality TEXT);
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT, weight INT, data_quality TEXT);
    CREATE TABLE IF NOT EXISTS weeks(id INTEGER PRIMARY KEY, label TEXT, status TEXT, frozen INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY AUTOINCREMENT, week_id INT, day INT, task_id INT, member_id INT, task_weight INT);
    CREATE TABLE IF NOT EXISTS swap_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, week_id INT, a_day INT, a_task INT, b_day INT, b_task INT, status TEXT, note TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS debt_entries(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      week_id INTEGER NOT NULL,
      member_id INTEGER NOT NULL,
      slots INTEGER NOT NULL,
      load INTEGER NOT NULL,
      avg_load REAL NOT NULL,
      debt_before REAL NOT NULL,
      debt_after REAL NOT NULL,
      frozen INTEGER NOT NULL DEFAULT 0,
      UNIQUE(week_id, member_id)
    );
    CREATE INDEX IF NOT EXISTS idx_debt_member_week ON debt_entries(member_id, week_id);
    """)
    # 幂等迁移：老库补列（CREATE TABLE IF NOT EXISTS 不会改既有表）
    assign_cols = {r["name"] for r in c.execute("PRAGMA table_info(assignments)")}
    if "task_weight" not in assign_cols:
        c.execute("ALTER TABLE assignments ADD COLUMN task_weight INTEGER")
    week_cols = {r["name"] for r in c.execute("PRAGMA table_info(weeks)")}
    if "frozen" not in week_cols:
        c.execute("ALTER TABLE weeks ADD COLUMN frozen INTEGER NOT NULL DEFAULT 0")
    if c.execute("SELECT COUNT(*) c FROM members").fetchone()["c"] == 0:
        c.executemany("INSERT INTO members(name,active,data_quality) VALUES (?,?,?)", [
            ("阿明", 1, "clean"), ("小雨", 1, "clean"), ("爷爷", 1, "clean"),
            ("幽灵成员", 0, "dirty"),
        ])
        c.executemany("INSERT INTO tasks(title,weight,data_quality) VALUES (?,?,?)", [
            ("洗碗", 1, "clean"), ("倒垃圾", 1, "clean"), ("扫地", 2, "clean"),
            ("负权重任务", -1, "dirty"),
        ])
        c.execute("INSERT INTO weeks(label,status) VALUES ('第12周','draft')")
        c.execute("INSERT INTO settings(key,value) VALUES ('household','绿纸之家')")
        c.commit()
    c.close()
