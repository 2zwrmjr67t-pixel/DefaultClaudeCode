#!/usr/bin/env python3
"""Passo 3 do "Mapeamento do Celeiro de Ases": gera a pagina HTML a
partir de saida/consolidado.json (passo 2). So le e renderiza -- nao
busca nem recalcula validacao.

Duas telas, troca de estado local (sem rota/URL nova):
  1. Lista  -- chips de pais rolaveis + linhas compactas de jogador.
  2. Ficha  -- tela cheia, botao de voltar volta pro mesmo ponto de
     rolagem da lista. Resumo (bio + 3 KPIs universais) direto; o resto
     (metricas por arquetipo, radar, historico completo) atras do "+".

Sem mapa-mundi: decisao final do usuario, os chips de pais sao a
solucao definitiva, nao um paliativo.

Uso:
    python3 scripts/gerar_html.py
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
        ("xG", "xg_total"),
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
    # So o que a fonte realmente traz pra goleiro; defesas e gols sofridos
    # nao vem no export -- nao forcar metrica de linha aqui.
    "Goleiro": [
        ("Jogos sem sofrer gols", ("Defendendo", "Jogos sem sofrer gols")),
    ],
}
RADAR_EIXOS = ["ATT", "TEC", "TAC", "DEF", "CRE"]

# Status -> familia de cor da pilula. Vermelho de marca = ainda no clube;
# ambar = atencao (sem clube); neutro = egresso (a maioria).
STATUS_TOM = {
    "Ainda no Internacional": "marca",
    "Ainda na base (U17)": "marca",
    "Sem clube": "warn",
    "Egresso": "neutro",
    "Aposentado": "neutro",
}
# Badge_Atividade da planilha (ja calculado, nunca recalculado aqui).
BADGE_TOM = {"🟢": "good", "🟡": "warn", "🔴": "bad"}

ICONE_VOLTAR = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>')
ICONE_SETA = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="m9 18 6-6-6-6"/></svg>')
ICONE_MAIS = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M12 5v14"/><path d="M5 12h14"/></svg>')
ICONE_MENOS = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
               '<path d="M5 12h14"/></svg>')

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

.radar-wrap{ display:flex; flex-direction:column; align-items:center }
.radar-wrap svg{ width:100%; max-width:320px; height:auto }
.radar-nota{ font-size:11.5px; color:var(--ink-3); text-align:center; margin:8px 0 0; line-height:1.5; max-width:46ch }

details.completo{ margin-top:14px }
details.completo > summary{
  list-style:none; cursor:pointer; display:flex; align-items:center; gap:9px;
  background:var(--card); border:1px solid var(--line); border-radius:12px; padding:15px 20px;
  font-size:14px; font-weight:600; color:var(--ink);
}
details.completo > summary::-webkit-details-marker{ display:none }
details.completo > summary:hover{ border-color:var(--line-2) }
details.completo > summary svg{ font-size:16px; color:var(--ink-3) }
details.completo[open] > summary{ border-bottom-left-radius:0; border-bottom-right-radius:0; border-bottom-color:transparent }
details.completo:not([open]) .ico-menos{ display:none }
details.completo[open] .ico-mais{ display:none }
.completo-corpo > .card:first-child{ border-top-left-radius:0; border-top-right-radius:0; border-top:none; margin-top:0 }

table.tabela{ width:100%; border-collapse:collapse; font-size:14px }
table.tabela th, table.tabela td{ text-align:left; padding:9px 8px; border-bottom:1px solid var(--line) }
table.tabela th{ font-size:11.5px; font-weight:600; color:var(--ink-3); text-transform:uppercase; letter-spacing:.04em }
table.tabela td.n{ text-align:right; font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums }
table.tabela tr:last-child td{ border-bottom:none }
table.tabela tr.total td{ font-weight:600 }
.tabela-wrap{ overflow-x:auto }
.bloco-cat + .bloco-cat{ margin-top:16px }
.bloco-cat h4{ font-size:13px; margin-bottom:6px }
ul.limites{ margin:0; padding-left:17px; font-size:13.5px; color:var(--ink-2); line-height:1.6 }
ul.limites li + li{ margin-top:5px }

footer.rodape{ margin-top:28px; font-size:12px; color:var(--ink-3); line-height:1.6 }
footer.rodape b{ font-weight:600; color:var(--ink-2) }
"""

FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">')


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def esc(s):
    return "" if s is None else str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slugify(nome: str) -> str:
    ascii_nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_nome.lower()).strip("-")


def iniciais(nome: str) -> str:
    partes = [p for p in re.split(r"\s+", nome.strip()) if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def nd(v):
    return '<span class="vazio">–</span>' if v is None or v in ("-", "") else esc(v)


def fnum(v):
    if v in (None, "-", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def par(label, valor_html, numerico=True):
    cls = "val num" if numerico else "val"
    return f'<div class="par"><span class="lbl">{esc(label)}</span><span class="{cls}">{valor_html}</span></div>'


def pilula(texto, tom="neutro", com_ponto=False):
    ponto = '<span class="ponto"></span>' if com_ponto else ""
    return f'<span class="pilula p-{tom}">{ponto}{esc(texto)}</span>'


# --------------------------------------------------------------------------
# Metricas
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
# Radar
# --------------------------------------------------------------------------

def radar_svg(valores: dict, largura=320, altura=250):
    cx, cy = largura / 2, altura / 2
    raio = min(largura, altura) * 0.30
    n = len(RADAR_EIXOS)

    aneis = []
    for frac in (0.33, 0.66, 1.0):
        pts = " ".join(f"{cx + raio * frac * math.cos(-math.pi/2 + i*2*math.pi/n):.1f},"
                        f"{cy + raio * frac * math.sin(-math.pi/2 + i*2*math.pi/n):.1f}" for i in range(n))
        aneis.append(f'<polygon points="{pts}" fill="none" stroke="var(--line)" stroke-width="1"/>')

    eixos = []
    for i in range(n):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        eixos.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx + raio*math.cos(ang):.1f}" '
                     f'y2="{cy + raio*math.sin(ang):.1f}" stroke="var(--line)" stroke-width="1"/>')

    pontos = []
    for i, eixo in enumerate(RADAR_EIXOS):
        v = max(0, min(100, fnum(valores.get(eixo)) or 0))
        ang = -math.pi / 2 + i * 2 * math.pi / n
        frac = v / 100
        pontos.append(f"{cx + raio*frac*math.cos(ang):.1f},{cy + raio*frac*math.sin(ang):.1f}")

    rotulos = []
    for i, eixo in enumerate(RADAR_EIXOS):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        lx, ly = cx + (raio + 22) * math.cos(ang), cy + (raio + 22) * math.sin(ang)
        anchor = "middle"
        if math.cos(ang) > 0.3:
            anchor = "start"
        elif math.cos(ang) < -0.3:
            anchor = "end"
        rotulos.append(
            f'<text x="{lx:.1f}" y="{ly - 6:.1f}" text-anchor="{anchor}" font-family="Source Sans 3,sans-serif" '
            f'font-size="11" fill="var(--ink-3)">{esc(eixo)}</text>'
            f'<text x="{lx:.1f}" y="{ly + 9:.1f}" text-anchor="{anchor}" font-family="IBM Plex Mono,monospace" '
            f'font-size="13" font-weight="600" fill="var(--ink)">{esc(valores.get(eixo))}</text>'
        )

    return (f'<svg viewBox="0 0 {largura} {altura}" role="img" aria-label="Radar de atributos Sofascore">'
            f'{"".join(aneis)}{"".join(eixos)}'
            f'<polygon points="{" ".join(pontos)}" fill="var(--radar-fill)" stroke="var(--radar-stroke)" stroke-width="2"/>'
            f'{"".join(rotulos)}</svg>')


