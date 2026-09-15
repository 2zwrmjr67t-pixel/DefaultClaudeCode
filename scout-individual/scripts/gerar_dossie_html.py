#!/usr/bin/env python3
"""Gera o preview em HTML do dossie de observacao a partir de saida/*.json
(gerado por etapa1_pipeline.py). E so isso -- le, nao busca nada, nao
recalcula validacao. Ver README.md desta pasta para a proveniencia dos
dados e as regras de leitura do grafico.

Uso:
    python3 scripts/gerar_dossie_html.py
    python3 scripts/gerar_dossie_html.py --saida saida --out saida/dossie_preview.html
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

TIER_ORDER = ["1ª divisão", "2ª divisão", "3ª divisão", "sem-liga"]
TIER_CLASS = {"1ª divisão": "tier1", "2ª divisão": "tier2", "3ª divisão": "tier3", "sem-liga": "tierna"}
TIER_LABEL = {"1ª divisão": "1ª divisão", "2ª divisão": "2ª divisão", "3ª divisão": "3ª divisão",
              "sem-liga": "sem liga classificada"}
# Classificacao de divisao por nome real de competicao (nunca por "Total do
# Ano"). So cobre o que ja apareceu nos exports recebidos -- uma competicao
# nova entra como "sem-liga" ate alguem adicionar aqui.
LEAGUE_TIERS = {
    "liga portugal betclic": "1ª divisão",
    "liga portugal 2": "2ª divisão",
    "primera nacional": "2ª divisão",
    "brasileirao betano": "1ª divisão",
    "brasileirao serie a": "1ª divisão",
    "brasileirao serie c": "3ª divisão",
}
CAT_MAP = {
    "Geral": ["MP", "MIN", "GLS", "AST", "ASR"],
    "Finalização": ["TOS", "SOT"],
    "Passe": ["APS%", "CA%"],
    "Defendendo": ["TACK", "INT", "YC"],
    "Adicional": ["XG", "XGI", "XA"],
}

CSS = """
:root{
  --paper:#EEEBDF; --paper-2:#E4E0D0; --ink:#16241D; --ink-soft:#3E4B41;
  --line: rgba(22,36,29,0.14); --line-strong: rgba(22,36,29,0.28);
  --brass:#8C6A22; --brass-strong:#6E5219; --brass-soft: rgba(140,106,34,0.14);
  --card:#F7F5EA;
  --good:#2F7A55; --good-soft: rgba(47,122,85,0.14);
  --pending:#7A6A3A; --pending-soft: rgba(122,106,58,0.16);
  --stale:#9B5A34; --stale-soft: rgba(155,90,52,0.13);
  --tier1:#8C6A22; --tier2:#3F7566; --tier3:#7A5289; --tierna:#8A8578;
  --shadow: 0 1px 0 rgba(22,36,29,0.06);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#0E1B15; --paper-2:#132A21; --ink:#F3F0E4; --ink-soft:#B9C2B9;
    --line: rgba(243,240,228,0.14); --line-strong: rgba(243,240,228,0.26);
    --brass:#D8B563; --brass-strong:#EFCF83; --brass-soft: rgba(216,181,99,0.14);
    --card:#132A21;
    --good:#5FBE93; --good-soft: rgba(95,190,147,0.14);
    --pending:#C9B778; --pending-soft: rgba(201,183,120,0.14);
    --stale:#D68F63; --stale-soft: rgba(214,143,99,0.14);
    --tier1:#D8B563; --tier2:#6FB39F; --tier3:#BC93D6; --tierna:#8A8578;
    --shadow: 0 1px 0 rgba(0,0,0,0.3);
  }
}
:root[data-theme="dark"]{
  --paper:#0E1B15; --paper-2:#132A21; --ink:#F3F0E4; --ink-soft:#B9C2B9;
  --line: rgba(243,240,228,0.14); --line-strong: rgba(243,240,228,0.26);
  --brass:#D8B563; --brass-strong:#EFCF83; --brass-soft: rgba(216,181,99,0.14);
  --card:#132A21;
  --good:#5FBE93; --good-soft: rgba(95,190,147,0.14);
  --pending:#C9B778; --pending-soft: rgba(201,183,120,0.14);
  --stale:#D68F63; --stale-soft: rgba(214,143,99,0.14);
  --tier1:#D8B563; --tier2:#6FB39F; --tier3:#BC93D6; --tierna:#8A8578;
  --shadow: 0 1px 0 rgba(0,0,0,0.3);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Source Sans 3", ui-sans-serif, system-ui, sans-serif;
  padding-inline: max(16px, calc((100% - 1180px)/2));
  padding-block: 40px 64px;
}
h1,h2,h3{font-family:"Fraunces", Georgia, serif; text-wrap:balance; margin:0}
.num{font-variant-numeric: tabular-nums; font-family:"IBM Plex Mono", ui-monospace, monospace}
a{color:var(--brass-strong)}
a:focus-visible, button:focus-visible, [tabindex]:focus-visible{outline:2px solid var(--brass); outline-offset:2px}
.page{max-width:1180px; margin-inline:auto}

