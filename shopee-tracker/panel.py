"""
Painel local para gerenciar a watchlist sem tocar em código/JSON na mão.

Rodar com:  python panel.py
Depois abrir: http://localhost:5000
"""
import hmac
import os
from flask import Flask, render_template, request, redirect, url_for
import watchlist_store as store
import db

app = Flask(__name__)

# Autenticação simples por senha, via query param na primeira visita
# (depois fica guardada num cookie). Evita deixar o painel público sem
# nenhuma trava, já que ele vai rodar numa URL fixa e acessível de
# qualquer lugar.
PAINEL_SENHA = os.environ.get("PAINEL_SENHA")


def _senha_confere(valor: str | None) -> bool:
    return bool(valor) and hmac.compare_digest(valor, PAINEL_SENHA)


@app.before_request
def checar_senha():
    if not PAINEL_SENHA:
        return  # sem senha configurada, roda aberto (uso local/dev)
    if not _senha_confere(request.args.get("senha")) and \
       not _senha_confere(request.cookies.get("painel_senha")):
        return "Acesso negado. Acesse com ?senha=SUA_SENHA", 401


@app.route("/")
def index():
    items = store.load_watchlist()
    # Junta o último preço conhecido de cada item, se houver histórico
    for it in items:
        history = db.latest_prices_by_watchlist_id(it["id"], n=1)
        it["ultimo_preco"] = history[0]["preco"] if history else None
        it["ultima_coleta"] = history[0]["coletado_em"] if history else None

    resp = app.make_response(render_template("index.html", items=items))
    # Se veio com ?senha=... correta, fixa um cookie pra não precisar
    # repetir na URL a cada clique.
    if PAINEL_SENHA and _senha_confere(request.args.get("senha")):
        eh_https = request.is_secure or request.headers.get("X-Forwarded-Proto") == "https"
        resp.set_cookie("painel_senha", PAINEL_SENHA, max_age=60 * 60 * 24 * 30,
                         httponly=True, samesite="Lax", secure=eh_https)
    return resp


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
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