# --------------------------------------------------------------------------
# Blocos da ficha
# --------------------------------------------------------------------------

def _data_br(iso):
    if not iso:
        return None
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def card_bio(p):
    itens = [
        par("Idade", nd(p.get("idade"))),
        par("Altura (cm)", nd((p.get("altura") or "").replace(" cm", "").strip() or None)),
        par("Pé", nd(p.get("pe_preferido")), numerico=False),
        par("Posição", nd(p.get("posicao")), numerico=False),
        par("Camisa", nd(p.get("numero_camisa"))),
        par("Contrato até", nd(_data_br(p.get("contrato_ate")))),
    ]
    return f'<div class="card"><div class="card-titulo">Bio</div><div class="grade-bio">{"".join(itens)}</div></div>'


def card_kpis(p):
    badge = p.get("badge_atividade") or ""
    tom = BADGE_TOM.get(badge, "neutro")
    jogos_3a = p.get("jogos_ultimos_3_anos")
    nivel = {"good": ("Alta", "60 jogos ou mais"), "warn": ("Média", "entre 20 e 59 jogos"),
             "bad": ("Baixa", "menos de 20 jogos")}.get(tom)
    extra = (f'<div class="kpi-extra" title="Atividade {esc(nivel[1])} nos últimos 3 anos">'
             f'{pilula(nivel[0], tom, com_ponto=True)}</div>') if nivel else ""

    vm = (p.get("valor_mercado") or {}).get("texto_original")
    valor_html = esc(vm) if vm else pilula("N/D", "neutro")

    kpis = (
        f'<div class="par"><span class="lbl">Jogos na temporada</span>'
        f'<span class="val">{nd(p.get("jogos_temporada_atual"))}</span></div>'
        f'<div class="par"><span class="lbl">Jogos (últimos 3 anos)</span>'
        f'<span class="val">{nd(jogos_3a)}</span>{extra}</div>'
        f'<div class="par"><span class="lbl">Valor de mercado</span>'
        f'<span class="val">{valor_html}</span></div>'
    )
    return f'<div class="card"><div class="card-titulo">Números</div><div class="grade-kpi">{kpis}</div></div>'


def card_metricas_arquetipo(p):
    arquetipo = p.get("arquetipo")
    specs = ARQUETIPO_METRICAS.get(arquetipo)
    blocos = p["performance_season"]["blocos"]

    if not specs:
        nota = "Sem perfil de métricas-chave definido para esta posição."
        titulo = f"Métricas-chave · {esc(arquetipo)}" if arquetipo else "Métricas-chave"
        return f'<div class="card"><div class="card-titulo">{titulo}</div><p class="nota-limite">{nota}</p></div>'

    resumo = resumo_temporada_atual(blocos)
    itens = "".join(
        par(l, nd(v), numerico=not (isinstance(v, str) and any(c.isalpha() for c in v)))
        for l, v in (resolve_metrica(s, blocos, resumo) for s in specs)
    )
    comp = blocos[0]["competicao"] if blocos else None
    jogos = resumo["jogos"]
    # A ressalva do xG so faz sentido pro arquetipo que tem xG na tabela.
    nota_xg = " xG é total da temporada, não por 90." if any(s[1] == "xg_total" for s in specs) else ""
    amostra = (f"{int(jogos)} {'jogo' if int(jogos) == 1 else 'jogos'} em {comp}, temporada atual.{nota_xg}"
               if jogos is not None and comp else f"Temporada atual.{nota_xg}")
    if not blocos:
        amostra = "Sem dados da temporada atual na fonte."
    if arquetipo == "Goleiro":
        amostra += (" Defesas e gols sofridos não vêm na fonte — por isso o perfil de goleiro é mais curto "
                    "que os de linha.")
    return (f'<div class="card"><div class="card-titulo">Métricas-chave · {esc(arquetipo)}</div>'
            f'<div class="grade-metricas">{itens}</div>'
            f'<p class="nota-limite" style="margin-top:14px">{esc(amostra)}</p></div>')


