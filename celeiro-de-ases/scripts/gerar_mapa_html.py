#!/usr/bin/env python3
"""Passo 3 do "Mapeamento do Celeiro de Ases": gera a pagina HTML (lista
de jogadores filtravel por pais + card por jogador, resumo/completo,
mobile-first) a partir de saida/consolidado.json (gerado pelo passo 2).
So le e renderiza -- nao busca nem recalcula validacao.

Sem mapa-mundi (removido a pedido do usuario apos revisao -- ficava so
o cabecalho com nome do pais): a navegacao por pais agora e so a fileira
de chips clicaveis, mesma logica de filtro de antes, sem o SVG.

Uso:
    python3 scripts/gerar_mapa_html.py
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from pathlib import Path

ARQUETIPO_METRICAS = {
    "Atacante": [
        ("Gols/90", "gls90"),
        ("xG (temporada)", "xg_total"),
        ("Conversão", ("Atacando", "Conversão de gols")),
        ("Finalizações/jogo", ("Atacando", "Finalizações")),
        ("Chutes no alvo/jogo", ("Atacando", "Chutes certos por jogo")),
    ],
    "Meio-campista": [
        ("Passes certos", ("Passe", "Passes certos")),
        ("Passes decisivos", ("Passe", "Passes decisivos")),
        ("Grandes chances criadas", ("Passe", "Grandes chances criadas")),
        ("Desarmes/jogo", ("Defendendo", "Desarmes por jogo")),
    ],
    "Zagueiro": [
        ("Desarmes/jogo", ("Defendendo", "Desarmes por jogo")),
        ("Interceptações", ("Defendendo", "Interceptações")),
        ("Duelos aéreos ganhos", ("Outros (por partida)", "Duelos aéreos ganhos")),
        ("Cortes/jogo", ("Defendendo", "Cortes por jogo")),
        ("Passes certos", ("Passe", "Passes certos")),
    ],
    "Lateral": [
        ("Desarmes/jogo", ("Defendendo", "Desarmes por jogo")),
        ("Interceptações", ("Defendendo", "Interceptações")),
        ("Duelos ganhos (chão e aéreo)", "duelos"),
        ("Cruzamentos certos", ("Passe", "Cruzamentos certos")),
        ("Passes certos no terço final", ("Passe", "Passes certos no terço final")),
    ],
}
RADAR_EIXOS = ["ATT", "TEC", "TAC", "DEF", "CRE"]

STATUS_CLASSE = {
    "Ainda no Internacional": "status-inter",
    "Ainda na base (U17)": "status-base",
    "Sem clube": "status-sem-clube",
    "Egresso": "status-egresso",
}

CSS = """
:root{
  --paper:#F3F1E7; --ink:#16241D; --ink-soft:#3E4B41; --ink-faint:#6B7568;
  --line: rgba(22,36,29,0.13); --line-strong: rgba(22,36,29,0.26);
  --accent:#E5050F; --accent-strong:#B90109; --accent-soft: rgba(229,5,15,0.10);
  --card:#FFFFFF;
  --good:#2F7A55; --good-soft: rgba(47,122,85,0.13);
  --bad:#A83B3B; --bad-soft: rgba(168,59,59,0.12);
  --spec:#9A7A1F; --spec-soft: rgba(154,122,31,0.15);
  --radar-fill: rgba(229,5,15,0.16); --radar-stroke:#E5050F;
  --vazio: rgba(22,36,29,0.30);
  --shadow: 0 1px 2px rgba(22,36,29,0.06), 0 1px 0 rgba(22,36,29,0.05);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#161311; --ink:#F3EDEA; --ink-soft:#C7B9B5; --ink-faint:#96857F;
    --line: rgba(243,237,234,0.13); --line-strong: rgba(243,237,234,0.24);
    --accent:#FF4B52; --accent-strong:#FF7A80; --accent-soft: rgba(255,75,82,0.16);
    --card:#211B19;
    --good:#5FBE93; --good-soft: rgba(95,190,147,0.13);
    --bad:#E08585; --bad-soft: rgba(224,133,133,0.13);
    --spec:#D9C273; --spec-soft: rgba(217,194,115,0.14);
    --radar-fill: rgba(255,75,82,0.18); --radar-stroke:#FF4B52;
    --vazio: rgba(243,237,234,0.28);
    --shadow: 0 1px 2px rgba(0,0,0,0.3);
  }
}
:root[data-theme="dark"]{
  --paper:#161311; --ink:#F3EDEA; --ink-soft:#C7B9B5; --ink-faint:#96857F;
  --line: rgba(243,237,234,0.13); --line-strong: rgba(243,237,234,0.24);
  --accent:#FF4B52; --accent-strong:#FF7A80; --accent-soft: rgba(255,75,82,0.16);
  --card:#211B19;
  --good:#5FBE93; --good-soft: rgba(95,190,147,0.13);
  --bad:#E08585; --bad-soft: rgba(224,133,133,0.13);
  --spec:#D9C273; --spec-soft: rgba(217,194,115,0.14);
  --radar-fill: rgba(255,75,82,0.18); --radar-stroke:#FF4B52;
  --vazio: rgba(243,237,234,0.28);
  --shadow: 0 1px 2px rgba(0,0,0,0.3);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Source Sans 3", ui-sans-serif, system-ui, sans-serif;
  font-size:16px;
  padding-inline: max(16px, calc((100% - 1180px)/2));
  padding-block: 28px 56px;
}
h1,h2,h3{font-family:"Fraunces", Georgia, serif; text-wrap:balance; margin:0}
.num{font-variant-numeric: tabular-nums; font-family:"IBM Plex Mono", ui-monospace, monospace}
a{color:var(--accent-strong)}
a:focus-visible, summary:focus-visible, button:focus-visible, input:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.page{max-width:1180px; margin-inline:auto}
.eyebrow{font-family:"IBM Plex Mono",monospace; font-size:11.5px; text-transform:uppercase; letter-spacing:.08em; color:var(--ink-faint)}

