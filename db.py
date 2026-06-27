import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

import os as _os
_data_dir = _os.environ.get("DATA_DIR", str(Path(__file__).parent / "data"))
DB_PATH = Path(_data_dir) / "app.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'employee',
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fanpages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    fb_url      TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_pages (
    user_id INTEGER NOT NULL,
    page_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, page_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (page_id) REFERENCES fanpages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ma_vach         TEXT,
    name            TEXT NOT NULL,
    link_anh        TEXT,
    gia_ban         REAL DEFAULT 0,
    danh_muc        TEXT,
    tinh_trang_kho  TEXT DEFAULT 'san',
    chien_luoc      TEXT DEFAULT 'mass',
    uu_tien         TEXT DEFAULT '2',
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS page_ratios (
    page_id     INTEGER NOT NULL,
    ratio_group TEXT NOT NULL,
    ratio_key   TEXT NOT NULL,
    percentage  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (page_id, ratio_group, ratio_key),
    FOREIGN KEY (page_id) REFERENCES fanpages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS page_settings (
    page_id INTEGER NOT NULL,
    key     TEXT NOT NULL,
    value   TEXT NOT NULL,
    PRIMARY KEY (page_id, key),
    FOREIGN KEY (page_id) REFERENCES fanpages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schedule_slots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    slot_date  TEXT NOT NULL,
    slot_order INTEGER NOT NULL DEFAULT 0,
    caption    TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (page_id)    REFERENCES fanpages(id)  ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)  ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
    _ensure_admin()


def _migrate(conn):
    """Add new columns to existing tables without losing data."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(schedule_slots)").fetchall()}
    if "media_type" not in cols:
        conn.execute("ALTER TABLE schedule_slots ADD COLUMN media_type TEXT DEFAULT ''")
    if "media_value" not in cols:
        conn.execute("ALTER TABLE schedule_slots ADD COLUMN media_value TEXT DEFAULT ''")


def _ensure_admin():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", generate_password_hash("admin123"), "admin"),
            )


# ── App settings ──────────────────────────────────────────────────────────────

def get_setting(key, default=None):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def set_setting(key, value):
    payload = json.dumps(value, ensure_ascii=False)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, payload),
        )


# ── Users ─────────────────────────────────────────────────────────────────────

def get_user_by_id(user_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def get_all_users():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    return [dict(r) for r in rows]


def create_user(username, password, role="employee"):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            (username, generate_password_hash(password), role),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_user_password(user_id, password):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (generate_password_hash(password), user_id),
        )


def delete_user(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))


def check_user_password(username, password):
    user = get_user_by_username(username)
    if not user:
        return None
    if check_password_hash(user["password_hash"], password):
        return user
    return None


# ── Fanpages ──────────────────────────────────────────────────────────────────

def get_fanpages():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM fanpages ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_fanpage(page_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM fanpages WHERE id=?", (page_id,)).fetchone()
    return dict(row) if row else None


def create_fanpage(name, fb_url="", description=""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO fanpages (name, fb_url, description) VALUES (?,?,?)",
            (name, fb_url, description),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_fanpage(page_id, name, fb_url="", description=""):
    with get_db() as conn:
        conn.execute(
            "UPDATE fanpages SET name=?, fb_url=?, description=? WHERE id=?",
            (name, fb_url, description, page_id),
        )


def delete_fanpage(page_id):
    with get_db() as conn:
        conn.execute("DELETE FROM fanpages WHERE id=?", (page_id,))


# ── User–Page assignment ───────────────────────────────────────────────────────

def get_user_pages(user_id):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT f.* FROM fanpages f
            JOIN user_pages up ON up.page_id = f.id
            WHERE up.user_id = ?
            ORDER BY f.name
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_page_users(page_id):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.role FROM users u
            JOIN user_pages up ON up.user_id = u.id
            WHERE up.page_id = ?
            ORDER BY u.username
            """,
            (page_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def assign_user_to_page(user_id, page_id):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_pages (user_id, page_id) VALUES (?,?)",
            (user_id, page_id),
        )


def remove_user_from_page(user_id, page_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM user_pages WHERE user_id=? AND page_id=?",
            (user_id, page_id),
        )


def user_has_page_access(user_id, page_id, role="employee"):
    if role == "admin":
        return True
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM user_pages WHERE user_id=? AND page_id=?",
            (user_id, page_id),
        ).fetchone()
    return row is not None


# ── Products ──────────────────────────────────────────────────────────────────

def clear_all_products():
    with get_db() as conn:
        conn.execute("DELETE FROM schedule_slots")
        conn.execute("DELETE FROM products")


def insert_products(products):
    with get_db() as conn:
        conn.executemany(
            """
            INSERT INTO products (ma_vach,name,link_anh,gia_ban,danh_muc,
                                  tinh_trang_kho,chien_luoc,uu_tien)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            [
                (
                    p.get("ma_vach", ""),
                    p["name"],
                    p.get("link_anh", ""),
                    p.get("gia_ban", 0),
                    p.get("danh_muc", ""),
                    p.get("tinh_trang_kho", "san"),
                    p.get("chien_luoc", "mass"),
                    p.get("uu_tien", "2"),
                )
                for p in products
            ],
        )


def get_all_products():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_products(limit=None):
    query = "SELECT * FROM products ORDER BY id"
    if limit:
        query += f" LIMIT {int(limit)}"
    with get_db() as conn:
        rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]


def count_products():
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]


def get_categories():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT danh_muc FROM products "
            "WHERE danh_muc IS NOT NULL AND danh_muc != '' ORDER BY danh_muc"
        ).fetchall()
    return [r["danh_muc"] for r in rows]


# ── Page ratios & settings ────────────────────────────────────────────────────

def get_page_ratios(page_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT ratio_group, ratio_key, percentage FROM page_ratios WHERE page_id=?",
            (page_id,),
        ).fetchall()
    result = {"type": {}, "category": {}}
    for r in rows:
        result[r["ratio_group"]][r["ratio_key"]] = r["percentage"]
    if not result["type"]:
        result["type"] = {"mass": 50.0, "thanh ly": 20.0, "mo ban": 20.0, "order": 10.0}
    return result


def save_page_ratios(page_id, type_ratios, category_ratios):
    with get_db() as conn:
        conn.execute("DELETE FROM page_ratios WHERE page_id=?", (page_id,))
        rows = []
        for k, v in type_ratios.items():
            rows.append((page_id, "type", k, float(v)))
        for k, v in category_ratios.items():
            rows.append((page_id, "category", k, float(v)))
        conn.executemany(
            "INSERT INTO page_ratios (page_id,ratio_group,ratio_key,percentage) VALUES (?,?,?,?)",
            rows,
        )


def get_page_setting(page_id, key, default=None):
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM page_settings WHERE page_id=? AND key=?",
            (page_id, key),
        ).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def set_page_setting(page_id, key, value):
    payload = json.dumps(value, ensure_ascii=False)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO page_settings (page_id,key,value) VALUES (?,?,?) "
            "ON CONFLICT(page_id,key) DO UPDATE SET value=excluded.value",
            (page_id, key, payload),
        )


# ── Schedule ──────────────────────────────────────────────────────────────────

def clear_schedule(page_id, week_start):
    """Delete all slots for page in the 7-day window starting week_start (YYYY-MM-DD)."""
    from datetime import date, timedelta
    start = date.fromisoformat(week_start)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    with get_db() as conn:
        conn.execute(
            f"DELETE FROM schedule_slots WHERE page_id=? AND slot_date IN ({','.join('?'*7)})",
            [page_id] + dates,
        )


def create_schedule(page_id, slots):
    """slots: list of {product_id, slot_date, slot_order}"""
    with get_db() as conn:
        conn.executemany(
            "INSERT INTO schedule_slots (page_id,product_id,slot_date,slot_order) VALUES (?,?,?,?)",
            [(page_id, s["product_id"], s["slot_date"], s["slot_order"]) for s in slots],
        )


def get_schedule(page_id, week_start):
    """Returns dict: {date_str: [slot_dicts]}"""
    from datetime import date, timedelta
    start = date.fromisoformat(week_start)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(7)]

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT ss.id, ss.slot_date, ss.slot_order, ss.caption,
                   ss.media_type, ss.media_value,
                   p.id AS product_id, p.name, p.link_anh, p.gia_ban,
                   p.danh_muc, p.tinh_trang_kho, p.chien_luoc, p.uu_tien
            FROM schedule_slots ss
            JOIN products p ON p.id = ss.product_id
            WHERE ss.page_id = ? AND ss.slot_date IN ({})
            ORDER BY ss.slot_date, ss.slot_order
            """.format(",".join("?" * 7)),
            [page_id] + dates,
        ).fetchall()

    result = {d: [] for d in dates}
    for r in rows:
        result[r["slot_date"]].append(dict(r))
    return result


def get_schedule_weeks(page_id):
    """Return distinct Monday dates that have schedule data for this page."""
    from datetime import date, timedelta
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT slot_date FROM schedule_slots WHERE page_id=? ORDER BY slot_date",
            (page_id,),
        ).fetchall()
    mondays = set()
    for r in rows:
        d = date.fromisoformat(r["slot_date"])
        monday = d - timedelta(days=d.weekday())
        mondays.add(monday.isoformat())
    return sorted(mondays)


