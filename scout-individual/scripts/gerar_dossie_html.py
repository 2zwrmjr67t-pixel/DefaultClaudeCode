#!/usr/bin/env python3
"""Passo 3: gera a pagina HTML (resumo + completo, mobile-first) a partir
de saida/consolidado.json (gerado por etapa1_pipeline.py). So le e
renderiza -- nao busca nem recalcula validacao. Ver README.md.

Layout do "resumo" segue o mockup aprovado pelo usuario: cabecalho com
selo de lesao, metricas-chave por arquetipo + radar Sofascore lado a
lado, bloco de mercado, bloco de rumores (rotulado [Especulação]). O
"completo" fica atras de um <details>/<summary> nativo (sem JS) com
100% do dado extraido, sem filtro de arquetipo.

Uso:
    python3 scripts/gerar_dossie_html.py
    python3 scripts/gerar_dossie_html.py --saida saida --out saida/dossie_preview.html
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# --------------------------------------------------------------------------
# Especificacao de metricas-chave por arquetipo (tabela do prompt v1-final)
# --------------------------------------------------------------------------

ARQUETIPO_METRICAS = {
    "Centroavante": [
        ("Gols/90", "gls90"),
        ("xG/90", "xg90"),
        ("Conversão", ("Atacando", "Conversão de gols")),
        ("Finalizações/jogo", ("Atacando", "Finalizações")),
        ("Chutes no alvo/jogo", ("Atacando", "Chutes certos por jogo")),
        ("Grandes chances perdidas", ("Atacando", "Grandes chances perdidas")),
    ],
    "Ponta/Extremo": [
        ("Gols/90", "gls90"),
        ("xG/90", "xg90"),
        ("Assistências/xA", "ast_xa"),
        ("Dribles certos", ("Outros (por partida)", "Dribles certos")),
        ("Grandes chances criadas", ("Passe", "Grandes chances criadas")),
        ("Passes decisivos", ("Passe", "Passes decisivos")),
    ],
    "Lateral/Ala": [
        ("Desarmes/jogo", ("Defendendo", "Desarmes por jogo")),
        ("Interceptações", ("Defendendo", "Interceptações")),
        ("Duelos ganhos (chão e aéreo)", "duelos"),
        ("Cruzamentos certos", ("Passe", "Cruzamentos certos")),
        ("Passes certos no terço final", ("Passe", "Passes certos no terço final")),
    ],
}
RUNNING_EXTRA = [
    ("Velocidade máxima", ("Desempenho de corrida (por 90)", "Velocidade máxima")),
    ("Distância/90", ("Desempenho de corrida (por 90)", "Distância percorrida")),
]
RADAR_EIXOS = ["ATT", "TEC", "TAC", "DEF", "CRE"]

CSS = """
:root{
  --paper:#F3F1E7; --ink:#16241D; --ink-soft:#3E4B41; --ink-faint:#6B7568;
  --line: rgba(22,36,29,0.13); --line-strong: rgba(22,36,29,0.26);
  --brass:#8C6A22; --brass-strong:#6E5219; --brass-soft: rgba(140,106,34,0.12);
  --card:#FFFFFF;
  --good:#2F7A55; --good-soft: rgba(47,122,85,0.13);
  --bad:#A83B3B; --bad-soft: rgba(168,59,59,0.12);
  --spec:#9A7A1F; --spec-soft: rgba(154,122,31,0.15);
  --radar-fill: rgba(62,75,65,0.22); --radar-stroke:#3E4B41;
  --shadow: 0 1px 2px rgba(22,36,29,0.06), 0 1px 0 rgba(22,36,29,0.05);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#111C16; --ink:#F1EEE3; --ink-soft:#B9C2B9; --ink-faint:#8A9389;
    --line: rgba(241,238,227,0.13); --line-strong: rgba(241,238,227,0.24);
    --brass:#D8B563; --brass-strong:#EFCF83; --brass-soft: rgba(216,181,99,0.13);
    --card:#182620;
    --good:#5FBE93; --good-soft: rgba(95,190,147,0.13);
    --bad:#E08585; --bad-soft: rgba(224,133,133,0.13);
    --spec:#D9C273; --spec-soft: rgba(217,194,115,0.14);
    --radar-fill: rgba(185,194,185,0.20); --radar-stroke:#B9C2B9;
    --shadow: 0 1px 2px rgba(0,0,0,0.3);
  }
}
:root[data-theme="dark"]{
  --paper:#111C16; --ink:#F1EEE3; --ink-soft:#B9C2B9; --ink-faint:#8A9389;
  --line: rgba(241,238,227,0.13); --line-strong: rgba(241,238,227,0.24);
  --brass:#D8B563; --brass-strong:#EFCF83; --brass-soft: rgba(216,181,99,0.13);
  --card:#182620;
  --good:#5FBE93; --good-soft: rgba(95,190,147,0.13);
  --bad:#E08585; --bad-soft: rgba(224,133,133,0.13);
  --spec:#D9C273; --spec-soft: rgba(217,194,115,0.14);
  --radar-fill: rgba(185,194,185,0.20); --radar-stroke:#B9C2B9;
  --shadow: 0 1px 2px rgba(0,0,0,0.3);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Source Sans 3", ui-sans-serif, system-ui, sans-serif;
  padding-inline: max(16px, calc((100% - 1180px)/2));
  padding-block: 36px 64px;
}
h1,h2,h3{font-family:"Fraunces", Georgia, serif; text-wrap:balance; margin:0}
.num{font-variant-numeric: tabular-nums; font-family:"IBM Plex Mono", ui-monospace, monospace}
a{color:var(--brass-strong)}
a:focus-visible, summary:focus-visible{outline:2px solid var(--brass); outline-offset:2px}
.page{max-width:1180px; margin-inline:auto}
.eyebrow{font-family:"IBM Plex Mono",monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:.1em; color:var(--ink-faint)}