.masthead{ border-bottom: 1px solid var(--line-strong); padding-bottom: 24px; margin-bottom: 26px; }
.masthead .kicker{ display:block; font-family:"IBM Plex Mono", monospace; font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent-strong); margin-bottom:10px; }
.masthead h1{font-size: clamp(26px, 4vw, 36px); font-weight:600; line-height:1.1}
.masthead .dek{color:var(--ink-soft); font-size:15px; max-width:72ch; margin-top:10px; line-height:1.55}

/* ---------- cabecalho de paises (sem mapa-mundi) ---------- */
.map-panel{
  background:var(--card); border:1px solid var(--line); border-radius:10px; box-shadow:var(--shadow);
  padding:18px 18px 16px; margin-bottom:22px;
}
.map-panel > .eyebrow{ display:block; margin-bottom:10px; }
.map-legend{ display:flex; flex-wrap:wrap; gap:8px; }
.map-legend button{
  font-family:"Source Sans 3",sans-serif; font-size:13px; color:var(--ink-soft); background:var(--paper);
  border:1px solid var(--line-strong); border-radius:20px; padding:6px 14px; cursor:pointer;
}
.map-legend button:hover{ background:var(--accent-soft); }
.map-legend button.ativo{ background:var(--accent); border-color:var(--accent); color:#fff; }
.map-legend button b{ font-family:"IBM Plex Mono",monospace; }
.btn-limpar{
  font-family:"IBM Plex Mono",monospace; font-size:11px; text-transform:uppercase; letter-spacing:.05em;
  background:none; border:1px solid var(--line-strong); border-radius:20px; padding:4px 12px; cursor:pointer;
  color:var(--accent-strong);
}
.btn-limpar:hover{ background:var(--accent-soft); }

/* ---------- layout partido: lista + detalhe ---------- */
.split{ display:grid; grid-template-columns: 300px 1fr; gap:20px; align-items:start; }
@media (max-width: 860px){ .split{ grid-template-columns:1fr; } }

.list-panel{
  background:var(--card); border:1px solid var(--line); border-radius:10px; box-shadow:var(--shadow);
  padding:16px; position:sticky; top:16px; max-height:calc(100vh - 32px); overflow-y:auto;
  display:flex; flex-direction:column;
}
@media (max-width: 860px){ .list-panel{ position:static; max-height:none; overflow-y:visible; } }
.list-panel-top{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; margin-bottom:10px; position:sticky; top:0; background:var(--card); padding-top:2px; z-index:1; }
.busca{
  width:100%; font-family:"Source Sans 3",sans-serif; font-size:14px; padding:9px 12px; border-radius:7px;
  border:1px solid var(--line-strong); background:var(--paper); color:var(--ink); margin-bottom:10px;
}
.player-list{ list-style:none; margin:0; padding:0; overflow-y:auto; }
.player-list li{ border-top:1px solid var(--line); }
.player-list li:first-child{ border-top:none; }
.player-list button{
  width:100%; text-align:left; background:none; border:none; cursor:pointer; padding:9px 6px;
  display:flex; justify-content:space-between; align-items:center; gap:8px; font-family:"Source Sans 3",sans-serif;
  color:var(--ink); border-radius:6px;
}
.player-list button:hover{ background:var(--accent-soft); }
.player-list li.ativo button{ background:var(--accent-soft); }
.player-list li.ativo button .nome{ color:var(--accent-strong); font-weight:700; }
.player-list .nome{ font-weight:600; font-size:14px; }
.player-list .clube{ display:block; font-size:11.5px; color:var(--ink-faint); margin-top:1px; }
.player-list .badge{ flex:none; font-size:13px; }
.grupo-clube{ margin-top:10px; }
.grupo-clube:first-child{ margin-top:0; }
.grupo-clube h4{
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--ink-faint); margin:0 0 2px; padding:6px 6px 4px;
}
.sem-clube-note{
  margin-top:12px; padding-top:12px; border-top:1px solid var(--line-strong); font-size:12px;
  color:var(--ink-soft); line-height:1.5;
}
.sem-clube-note button{
  display:block; width:100%; text-align:left; background:none; border:none; cursor:pointer; padding:4px 0;
  color:var(--accent-strong); font-family:"Source Sans 3",sans-serif; font-size:13px; font-weight:600;
}
.lista-vazia{ font-size:13px; color:var(--ink-faint); font-style:italic; padding:10px 6px; }

