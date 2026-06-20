"""Ingredient override management backed by SQLite.

Stores ingredient name -> fdc_id mappings that take priority over FTS search.
Persists in the runtime database so overrides survive container rebuilds.
"""

import sqlite3
from datetime import datetime, timezone

from app.config import settings

# Default overrides seeded on first run. These cover common ingredients
# where FTS ranking consistently picks the wrong USDA entry.
DEFAULT_OVERRIDES: dict[str, int] = {
    # Proteins
    "egg": 171287,          # Egg, whole, raw, fresh
    "eggs": 171287,
    # Dairy
    "butter": 173410,       # Butter, salted
    "milk": 171265,         # Milk, whole, 3.25% milkfat
    "cream cheese": 2346385,# Cream cheese, full fat, block
    "sour cream": 171257,   # Cream, sour, cultured
    "parmesan cheese": 171247,  # Cheese, parmesan, grated
    "parmesan": 171247,
    # Oils
    "olive oil": 171413,    # Oil, olive, salad or cooking
    "extra virgin olive oil": 171413,
    "vegetable oil": 171411,# Oil, soybean, salad or cooking
    "cooking oil": 171411,
    # Nuts
    "walnuts": 170187,      # Nuts, walnuts, english
    "walnut": 170187,
    "pecans": 170182,       # Nuts, pecans
    "almonds": 170567,      # Nuts, almonds
    # Spices & seasonings
    "cinnamon": 171320,     # Spices, cinnamon, ground
    "black pepper": 170931, # Spices, pepper, black
    "pepper": 170931,
    "bay leaves": 170917,   # Spices, bay leaf
    "bay leaf": 170917,
    "sea salt": 173468,     # Salt, table
    "sea salt flakes": 173468,
    "kosher salt": 173468,
    "salt": 173468,
    # Vegetables
    "onion": 170000,        # Onions, raw
    "onions": 170000,
    "brown onion": 170000,
    "yellow onion": 170000,
    "white onion": 170000,
    "red onion": 790577,    # Onions, red, raw
    "garlic": 169230,       # Garlic, raw
    # Canned goods
    "canned tomatoes": 333281,      # Tomatoes, canned, red, ripe, diced
    "canned chopped tomatoes": 333281,
    "canned diced tomatoes": 333281,
    "diced tomatoes": 333281,
    "crushed tomatoes": 170501,     # Tomato products, crushed, canned
    "tomato paste": 170460,         # Tomato products, canned, puree
    "beef broth": 171538,           # Soup, beef broth, canned, ready-to-serve
    "beef stock": 171538,
    "chicken broth": 172192,        # Soup, chicken broth, ready-to-serve
    "chicken stock": 172192,
}

_db: sqlite3.Connection | None = None


def _get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = sqlite3.connect(settings.runtime_db_path)
        _db.row_factory = sqlite3.Row
        _db.execute("""
            CREATE TABLE IF NOT EXISTS ingredient_override (
                ingredient_name TEXT PRIMARY KEY,
                fdc_id INTEGER NOT NULL,
                usda_description TEXT,
                created_at TEXT NOT NULL
            )
        """)
        _db.commit()
    return _db


def seed_defaults():
    """Seed default overrides without overwriting user-added entries."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.executemany(
        """
        INSERT OR IGNORE INTO ingredient_override
            (ingredient_name, fdc_id, created_at)
        VALUES (?, ?, ?)
        """,
        [(name, fdc_id, now) for name, fdc_id in DEFAULT_OVERRIDES.items()],
    )
    db.commit()


def get_override(ingredient_name: str) -> int | None:
    """Look up an override fdc_id for an ingredient name. Returns None if not found."""
    db = _get_db()
    cur = db.execute(
        "SELECT fdc_id FROM ingredient_override WHERE ingredient_name = ?",
        (ingredient_name.lower().strip(),),
    )
    row = cur.fetchone()
    return row["fdc_id"] if row else None


def list_overrides() -> list[dict]:
    """List all ingredient overrides."""
    db = _get_db()
    cur = db.execute(
        "SELECT ingredient_name, fdc_id, usda_description, created_at "
        "FROM ingredient_override ORDER BY ingredient_name"
    )
    return [dict(row) for row in cur.fetchall()]


def set_override(ingredient_name: str, fdc_id: int, usda_description: str | None = None):
    """Add or update an ingredient override."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """
        INSERT INTO ingredient_override (ingredient_name, fdc_id, usda_description, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ingredient_name) DO UPDATE SET
            fdc_id = excluded.fdc_id,
            usda_description = excluded.usda_description,
            created_at = excluded.created_at
        """,
        (ingredient_name.lower().strip(), fdc_id, usda_description, now),
    )
    db.commit()


def delete_override(ingredient_name: str) -> bool:
    """Delete an override. Returns True if it existed."""
    db = _get_db()
    cur = db.execute(
        "DELETE FROM ingredient_override WHERE ingredient_name = ?",
        (ingredient_name.lower().strip(),),
    )
    db.commit()
    return cur.rowcount > 0