.masthead{
  border-bottom: 1px solid var(--line-strong); padding-bottom: 28px; margin-bottom: 34px;
  display:flex; flex-wrap:wrap; gap:24px; justify-content:space-between; align-items:flex-end;
}
.masthead .kicker{
  display:block; font-family:"IBM Plex Mono", monospace; font-size:12px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--brass-strong); margin-bottom:10px;
}
.masthead h1{font-size: clamp(28px, 4vw, 40px); font-weight:600; line-height:1.08}
.masthead .dek{color:var(--ink-soft); font-size:15.5px; max-width:50ch; margin-top:10px; line-height:1.5}
.meta-strip{
  display:flex; flex-direction:column; gap:6px; font-family:"IBM Plex Mono", monospace;
  font-size:12.5px; color:var(--ink-soft); text-align:right; min-width:210px;
}
.meta-strip .row{display:flex; justify-content:space-between; gap:18px}
.meta-strip .row b{color:var(--ink); font-weight:600}

.grid{ display:grid; grid-template-columns: repeat(2, 1fr); gap:22px; }
@media (max-width: 900px){ .grid{grid-template-columns:1fr} }

.card{
  background:var(--card); border:1px solid var(--line); border-radius:3px;
  box-shadow: var(--shadow); display:flex; flex-direction:column;
}
.card-head{
  display:flex; justify-content:space-between; gap:14px; align-items:flex-start;
  padding: 20px 22px 16px; border-bottom:1px solid var(--line);
}
.card-head h2{font-size:23px; font-weight:600}
.club-line{ margin:6px 0 0; font-size:13.5px; color:var(--ink-soft) }
.club-line .comp{color:var(--ink); font-weight:600}

.chip{
  display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border-radius:20px;
  font-family:"IBM Plex Mono", monospace; font-size:11px; letter-spacing:.03em; text-transform:uppercase; white-space:nowrap;
}
.chip::before{content:""; width:6px; height:6px; border-radius:50%; background:currentColor; flex:none}
.chip-good{ background:var(--good-soft); color:var(--good) }
.chip-pending{ background:var(--pending-soft); color:var(--pending) }
.chip-stale{ background:var(--stale-soft); color:var(--stale) }
.chip-tier1{ background: color-mix(in srgb, var(--tier1) 16%, transparent); color:var(--tier1) }
.chip-tier2{ background: color-mix(in srgb, var(--tier2) 16%, transparent); color:var(--tier2) }
.chip-tier3{ background: color-mix(in srgb, var(--tier3) 16%, transparent); color:var(--tier3) }
.chip-tierna{ background: color-mix(in srgb, var(--tierna) 16%, transparent); color:var(--tierna) }

.snapshot{ padding: 18px 22px 4px }
.snap-header{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:8px 12px; margin-bottom:14px; }
.snap-header .value{font-family:"Fraunces",serif; font-size:16px; font-weight:600}
.snap-chips{display:flex; gap:6px; flex-wrap:wrap}