/* ---------- card de detalhe ---------- */
.player[hidden]{ display:none; }
.player{
  background:var(--card); border:1px solid var(--line); border-radius:10px; box-shadow:var(--shadow); overflow:hidden;
}
.player-head{ display:flex; justify-content:space-between; gap:14px; align-items:flex-start; padding:20px 22px 14px; flex-wrap:wrap; }
.player-head h2{ font-size:26px; font-weight:600; }
.player-sub{ margin:6px 0 0; font-size:14.5px; color:var(--ink-soft); }
.player-sub b{ color:var(--ink); font-weight:600; }
.head-badges{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }

.status-badge{
  display:inline-flex; align-items:center; padding:4px 11px; border-radius:20px; font-size:11.5px; font-weight:700;
  font-family:"IBM Plex Mono",monospace; text-transform:uppercase; letter-spacing:.03em; white-space:nowrap;
}
.status-egresso{ background:var(--line); color:var(--ink-soft); }
.status-inter{ background:var(--accent); color:#fff; }
.status-base{ background:var(--spec-soft); color:var(--spec); border:1px solid var(--spec); }
.status-sem-clube{ background:var(--bad-soft); color:var(--bad); border:1px solid var(--bad); }
.badge-atividade{ font-size:17px; }

.resumo{ padding: 6px 22px 22px; }
.ficha{ display:flex; flex-wrap:wrap; gap:6px 18px; font-size:12.5px; color:var(--ink-soft); margin-bottom:16px; padding-bottom:14px; border-bottom:1px solid var(--line); }
.ficha b{ color:var(--ink); font-weight:600; }
.resumo-grid{ display:grid; grid-template-columns: 1.15fr 1fr; gap:20px; align-items:start; }
@media (max-width: 720px){ .resumo-grid{grid-template-columns:1fr} }

.panel{ border:1px solid var(--line); border-radius:8px; padding:16px 16px 14px; }
.panel > .eyebrow{margin-bottom:12px; display:block}
.metric-headline{ display:grid; grid-template-columns: repeat(3,1fr); gap:10px; margin-bottom:14px; }
.metric-tile{ text-align:center; padding:14px 6px; background:var(--paper); border-radius:6px; }
.metric-tile .lbl{ font-size:10.5px; color:var(--ink-faint); text-transform:uppercase; letter-spacing:.03em; }
.metric-tile .val{ font-family:"IBM Plex Mono",monospace; font-size:22px; font-weight:600; margin-top:5px; }
.metric-list{ display:flex; flex-direction:column; gap:0; }
.metric-list .row{ display:flex; justify-content:space-between; gap:10px; padding:10px 2px; border-top:1px solid var(--line); font-size:14.5px; }
.metric-list .row span{color:var(--ink-soft)}
.metric-list .row b{font-weight:600; font-family:"IBM Plex Mono",monospace}
.metric-note{ font-size:11.5px; color:var(--ink-faint); line-height:1.5; margin-top:12px; }

.radar-wrap{ display:flex; flex-direction:column; align-items:center; }
.radar-wrap svg{ max-width:100%; height:auto; }
.radar-note{ font-size:11px; color:var(--ink-faint); text-align:center; margin-top:6px; line-height:1.45; }

/* ---------- completo (details) ---------- */
details.completo{ border-top:1px solid var(--line-strong); }
details.completo summary{
  cursor:pointer; padding:14px 22px; font-family:"IBM Plex Mono",monospace; font-size:11.5px;
  text-transform:uppercase; letter-spacing:.08em; color:var(--accent-strong); list-style:none;
  display:flex; align-items:center; gap:8px; user-select:none;
}
details.completo summary::-webkit-details-marker{display:none}
details.completo summary::before{ content:"+"; font-family:"IBM Plex Mono",monospace; font-size:14px; width:14px; }
details.completo[open] summary::before{ content:"−"; }
details.completo summary:hover{ background:var(--accent-soft); }
.completo-body{ padding: 4px 22px 26px; }
.full-section{ margin-top:20px; }
.full-section h4{
  font-family:"IBM Plex Mono",monospace; font-size:11px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--ink-faint); margin:0 0 8px; padding-bottom:6px; border-bottom:1px solid var(--line);
}
.full-table{ width:100%; border-collapse:collapse; font-size:12.5px; }
.full-table th, .full-table td{ text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); }
.full-table th{ color:var(--ink-faint); font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.03em; }
.full-table td.num{ text-align:right; }
.full-table-wrap{ overflow-x:auto; }
.full-table tr.total-linha td{ font-weight:700; }
.vazio{ color:var(--vazio); }
.season-block{ margin-bottom:14px; }
.season-block .season-title{ font-weight:600; font-size:13px; margin-bottom:4px; }
.limitacoes{ margin:0; padding-left:18px; font-size:12.5px; color:var(--ink-soft); line-height:1.6; }
.limitacoes li{margin-bottom:4px}
.tag-inline{
  font-family:"IBM Plex Mono",monospace; font-size:9.5px; text-transform:uppercase; padding:1px 5px;
  border-radius:3px; margin-left:6px; white-space:nowrap;
}
.tag-verificado{ background:var(--good-soft); color:var(--good) }
.tag-inferencia{ background:var(--spec-soft); color:var(--spec) }
.tag-especulacao{ background:var(--spec-soft); color:var(--spec) }

