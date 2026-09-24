#!/usr/bin/env python3
"""MVP "Mapeamento de Base": ranking de minutagem dos egressos validados de
7 clubes formadores, a partir de dados/mapeamento_base_mvp.xlsx.

Tudo ja vem calculado na planilha (minutos, badge, ranking, trajetoria
curta) -- aqui so se le e renderiza, nunca se recalcula. Chave e
ID_Base, nunca o nome (ha homonimos: tres "Wesley", dois "Estevao").

Duas telas, troca de estado local (sem rota nova), mesmo padrao visual
do Celeiro de Ases -- o CSS base foi copiado de la, nao importado, pra
que mexer num nao mude o outro:
  1. Ranking -- cabecalho fixo com duas fileiras de chips (clube
     formador; pais do clube atual, com contagem que acompanha o
     formador). Ordem sempre por minutos; numero do ranking e o geral.
  2. Ficha   -- bio + minutos (3 anos, por temporada, temporada atual).

Uso:
    python3 scripts/gerar_html.py
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

BADGE_TOM = {"🟢": "good", "🟡": "warn", "🔴": "bad"}
BADGE_PALAVRA = {"good": "Alta", "warn": "Média", "bad": "Baixa"}
STATUS_TOM = {"No clube formador": "marca", "Sem clube": "warn", "Egresso": "neutro", "Aposentado": "neutro"}
TEMPORADAS = [("2023", "Min_2023"), ("2024", "Min_2024"), ("2025", "Min_2025")]
MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

ICONE_VOLTAR = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>')

CSS = """
:root{
  --paper:#F4F4F2; --card:#FFFFFF;
  --ink:#1A1A18; --ink-2:#5C5F5B; --ink-3:#8A8D88;
  --line:#E3E3DF; --line-2:#CFCFC9;
  --marca:#E5050F; --marca-forte:#B90109; --marca-suave:#FDECEC;
  --good:#1F6B44; --good-bg:#E6F2EB;
  --warn:#8A6A12; --warn-bg:#FBF1DC;
  --bad:#9E2B2B; --bad-bg:#FBE9E9;
  --neutro:#5C5F5B; --neutro-bg:#EFEFEC;
  --vazio:#B4B7B2;
  --radar-fill:rgba(229,5,15,0.12); --radar-stroke:#E5050F;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#131312; --card:#1C1C1A;
    --ink:#F2F1EE; --ink-2:#B4B4AE; --ink-3:#83837E;
    --line:#2C2C29; --line-2:#3C3C38;
    --marca:#FF4B52; --marca-forte:#FF7A80; --marca-suave:rgba(255,75,82,0.14);
    --good:#71C79B; --good-bg:rgba(113,199,155,0.14);
    --warn:#DCBE72; --warn-bg:rgba(220,190,114,0.14);
    --bad:#E88C8C; --bad-bg:rgba(232,140,140,0.14);
    --neutro:#B4B4AE; --neutro-bg:rgba(180,180,174,0.13);
    --vazio:#5A5A56;
    --radar-fill:rgba(255,75,82,0.16); --radar-stroke:#FF4B52;
  }
}
:root[data-theme="dark"]{
  --paper:#131312; --card:#1C1C1A;
  --ink:#F2F1EE; --ink-2:#B4B4AE; --ink-3:#83837E;
  --line:#2C2C29; --line-2:#3C3C38;
  --marca:#FF4B52; --marca-forte:#FF7A80; --marca-suave:rgba(255,75,82,0.14);
  --good:#71C79B; --good-bg:rgba(113,199,155,0.14);
  --warn:#DCBE72; --warn-bg:rgba(220,190,114,0.14);
  --bad:#E88C8C; --bad-bg:rgba(232,140,140,0.14);
  --neutro:#B4B4AE; --neutro-bg:rgba(180,180,174,0.13);
  --vazio:#5A5A56;
  --radar-fill:rgba(255,75,82,0.16); --radar-stroke:#FF4B52;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Source Sans 3", ui-sans-serif, system-ui, -apple-system, sans-serif;
  font-size:16px; line-height:1.5; font-weight:400;
  padding-block: 0 64px;
}
.conteudo{
  max-width:760px; margin-inline:auto;
  padding-inline: max(16px, env(safe-area-inset-left, 0px)) max(16px, env(safe-area-inset-right, 0px));
}
/* Cabecalho fixo: titulo + chips ficam visiveis enquanto a lista rola por
   baixo. O padding-top soma o safe-area do iOS pra nao ficar atras da
   barra de status/notch; o fundo cobre essa faixa. */
