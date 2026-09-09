"""
Leitura/escrita simples do watchlist.json.
Mantido separado para que tanto o painel (panel.py) quanto o job
diário (main.py) usem sempre a mesma lógica de acesso ao arquivo.
"""
import json
import uuid
from pathlib import Path

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"


def load_watchlist() -> list[dict]:
    if not WATCHLIST_PATH.exists():
        return []
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_watchlist(items: list[dict]) -> None:
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_item(item: dict) -> dict:
    items = load_watchlist()
    item["id"] = item.get("id") or f"{item['tipo']}-{uuid.uuid4().hex[:8]}"
    item.setdefault("ativo", True)
    items.append(item)
    save_watchlist(items)
    return item


def update_item(item_id: str, changes: dict) -> dict | None:
    items = load_watchlist()
    for it in items:
        if it["id"] == item_id:
            it.update(changes)
            save_watchlist(items)
            return it
    return None


def delete_item(item_id: str) -> bool:
    items = load_watchlist()
    new_items = [it for it in items if it["id"] != item_id]
    if len(new_items) == len(items):
        return False
    save_watchlist(new_items)
    return True


def toggle_active(item_id: str) -> dict | None:
    items = load_watchlist()
    for it in items:
        if it["id"] == item_id:
            it["ativo"] = not it.get("ativo", True)
            save_watchlist(items)
            return it
    return None