.colophon{
  margin-top:30px; padding-top:20px; border-top:1px solid var(--line-strong);
  display:grid; grid-template-columns: repeat(3,1fr); gap:20px;
  font-size:12px; color:var(--ink-soft); line-height:1.55;
}
@media (max-width:760px){ .colophon{grid-template-columns:1fr} }
.colophon h4{
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--accent-strong); margin:0 0 7px; font-weight:600;
}
.colophon code{ font-family:"IBM Plex Mono",monospace; background:var(--accent-soft); padding:1px 5px; border-radius:3px; color:var(--ink) }
"""
FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;'
             '9..144,500;9..144,600;9..144,700&family=Source+Sans+3:wght@400;500;600;700&family=IBM+Plex+Mono:'
             'wght@400;500;600&display=swap">')


def esc(s):
    return "" if s is None else str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slugify(nome: str) -> str:
    ascii_nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_nome.lower()).strip("-")


def pais_slug(pais: str | None) -> str:
    if not pais:
        return "sem-pais"
    return slugify(pais)


def nd(v):
    return '<span class="vazio">–</span>' if v is None or v in ("-", "") else esc(v)


def fnum(v):
    if v in (None, "-", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Extracao de metricas (blocos = performance_season.blocos, mesma forma de
# performance_carreira.blocos)
# --------------------------------------------------------------------------

def extrai(blocos, cat_nome, chave):
    for b in blocos:
        if b["categoria"] == cat_nome:
            v = b["metricas"].get(chave)
            return v if v not in (None, "-", "") else None
    return None


def resumo_temporada_atual(blocos_season):
    jogos = fnum(extrai(blocos_season, "Resumo da Temporada", "JOGOS"))
    min_jogo = fnum(extrai(blocos_season, "Resumo da Temporada", "MINUTOS POR JOGO"))
    minutos = jogos * min_jogo if jogos is not None and min_jogo is not None else None
    gols = fnum(extrai(blocos_season, "Resumo da Temporada", "GOLS"))
    xg = fnum(extrai(blocos_season, "Resumo da Temporada", "GOLS ESPERADOS (XG)"))
    if xg is None:
        xg = fnum(extrai(blocos_season, "Atacando", "Gols esperados (xG)"))
    return {"jogos": jogos, "minutos": minutos, "gols": gols, "xg": xg}


def resolve_metrica(spec, blocos, resumo):
    label, source = spec
    if source == "gls90":
        gls, minutos = resumo["gols"], resumo["minutos"]
        val = f"{gls / minutos * 90:.2f}" if gls is not None and minutos else None
    elif source == "xg_total":
        val = f"{resumo['xg']:.2f}" if resumo["xg"] is not None else None
    elif source == "duelos":
        chao = extrai(blocos, "Outros (por partida)", "Duelos ganhos pelo chão")
        aereo = extrai(blocos, "Outros (por partida)", "Duelos aéreos ganhos")
        val = f"chão {chao} · aéreo {aereo}" if chao and aereo else (chao or aereo)
    else:
        cat_nome, chave = source
        val = extrai(blocos, cat_nome, chave)
    return label, val


# --------------------------------------------------------------------------
# Radar SVG (mesmo desenho do Scout Individual)
# --------------------------------------------------------------------------

def radar_svg(valores: dict, largura=300, altura=235):
    cx, cy = largura / 2, altura / 2
    raio = min(largura, altura) * 0.30
    n = len(RADAR_EIXOS)
    pontos_eixo = []
    for i, eixo in enumerate(RADAR_EIXOS):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        pontos_eixo.append((cx + raio * math.cos(ang), cy + raio * math.sin(ang)))

    aneis = []
    for frac in (0.33, 0.66, 1.0):
        pts = " ".join(f"{cx + raio * frac * math.cos(-math.pi/2 + i*2*math.pi/n):.1f},"
                        f"{cy + raio * frac * math.sin(-math.pi/2 + i*2*math.pi/n):.1f}" for i in range(n))
        aneis.append(f'<polygon points="{pts}" fill="none" stroke="var(--line-strong)" stroke-width="1"/>')

    eixos_svg = "".join(
        f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{px:.1f}" y2="{py:.1f}" stroke="var(--line-strong)" stroke-width="1"/>'
        for px, py in pontos_eixo
    )

    poligono_pts = []
    for i, eixo in enumerate(RADAR_EIXOS):
        v = max(0, min(100, fnum(valores.get(eixo)) or 0))
        ang = -math.pi / 2 + i * 2 * math.pi / n
        frac = v / 100
        poligono_pts.append((cx + raio * frac * math.cos(ang), cy + raio * frac * math.sin(ang)))
    poligono = " ".join(f"{x:.1f},{y:.1f}" for x, y in poligono_pts)

    labels_svg = []
    for i, eixo in enumerate(RADAR_EIXOS):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        lx = cx + (raio + 20) * math.cos(ang)
        ly = cy + (raio + 20) * math.sin(ang)
        v = valores.get(eixo, "–")
        anchor = "middle"
        if math.cos(ang) > 0.3:
            anchor = "start"
        elif math.cos(ang) < -0.3:
            anchor = "end"
        labels_svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" dominant-baseline="middle" '
            f'font-family="IBM Plex Mono, monospace" font-size="12" fill="var(--ink-soft)">{esc(eixo)} '
            f'<tspan font-weight="700" fill="var(--ink)">{esc(v)}</tspan></text>'
        )

    return f'''<svg viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}" role="img" aria-label="Radar Sofascore">
      {''.join(aneis)}
      {eixos_svg}
      <polygon points="{poligono}" fill="var(--radar-fill)" stroke="var(--radar-stroke)" stroke-width="2"/>
      {''.join(labels_svg)}
    </svg>'''


# --------------------------------------------------------------------------
# Bloco "resumo"
# --------------------------------------------------------------------------

def bloco_metricas_chave(p):
    arquetipo = p.get("arquetipo")
    specs = ARQUETIPO_METRICAS.get(arquetipo)
    blocos_season = p["performance_season"]["blocos"]
    if not specs:
        motivo = ("Limitação conhecida: as categorias capturadas (Atacando/Passe/Defendendo) são voltadas a "
                   "jogador de linha — não há dado de defesas, gols sofridos ou clean sheets pro goleiro. "
                   "Card estruturalmente mais magro, não por falha de captura."
                   if arquetipo == "Goleiro" else
                   "Sem arquétipo com perfil de métricas-chave definido nesta rodada.")
        return f'<div class="panel"><span class="eyebrow">Métricas-chave</span><p class="metric-note">{esc(motivo)}</p></div>'

    resumo = resumo_temporada_atual(blocos_season)
    resolved = [resolve_metrica(s, blocos_season, resumo) for s in specs]
    headline, lista = resolved[:3], resolved[3:]

    headline_html = "".join(
        f'<div class="metric-tile"><div class="lbl">{esc(l)}</div><div class="val">{nd(v)}</div></div>'
        for l, v in headline
    )
    lista_html = "".join(
        f'<div class="row"><span>{esc(l)}</span><b>{nd(v)}</b></div>' for l, v in lista
    )

    jogos = resumo["jogos"]
    comp_atual = blocos_season[0]["competicao"] if blocos_season else None
    amostra = (f'{int(jogos)} jogos em {comp_atual} (temporada atual)' if jogos is not None and comp_atual
               else "amostra desconhecida")

    return f'''<div class="panel">
      <span class="eyebrow">Métricas-chave · {esc(arquetipo)}</span>
      <div class="metric-headline">{headline_html}</div>
      <div class="metric-list">{lista_html}</div>
      <p class="metric-note">{esc(amostra)} — xG é total da temporada, não por 90. Métricas completas (toda "
      "categoria, todo histórico) na visão detalhada abaixo.</p>
    </div>'''


def bloco_radar(p):
    radar = p.get("radar")
    if not radar:
        return '<div class="panel"><span class="eyebrow">Índice Sofascore</span><p class="metric-note">Sem radar nesta rodada — ausência real de volume mínimo de minutos ou de clube ativo, não falha de captura.</p></div>'
    valores = {eixo: radar.get(eixo) for eixo in RADAR_EIXOS}
    return f'''<div class="panel radar-wrap">
      <span class="eyebrow" style="align-self:flex-start">Índice Sofascore</span>
      {radar_svg(valores)}
      <p class="radar-note">Composto proprietário do Sofascore (0–100), não é contagem direta de evento — não comparar com as métricas-chave ao lado como se fossem a mesma escala.</p>
    </div>'''


# --------------------------------------------------------------------------
# Bloco "completo"
# --------------------------------------------------------------------------

def tabela_categorias(blocos, titulo_temporada=None):
    partes = []
    vistas = []
    for b in blocos:
        if b["categoria"] not in vistas:
            vistas.append(b["categoria"])
    for cat in vistas:
        linhas = [b for b in blocos if b["categoria"] == cat]
        linha = linhas[0]
        rows = "".join(
            f'<tr><td>{esc(k)}</td><td class="num">{nd(v)}</td></tr>' for k, v in linha["metricas"].items()
        )
        sufixo = f" · {esc(titulo_temporada)}" if titulo_temporada else ""
        partes.append(f'''<div class="season-block">
          <div class="season-title">{esc(cat)}{sufixo}</div>
          <div class="full-table-wrap"><table class="full-table"><tbody>{rows}</tbody></table></div>
        </div>''')
    return "".join(partes)


def tabela_historico_carreira(blocos_carreira):
    linhas_por_temp = {}
    ordem = []
    for b in blocos_carreira:
        if b["categoria"] != "Geral":
            continue
        chave = (b["temporada"], b["competicao"])
        if chave not in linhas_por_temp:
            linhas_por_temp[chave] = b
            ordem.append(chave)
    partes = []
    for temp, comp in ordem:
        b = linhas_por_temp[(temp, comp)]
        m = b["metricas"]
        cls = ' class="total-linha"' if b.get("tipo_linha") == "total_temporada" else ""
        partes.append(
            f'<tr{cls}><td>{esc(temp)}</td><td>{esc(comp)}</td>'
            f'<td class="num">{nd(m.get("MP"))}</td><td class="num">{nd(m.get("MIN"))}</td>'
            f'<td class="num">{nd(m.get("GLS"))}</td><td class="num">{nd(m.get("AST"))}</td>'
            f'<td class="num">{nd(m.get("ASR"))}</td></tr>'
        )
    rows = "".join(partes)
    return f'''<div class="full-table-wrap"><table class="full-table">
      <thead><tr><th>Temporada</th><th>Competição</th><th>MP</th><th>MIN</th><th>Gols</th><th>Ast.</th><th>Nota</th></tr></thead>
      <tbody>{rows}</tbody></table></div>'''


def limitacoes(p):
    items = []
    if p.get("pais_clube"):
        items.append(f'<b>País/clube</b> é <b>[Inferência]</b> — {esc(p["pais_clube"]["fonte"].split("] ", 1)[-1])}')
    else:
        items.append("Sem <b>Pais_Clube</b> — jogador sem clube no momento, sem localização possível no mapa "
                      "(estado explícito, não erro).")
    if not p.get("radar"):
        items.append("Sem <b>radar Sofascore</b> (ATT/TEC/TAC/DEF/CRE) nesta rodada — ausência real de volume "
                      "mínimo de minutos ou de clube ativo, não falha de captura.")
    if p.get("arquetipo") == "Goleiro":
        items.append("Único goleiro da base — categorias capturadas (Atacando/Passe/Defendendo) são voltadas a "
                      "jogador de linha, sem dado de defesas, gols sofridos ou clean sheets. Card "
                      "estruturalmente mais magro por essa razão estrutural.")
    if not (p.get("valor_mercado") or {}).get("valor_eur"):
        items.append("Sem <b>Valor de mercado</b> no Transfermarkt (campo vazio na fonte).")
    if (p.get("agente") or "").strip() == "Desconhecido":
        items.append("Agente/empresário consta como <b>Desconhecido</b> na fonte — não confirmado.")
    return "".join(f"<li>{it}</li>" for it in items)


def bloco_completo(p):
    perf_hist = tabela_historico_carreira(p["performance_carreira"]["blocos"])
    blocos_season = p["performance_season"]["blocos"]
    cats = tabela_categorias(blocos_season, blocos_season[0]["temporada"] if blocos_season else None)
    limit_html = limitacoes(p)
    return f'''<details class="completo">
    <summary>Ver visão completa — todos os dados extraídos (carreira + temporada atual)</summary>
    <div class="completo-body">
      <div class="full-section"><h4>Histórico de carreira (Performance_Carreira, por temporada)</h4>{perf_hist}</div>
      <div class="full-section"><h4>Temporada atual por categoria (Performance_Season)</h4>{cats}</div>
      <div class="full-section"><h4>Limitações desta rodada</h4><ul class="limitacoes">{limit_html}</ul></div>
    </div>
  </details>'''


# --------------------------------------------------------------------------
# Card de um jogador
# --------------------------------------------------------------------------

def player_card(p, ativo):
    slug = slugify(p["jogador"])
    hidden_attr = "" if ativo else " hidden"
    status = p.get("status") or "Egresso"
    status_classe = STATUS_CLASSE.get(status, "status-egresso")
    pais_info = p.get("pais_clube")
    pais_txt = pais_info["valor"] if pais_info else "sem localização"
    pais_tag = ('<span class="tag-inline tag-inferencia">inferência</span>' if pais_info
                else '<span class="tag-inline tag-especulacao">sem clube</span>')

    ficha_itens = []
    if p.get("idade") is not None:
        ficha_itens.append(f'<span><b>{p["idade"]}</b> anos</span>')
    if p.get("altura"):
        ficha_itens.append(f'<span><b>{esc(p["altura"])}</b></span>')
    if p.get("pe_preferido"):
        ficha_itens.append(f'<span>pé <b>{esc(p["pe_preferido"])}</b></span>')
    if p.get("numero_camisa"):
        ficha_itens.append(f'<span>camisa <b>{esc(p["numero_camisa"])}</b></span>')
    vm = p.get("valor_mercado") or {}
    if vm.get("texto_original"):
        ficha_itens.append(f'<span>valor <b>{esc(vm["texto_original"])}</b></span>')
    if p.get("contrato_ate"):
        ficha_itens.append(f'<span>contrato até <b>{esc(p["contrato_ate"])}</b></span>')
    if p.get("jogos_ultimos_3_anos") is not None:
        ficha_itens.append(f'<span><b>{p["jogos_ultimos_3_anos"]}</b> jogos (últimos 3 anos)</span>')
    ficha_html = "".join(ficha_itens)

    return f'''<article class="player" id="p-{slug}" data-country="{pais_slug(pais_info["valor"] if pais_info else None)}"{hidden_attr}>
    <div class="player-head">
      <div>
        <h2>{esc(p["jogador"])}</h2>
        <p class="player-sub"><b>{esc(p.get("clube_atual") or "sem clube")}</b> · {esc(pais_txt)}{pais_tag} · {esc(p.get("arquetipo") or "sem arquétipo")}</p>
      </div>
      <div class="head-badges">
        <span class="status-badge {status_classe}">{esc(status)}</span>
        <span class="badge-atividade" title="Badge de atividade (jogos nos últimos 3 anos)">{esc(p.get("badge_atividade") or "")}</span>
      </div>
    </div>
    <div class="resumo">
      <div class="ficha">{ficha_html}</div>
      <div class="resumo-grid">
        {bloco_metricas_chave(p)}
        {bloco_radar(p)}
      </div>
    </div>
    {bloco_completo(p)}
  </article>'''


# --------------------------------------------------------------------------
# Lista de jogadores (flat + agrupada por clube pro Brasil)
# --------------------------------------------------------------------------

def item_lista(p, ativo):
    slug = slugify(p["jogador"])
    pais_info = p.get("pais_clube")
    cls = ' class="ativo"' if ativo else ""
    return (f'<li{cls} data-slug="{slug}" data-country="{pais_slug(pais_info["valor"] if pais_info else None)}" '
            f'data-nome="{esc(p["jogador"].lower())}"><button type="button" data-target="p-{slug}">'
            f'<span><span class="nome">{esc(p["jogador"])}</span>'
            f'<span class="clube">{esc(p.get("clube_atual") or "sem clube")}</span></span>'
            f'<span class="badge">{esc(p.get("badge_atividade") or "")}</span></button></li>')


def lista_flat_html(consolidado, slug_ativo):
    itens = "".join(item_lista(p, slugify(p["jogador"]) == slug_ativo) for p in consolidado)
    return f'<ul class="player-list" id="lista-flat">{itens}</ul>'


def lista_agrupada_brasil_html(consolidado, slug_ativo):
    brasil = [p for p in consolidado if (p.get("pais_clube") or {}).get("valor") == "Brasil"]
    por_clube: dict[str, list] = {}
    for p in brasil:
        clube = p.get("clube_atual") or "sem clube"
        por_clube.setdefault(clube, []).append(p)
    grupos = []
    for clube in sorted(por_clube):
        itens = "".join(item_lista(p, slugify(p["jogador"]) == slug_ativo) for p in por_clube[clube])
        grupos.append(f'<div class="grupo-clube"><h4>{esc(clube)}</h4><ul class="player-list">{itens}</ul></div>')
    return f'<div id="lista-brasil" hidden>{"".join(grupos)}</div>'


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=Path(__file__).resolve().parent.parent / "saida")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (args.saida / "mapa_preview.html")

    consolidado = json.loads((args.saida / "consolidado.json").read_text(encoding="utf-8"))
    consolidado.sort(key=lambda p: p["jogador"])

    contagem_por_pais: dict[str, int] = {}
    for p in consolidado:
        pais_info = p.get("pais_clube")
        if pais_info:
            contagem_por_pais[pais_info["valor"]] = contagem_por_pais.get(pais_info["valor"], 0) + 1
    sem_clube = [p for p in consolidado if not p.get("pais_clube")]

    slug_ativo = slugify(consolidado[0]["jogador"])
    cards = "".join(player_card(p, i == 0) for i, p in enumerate(consolidado))
    lista_flat = lista_flat_html(consolidado, slug_ativo)
    lista_brasil = lista_agrupada_brasil_html(consolidado, slug_ativo)

    sem_clube_botoes = "".join(
        f'<button type="button" data-target="p-{slugify(p["jogador"])}">{esc(p["jogador"])} ({esc(p.get("status") or "")})</button>'
        for p in sem_clube
    )
    n_paises = len(contagem_por_pais)

    legenda_itens = "".join(
        f'<button type="button" data-country="{pais_slug(pais)}">{esc(pais)} <b>{n}</b></button>'
        for pais, n in sorted(contagem_por_pais.items(), key=lambda x: -x[1])
    )
    pais_por_slug = {pais_slug(pais): {"nome": pais, "n": n} for pais, n in contagem_por_pais.items()}

    html = f"""<title>Mapeamento do Celeiro de Ases</title>
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
<link rel="preconnect" href="https://fonts.googleapis.com">
{FONT_LINK}
<style>{CSS}</style>