def card_radar(p):
    radar = p.get("radar")
    if not radar:
        return ('<div class="card"><div class="card-titulo">Índice Sofascore</div>'
                '<p class="nota-limite">Sem radar de atributos nesta rodada — ausência real (sem clube, sem volume '
                'mínimo de minutos, ou ainda no U17), não falha de captura.</p></div>')
    valores = {e: radar.get(e) for e in RADAR_EIXOS}
    return (f'<div class="card"><div class="card-titulo">Índice Sofascore</div>'
            f'<div class="radar-wrap">{radar_svg(valores)}'
            f'<p class="radar-nota">Composto proprietário do Sofascore (0–100). Não é contagem direta de evento — '
            f'não comparar com as métricas-chave como se fosse a mesma escala.</p></div></div>')


def tabela_carreira(blocos):
    vistos, ordem = {}, []
    for b in blocos:
        if b["categoria"] != "Geral":
            continue
        chave = (b["temporada"], b["competicao"])
        if chave not in vistos:
            vistos[chave] = b
            ordem.append(chave)
    linhas = []
    for chave in ordem:
        b = vistos[chave]
        m = b["metricas"]
        cls = ' class="total"' if b.get("tipo_linha") == "total_temporada" else ""
        linhas.append(
            f'<tr{cls}><td>{esc(chave[0])}</td><td>{esc(chave[1])}</td>'
            f'<td class="n">{nd(m.get("MP"))}</td><td class="n">{nd(m.get("MIN"))}</td>'
            f'<td class="n">{nd(m.get("GLS"))}</td><td class="n">{nd(m.get("AST"))}</td>'
            f'<td class="n">{nd(m.get("ASR"))}</td></tr>'
        )
    return (f'<div class="tabela-wrap"><table class="tabela"><thead><tr>'
            f'<th>Temporada</th><th>Competição</th><th>MP</th><th>MIN</th><th>Gols</th><th>Ast.</th><th>Nota</th>'
            f'</tr></thead><tbody>{"".join(linhas)}</tbody></table></div>')


def tabela_categorias(blocos):
    vistas = []
    for b in blocos:
        if b["categoria"] not in vistas:
            vistas.append(b["categoria"])
    partes = []
    for cat in vistas:
        b = next(x for x in blocos if x["categoria"] == cat)
        linhas = "".join(f'<tr><td>{esc(k)}</td><td class="n">{nd(v)}</td></tr>' for k, v in b["metricas"].items())
        partes.append(f'<div class="bloco-cat"><h4>{esc(cat)}</h4>'
                      f'<div class="tabela-wrap"><table class="tabela"><tbody>{linhas}</tbody></table></div></div>')
    return "".join(partes)


def card_limitacoes(p):
    itens = []
    if p.get("pais_clube"):
        itens.append("<b>País do clube</b> é [Inferência] — derivado do nome do clube, não confirmado na fonte.")
    else:
        itens.append("<b>Sem país associado</b> — jogador sem clube no momento; aparece na lista, mas fora dos "
                     "filtros de país.")
    if not p.get("radar"):
        itens.append("<b>Sem radar de atributos</b> — ausência real (sem clube, sem volume mínimo de minutos, ou "
                     "ainda no U17), não falha de captura.")
    if p.get("arquetipo") == "Goleiro":
        itens.append("<b>Goleiro</b> — a fonte não traz defesas nem gols sofridos; as categorias capturadas "
                     "são pensadas para jogador de linha.")
    if not p["performance_season"]["blocos"]:
        itens.append("<b>Sem dados da temporada atual</b> — jogador ausente da aba Performance_Season.")
    if not (p.get("valor_mercado") or {}).get("valor_eur"):
        itens.append("<b>Valor de mercado N/D</b> — campo vazio na fonte, não omitido.")
    if (p.get("agente") or "").strip() == "Desconhecido":
        itens.append("<b>Agente</b> consta como “Desconhecido” na fonte.")
    return ('<div class="card"><div class="card-titulo">Limitações desta ficha</div>'
            f'<ul class="limites">{"".join(f"<li>{i}</li>" for i in itens)}</ul></div>')


