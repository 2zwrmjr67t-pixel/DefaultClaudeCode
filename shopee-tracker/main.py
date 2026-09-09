"""
Job diário de coleta.

Rodar manualmente:  python main.py
Ou agendado via GitHub Actions (ver .github/workflows/daily.yml)
"""
from dotenv import load_dotenv
load_dotenv()

import watchlist_store as store
import db
from shopee_client import ShopeeAffiliateClient
from telegram_alert import send_alert


def processar_item(client: ShopeeAffiliateClient, it: dict) -> None:
    produto = client.get_product_by_item_id(it["item_id"], it.get("shop_id"))
    if not produto:
        print(f"[{it['nome_amigavel']}] produto não encontrado.")
        return

    preco = float(produto["price"])
    db.log_price(it["id"], produto["itemId"], produto["productName"],
                 preco, it["preco_alvo"], produto.get("offerLink"))

    print(f"[{it['nome_amigavel']}] preço atual: R$ {preco:.2f} (alvo: R$ {it['preco_alvo']:.2f})")

    if preco <= it["preco_alvo"]:
        send_alert(
            f"🎯 <b>{it['nome_amigavel']}</b>\n"
            f"Preço atual: R$ {preco:.2f} (alvo: R$ {it['preco_alvo']:.2f})\n"
            f"{produto.get('offerLink', '')}"
        )


def processar_keyword(client: ShopeeAffiliateClient, it: dict) -> None:
    produtos = client.get_products_by_keyword(
        it["termo_busca"], limit=it.get("max_resultados", 20)
    )
    if not produtos:
        print(f"[{it['nome_amigavel']}] nenhum resultado para a busca.")
        return

    for produto in produtos:
        preco = float(produto["price"])
        db.log_price(it["id"], produto["itemId"], produto["productName"],
                     preco, it["preco_alvo"], produto.get("offerLink"))

        if preco <= it["preco_alvo"]:
            send_alert(
                f"🎯 <b>{it['nome_amigavel']}</b> (busca: {it['termo_busca']})\n"
                f"{produto['productName']}\n"
                f"Preço: R$ {preco:.2f} (alvo: R$ {it['preco_alvo']:.2f})\n"
                f"{produto.get('offerLink', '')}"
            )

    menor = min(float(p["price"]) for p in produtos)
    print(f"[{it['nome_amigavel']}] {len(produtos)} resultados, menor preço: R$ {menor:.2f}")


def run():
    client = ShopeeAffiliateClient()
    items = [it for it in store.load_watchlist() if it.get("ativo", True)]

    if not items:
        print("Watchlist vazia ou sem itens ativos.")
        return

    for it in items:
        try:
            if it["tipo"] == "keyword":
                processar_keyword(client, it)
            else:
                processar_item(client, it)
        except Exception as e:
            print(f"[erro] {it['nome_amigavel']}: {e}")


if __name__ == "__main__":
    run()