.headline-row{ display:grid; grid-template-columns: repeat(3, 1fr); gap:14px 12px; margin:0 0 10px; }
@media (max-width:560px){ .headline-row{grid-template-columns: 1fr} }
.tile dt{
  font-family:"IBM Plex Mono", monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--brass-strong); margin-bottom:7px; border-bottom:1px solid var(--line); padding-bottom:5px;
}
.tile dd{ margin:0 0 3px; display:flex; justify-content:space-between; align-items:baseline; gap:8px; font-size:13px; }
.tile dd span.k{color:var(--ink-soft)}
.tile dd b{font-weight:600}
.tile dd b.up{color:var(--good)}
.tile dd b.down{color:var(--stale)}
.tile .sub{font-size:10.5px; color:var(--ink-soft); font-weight:400}
.caveat{
  font-size:12px; color:var(--ink-soft); line-height:1.5; margin:2px 0 16px;
  padding:8px 10px; background:var(--pending-soft); border-radius:3px; border-left:2px solid var(--pending);
}
.secondary-row{ display:grid; grid-template-columns: repeat(2, 1fr); gap:12px; margin:0 0 18px; opacity:.86 }
.secondary-row .tile dt{font-size:10px}
.secondary-row .tile dd{font-size:12px}

.trend{ padding: 4px 22px 18px; border-bottom:1px solid var(--line) }
.trend-label{ font-family:"IBM Plex Mono", monospace; font-size:11px; color:var(--ink-soft); margin:0 0 18px; text-transform:uppercase; letter-spacing:.08em; }
.bars{ display:flex; align-items:flex-end; gap: 8px; height:76px; margin-top:20px; }
.bar-col{ flex:1 1 0; min-width:0; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; position:relative; }
.bar{
  width:100%; max-width:28px; border-radius:3px 3px 1px 1px; position:relative;
  transition: filter .15s ease;
}
.bar-col:hover .bar{ filter: brightness(1.12) }
.bar.tier1{ background: var(--tier1) }
.bar.tier2{ background: var(--tier2) }
.bar.tier3{ background: var(--tier3) }
.bar.tierna{ background: var(--tierna) }
.bar.parcial{
  opacity:.6;
  background-image: repeating-linear-gradient(45deg, rgba(0,0,0,.28) 0 4px, transparent 4px 8px);
}
.bar-label{
  position:absolute; bottom:100%; left:50%; transform:translateX(-50%); margin-bottom:5px;
  font-family:"IBM Plex Mono",monospace; font-size:10px; color:var(--ink-soft); white-space:nowrap;
}
.bar-col[data-tip]{ cursor:default }
.bar-col[data-tip]:hover::after{
  content: attr(data-tip); position:absolute; bottom:calc(100% + 20px); left:50%; transform:translateX(-50%);
  background:var(--ink); color:var(--paper); font-family:"IBM Plex Mono",monospace; font-size:11px;
  padding:6px 8px; border-radius:4px; white-space:nowrap; z-index:2; box-shadow:0 4px 14px rgba(0,0,0,.25);
}
.season-tick{ margin-top:8px; font-family:"IBM Plex Mono",monospace; font-size:10.5px; color:var(--ink-soft); text-align:center; }
.season-tick.atual{ color:var(--ink); font-weight:600 }
.trend-legend{
  display:flex; flex-wrap:wrap; gap:12px 16px; margin-top:16px; font-size:11px; color:var(--ink-soft);
  font-family:"IBM Plex Mono",monospace;
}
.trend-legend .sw{display:inline-flex; align-items:center; gap:5px}
.trend-legend .dot{width:9px;height:9px;border-radius:2px;display:inline-block}
.trend-legend .hatch{
  width:9px;height:9px;border-radius:2px;display:inline-block; background:var(--ink-soft);
  background-image: repeating-linear-gradient(45deg, rgba(255,255,255,.5) 0 2px, transparent 2px 4px);
}
.trend-foot{ font-size:11.5px; color:var(--ink-soft); margin-top:12px; line-height:1.5 }

