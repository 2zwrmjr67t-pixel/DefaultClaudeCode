"""
Painel local para gerenciar a watchlist sem tocar em código/JSON na mão.

Rodar com:  python panel.py
Depois abrir: http://localhost:5000
"""
from flask import Flask, render_template, request, redirect, url_for
import watchlist_store as store
import db

app = Flask(__name__)


@app.route("/")
def index():
    items = store.load_watchlist()
    # Junta o último preço conhecido de cada item, se houver histórico
    for it in items:
        history = db.latest_prices_by_watchlist_id(it["id"], n=1)
        it["ultimo_preco"] = history[0]["preco"] if history else None
        it["ultima_coleta"] = history[0]["coletado_em"] if history else None
    return render_template("index.html", items=items)


@app.route("/add", methods=["POST"])
def add():
    tipo = request.form["tipo"]
    nome_amigavel = request.form["nome_amigavel"]
    preco_alvo = float(request.form["preco_alvo"])

    if tipo == "keyword":
        novo_item = {
            "tipo": "keyword",
            "nome_amigavel": nome_amigavel,
            "termo_busca": request.form["termo_busca"],
            "preco_alvo": preco_alvo,
            "max_resultados": int(request.form.get("max_resultados") or 20),
            "ordenar_por": "relevancia",
        }
    else:
        novo_item = {
            "tipo": "item",
            "nome_amigavel": nome_amigavel,
            "item_id": request.form["item_id"],
            "shop_id": request.form.get("shop_id", ""),
            "preco_alvo": preco_alvo,
        }

    store.add_item(novo_item)
    return redirect(url_for("index"))


@app.route("/edit/<item_id>", methods=["POST"])
def edit(item_id):
    changes = {}
    if request.form.get("nome_amigavel"):
        changes["nome_amigavel"] = request.form["nome_amigavel"]
    if request.form.get("preco_alvo"):
        changes["preco_alvo"] = float(request.form["preco_alvo"])
    if request.form.get("termo_busca"):
        changes["termo_busca"] = request.form["termo_busca"]
    if request.form.get("item_id"):
        changes["item_id"] = request.form["item_id"]

    store.update_item(item_id, changes)
    return redirect(url_for("index"))


@app.route("/toggle/<item_id>", methods=["POST"])
def toggle(item_id):
    store.toggle_active(item_id)
    return redirect(url_for("index"))


@app.route("/delete/<item_id>", methods=["POST"])
def delete(item_id):
    store.delete_item(item_id)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