.topo{
  position:sticky; top:0; z-index:10; background:var(--paper);
  padding-top:calc(env(safe-area-inset-top, 0px) + 16px); padding-bottom:12px;
  border-bottom:1px solid var(--line);
}
.lista-card{ margin-top:14px }
.ficha-conteudo{ padding-top:calc(env(safe-area-inset-top, 0px) + 20px) }
h1,h2,h3,h4{margin:0; font-weight:600; letter-spacing:-0.01em; text-wrap:balance}
.num{font-family:"IBM Plex Mono", ui-monospace, monospace; font-variant-numeric:tabular-nums}
button{font-family:inherit; font-size:inherit; color:inherit}
:focus-visible{outline:2px solid var(--marca); outline-offset:2px; border-radius:6px}
svg{width:1em; height:1em; display:block}

/* ---------- estruturas base ---------- */
.card{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; }
.card + .card{ margin-top:14px; }
.card-titulo{ font-size:12.5px; font-weight:600; color:var(--ink-3); letter-spacing:.04em; text-transform:uppercase; margin-bottom:14px; }
.pilula{
  display:inline-flex; align-items:center; gap:6px; padding:4px 11px; border-radius:999px;
  font-size:12.5px; font-weight:600; letter-spacing:.01em; white-space:nowrap; line-height:1.6;
}
.p-good{ background:var(--good-bg); color:var(--good) }
.p-warn{ background:var(--warn-bg); color:var(--warn) }
.p-bad{ background:var(--bad-bg); color:var(--bad) }
.p-neutro{ background:var(--neutro-bg); color:var(--neutro) }
.p-marca{ background:var(--marca-suave); color:var(--marca-forte) }
.ponto{ width:6px; height:6px; border-radius:50%; background:currentColor; flex:none }
.vazio{ color:var(--vazio) }

/* par label-em-cima / valor-embaixo */
.par{ display:flex; flex-direction:column; gap:2px; }
.par .lbl{ font-size:12.5px; color:var(--ink-3); font-weight:400; letter-spacing:.02em }
.par .val{ font-size:19px; color:var(--ink); font-weight:600 }
.par .val.num{ font-family:"IBM Plex Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums }

/* ---------- tela: lista ---------- */
.masthead{ margin-bottom:12px }
.masthead .kicker{ display:block; font-size:11.5px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--marca-forte); margin-bottom:4px }
.masthead h1{ font-size:clamp(23px,4.4vw,30px); line-height:1.15 }