.mercado{ padding: 18px 22px; border-bottom:1px solid var(--line); }
.mercado-head{display:flex; justify-content:space-between; align-items:baseline; margin-bottom:12px}
.mercado-head .label{font-family:"IBM Plex Mono",monospace; font-size:11px; text-transform:uppercase; letter-spacing:.1em; color:var(--ink-soft)}
.valor-mercado{font-family:"Fraunces",serif; font-size:22px; font-weight:600; color:var(--brass-strong)}
.valor-mercado .upd{font-family:"IBM Plex Mono",monospace; font-size:10.5px; color:var(--ink-soft); font-weight:400; margin-left:8px}
.mercado-grid{ display:grid; grid-template-columns: repeat(2, 1fr); gap:6px 18px; font-size:12.5px; margin-top:12px;}
.mercado-grid .row{display:flex; justify-content:space-between; gap:8px; border-bottom:1px dotted var(--line); padding-bottom:4px}
.mercado-grid .row span{color:var(--ink-soft)}
.mercado-grid .row b{font-weight:600; text-align:right}

.news{ padding: 18px 22px 22px; }
.news-head{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.news-head .label{font-family:"IBM Plex Mono",monospace; font-size:11px; text-transform:uppercase; letter-spacing:.1em; color:var(--ink-soft)}
.news h3{ font-size:16.5px; line-height:1.35; font-weight:600; margin:0 0 6px; }
.news p{ font-size:13.5px; line-height:1.55; color:var(--ink-soft); margin:0 0 10px; }
.news .src{ font-family:"IBM Plex Mono",monospace; font-size:11.5px; color:var(--ink-soft); }
.news .src a{text-decoration:none; border-bottom:1px dotted var(--line-strong)}
.news-empty{ font-size:13.5px; color:var(--ink-soft); line-height:1.5; }

.colophon{
  margin-top:40px; padding-top:22px; border-top:1px solid var(--line-strong);
  display:grid; grid-template-columns: repeat(3,1fr); gap:22px;
  font-size:12.5px; color:var(--ink-soft); line-height:1.55;
}
@media (max-width:760px){ .colophon{grid-template-columns:1fr} }
.colophon h4{
  font-family:"IBM Plex Mono",monospace; font-size:11px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--brass-strong); margin:0 0 8px; font-weight:600;
}
.colophon code{ font-family:"IBM Plex Mono",monospace; background:var(--brass-soft); padding:1px 5px; border-radius:3px; color:var(--ink) }
"""
FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;'
             '9..144,500;9..144,600;9..144,700&family=Source+Sans+3:wght@400;500;600;700&family=IBM+Plex+Mono:'
             'wght@400;500;600&display=swap">')


def _norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower().strip()


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
# Curadoria: saida/<jogador>.json -> estrutura enxuta pro template
# --------------------------------------------------------------------------

def season_rows(temporadas, temp):
    return [t for t in temporadas if t["temporada"] == temp]


def classify_tier(rows_this_season):
    for t in rows_this_season:
        if t["tipo_linha"] == "competicao" and _norm(t["competicao"]) in LEAGUE_TIERS:
            return LEAGUE_TIERS[_norm(t["competicao"])], t["competicao"]
    return None, None


def curar_jogador(data):
    temporadas = data["performance"]["temporadas"]
    if not temporadas:
        return None
    temp_atual = temporadas[0]["temporada"]
    rows_atual = season_rows(temporadas, temp_atual)
    tier, comp_liga = classify_tier(rows_atual)
    if not comp_liga:
        comp_liga = next((t["competicao"] for t in rows_atual if t["tipo_linha"] == "competicao"), None)

    snap = {}
    for t in rows_atual:
        if t["tipo_linha"] == "total_temporada" and t["categoria"] in CAT_MAP:
            snap[t["categoria"]] = {k: t["metricas"].get(k) for k in CAT_MAP[t["categoria"]]}

    vistos, ordem = {}, []
    for t in temporadas:
        if t["categoria"] == "Geral" and t["tipo_linha"] == "total_temporada" and t["temporada"] not in vistos:
            vistos[t["temporada"]] = t["metricas"]
            ordem.append(t["temporada"])
    ordem.reverse()
    trend = []
    for temp in ordem:
        m = vistos[temp]
        t_tier, _ = classify_tier(season_rows(temporadas, temp))
        mp = fnum(m.get("MP"))
        trend.append({
            "temporada": temp, "mp": m.get("MP"), "min": m.get("MIN"), "gls": m.get("GLS"),
            "ast": m.get("AST"), "asr": m.get("ASR"), "tier": t_tier or "sem-liga",
            "amostra_parcial": mp is not None and mp < 10,
        })

    return {
        "jogador": data["jogador"],
        "clube_atual": data.get("clube_atual"),
        "temporada_atual": temp_atual,
        "competicao_atual": comp_liga,
        "tier_atual": tier or "sem-liga",
        "snapshot": snap,
        "trend": trend,
        "mercado": data.get("mercado"),
        "noticias": data["noticias"],
    }


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def tile(title, rows):
    parts = []
    for k, v, cls, sub in rows:
        cls_attr = f" {cls}" if cls else ""
        sub_html = f'<span class="sub">{esc(sub)}</span>' if sub else ""
        parts.append(f'<dd><span class="k">{esc(k)}</span><b class="num{cls_attr}">{v}</b>{sub_html}</dd>')
    return f'<div class="tile"><dt>{esc(title)}</dt>{"".join(parts)}</div>'


def market_value_short(valor):
    if not valor or not valor.get("texto_original"):
        return "N/D", None
    texto = valor["texto_original"].split("Última")[0].split("ltima")[0].strip()
    return texto, valor.get("ultima_alteracao")


def bars_html(trend):
    vals = [float(t["min"]) if t["min"] not in (None, "-") else 0 for t in trend]
    vmax = max(vals) if vals and max(vals) > 0 else 1
    out = []
    for i, (t, v) in enumerate(zip(trend, vals)):
        pct = max(6, round(v / vmax * 100))
        tier_cls = TIER_CLASS.get(t["tier"], "tierna")
        parcial_cls = " parcial" if t["amostra_parcial"] else ""
        gls = t["gls"] if t["gls"] not in (None, "-") else "0"
        tip = (f'{esc(t["temporada"])} · {esc(t["min"])} min · {esc(t["mp"])} MP · '
               f'{esc(t["ast"])} assist · nota {esc(t.get("asr") or "N/D")}')
        atual_cls = " atual" if i == len(trend) - 1 else ""
        out.append(
            f'<div class="bar-col" data-tip="{tip}">'
            f'<div class="bar {tier_cls}{parcial_cls}" style="height:{pct}%">'
            f'<span class="bar-label">{esc(gls)}g</span></div>'
            f'<div class="season-tick{atual_cls}">{esc(t["temporada"])}</div></div>'
        )
    return "".join(out)


def trend_legend_html(trend):
    tiers_presentes = [t for t in TIER_ORDER if any(x["tier"] == t for x in trend)]
    sw = "".join(
        f'<span class="sw"><span class="dot" style="background:var(--{TIER_CLASS[t]})"></span>{esc(TIER_LABEL[t])}</span>'
        for t in tiers_presentes
    )
    if any(x["amostra_parcial"] for x in trend):
        sw += '<span class="sw"><span class="hatch"></span>amostra parcial (&lt;10 jogos)</span>'
    return sw


def news_html(noticias):
    itens = noticias.get("itens", [])
    if not itens:
        return '<div class="news-empty">Nenhuma notícia encontrada — nem dentro nem fora da janela de 15 dias.</div>'
    it = itens[0]
    if it.get("dentro_da_janela"):
        chip, head_label = f'<span class="chip chip-good">há {it["idade_dias"]} dias</span>', "Notícia recente"
    else:
        chip = f'<span class="chip chip-stale">há {it["idade_dias"]} dias</span>'
        head_label = "Sem notícia dentro da janela — mais próxima:"
    return (f'<div class="news-head"><span class="label">{esc(head_label)}</span>{chip}</div>'
            f'<h3>{esc(it["titulo"])}</h3><p>{esc(it["resumo"])}</p>'
            f'<div class="src"><a href="{esc(it["url"])}" target="_blank" rel="noopener">{esc(it.get("fonte",""))}</a>'
            f' · publicado em {esc(it["data_publicacao"])}</div>')


def mercado_html(m):
    if not m:
        return ('<div class="mercado"><div class="mercado-head"><span class="label">Mercado</span></div>'
                '<p class="news-empty">Sem dado de mercado/empresário nesta rodada.</p></div>')
    valor_txt, atualizado = market_value_short(m.get("valor_mercado"))
    contrato = (f'{m["contrato_inicio"] or "N/D"} → {m["contrato_fim"] or "N/D"}'
                if m.get("contrato_inicio") or m.get("contrato_fim") else "N/D")
    rows = [
        ("Posição (Transfermarkt)", nd(m.get("posicao"))),
        ("Pé preferido", nd(m.get("pe_preferido"))),
        ("Altura", f'{m["altura_m"]:.2f} m' if m.get("altura_m") else "N/D"),
        ("Idade", f'{m["idade"]} anos' if m.get("idade") else "N/D"),
        ("Empresário", nd(m.get("empresario"))),
        ("Contrato", contrato),
    ]
    grid = "".join(f'<div class="row"><span>{esc(k)}</span><b>{v}</b></div>' for k, v in rows)
    upd = f'atualizado em {esc(atualizado)}' if atualizado else ""
    return (f'<div class="mercado"><div class="mercado-head"><span class="label">Mercado · Transfermarkt</span></div>'
            f'<div class="valor-mercado">{esc(valor_txt)}<span class="upd">{upd}</span></div>'
            f'<div class="mercado-grid">{grid}</div></div>')


def player_card(p):
    snap = p["snapshot"]
    geral, fin, adc = snap.get("Geral", {}), snap.get("Finalização", {}), snap.get("Adicional", {})

    mp, minutos, gls = fnum(geral.get("MP")), fnum(geral.get("MIN")), fnum(geral.get("GLS"))
    gls_p90 = round(gls / minutos * 90, 2) if gls is not None and minutos else None
    tos, sot = fnum(fin.get("TOS")), fnum(fin.get("SOT"))
    precisao = round(sot / tos * 100) if sot is not None and tos else None
    xg = fnum(adc.get("XG"))
    delta_xg = round(gls - xg, 2) if gls is not None and xg is not None else None
    amostra_parcial = mp is not None and mp < 10

    headline = "".join([
        tile("Geral", [
            ("MP", nd(geral.get("MP")), None, None),
            ("MIN", nd(geral.get("MIN")), None, None),
            ("GLS", nd(geral.get("GLS")), None, f"({gls_p90:.2f}/90)" if gls_p90 is not None else None),
            ("AST", nd(geral.get("AST")), None, None),
        ]),
        tile("Finalização", [
            ("TOS", nd(fin.get("TOS")), None, None),
            ("SOT", nd(fin.get("SOT")), None, None),
            ("Precisão", f"{precisao}%" if precisao is not None else "N/D", None, None),
        ]),
        tile("xG (Adicional)", [
            ("xG", nd(adc.get("XG")), None, None),
            ("Gols−xG", f"{'+' if (delta_xg or 0) >= 0 else ''}{delta_xg}" if delta_xg is not None else "N/D",
             ("up" if (delta_xg or 0) >= 0 else "down") if delta_xg is not None else None, None),
            ("xA", nd(adc.get("XA")), None, None),
            ("Nota", nd(geral.get("ASR")), None, None),
        ]),
    ])

    caveat = ""
    if delta_xg is not None and amostra_parcial:
        sinal = "acima" if delta_xg >= 0 else "abaixo"
        caveat = (f'<p class="caveat">Gols−xG de {"+" if delta_xg>=0 else ""}{delta_xg} em {int(mp)} jogos é ruído '
                   f'estatístico ({sinal} do esperado), não sinal de eficiência — amostra pequena demais pra '
                   f'afirmar tendência.</p>')

    passe, defend = snap.get("Passe", {}), snap.get("Defendendo", {})
    secondary = (f'<div class="secondary-row">'
                 f'{tile("Passe", [("APS%", nd(passe.get("APS%")), None, None), ("CA%", nd(passe.get("CA%")), None, None)])}'
                 f'{tile("Defendendo", [("TACK", nd(defend.get("TACK")), None, None), ("INT", nd(defend.get("INT")), None, None), ("YC", nd(defend.get("YC")), None, None)])}'
                 f'</div>')

    tier_cls = TIER_CLASS.get(p["tier_atual"], "tierna")
    chips = f'<span class="chip chip-{tier_cls}">{esc(TIER_LABEL.get(p["tier_atual"], "sem liga"))}</span>'
    if amostra_parcial:
        chips += f'<span class="chip chip-pending">amostra parcial · {int(mp)} jogos</span>'

    clube = p.get("clube_atual") or (p["mercado"] or {}).get("clube_atual") or "clube não confirmado"
    return (
        f'<article class="card"><div class="card-head"><div class="card-id">'
        f'<h2>{esc(p["jogador"])}</h2>'
        f'<p class="club-line">{esc(clube)} · <span class="comp">{esc(p["competicao_atual"])}</span></p></div>'
        f'<span class="chip chip-good">performance validada</span></div>'
        f'<div class="snapshot"><div class="snap-header">'
        f'<span class="value">Temporada {esc(p["temporada_atual"])}</span>'
        f'<div class="snap-chips">{chips}</div></div>'
        f'<div class="headline-row">{headline}</div>{caveat}{secondary}</div>'
        f'<div class="trend"><p class="trend-label">Minutos por temporada</p>'
        f'<div class="bars">{bars_html(p["trend"])}</div>'
        f'<div class="trend-legend">{trend_legend_html(p["trend"])}</div>'
        f'<p class="trend-foot">Altura da barra = minutos jogados (escala própria do jogador). Número acima = '
        f'gols na temporada. Passe o cursor pra ver MP, assistências e nota média.</p></div>'
        f'{mercado_html(p["mercado"])}'
        f'<div class="news">{news_html(p["noticias"])}</div></article>'
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=Path(__file__).resolve().parent.parent / "saida")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--data-geracao", type=str, default=None)
    args = ap.parse_args()
    out = args.out or (args.saida / "dossie_preview.html")

    consolidado = json.loads((args.saida / "consolidado.json").read_text(encoding="utf-8"))
    curados = [c for c in (curar_jogador(d) for d in consolidado) if c is not None]
    ORDEM_SHORTLIST = ["André Clóvis", "Thiago Ocampo", "Thauan Lara", "Renê"]
    curados.sort(key=lambda c: ORDEM_SHORTLIST.index(c["jogador"]) if c["jogador"] in ORDEM_SHORTLIST else 99)

    cards = "".join(player_card(p) for p in curados)
    n_dias = curados[0]["noticias"]["janela_dias"] if curados else 15

    html = f"""<title>Dossiê de Observação</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
{FONT_LINK}
<style>{CSS}</style>