<div class="page">
  <header class="masthead">
    <span class="kicker">Projeto Futebol · Celeiro de Ases</span>
    <h1>Mapeamento do Celeiro de Ases</h1>
    <p class="dek">Onde estão hoje os {len(consolidado)} egressos das categorias de base do Internacional — performance, país/clube atual e atividade recente. Todo dado é <span class="tag-inline tag-verificado">verificado</span> ou <span class="tag-inline tag-inferencia">inferência</span> — País/clube é sempre [Inferência], derivado do nome do clube, nunca apresentado como confirmado.</p>
  </header>

  <section class="map-panel">
    <span class="eyebrow">Países · {n_paises} com jogadores · clique pra filtrar a lista</span>
    <div class="map-legend">{legenda_itens}</div>
  </section>

  <section class="split">
    <aside class="list-panel">
      <div class="list-panel-top">
        <span class="eyebrow" id="filtro-label">Todos os países · {len(consolidado)} jogadores</span>
        <button class="btn-limpar" id="btn-limpar" hidden>limpar</button>
      </div>
      <input type="search" class="busca" id="busca" placeholder="Buscar jogador...">
      {lista_flat}
      {lista_brasil}
      <p class="lista-vazia" id="lista-vazia" hidden>Nenhum jogador encontrado.</p>
      <div class="sem-clube-note">
        <span class="eyebrow">Sem clube · sem país associado</span>
        {sem_clube_botoes}
      </div>
    </aside>

    <main>{cards}</main>
  </section>

  <footer class="colophon">
    <div>
      <h4>Metodologia</h4>
      <p>Fonte única: <code>celeiro_de_ases_dados.xlsx</code> (3 abas já reconciliadas manualmente antes de chegar aqui — Jogadores/Performance_Carreira/Performance_Season). Categoria "Partidas" sempre descartada. Sem lesões e sem Transfermarkt (mercado/rumores) nesta versão, por escopo.</p>
    </div>
    <div>
      <h4>Países</h4>
      <p>Chips clicáveis no topo, contagem real de jogadores por país — clicar filtra a lista abaixo; Brasil (19/34) sub-agrupa por clube. Sem mapa-múndi nesta versão.</p>
    </div>
    <div>
      <h4>Em aberto</h4>
      <p>Escopo desta versão não inclui lesões nem Transfermarkt (mercado já vem da planilha, mas sem rumores/empresário detalhado). Cadastro de país/clube segue [Inferência] até confirmação manual.</p>
    </div>
  </footer>
