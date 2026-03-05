import sqlite3
import json
import os
from messenger import send_message

DB_PATH     = "tasks.db"
MENU_PATH   = os.path.join(os.path.dirname(__file__), "menu.json")
OWNER_NUMBER = os.getenv("OWNER_NUMBER", "919315544065")


# ──────────────────────────────────────────────
#  DB SETUP
# ──────────────────────────────────────────────

def init_menu_table():
    """
    Creates menu_items table and loads from menu.json.
    Called once at startup in database.py
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id                   TEXT PRIMARY KEY,   -- e.g. "M001"
            category_id          TEXT NOT NULL,       -- e.g. "mains"
            category_name        TEXT NOT NULL,       -- e.g. "🍛 Main Course"
            name                 TEXT NOT NULL,
            price                INTEGER NOT NULL,
            veg                  INTEGER DEFAULT 1,   -- 1=veg, 0=non-veg
            is_available         INTEGER DEFAULT 1,   -- 1=available, 0=unavailable
            stock_count          INTEGER DEFAULT 99,
            low_stock_threshold  INTEGER DEFAULT 3
        )
    """)
    conn.commit()

    # ── Load from menu.json only if table is empty ──
    c.execute("SELECT COUNT(*) FROM menu_items")
    count = c.fetchone()[0]

    if count == 0:
        _seed_menu_from_json(conn)

    conn.close()
    print("✅ Menu table ready")


def _seed_menu_from_json(conn):
    """Seeds menu_items table from menu.json on first run."""
    try:
        with open(MENU_PATH, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("⚠️  menu.json not found — menu table will be empty")
        return

    c = conn.cursor()
    threshold = data.get("low_stock_default_threshold", 3)

    for cat in data.get("categories", []):
        for item in cat.get("items", []):
            c.execute("""
                INSERT OR IGNORE INTO menu_items
                (id, category_id, category_name, name, price, veg,
                 is_available, stock_count, low_stock_threshold)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                item["id"],
                cat["id"],
                cat["name"],
                item["name"],
                item["price"],
                1 if item.get("veg", True) else 0,
                item.get("stock", 99),
                threshold
            ))
    conn.commit()
    print(f"✅ Menu seeded from menu.json")


# ──────────────────────────────────────────────
#  READ FUNCTIONS (used by menu_messages.py)
# ──────────────────────────────────────────────

def get_all_categories() -> list:
    """Returns list of unique categories that have at least one available item."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT category_id, category_name
        FROM menu_items
        WHERE is_available = 1
        ORDER BY category_id
    """)
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in rows]


def get_items_by_category(category_id: str) -> list:
    """Returns all available items in a category."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, name, price, veg, stock_count
        FROM menu_items
        WHERE category_id = ? AND is_available = 1
        ORDER BY name
    """, (category_id,))
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "price": r[2],
         "veg": bool(r[3]), "stock": r[4]}
        for r in rows
    ]


def get_all_available_items() -> list:
    """Returns all available items across all categories."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, category_id, category_name, name, price, veg, stock_count
        FROM menu_items
        WHERE is_available = 1
        ORDER BY category_id, name
    """)
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "category_id": r[1], "category_name": r[2],
         "name": r[3], "price": r[4], "veg": bool(r[5]), "stock": r[6]}
        for r in rows
    ]


def get_item_by_id(item_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "category_id": row[1], "category_name": row[2],
        "name": row[3], "price": row[4], "veg": bool(row[5]),
        "is_available": bool(row[6]), "stock_count": row[7],
        "low_stock_threshold": row[8]
    }


def search_item_by_name(name_query: str) -> list:
    """Fuzzy search items by name — used by owner update parser."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, name, category_name, price, is_available, stock_count
        FROM menu_items
        WHERE LOWER(name) LIKE ?
    """, (f"%{name_query.lower()}%",))
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "category": r[2],
         "price": r[3], "is_available": bool(r[4]), "stock": r[5]}
        for r in rows
    ]


# ──────────────────────────────────────────────
#  WRITE FUNCTIONS (used by owner_menu_update.py)
# ──────────────────────────────────────────────

def mark_item_unavailable(item_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE menu_items SET is_available = 0 WHERE id = ?", (item_id,)
    )
    conn.commit()
    conn.close()


def mark_item_available(item_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE menu_items SET is_available = 1 WHERE id = ?", (item_id,)
    )
    conn.commit()
    conn.close()


def update_stock_count(item_id: str, new_count: int):
    conn = sqlite3.connect(DB_PATH)
    # Auto mark unavailable if stock hits 0
    available = 1 if new_count > 0 else 0
    conn.execute(
        "UPDATE menu_items SET stock_count = ?, is_available = ? WHERE id = ?",
        (new_count, available, item_id)
    )
    conn.commit()
    conn.close()


def reset_menu():
    """Marks all items as available — called at start of day."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE menu_items SET is_available = 1")
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
#  LOW STOCK CHECKER (called by scheduler)
# ──────────────────────────────────────────────

def check_low_stock():
    """
    Checks for items running low on stock.
    Called by scheduler every hour.
    Sends one consolidated alert to owner — not one per item.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT name, stock_count, low_stock_threshold
        FROM menu_items
        WHERE is_available = 1
        AND stock_count <= low_stock_threshold
        AND stock_count > 0
        ORDER BY stock_count ASC
    """)
    low_items = c.fetchall()
    conn.close()

    if not low_items:
        return

    # Build consolidated alert
    alert = "⚠️ *Low Stock Alert*\n\nThese items are running low:\n\n"
    for name, count, threshold in low_items:
        alert += f"• {name}: only {count} left\n"

    alert += "\nReply 'stock [item name] [count]' to update\nExample: stock dal makhani 10"

    send_message(OWNER_NUMBER, alert)
    print(f"⚠️  Low stock alert sent for {len(low_items)} items")


def get_full_stock_report() -> str:
    """
    Returns a formatted stock report string.
    Used when owner asks 'stock report' or 'menu status'.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT category_name, name, stock_count, is_available
        FROM menu_items
        ORDER BY category_id, name
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        return "No menu items found."

    # Group by category
    report = "📊 *Menu Status*\n\n"
    current_cat = None

    for cat_name, name, stock, available in rows:
        if cat_name != current_cat:
            report += f"\n*{cat_name}*\n"
            current_cat = cat_name

        status = "✅" if available else "❌"
        report += f"{status} {name} — {stock} left\n"

    return report