.chips-wrap{ margin:0 -16px; padding:0 16px; overflow-x:auto; scrollbar-width:none; -ms-overflow-style:none }
.chips-wrap::-webkit-scrollbar{ display:none }
.chips{ display:flex; gap:8px; width:max-content; padding-bottom:2px }
.chip{
  flex:none; display:inline-flex; align-items:center; gap:7px; cursor:pointer;
  background:var(--card); border:1px solid var(--line); border-radius:999px;
  padding:9px 16px; font-size:14.5px; color:var(--ink-2); white-space:nowrap;
}
.chip:hover{ border-color:var(--line-2) }
.chip .n{ font-family:"IBM Plex Mono",monospace; font-size:13px; color:var(--ink-3); font-variant-numeric:tabular-nums }
.chip.ativo{ background:var(--marca); border-color:var(--marca); color:#FFFFFF }
.chip.ativo .n{ color:#FFFFFF; opacity:.75 }

.lista{ list-style:none; margin:0; padding:0 }
.lista li + li{ border-top:1px solid var(--line) }
.lista li[hidden]{ display:none }
.linha{
  width:100%; display:flex; align-items:center; gap:13px; padding:13px 4px; min-height:64px;
  background:none; border:none; cursor:pointer; text-align:left; border-radius:8px;
}
.linha:hover{ background:var(--paper) }
.avatar{
  flex:none; width:44px; height:44px; border-radius:50%; background:var(--neutro-bg); color:var(--ink-2);
  display:flex; align-items:center; justify-content:center; font-size:14.5px; font-weight:600; letter-spacing:.02em;
}
.linha-info{ flex:1; min-width:0 }
.linha-nome{ display:block; font-size:16.5px; font-weight:600; color:var(--ink); overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.linha-sub{ display:block; font-size:13.5px; color:var(--ink-3); overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.linha .seta{ flex:none; color:var(--ink-3); font-size:18px }
.lista-vazia{ padding:16px 4px; color:var(--ink-3); font-size:14px }

/* ---------- tela: ficha ---------- */
.ficha[hidden], #tela-lista[hidden], #tela-ficha[hidden]{ display:none }
.btn-voltar{
  display:inline-flex; align-items:center; gap:7px; background:none; border:1px solid var(--line);
  border-radius:999px; padding:10px 18px 10px 14px; font-size:14.5px; min-height:44px; color:var(--ink-2); cursor:pointer;
  margin-bottom:18px;
}
.btn-voltar:hover{ border-color:var(--line-2); color:var(--ink) }
.btn-voltar svg{ font-size:15px }

.ficha-head{ display:flex; align-items:center; gap:14px; margin-bottom:18px; flex-wrap:wrap }
.avatar-lg{ width:60px; height:60px; font-size:19px }
.ficha-id{ flex:1; min-width:0 }
.ficha-id h2{ font-size:25px; line-height:1.2 }
.ficha-id .sub{ margin:3px 0 0; font-size:14.5px; color:var(--ink-3) }

.grade-bio{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px 14px }
.grade-kpi{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px }
.grade-kpi .val{ font-size:27px }
.grade-metricas{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px 14px }
@media (max-width:640px){
  body{ padding-block:0 56px }
  .grade-bio{ grid-template-columns:repeat(2,1fr); gap:16px }
  .grade-kpi{ grid-template-columns:repeat(2,1fr); gap:18px }
  .grade-metricas{ grid-template-columns:repeat(2,1fr); gap:18px 14px }
  .grade-kpi .val{ font-size:26px }
  .card{ padding:16px }
  .topo .masthead h1{ font-size:21px; letter-spacing:-0.015em }
}
.kpi-extra{ margin-top:5px }
.nota-limite{ font-size:13.5px; color:var(--ink-2); line-height:1.55; margin:0 }


footer.rodape{ margin-top:28px; font-size:12px; color:var(--ink-3); line-height:1.6 }
footer.rodape b{ font-weight:600; color:var(--ink-2) }

/* ---------- especifico do Mapeamento de Base ---------- */
.chips-wrap + .chips-wrap{ margin-top:8px }
.chip-rotulo{
  flex:none; align-self:center; font-size:11px; font-weight:600; letter-spacing:.08em;
  text-transform:uppercase; color:var(--ink-3); padding-right:2px;
}
.chip[hidden]{ display:none }
.rank{
  flex:none; width:28px; text-align:right; font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums; font-size:13px; color:var(--ink-3);
}
.linha-sub{ display:flex !important; align-items:center; gap:7px; min-width:0 }
.linha-sub .txt{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0 }
.pilula.mini{ padding:1px 8px; font-size:11px; font-weight:600; flex:none }
.min-pill{ flex:none; font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums }

.destaque{ display:flex; align-items:flex-end; flex-wrap:wrap; gap:10px 12px }
.destaque .val{ font-size:34px; line-height:1.05 }
.destaque .unid{ font-size:15px; color:var(--ink-3); font-weight:400; margin-left:4px; font-family:"Source Sans 3",sans-serif }
.destaque-pills{ display:flex; gap:8px; flex-wrap:wrap; padding-bottom:5px }
.sub-par{ margin-top:16px }
.sep{ border:none; border-top:1px solid var(--line); margin:18px 0 16px }
.barras-titulo{ font-size:12.5px; font-weight:600; color:var(--ink-3); letter-spacing:.04em; text-transform:uppercase; margin-bottom:12px }
.barra{ display:grid; grid-template-columns:42px 1fr 64px; align-items:center; gap:12px }
.barra + .barra{ margin-top:12px }
.barra .ano{ font-size:14px; color:var(--ink-2); font-family:"IBM Plex Mono",monospace }
.barra .trilho{ height:10px; background:var(--neutro-bg); border-radius:4px; overflow:hidden }
.barra .preench{ display:block; height:100%; background:var(--ink-2); border-radius:0 4px 4px 0 }
.barra .qtd{ text-align:right; font-size:15px; font-weight:600; font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums }
.escala{ margin:10px 0 0 54px; font-size:11.5px; color:var(--ink-3) }
.atual .val{ font-size:28px }

.legenda{ margin-top:24px }
.legenda > summary{
  list-style:none; cursor:pointer; display:inline-flex; align-items:center; gap:8px;
  font-size:13.5px; font-weight:600; color:var(--ink-2); padding:8px 0;
}
.legenda > summary::-webkit-details-marker{ display:none }
.legenda > summary svg{ font-size:15px; transition:transform .15s }
.legenda[open] > summary svg{ transform:rotate(90deg) }
.legenda dl{ margin:8px 0 0; display:grid; gap:12px; font-size:13.5px; line-height:1.55 }
.legenda dt{ font-weight:600; color:var(--ink) }
.legenda dd{ margin:2px 0 0; color:var(--ink-2) }
.legenda .pills-regua{ display:flex; flex-wrap:wrap; gap:6px; margin-top:4px }
@media (prefers-reduced-motion: reduce){ .legenda > summary svg{ transition:none } }
@media (max-width:640px){
  .grade-bio{ grid-template-columns:repeat(2,1fr) }
  .rank{ width:24px; font-size:12px }
  .destaque .val{ font-size:31px }
}
"""

FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">')
ICONE_SETA = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>')


def esc(s):
    return "" if s is None else str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def slugify(txt: str) -> str:
    a = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", a.lower()).strip("-")


def iniciais(nome: str) -> str:
    partes = [p for p in nome.split() if p]
    if not partes:
        return "?"
    return partes[0][:2].upper() if len(partes) == 1 else (partes[0][0] + partes[-1][0]).upper()


def milhar(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def vazio(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def data_br(txt):
    """'31 de dez. de 2028' -> '31/12/2028'."""
    if vazio(txt):
        return None
    m = re.search(r"(\d{1,2})\s*de\s*([a-zç]+)\.?\s*de\s*(\d{4})", str(txt), re.I)
    if not m:
        return str(txt)
    d, mes, a = m.groups()
    n = MESES.get(unicodedata.normalize("NFKD", mes).encode("ascii", "ignore").decode()[:3].lower())
    return f"{int(d):02d}/{n:02d}/{a}" if n else str(txt)


def pilula(texto, tom="neutro", ponto=False, extra=""):
    p = '<span class="ponto"></span>' if ponto else ""
    return f'<span class="pilula p-{tom}{(" " + extra) if extra else ""}">{p}{esc(texto)}</span>'


def par(label, valor_html, numerico=True):
    cls = "val num" if numerico else "val"
    return f'<div class="par"><span class="lbl">{esc(label)}</span><span class="{cls}">{valor_html}</span></div>'


TRACO = '<span class="vazio">–</span>'


# --------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------

def carregar(caminho: Path):
    x = pd.read_excel(caminho, sheet_name=None)
    df = x["Jogadores"]
    jogadores = []
    for _, r in df.iterrows():
        badge = "" if vazio(r["Badge_Minutos"]) else str(r["Badge_Minutos"]).strip()
        nd = badge.upper() == "N/D" or vazio(r["Minutos_ultimos_3_anos"])
        pais = None if vazio(r["Pais_Clube"]) else str(r["Pais_Clube"]).strip()
        jogadores.append({
            "id": slugify(r["ID_Base"]),
            "ranking": None if vazio(r["Ranking"]) else int(r["Ranking"]),
            "nome": str(r["Nome"]).strip(),
            "formador": str(r["Clube_Formador"]).strip(),
            "clube": None if vazio(r["Clube_Atual"]) else str(r["Clube_Atual"]).strip(),
            "pais": pais,
            "status": None if vazio(r["Status_Atual"]) else str(r["Status_Atual"]).strip(),
            "posicao": None if vazio(r["Posicao"]) else str(r["Posicao"]).strip(),
            "idade": None if vazio(r["Idade"]) else int(r["Idade"]),
            "contrato": data_br(r["Contrato_Ate"]),
            "nd": nd,
            "min3": None if nd else int(r["Minutos_ultimos_3_anos"]),
            "jogos3": None if vazio(r["Jogos_ultimos_3_anos"]) else int(r["Jogos_ultimos_3_anos"]),
            "tom": "neutro" if nd else BADGE_TOM.get(badge, "neutro"),
            "curta": bool(r["Trajetoria_Curta"]) if not vazio(r["Trajetoria_Curta"]) else False,
            "temporadas": [(ano, None if vazio(r[c]) else int(r[c])) for ano, c in TEMPORADAS],
            "atual": None if vazio(r["Min_Temporada_Atual_2026"]) else int(r["Min_Temporada_Atual_2026"]),
        })
    # A planilha ja vem ordenada; so garantimos a regra (N/D no fim) sem
    # recalcular nada -- a posicao exibida continua sendo a coluna Ranking.
    jogadores.sort(key=lambda j: (j["nd"], -(j["min3"] or 0), j["ranking"] or 10**6))
    legenda = [(str(a).strip(), str(b).strip()) for a, b in x["Legenda"].itertuples(index=False) if not vazio(a)]
    return jogadores, legenda


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def sub_clube(j):
    clube = j["clube"] or "Sem clube"
    return f"{clube} · {j['pais']}" if j["pais"] else clube


def pilula_minutos(j):
    if j["nd"]:
        return pilula("em coleta", "neutro", extra="min-pill")
    return pilula(milhar(j["min3"]), j["tom"], ponto=True, extra="min-pill")


def linha(j):
    rank = str(j["ranking"]) if j["ranking"] else "–"
    pais = slugify(j["pais"]) if j["pais"] else "sem-clube"
    return (f'<li data-f="{slugify(j["formador"])}" data-p="{pais}">'
            f'<button type="button" class="linha" data-id="{j["id"]}">'
            f'<span class="rank">{rank}</span>'
            f'<span class="avatar">{esc(iniciais(j["nome"]))}</span>'
            f'<span class="linha-info"><span class="linha-nome">{esc(j["nome"])}</span>'
            f'<span class="linha-sub">{pilula(j["formador"], "neutro", extra="mini")}'
            f'<span class="txt">{esc(sub_clube(j))}</span></span></span>'
            f'{pilula_minutos(j)}</button></li>')


def card_minutos(j, escala_max):
    if j["nd"]:
        return ('<div class="card"><div class="card-titulo">Minutos</div>'
                f'<div class="destaque">{pilula("em coleta", "neutro")}</div>'
                '<p class="nota-limite" style="margin-top:12px">Minutos ainda não coletados para este '
                'jogador — por isso ele aparece no fim do ranking.</p></div>')

    pills = [pilula(BADGE_PALAVRA.get(j["tom"], ""), j["tom"], ponto=True)]
    if j["curta"]:
        pills.append(pilula("trajetória curta", "neutro"))
    destaque = (f'<div class="par"><span class="lbl">Minutos nos últimos 3 anos</span>'
                f'<div class="destaque"><span class="val num">{milhar(j["min3"])}<span class="unid">min</span></span>'
                f'<span class="destaque-pills">{"".join(pills)}</span></div></div>')
    jogos = par("Jogos nos últimos 3 anos", milhar(j["jogos3"]) if j["jogos3"] is not None else TRACO)

    barras = []
    for ano, v in j["temporadas"]:
        largura = 0 if not v else max(1.5, v / escala_max * 100)
        preench = f'<span class="preench" style="width:{largura:.1f}%"></span>' if v else ""
        valor = milhar(v) if v is not None else TRACO
        barras.append(f'<div class="barra" title="{ano}: {valor if v is not None else "sem dado"} min">'
                      f'<span class="ano">{ano}</span><span class="trilho">{preench}</span>'
                      f'<span class="qtd">{valor}</span></div>')
    return (f'<div class="card"><div class="card-titulo">Minutos</div>{destaque}'
            f'<div class="sub-par">{jogos}</div><hr class="sep">'
            f'<div class="barras-titulo">Por temporada</div>{"".join(barras)}'
            f'<p class="escala">Escala comum a todos os jogadores (máx. {milhar(escala_max)} min numa temporada).</p></div>')


def card_atual(j):
    v = j["atual"]
    valor = TRACO if v is None else f'{milhar(v)}<span class="unid" style="font-size:14px;color:var(--ink-3);font-weight:400;margin-left:4px">min</span>'
    return (f'<div class="card atual"><div class="card-titulo">Temporada atual · 2026</div>'
            f'{par("Minutos", valor)}</div>')


def ficha(j, escala_max):
    status = j["status"] or "Egresso"
    bio = [
        par("Idade", str(j["idade"]) if j["idade"] is not None else TRACO),
        par("Posição", esc(j["posicao"]) if j["posicao"] else TRACO, numerico=False),
        par("Clube formador", esc(j["formador"]), numerico=False),
        par("Contrato até", j["contrato"] if j["contrato"] else pilula("N/D", "neutro")),
    ]
    return f'''<article class="ficha" id="f-{j["id"]}" hidden>
  <button type="button" class="btn-voltar" data-voltar>{ICONE_VOLTAR}Voltar</button>
  <div class="ficha-head">
    <span class="avatar avatar-lg">{esc(iniciais(j["nome"]))}</span>
    <div class="ficha-id"><h2>{esc(j["nome"])}</h2><p class="sub">{esc(sub_clube(j))}</p></div>
    {pilula(status, STATUS_TOM.get(status, "neutro"))}
  </div>
  <div class="card"><div class="card-titulo">Bio</div><div class="grade-bio">{"".join(bio)}</div></div>
  {card_minutos(j, escala_max)}
  {card_atual(j)}
</article>'''


def bloco_legenda(legenda):
    itens = []
    for item, regra in legenda:
        if item.lower().startswith("marcador"):
            regua = (pilula("≥ 4.500", "good", ponto=True) + pilula("1.500–4.499", "warn", ponto=True)
                     + pilula("< 1.500", "bad", ponto=True) + pilula("em coleta", "neutro"))
            itens.append(f'<div><dt>{esc(item)}</dt><dd>Minutos nos últimos 3 anos.'
                         f'<div class="pills-regua">{regua}</div></dd></div>')
        else:
            itens.append(f'<div><dt>{esc(item)}</dt><dd>{esc(regra)}</dd></div>')
    return (f'<details class="legenda"><summary>{ICONE_SETA}Como ler os números</summary>'
            f'<dl>{"".join(itens)}</dl></details>')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent.parent
    ap.add_argument("--planilha", type=Path, default=base / "dados" / "mapeamento_base_mvp.xlsx")
    ap.add_argument("--out", type=Path, default=base / "saida" / "index.html")
    args = ap.parse_args()

    jogadores, legenda = carregar(args.planilha)
    escala_max = max(v for j in jogadores for _, v in j["temporadas"] if v)

    formadores: dict[str, int] = {}
    paises: dict[str, int] = {}
    for j in jogadores:
        formadores[j["formador"]] = formadores.get(j["formador"], 0) + 1
        chave = j["pais"] or "Sem clube"
        paises[chave] = paises.get(chave, 0) + 1

    chips_f = [f'<span class="chip-rotulo">Formador</span>',
               f'<button type="button" class="chip ativo" data-f="todos">Todos <span class="n">{len(jogadores)}</span></button>']
    for nome, n in sorted(formadores.items(), key=lambda x: (-x[1], x[0])):
        chips_f.append(f'<button type="button" class="chip" data-f="{slugify(nome)}">{esc(nome)} <span class="n">{n}</span></button>')

    ordem_paises = sorted(paises.items(), key=lambda x: (x[0] == "Sem clube", -x[1], x[0]))
    chips_p = [f'<span class="chip-rotulo">País</span>',
               f'<button type="button" class="chip ativo" data-p="todos">Todos <span class="n">{len(jogadores)}</span></button>']
    for nome, n in ordem_paises:
        chips_p.append(f'<button type="button" class="chip" data-p="{slugify(nome)}">{esc(nome)} <span class="n">{n}</span></button>')

    html = f"""<title>Mapeamento de Base</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
<meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{FONT_LINK}
<style>{CSS}</style>

<section id="tela-lista">
  <header class="topo">
    <div class="conteudo">
      <div class="masthead">
        <span class="kicker">Projeto Futebol • Mapeamento de Base</span>
        <h1>Para onde vão as crias da base</h1>
      </div>
      <div class="chips-wrap"><nav class="chips" aria-label="Filtrar por clube formador">{"".join(chips_f)}</nav></div>
      <div class="chips-wrap"><nav class="chips" aria-label="Filtrar por país do clube atual">{"".join(chips_p)}</nav></div>
    </div>
  </header>
  <div class="conteudo">
    <div class="card lista-card" style="padding:6px 16px">
      <ul class="lista" id="lista">{"".join(linha(j) for j in jogadores)}</ul>
      <p class="lista-vazia" id="lista-vazia" hidden>Nenhum jogador nesse cruzamento de filtros.</p>
    </div>
    {bloco_legenda(legenda)}
  </div>
</section>

<section id="tela-ficha" hidden><div class="conteudo ficha-conteudo">{"".join(ficha(j, escala_max) for j in jogadores)}</div></section>

<script>
(function(){{
  var telaLista = document.getElementById('tela-lista');
  var telaFicha = document.getElementById('tela-ficha');
  var lista = document.getElementById('lista');
  var vazia = document.getElementById('lista-vazia');
  var itens = Array.prototype.slice.call(lista.querySelectorAll('li'));
  var chipsF = document.querySelectorAll('.chip[data-f]');
  var chipsP = document.querySelectorAll('.chip[data-p]');
  var fichas = telaFicha.querySelectorAll('.ficha');
  var filtroF = 'todos', filtroP = 'todos', rolagem = 0;

  // Contagem por pais acompanha o formador escolhido; pais zerado some.
  function recontaPaises(){{
    var cont = {{}}, total = 0;
    itens.forEach(function(li){{
      if (filtroF !== 'todos' && li.dataset.f !== filtroF) return;
      cont[li.dataset.p] = (cont[li.dataset.p] || 0) + 1; total++;
    }});
    chipsP.forEach(function(c){{
      var n = c.dataset.p === 'todos' ? total : (cont[c.dataset.p] || 0);
      c.querySelector('.n').textContent = n;
      c.hidden = c.dataset.p !== 'todos' && n === 0;
    }});
    if (filtroP !== 'todos' && !cont[filtroP]) filtroP = 'todos';
  }}

  function aplica(){{
    var n = 0;
    itens.forEach(function(li){{
      var ok = (filtroF === 'todos' || li.dataset.f === filtroF) && (filtroP === 'todos' || li.dataset.p === filtroP);
      li.hidden = !ok; if (ok) n++;
    }});
    chipsF.forEach(function(c){{ c.classList.toggle('ativo', c.dataset.f === filtroF); }});
    chipsP.forEach(function(c){{ c.classList.toggle('ativo', c.dataset.p === filtroP); }});
    vazia.hidden = n > 0;
    window.scrollTo(0, 0);
  }}

  chipsF.forEach(function(c){{ c.addEventListener('click', function(){{ filtroF = c.dataset.f; recontaPaises(); aplica(); }}); }});
  chipsP.forEach(function(c){{ c.addEventListener('click', function(){{ filtroP = c.dataset.p; aplica(); }}); }});

  function abrir(id){{
    rolagem = window.scrollY;
    fichas.forEach(function(f){{ f.hidden = f.id !== ('f-' + id); }});
    telaLista.hidden = true; telaFicha.hidden = false;
    window.scrollTo(0, 0);
  }}
  function voltar(){{
    telaFicha.hidden = true; telaLista.hidden = false;
    window.scrollTo(0, rolagem);
  }}
  lista.addEventListener('click', function(e){{
    var b = e.target.closest('.linha'); if (b) abrir(b.dataset.id);
  }});
  telaFicha.addEventListener('click', function(e){{ if (e.target.closest('[data-voltar]')) voltar(); }});
  document.addEventListener('keydown', function(e){{ if (e.key === 'Escape' && !telaFicha.hidden) voltar(); }});
}})();
</script>
"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(html)} bytes, {len(jogadores)} jogadores, escala {escala_max} min)")


if __name__ == "__main__":
    main()