.masthead{ border-bottom: 1px solid var(--line-strong); padding-bottom: 26px; margin-bottom: 30px; }
.masthead .kicker{ display:block; font-family:"IBM Plex Mono", monospace; font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--brass-strong); margin-bottom:10px; }
.masthead h1{font-size: clamp(26px, 4vw, 38px); font-weight:600; line-height:1.08}
.masthead .dek{color:var(--ink-soft); font-size:15px; max-width:60ch; margin-top:10px; line-height:1.5}

.stack{ display:flex; flex-direction:column; gap:28px; }

/* ---------- player card shell ---------- */
.player{
  background:var(--card); border:1px solid var(--line); border-radius:10px;
  box-shadow: var(--shadow); overflow:hidden;
}
.player-head{
  display:flex; justify-content:space-between; gap:14px; align-items:flex-start;
  padding: 20px 22px 14px;
}
.player-head h2{font-size:24px; font-weight:600}
.player-sub{ margin:6px 0 0; font-size:13.5px; color:var(--ink-soft) }
.player-sub b{color:var(--ink); font-weight:600}

.chip{
  display:inline-flex; align-items:center; gap:6px; padding:5px 11px; border-radius:20px;
  font-size:12px; font-weight:600; white-space:nowrap;
}
.chip::before{content:""; width:7px; height:7px; border-radius:50%; background:currentColor; flex:none}
.chip-good{ background:var(--good-soft); color:var(--good) }
.chip-bad{ background:var(--bad-soft); color:var(--bad) }
.chip-spec{
  display:inline-flex; align-items:center; padding:4px 10px; border-radius:20px;
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:.04em;
  background:var(--spec-soft); color:var(--spec); white-space:nowrap;
}

.resumo{ padding: 6px 22px 22px; }
.resumo-grid{ display:grid; grid-template-columns: 1.15fr 1fr; gap:20px; align-items:start; }
@media (max-width: 720px){ .resumo-grid{grid-template-columns:1fr} }

.panel{ border:1px solid var(--line); border-radius:8px; padding:16px 16px 14px; }
.panel > .eyebrow{margin-bottom:12px; display:block}

.metric-headline{ display:grid; grid-template-columns: repeat(3,1fr); gap:10px; margin-bottom:14px; }
@media (max-width: 420px){ .metric-headline{grid-template-columns: repeat(3,1fr); gap:6px} }
.metric-tile{ text-align:center; padding:10px 4px; background:var(--paper); border-radius:6px; }
.metric-tile .lbl{ font-size:10.5px; color:var(--ink-faint); text-transform:uppercase; letter-spacing:.04em; }
.metric-tile .val{ font-family:"IBM Plex Mono",monospace; font-size:19px; font-weight:600; margin-top:4px; }
.metric-list{ display:flex; flex-direction:column; gap:0; }
.metric-list .row{ display:flex; justify-content:space-between; gap:10px; padding:7px 2px; border-top:1px solid var(--line); font-size:13px; }
.metric-list .row span{color:var(--ink-soft)}
.metric-list .row b{font-weight:600; font-family:"IBM Plex Mono",monospace}
.metric-note{ font-size:11.5px; color:var(--ink-faint); line-height:1.5; margin-top:12px; }