def ficha(p):
    slug = slugify(p["jogador"])
    status = p.get("status") or "Egresso"
    pais = (p.get("pais_clube") or {}).get("valor")
    clube = p.get("clube_atual") or "Sem clube"
    sub = f"{clube} · {pais}" if pais else clube
    blocos_season = p["performance_season"]["blocos"]

    completo = (
        card_metricas_arquetipo(p)
        + card_radar(p)
        + f'<div class="card"><div class="card-titulo">Histórico de carreira</div>{tabela_carreira(p["performance_carreira"]["blocos"])}</div>'
        + f'<div class="card"><div class="card-titulo">Temporada atual por categoria</div>{tabela_categorias(blocos_season)}</div>'
        + card_limitacoes(p)
    )

    return f'''<article class="ficha" id="f-{slug}" hidden>
  <button type="button" class="btn-voltar" data-voltar>{ICONE_VOLTAR}Voltar</button>
  <div class="ficha-head">
    <span class="avatar avatar-lg">{esc(iniciais(p["jogador"]))}</span>
    <div class="ficha-id">
      <h2>{esc(p["jogador"])}</h2>
      <p class="sub">{esc(sub)}</p>
    </div>
    {pilula(status, STATUS_TOM.get(status, "neutro"))}
  </div>
  {card_bio(p)}
  {card_kpis(p)}
  <details class="completo">
    <summary><span class="ico-mais">{ICONE_MAIS}</span><span class="ico-menos">{ICONE_MENOS}</span>Ver completo — métricas do arquétipo, radar e histórico</summary>
    <div class="completo-corpo">{completo}</div>
  </details>
</article>'''