</div>
<script>
(function(){{
  var listaFlat = document.getElementById('lista-flat');
  var listaBrasil = document.getElementById('lista-brasil');
  var listaVazia = document.getElementById('lista-vazia');
  var filtroLabel = document.getElementById('filtro-label');
  var btnLimpar = document.getElementById('btn-limpar');
  var busca = document.getElementById('busca');
  var legendaBtns = document.querySelectorAll('.map-legend button');
  var players = document.querySelectorAll('.player');
  var allListItems = document.querySelectorAll('.player-list li');
  var paisPorSlug = {json.dumps(pais_por_slug, ensure_ascii=False)};

  var paisAtivo = null;

  function ativaJogador(slug){{
    players.forEach(function(p){{ p.hidden = p.id !== ('p-' + slug); }});
    allListItems.forEach(function(li){{ li.classList.toggle('ativo', li.dataset.slug === slug); }});
    var alvo = document.getElementById('p-' + slug);
    if (alvo && window.innerWidth < 860) {{ alvo.scrollIntoView({{behavior:'smooth', block:'start'}}); }}
  }}

  function aplicaFiltroPais(slugPais){{
    paisAtivo = slugPais;
    legendaBtns.forEach(function(b){{ b.classList.toggle('ativo', b.dataset.country === slugPais); }});
    var termo = busca.value.trim().toLowerCase();

    if (slugPais === 'brasil'){{
      listaFlat.hidden = true;
      listaBrasil.hidden = false;
      btnLimpar.hidden = false;
      var infoBrasil = paisPorSlug['brasil'] || {{nome:'Brasil', n:0}};
      filtroLabel.textContent = infoBrasil.nome + ' · ' + infoBrasil.n + ' jogadores (por clube)';
    }} else {{
      listaFlat.hidden = false;
      listaBrasil.hidden = true;
      if (slugPais){{
        btnLimpar.hidden = false;
        var info = paisPorSlug[slugPais] || {{nome: slugPais, n: 0}};
        filtroLabel.textContent = info.nome + ' · ' + info.n + ' jogador' + (info.n !== 1 ? 'es' : '');
      }} else {{
        btnLimpar.hidden = true;
        filtroLabel.textContent = 'Todos os países · ' + allListItemsCount() + ' jogadores';
      }}
    }}
    filtraLista(termo);
  }}

  function allListItemsCount(){{ return listaFlat.querySelectorAll('li').length; }}

  function filtraLista(termo){{
    var visiveisFlat = 0;
    listaFlat.querySelectorAll('li').forEach(function(li){{
      var okPais = !paisAtivo || paisAtivo === 'brasil' || li.dataset.country === paisAtivo;
      var okBusca = !termo || li.dataset.nome.indexOf(termo) !== -1;
      var visivel = okPais && okBusca;
      li.hidden = !visivel;
      if (visivel) visiveisFlat++;
    }});
    var visiveisBrasil = 0;
    listaBrasil.querySelectorAll('li').forEach(function(li){{
      var okBusca = !termo || li.dataset.nome.indexOf(termo) !== -1;
      li.hidden = !okBusca;
      if (okBusca) visiveisBrasil++;
    }});
    listaBrasil.querySelectorAll('.grupo-clube').forEach(function(g){{
      var temVisivel = Array.prototype.some.call(g.querySelectorAll('li'), function(li){{ return !li.hidden; }});
      g.hidden = !temVisivel;
    }});
    var total = (paisAtivo === 'brasil') ? visiveisBrasil : visiveisFlat;
    listaVazia.hidden = total !== 0;
  }}

  legendaBtns.forEach(function(b){{
    b.addEventListener('click', function(){{ aplicaFiltroPais(paisAtivo === b.dataset.country ? null : b.dataset.country); }});
  }});
  btnLimpar.addEventListener('click', function(){{ aplicaFiltroPais(null); }});
  busca.addEventListener('input', function(){{ aplicaFiltroPais(paisAtivo); }});

  document.querySelectorAll('.player-list button').forEach(function(btn){{
    btn.addEventListener('click', function(){{
      var slug = btn.dataset.target.replace('p-', '');
      ativaJogador(slug);
    }});
  }});
  document.querySelectorAll('.sem-clube-note button').forEach(function(btn){{
    btn.addEventListener('click', function(){{
      aplicaFiltroPais(null);
      ativaJogador(btn.dataset.target.replace('p-', ''));
    }});
  }});
}})();
</script>
"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