<div class="page">
  <header class="masthead">
    <div class="title-block">
      <span class="kicker">Scout individual · etapa 1</span>
      <h1>Dossiê de Observação</h1>
      <p class="dek">Performance (Sofascore) + mercado/empresário (Transfermarkt) + notícia recente da web, para a shortlist ativa. Ainda sem publicação — isso vem depois.</p>
    </div>
    <div class="meta-strip">
      <div class="row"><span>Gerado em</span><b>{esc(args.data_geracao or "-")}</b></div>
      <div class="row"><span>Janela de notícia</span><b>{n_dias} dias</b></div>
      <div class="row"><span>Jogadores</span><b>{len(curados)} validados</b></div>
    </div>
  </header>

  <section class="grid">{cards}</section>

  <footer class="colophon">
    <div>
      <h4>Metodologia</h4>
      <p>Junção Sofascore↔Transfermarkt por nome + alias manual (ver <code>NOME_ALIAS</code> em <code>etapa1_pipeline.py</code>) — ainda não é junção por ID real, aguardando aba <code>Jogadores</code> com <code>ID_Sofascore</code>/<code>ID_Transfermarkt</code>. Divisão de cada temporada é classificada pelo nome real da competição, nunca pelo rótulo "Total do Ano".</p>
    </div>
    <div>
      <h4>Leitura do gráfico</h4>
      <p>Cor da barra = divisão disputada naquela temporada. Hachura + opacidade reduzida = amostra pequena (menos de 10 jogos) — não tirar conclusão de eficiência (gols−xG, %) sobre essas temporadas.</p>
    </div>
    <div>
      <h4>Em aberto</h4>
      <p>Cadastro formal com IDs reais (aba <code>Jogadores</code>) e a etapa de publicação em HTML/GitHub Pages seguem pendentes por decisão do usuário.</p>
    </div>
  </footer>
</div>
"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