def linha_lista(p):
    slug = slugify(p["jogador"])
    pais = (p.get("pais_clube") or {}).get("valor")
    clube = p.get("clube_atual") or "Sem clube"
    sub = f"{clube} · {pais}" if pais else clube
    badge = p.get("badge_atividade") or ""
    tom = BADGE_TOM.get(badge, "neutro")
    jogos = p.get("jogos_ultimos_3_anos")
    pill = pilula(str(jogos) if jogos is not None else "–", tom, com_ponto=True)
    filtro = slugify(pais) if pais else slugify(p.get("status") or "sem-clube")
    return (f'<li data-pais="{filtro}"><button type="button" class="linha" data-slug="{slug}">'
            f'<span class="avatar">{esc(iniciais(p["jogador"]))}</span>'
            f'<span class="linha-info"><span class="linha-nome">{esc(p["jogador"])}</span>'
            f'<span class="linha-sub">{esc(sub)}</span></span>'
            f'{pill}<span class="seta">{ICONE_SETA}</span></button></li>')


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=Path(__file__).resolve().parent.parent / "saida")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (args.saida / "celeiro_de_ases.html")

    jogadores = json.loads((args.saida / "consolidado.json").read_text(encoding="utf-8"))
    jogadores.sort(key=lambda p: slugify(p["jogador"]))

    contagem: dict[str, int] = {}
    sem_pais: dict[str, int] = {}
    for p in jogadores:
        pais = (p.get("pais_clube") or {}).get("valor")
        if pais:
            contagem[pais] = contagem.get(pais, 0) + 1
        else:
            st = p.get("status") or "Sem clube"
            sem_pais[st] = sem_pais.get(st, 0) + 1

    chips = [f'<button type="button" class="chip ativo" data-filtro="todos">Todos <span class="n">{len(jogadores)}</span></button>']
    for pais, n in sorted(contagem.items(), key=lambda x: (-x[1], x[0])):
        chips.append(f'<button type="button" class="chip" data-filtro="{slugify(pais)}">{esc(pais)} '
                     f'<span class="n">{n}</span></button>')
    for st, n in sorted(sem_pais.items(), key=lambda x: (-x[1], x[0])):
        chips.append(f'<button type="button" class="chip" data-filtro="{slugify(st)}">{esc(st)} '
                     f'<span class="n">{n}</span></button>')

    linhas = "".join(linha_lista(p) for p in jogadores)
    fichas = "".join(ficha(p) for p in jogadores)

    html = f"""<title>Mapeamento do Celeiro de Ases</title>
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
        <span class="kicker">Projeto Futebol • Celeiro de Ases</span>
        <h1>Mapeamento do Celeiro de Ases</h1>
      </div>
      <div class="chips-wrap"><nav class="chips" aria-label="Filtrar por país">{"".join(chips)}</nav></div>
    </div>
  </header>
  <div class="conteudo">
  <div class="card lista-card" style="padding:6px 16px">
    <ul class="lista" id="lista">{linhas}</ul>
    <p class="lista-vazia" id="lista-vazia" hidden>Nenhum jogador neste filtro.</p>
  </div>
  <footer class="rodape">
    <p>Fonte única: <b>celeiro_de_ases_dados.xlsx</b> — abas Jogadores, Performance_Carreira e Performance_Season, já reconciliadas antes de chegar aqui. Categoria “Partidas” descartada; “Total do Ano” é agregado, não liga. Sem lesões e sem Transfermarkt nesta versão, por escopo.</p>
  </footer>
  </div>
</section>

<section id="tela-ficha" hidden><div class="conteudo ficha-conteudo">{fichas}</div></section>

<script>
(function(){{
  var telaLista = document.getElementById('tela-lista');
  var telaFicha = document.getElementById('tela-ficha');
  var lista = document.getElementById('lista');
  var listaVazia = document.getElementById('lista-vazia');
  var chips = document.querySelectorAll('.chip');
  var fichas = telaFicha.querySelectorAll('.ficha');
  var rolagemLista = 0;

  function abrir(slug){{
    rolagemLista = window.scrollY;
    fichas.forEach(function(f){{ f.hidden = f.id !== ('f-' + slug); }});
    telaLista.hidden = true;
    telaFicha.hidden = false;
    window.scrollTo(0, 0);
  }}

  function voltar(){{
    telaFicha.hidden = true;
    telaLista.hidden = false;
    fichas.forEach(function(f){{ f.hidden = true; }});
    window.scrollTo(0, rolagemLista);
  }}

  function filtrar(valor){{
    var visiveis = 0;
    lista.querySelectorAll('li').forEach(function(li){{
      var ok = valor === 'todos' || li.dataset.pais === valor;
      li.hidden = !ok;
      if (ok) visiveis++;
    }});
    listaVazia.hidden = visiveis > 0;
  }}

  lista.querySelectorAll('.linha').forEach(function(btn){{
    btn.addEventListener('click', function(){{ abrir(btn.dataset.slug); }});
  }});
  telaFicha.querySelectorAll('[data-voltar]').forEach(function(btn){{
    btn.addEventListener('click', voltar);
  }});
  chips.forEach(function(chip){{
    chip.addEventListener('click', function(){{
      chips.forEach(function(c){{ c.classList.toggle('ativo', c === chip); }});
      filtrar(chip.dataset.filtro);
      window.scrollTo(0, 0);
    }});
  }});
  document.addEventListener('keydown', function(e){{
    if (e.key === 'Escape' && !telaFicha.hidden) voltar();
  }});
}})();
</script>
"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes, {len(jogadores)} jogadores)")


if __name__ == "__main__":
    main()