def get_slot(slot_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM schedule_slots WHERE id=?", (slot_id,)).fetchone()
    return dict(row) if row else None


def swap_schedule_slots(slot_id_a, slot_id_b):
    with get_db() as conn:
        a = conn.execute(
            "SELECT slot_date, slot_order FROM schedule_slots WHERE id=?", (slot_id_a,)
        ).fetchone()
        b = conn.execute(
            "SELECT slot_date, slot_order FROM schedule_slots WHERE id=?", (slot_id_b,)
        ).fetchone()
        if not a or not b:
            return False
        conn.execute(
            "UPDATE schedule_slots SET slot_date=?, slot_order=? WHERE id=?",
            (b["slot_date"], b["slot_order"], slot_id_a),
        )
        conn.execute(
            "UPDATE schedule_slots SET slot_date=?, slot_order=? WHERE id=?",
            (a["slot_date"], a["slot_order"], slot_id_b),
        )
    return True


def update_slot_caption(slot_id, caption):
    with get_db() as conn:
        conn.execute(
            "UPDATE schedule_slots SET caption=? WHERE id=?", (caption, slot_id)
        )


def update_slot_media(slot_id, media_type, media_value):
    with get_db() as conn:
        conn.execute(
            "UPDATE schedule_slots SET media_type=?, media_value=? WHERE id=?",
            (media_type, media_value, slot_id),
        )


def clear_slot_media(slot_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE schedule_slots SET media_type='', media_value='' WHERE id=?",
            (slot_id,),
        )