.radar-wrap{ display:flex; flex-direction:column; align-items:center; }
.radar-wrap svg{ max-width:100%; height:auto; }
.radar-note{ font-size:11px; color:var(--ink-faint); text-align:center; margin-top:6px; line-height:1.45; }

.mercado{ margin-top:16px; }
.mercado-top{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:10px; }
.valor-mercado{ font-family:"Fraunces",serif; font-size:26px; font-weight:600; color:var(--brass-strong); }
.contrato-ate{ font-size:12.5px; color:var(--ink-soft); }
.mercado-foot{ font-size:12px; color:var(--ink-faint); margin-top:6px; }

.rumores{ margin-top:16px; }
.rumores-top{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.rumor-row{ display:flex; justify-content:space-between; gap:10px; padding:8px 0; border-top:1px solid var(--line); font-size:13px; }
.rumor-row:first-of-type{border-top:none}
.rumor-row .clube{font-weight:600}
.rumor-row .quando{ color:var(--ink-faint); font-size:12px; text-align:right; white-space:nowrap; font-family:"IBM Plex Mono",monospace }
.rumor-empty, .noticia-empty{ font-size:13px; color:var(--ink-faint); font-style:italic; }
.rumor-foot, .noticia-foot{ font-size:11.5px; color:var(--ink-faint); margin-top:8px; line-height:1.5; }

.noticia{ margin-top:16px; }
.noticia h3{ font-size:15px; font-weight:600; margin:6px 0 5px; line-height:1.35 }
.noticia p{ font-size:13px; color:var(--ink-soft); line-height:1.5; margin:0 0 6px; }
.noticia .src{ font-family:"IBM Plex Mono",monospace; font-size:11px; color:var(--ink-faint); }
.noticia .src a{ text-decoration:none; border-bottom:1px dotted var(--line-strong) }

/* ---------- completo (details) ---------- */
details.completo{ border-top:1px solid var(--line-strong); }
details.completo summary{
  cursor:pointer; padding:14px 22px; font-family:"IBM Plex Mono",monospace; font-size:11.5px;
  text-transform:uppercase; letter-spacing:.08em; color:var(--brass-strong); list-style:none;
  display:flex; align-items:center; gap:8px; user-select:none;
}
details.completo summary::-webkit-details-marker{display:none}
details.completo summary::before{ content:"+"; font-family:"IBM Plex Mono",monospace; font-size:14px; width:14px; }
details.completo[open] summary::before{ content:"−"; }
details.completo summary:hover{ background:var(--brass-soft); }
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
  margin-top:36px; padding-top:20px; border-top:1px solid var(--line-strong);
  display:grid; grid-template-columns: repeat(3,1fr); gap:20px;
  font-size:12px; color:var(--ink-soft); line-height:1.55;
}
@media (max-width:760px){ .colophon{grid-template-columns:1fr} }
.colophon h4{
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--brass-strong); margin:0 0 7px; font-weight:600;
}
.colophon code{ font-family:"IBM Plex Mono",monospace; background:var(--brass-soft); padding:1px 5px; border-radius:3px; color:var(--ink) }
"""
FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;'
             '9..144,500;9..144,600;9..144,700&family=Source+Sans+3:wght@400;500;600;700&family=IBM+Plex+Mono:'
             'wght@400;500;600&display=swap">')


def esc(s):
    return "" if s is None else str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nd(v):
    return "N/D" if v is None or v in ("-", "") else esc(v)


def fnum(v):
    if v in (None, "-", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Extracao de metricas
# --------------------------------------------------------------------------

def extrai(categorias, cat_nome, chave):
    for c in categorias:
        if c["categoria"] == cat_nome:
            v = c["metricas"].get(chave)
            return v if v not in (None, "-", "") else None
    return None


def geral_e_adicional_atuais(performance):
    temporadas = performance.get("temporadas") or []
    if not temporadas:
        return {}, {}
    temp_atual = temporadas[0]["temporada"]
    geral = next((t["metricas"] for t in temporadas
                  if t["temporada"] == temp_atual and t["tipo_linha"] == "total_temporada" and t["categoria"] == "Geral"), {})
    adicional = next((t["metricas"] for t in temporadas
                       if t["temporada"] == temp_atual and t["tipo_linha"] == "total_temporada" and t["categoria"] == "Adicional"), {})
    return geral, adicional


def resumo_temporada(categorias, geral, adicional):
    """Numeros do Resumo da Temporada (Performance_Season) -- todos no
    MESMO escopo (a competicao principal daquela temporada, ex.: so
    Brasileirao Betano pro Rene, nao o agregado 'Total do Ano' que
    performance.Geral traz). Nunca misturar minutos agregados com xG
    escopado a uma competicao so -- foi um bug real, corrigido aqui:
    tudo sai de Resumo da Temporada/Atacando/Passe (mesma escopo), e so
    cai pro agregado (geral/adicional) quando a Performance_Season nao
    tem o campo de jeito nenhum."""
    jogos = fnum(extrai(categorias, "Resumo da Temporada", "JOGOS"))
    min_jogo = fnum(extrai(categorias, "Resumo da Temporada", "MINUTOS POR JOGO"))
    minutos = jogos * min_jogo if jogos is not None and min_jogo is not None else fnum(geral.get("MIN"))
    gols = fnum(extrai(categorias, "Resumo da Temporada", "GOLS"))
    if gols is None:
        gols = fnum(geral.get("GLS"))
    ast = extrai(categorias, "Resumo da Temporada", "ASSISTÊNCIAS") or geral.get("AST")
    xg = fnum(extrai(categorias, "Resumo da Temporada", "GOLS ESPERADOS (XG)"))
    if xg is None:
        xg = fnum(extrai(categorias, "Atacando", "Gols esperados (xG)"))
    if xg is None:
        xg = fnum(adicional.get("XG"))
    xa = extrai(categorias, "Passe", "Assistências Esperadas (xA)") or adicional.get("XA")
    return {"jogos": jogos, "minutos": minutos, "gols": gols, "ast": ast, "xg": xg, "xa": xa}


def resolve_metrica(spec, categorias, resumo):
    label, source = spec
    if source == "gls90":
        gls, minutos = resumo["gols"], resumo["minutos"]
        val = f"{gls / minutos * 90:.2f}" if gls is not None and minutos else None
    elif source == "xg90":
        xg, minutos = resumo["xg"], resumo["minutos"]
        val = f"{xg / minutos * 90:.2f}" if xg is not None and minutos else None
    elif source == "ast_xa":
        ast, xa = resumo["ast"], resumo["xa"]
        val = f"{nd(ast)} · {xa} xA" if ast not in (None, "-") and xa not in (None, "-") else None
    elif source == "duelos":
        chao = extrai(categorias, "Outros (por partida)", "Duelos ganhos pelo chão")
        aereo = extrai(categorias, "Outros (por partida)", "Duelos aéreos ganhos")
        val = f"chão {chao} · aéreo {aereo}" if chao and aereo else (chao or aereo)
    else:
        cat_nome, chave = source
        val = extrai(categorias, cat_nome, chave)
    return label, val


# --------------------------------------------------------------------------
# Radar SVG
# --------------------------------------------------------------------------

def radar_svg(valores: dict, largura=260, altura=200):
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
        lx = cx + (raio + 22) * math.cos(ang)
        ly = cy + (raio + 22) * math.sin(ang)
        v = valores.get(eixo, "N/D")
        anchor = "middle"
        if math.cos(ang) > 0.3:
            anchor = "start"
        elif math.cos(ang) < -0.3:
            anchor = "end"
        labels_svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" dominant-baseline="middle" '
            f'font-family="IBM Plex Mono, monospace" font-size="11" fill="var(--ink-soft)">{esc(eixo)} '
            f'<tspan font-weight="700" fill="var(--ink)">{esc(v)}</tspan></text>'
        )

    return f'''<svg viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}" role="img" aria-label="Radar Sofascore">
      {''.join(aneis)}
      {eixos_svg}
      <polygon points="{poligono}" fill="var(--radar-fill)" stroke="var(--radar-stroke)" stroke-width="2"/>
      {''.join(labels_svg)}
    </svg>'''


# --------------------------------------------------------------------------
# Blocos do resumo
# --------------------------------------------------------------------------

def bloco_metricas_chave(p):
    arquetipo = (p.get("arquetipo") or {}).get("valor")
    specs = ARQUETIPO_METRICAS.get(arquetipo)
    categorias = p["performance_season"]["categorias"]
    geral, adicional = geral_e_adicional_atuais(p["performance"])
    if not specs:
        return '<div class="panel"><p class="metric-note">Sem arquétipo definido — métricas-chave não puderam ser montadas.</p></div>'

    resumo = resumo_temporada(categorias, geral, adicional)
    resolved = [resolve_metrica(s, categorias, resumo) for s in specs]
    headline, lista = resolved[:3], resolved[3:]
    running = [resolve_metrica(s, categorias, resumo) for s in RUNNING_EXTRA]

    headline_html = "".join(
        f'<div class="metric-tile"><div class="lbl">{esc(l)}</div><div class="val">{nd(v)}</div></div>'
        for l, v in headline
    )
    lista_html = "".join(
        f'<div class="row"><span>{esc(l)}</span><b>{nd(v)}</b></div>' for l, v in (lista + running)
    )

    jogos = resumo["jogos"]
    comp_atual = categorias[0]["competicao"] if categorias else None
    amostra = f'{int(jogos)} jogos em {comp_atual}' if jogos is not None and comp_atual else (
        f'{int(jogos)} jogos' if jogos is not None else "amostra desconhecida")
    amostra_nota = " · amostra parcial" if jogos is not None and jogos < 10 else ""

    return f'''<div class="panel">
      <span class="eyebrow">Métricas-chave · {esc(arquetipo)}</span>
      <div class="metric-headline">{headline_html}</div>
      <div class="metric-list">{lista_html}</div>
      <p class="metric-note">{esc(amostra)}{amostra_nota} — escopo da competição principal da temporada, não o agregado de todas as competições. Métricas completas (passe, defesa, cartões) na visão detalhada abaixo.</p>
    </div>'''


def bloco_radar(p):
    radar = p.get("radar")
    if not radar or not radar.get("temporadas"):
        return '<div class="panel"><span class="eyebrow">Índice Sofascore</span><p class="metric-note">Sem dado de radar nesta rodada.</p></div>'
    valores = radar["temporadas"][0]
    return f'''<div class="panel radar-wrap">
      <span class="eyebrow" style="align-self:flex-start">Índice Sofascore</span>
      {radar_svg(valores)}
      <p class="radar-note">Composto proprietário do Sofascore (0–100), não é contagem direta de evento — não comparar com as métricas-chave ao lado como se fossem a mesma escala.</p>
    </div>'''


def bloco_mercado(p):
    m = p.get("mercado")
    if not m:
        return '<div class="mercado"><span class="eyebrow">Mercado</span><p class="metric-note">Sem dado de mercado nesta rodada.</p></div>'
    valor = m.get("valor_mercado") or {}
    texto = (valor.get("texto_original") or "N/D").split("Última")[0].split("ltima")[0].strip()
    contrato = f'contrato até {m["contrato_fim"]}' if m.get("contrato_fim") else "contrato N/D"
    upd = valor.get("ultima_alteracao")
    return f'''<div class="mercado">
      <span class="eyebrow">Mercado</span>
      <div class="mercado-top">
        <span class="valor-mercado">{esc(texto)}</span>
        <span class="contrato-ate">{esc(contrato)}</span>
      </div>
      <p class="mercado-foot">{f"atualizado em {esc(upd)}" if upd else ""} · empresário: {esc(m.get("empresario") or "N/D")}</p>
    </div>'''


def _dias_atras(data_iso, hoje):
    from datetime import date as _date
    if not data_iso:
        return None
    y, mo, d = map(int, data_iso.split("-"))
    return (hoje - _date(y, mo, d)).days


def bloco_rumores(p, hoje):
    r = p.get("rumores") or {"itens": [], "tem_rumor": False}
    itens = r.get("itens", [])
    if not itens:
        return '''<div class="rumores">
          <div class="rumores-top"><span class="eyebrow">Rumores de mercado</span><span class="chip-spec">especulação, não fato</span></div>
          <p class="rumor-empty">Nenhum rumor de mercado registrado no Transfermarkt.</p>
        </div>'''
    com_idade = sorted(
        [{**it, "dias": _dias_atras(it["data_mencao"], hoje)} for it in itens],
        key=lambda x: x["dias"] if x["dias"] is not None else 99999
    )
    dentro_15 = [it for it in com_idade if it["dias"] is not None and it["dias"] <= 15]
    mostrados = com_idade[:2]
    linhas = "".join(
        f'<div class="rumor-row"><span class="clube">{esc(it["clube_interessado"])}</span>'
        f'<span class="quando">{esc(it["data_mencao"])} · {it["dias"]} dias atrás</span></div>'
        for it in mostrados
    )
    if dentro_15:
        rodape = f"{len(dentro_15)} rumor(es) dentro dos últimos 15 dias, de {len(itens)} registrados no total."
    else:
        rodape = (f"Sem rumor dentro dos últimos 15 dias — os {len(mostrados)} mais recentes de "
                  f"{len(itens)} registrados exibidos, como contexto histórico.")
    return f'''<div class="rumores">
      <div class="rumores-top"><span class="eyebrow">Rumores de mercado</span><span class="chip-spec">especulação, não fato</span></div>
      {linhas}
      <p class="rumor-foot">{esc(rodape)}</p>
    </div>'''


def bloco_noticia(p):
    n = p.get("noticias") or {}
    itens = n.get("itens", [])
    if not itens:
        return '<div class="noticia"><span class="eyebrow">Notícia</span><p class="noticia-empty">Nenhuma notícia encontrada, dentro ou fora da janela de 15 dias.</p></div>'
    it = itens[0]
    if it.get("dentro_da_janela"):
        chip, label = '<span class="chip chip-good">recente</span>', "Notícia recente"
    else:
        chip, label = f'<span class="chip chip-bad">há {it["idade_dias"]} dias</span>', "Sem notícia recente — mais próxima"
    return f'''<div class="noticia">
      <div class="rumores-top"><span class="eyebrow">{esc(label)}</span>{chip}</div>
      <h3>{esc(it["titulo"])}</h3>
      <p>{esc(it["resumo"])}</p>
      <div class="src"><a href="{esc(it["url"])}" target="_blank" rel="noopener">{esc(it.get("fonte",""))}</a> · {esc(it["data_publicacao"])}</div>
    </div>'''


# --------------------------------------------------------------------------
# Bloco "completo"
# --------------------------------------------------------------------------

def tabela_categorias(categorias, titulo_temporada=None):
    blocos = []
    vistas = []
    for c in categorias:
        if c["categoria"] not in vistas:
            vistas.append(c["categoria"])
    for cat in vistas:
        linhas = [c for c in categorias if c["categoria"] == cat]
        linha = linhas[0]
        rows = "".join(
            f'<tr><td>{esc(k)}</td><td class="num">{nd(v)}</td></tr>' for k, v in linha["metricas"].items()
        )
        blocos.append(f'''<div class="season-block">
          <div class="season-title">{esc(cat)}{f" · {esc(titulo_temporada)}" if titulo_temporada else ""}</div>
          <div class="full-table-wrap"><table class="full-table"><tbody>{rows}</tbody></table></div>
        </div>''')
    return "".join(blocos)


def tabela_historico_sofascore(temporadas):
    linhas_por_temp = {}
    ordem = []
    for t in temporadas:
        if t["categoria"] != "Geral":
            continue
        chave = (t["temporada"], t["competicao"])
        if chave not in linhas_por_temp:
            linhas_por_temp[chave] = t["metricas"]
            ordem.append(chave)
    rows = "".join(
        f'<tr><td>{esc(temp)}</td><td>{esc(comp)}</td>'
        f'<td class="num">{nd(m.get("MP"))}</td><td class="num">{nd(m.get("MIN"))}</td>'
        f'<td class="num">{nd(m.get("GLS"))}</td><td class="num">{nd(m.get("AST"))}</td>'
        f'<td class="num">{nd(m.get("ASR"))}</td></tr>'
        for temp, comp in ordem for m in [linhas_por_temp[(temp, comp)]]
    )
    return f'''<div class="full-table-wrap"><table class="full-table">
      <thead><tr><th>Temporada</th><th>Competição</th><th>MP</th><th>MIN</th><th>Gols</th><th>Ast.</th><th>Nota</th></tr></thead>
      <tbody>{rows}</tbody></table></div>'''


def tabela_lesoes(lesoes):
    if not lesoes:
        return '<p class="metric-note">Sem registro de lesão.</p>'
    rows = "".join(
        f'<tr><td>{esc(l.get("temporada") or "—")}</td><td>{esc(l["lesao"])}</td>'
        f'<td>{esc(l.get("de") or "—")}</td><td>{esc(l.get("ate") or "—")}</td>'
        f'<td class="num">{nd(l.get("dias"))}</td><td class="num">{nd(l.get("jogos_perdidos"))}</td></tr>'
        for l in lesoes
    )
    return f'''<div class="full-table-wrap"><table class="full-table">
      <thead><tr><th>Temporada</th><th>Lesão</th><th>De</th><th>Até</th><th>Dias</th><th>Jogos perdidos</th></tr></thead>
      <tbody>{rows}</tbody></table></div>'''


def tabela_rumores_completa(rumores, hoje):
    itens = rumores.get("itens", [])
    if not itens:
        return '<p class="metric-note">Nenhum rumor registrado.</p>'
    com_idade = sorted(
        [{**it, "dias": _dias_atras(it["data_mencao"], hoje)} for it in itens],
        key=lambda x: x["dias"] if x["dias"] is not None else 99999
    )
    rows = "".join(
        f'<tr><td>{esc(it["clube_interessado"])}</td><td>{esc(it["data_mencao"])}</td>'
        f'<td class="num">{it["dias"]} dias atrás</td></tr>' for it in com_idade
    )
    return f'''<div class="full-table-wrap"><table class="full-table">
      <thead><tr><th>Clube interessado</th><th>Data</th><th>Idade</th></tr></thead>
      <tbody>{rows}</tbody></table></div>'''


def limitacoes(p):
    items = []
    arquetipo_info = p.get("arquetipo") or {}
    if "Inferência" in (arquetipo_info.get("fonte") or ""):
        items.append(f'Arquétipo "{esc(arquetipo_info.get("valor"))}" é <b>[Inferência]</b> — '
                      f'{esc(arquetipo_info["fonte"].split("] ", 1)[-1])}')
    categorias_presentes = {c["categoria"] for c in p["performance_season"]["categorias"]}
    if "Desempenho de corrida (por 90)" not in categorias_presentes:
        items.append("Sem dado de <b>Desempenho de corrida</b> nesta liga — rastreamento físico provavelmente "
                      "não coberto pelo Sofascore nesta competição.")
    m = p.get("mercado") or {}
    if m and not (m.get("valor_mercado_maximo") or {}).get("valor_eur"):
        items.append("<b>Valor de mercado máximo</b> histórico sem fonte confirmada (campo vazio no Transfermarkt).")
    if not p["clube_atual"]:
        items.append("<b>Clube atual</b> e cadastro formal (aba <code>Jogadores</code> com IDs) ainda não "
                      "confirmados — junção com o Sofascore hoje é por nome, não por ID.")
    if not items:
        items.append("Nenhuma limitação de fonte identificada nesta rodada além das já citadas na metodologia.")
    return "".join(f"<li>{it}</li>" for it in items)


def bloco_completo(p, hoje):
    perf_hist = tabela_historico_sofascore(p["performance"]["temporadas"])
    cats = tabela_categorias(p["performance_season"]["categorias"], p["performance_season"]["categorias"][0]["temporada"] if p["performance_season"]["categorias"] else None)
    lesoes_html = tabela_lesoes(p.get("lesoes") or [])
    rumores_html = tabela_rumores_completa(p.get("rumores") or {"itens": []}, hoje)
    limit_html = limitacoes(p)
    return f'''<details class="completo">
    <summary>Ver visão completa — todos os dados extraídos, sem filtro de arquétipo</summary>
    <div class="completo-body">
      <div class="full-section"><h4>Histórico de carreira (Performance_Sofascore, por temporada)</h4>{perf_hist}</div>
      <div class="full-section"><h4>Temporada atual por categoria (Performance_Season)</h4>{cats}</div>
      <div class="full-section"><h4>Lesões</h4>{lesoes_html}</div>
      <div class="full-section"><h4>Rumores de mercado (todos os registrados)</h4>{rumores_html}</div>
      <div class="full-section"><h4>Limitações desta rodada</h4><ul class="limitacoes">{limit_html}</ul></div>
    </div>
  </details>'''


# --------------------------------------------------------------------------
# Card completo de um jogador
# --------------------------------------------------------------------------

def sem_lesao(lesoes):
    if not lesoes:
        return True, None
    ativas = [l for l in lesoes if l["lesao"] and l["lesao"] != "Nenhuma lesão registrada"]
    if not ativas:
        return True, None
    return False, ativas[0]["lesao"]


def player_card(p, hoje):
    ok, detalhe = sem_lesao(p.get("lesoes") or [])
    chip_lesao = (f'<span class="chip chip-good">sem lesão</span>' if ok
                  else f'<span class="chip chip-bad">{esc(detalhe)}</span>')
    clube = p.get("clube_atual") or (p.get("mercado") or {}).get("clube_atual") or "clube não confirmado"
    categorias_season = p["performance_season"]["categorias"]
    comp = (p.get("competicao_principal") or (categorias_season[0]["competicao"] if categorias_season else None)
            or "competição não confirmada")
    arquetipo = (p.get("arquetipo") or {}).get("valor") or "sem arquétipo"
    inferencia_tag = ('<span class="tag-inline tag-inferencia">inferência</span>'
                       if "Inferência" in ((p.get("arquetipo") or {}).get("fonte") or "") else "")

    return f'''<article class="player">
    <div class="player-head">
      <div>
        <h2>{esc(p["jogador"])}</h2>
        <p class="player-sub"><b>{esc(clube)}</b> · {esc(comp)} · {esc(arquetipo)}{inferencia_tag}</p>
      </div>
      {chip_lesao}
    </div>
    <div class="resumo">
      <div class="resumo-grid">
        {bloco_metricas_chave(p)}
        {bloco_radar(p)}
      </div>
      {bloco_mercado(p)}
      {bloco_rumores(p, hoje)}
      {bloco_noticia(p)}
    </div>
    {bloco_completo(p, hoje)}
  </article>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=Path(__file__).resolve().parent.parent / "saida")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--data-geracao", type=str, default=None)
    ap.add_argument("--data-referencia", type=str, default=None, help="AAAA-MM-DD, default hoje")
    args = ap.parse_args()
    out = args.out or (args.saida / "dossie_preview.html")

    from datetime import date as _date
    hoje = _date.fromisoformat(args.data_referencia) if args.data_referencia else _date.today()

    consolidado = json.loads((args.saida / "consolidado.json").read_text(encoding="utf-8"))
    ORDEM_SHORTLIST = ["André Clóvis", "Thiago Ocampo", "Thauan Lara", "Renê"]
    consolidado.sort(key=lambda p: ORDEM_SHORTLIST.index(p["jogador"]) if p["jogador"] in ORDEM_SHORTLIST else 99)

    cards = "".join(player_card(p, hoje) for p in consolidado)

    html = f"""<title>Dossiê de Observação</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
{FONT_LINK}
<style>{CSS}</style>

