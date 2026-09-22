"""
Histórico de preços em SQLite. Um arquivo local (price_history.db),
sem servidor de banco separado.
"""
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "price_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id TEXT NOT NULL,
    item_id TEXT,
    nome_produto TEXT,
    preco REAL NOT NULL,
    preco_alvo REAL,
    link TEXT,
    coletado_em TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def log_price(watchlist_id: str, item_id: str | None, nome_produto: str,
              preco: float, preco_alvo: float | None, link: str | None) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT INTO price_history
               (watchlist_id, item_id, nome_produto, preco, preco_alvo, link, coletado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (watchlist_id, item_id, nome_produto, preco, preco_alvo, link,
             datetime.now(timezone.utc).isoformat()),
        )
    conn.close()


def latest_prices_by_watchlist_id(watchlist_id: str, n: int = 10) -> list[sqlite3.Row]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM price_history WHERE watchlist_id = ?
           ORDER BY coletado_em DESC LIMIT ?""",
        (watchlist_id, n),
    ).fetchall()
    conn.close()
    return rows