<div class="page">
  <header class="masthead">
    <span class="kicker">Scout individual · v1 completa</span>
    <h1>Dossiê de Observação</h1>
    <p class="dek">Acompanhamento individual de 4 jogadores — performance, mercado, lesão, rumor e notícia recente. Todo dado é <span class="tag-inline tag-verificado">verificado</span>, <span class="tag-inline tag-inferencia">inferência</span> ou <span class="tag-inline tag-especulacao">especulação</span> — nunca apresentado sem essa marcação quando a incerteza existe.</p>
  </header>

  <section class="stack">{cards}</section>

  <footer class="colophon">
    <div>
      <h4>Metodologia</h4>
      <p>Junção Transfermarkt↔Lesões↔Rumores por <code>ID_Transfermarkt</code> real; Sofascore (Performance e Performance_Season) ainda por nome + alias manual, documentado em <code>etapa1_pipeline.py</code>. Categoria "Partidas" do Performance_Season é sempre descartada (despejo corrompido, não uma categoria real).</p>
    </div>
    <div>
      <h4>Arquétipos</h4>
      <p>Vêm da tabela do prompt, não de uma coluna <code>Jogadores.Arquetipo</code> real ainda. O caso do Renê fica marcado como inferência no próprio card — etiqueta oficial do Transfermarkt diz "Ponta/Extremo", mas o volume de gols sugere centroavante.</p>
    </div>
    <div>
      <h4>Em aberto</h4>
      <p>Publicação em GitHub Pages é o próximo passo, pendente de aprovação. Cadastro formal com IDs (aba <code>Jogadores</code>) segue pendente.</p>
    </div>
  </footer>
</div>
"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
