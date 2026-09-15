#!/usr/bin/env python3
"""Etapa 1 (v2) do scout individual: le performance (Sofascore) + mercado
e empresario (Transfermarkt), e combina com noticias ja pesquisadas na
web. Nao gera HTML ainda -- ver README.md nesta pasta para o formato dos
arquivos de entrada/saida.

Formato real confirmado do export do Sofascore (uma linha = um "bloco"
de metricas de uma Categoria, para um Jogador+Ano_Temporada+Competicao):
    DataHora, Jogador, Categoria, Ano_Temporada, Competicao,
    Colunas_Metricas ("MP | MIN | GLS | AST | ASR"),
    Valores ("25 | 1788 | 4 | 3")
Quando Valores tem menos itens que Colunas_Metricas, os rotulos sem valor
correspondente sao a metrica que sumiu na exportacao. Um valor "-"
presente (contagem batendo) e uma proporcao indefinida do proprio
Sofascore (ex.: CA% quando ACR=0), nao um bug de exportacao.

Formato real confirmado do export do Transfermarkt (CSV sem cabecalho,
cada linha inteira entre aspas extras que precisam ser removidas antes
do parse -- ver _corrige_linha_bruta): 15 campos posicionais,
DataHora, Jogador, ID_Transfermarkt, Clube_Atual,
Valor_Mercado_Maximo_Texto (quase sempre vazio), Valor_Mercado_Texto
(inclui "Ultima alteracao: DD/MM/AAAA" embutido no mesmo campo),
Data_Nascimento_Idade, Naturalidade, Nacionalidade, Altura, Posicao, Pe,
Contrato_Inicio, Contrato_Fim, Empresario.

Junção por nome, nao por ID: ainda nao existe a aba `Jogadores` com
ID_Sofascore/ID_Transfermarkt reais, entao a junção entre as fontes usa
nome canonico com um pequeno mapa de apelidos (NOME_ALIAS) -- ja
confirmado com dado real que o Sofascore usa "Renê Sousa" e o
Transfermarkt usa "Renê" para o mesmo jogador. Isso e um paliativo
documentado, nao a junção por ID que o pipeline final deve usar.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ABA_JOGADORES = "Jogadores"
ABA_PERFORMANCE = "Performance_Sofascore"
ABA_PERFORMANCE_SEASON = "Performance_Season"
ABA_TRANSFERMARKT = "Transfermarkt"
ABA_LESOES = "Lesoes"
ABA_RUMORES = "Rumores"
JANELA_DIAS_NOTICIA = 15
# Confirmado com dado real (v1-final.md, prompt do usuario): categoria
# "Partidas" no export de Performance_Season e despejo bruto corrompido da
# pagina do Sofascore (concatena secoes inteiras num unico Colunas_Metricas/
# Valores gigante) -- nao e uma categoria real, sempre descartada.
CATEGORIA_DESCARTADA_SEASON = {"partidas"}
# Arquetipo por jogador -- do prompt "v1 completa" (tabela), NAO de uma
# coluna Jogadores.Arquetipo real ainda (essa aba nao existe). Trocar por
# leitura real assim que a planilha combinada chegar. Rene marcado como
# [Inferencia]: rotulo oficial Transfermarkt e "Ponta/Extremo" mas o volume
# de gols dele (~0.35-0.53 gols/90 dependendo da temporada) se parece mais
# com centroavante -- nao decidir silenciosamente, so documentar a duvida.
ARQUETIPOS = {
    "André Clóvis": {"arquetipo": "Centroavante", "fonte": "[Verificado] tabela do prompt"},
    "Thiago Ocampo": {"arquetipo": "Ponta/Extremo", "fonte": "[Verificado] tabela do prompt"},
    "Thauan Lara": {"arquetipo": "Lateral/Ala", "fonte": "[Verificado] tabela do prompt"},
    "Renê": {"arquetipo": "Ponta/Extremo", "fonte": "[Inferência] etiqueta oficial Transfermarkt; "
             "volume de gols sugere centroavante -- nao confirmado"},
}
TOTAL_ANO_LABEL = "total do ano"
# ASR faltou sistematicamente num export anterior (14/09) mas veio completo
# no export de 15/09 -- nao e um gap permanente do Sofascore, so algo a
# manter no radar. Mantido como aceito por seguranca: se um export futuro
# voltar a perder ASR isoladamente, isso nao trava a validacao, so fica
# documentado em metricas_faltantes/metricas_faltantes_aceitas.
METRICAS_GAP_ACEITO = {"asr"}
# Ver docstring do modulo: paliativo ate existir ID_Sofascore/ID_Transfermarkt
# real numa aba Jogadores.
NOME_ALIAS = {"rene sousa": "Renê"}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def _normaliza(texto) -> str:
    """minusculas, sem acento, sem espaco nas pontas -- para casar nomes
    de colunas/jogadores de forma tolerante a variacao de grafia."""
    if texto is None:
        return ""
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.lower()


def _acha_coluna(colunas, *aliases) -> str | None:
    normalizadas = {_normaliza(c): c for c in colunas}
    for alias in aliases:
        if alias in normalizadas:
            return normalizadas[alias]
    return None


def _vazio(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and pd.isna(valor):
        return True
    return str(valor).strip() == ""


def _nome_canonico(nome: str) -> str:
    """Aplica NOME_ALIAS (ex.: 'Renê Sousa' do Sofascore -> 'Renê' usado no
    resto do pipeline). Sem match, devolve o nome como veio."""
    return NOME_ALIAS.get(_normaliza(nome), nome.strip())


def _formata_valor(valor) -> str:
    """Evita que um Valor inteiro vire '30.0' so porque a coluna do Excel
    foi lida como float (acontece quando todas as linhas sao numericas)."""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


class Alerta:
    def __init__(self, nivel: str, jogador: str | None, mensagem: str):
        self.nivel = nivel  # "ERRO" | "ALERTA" | "INFO"
        self.jogador = jogador
        self.mensagem = mensagem

    def __str__(self) -> str:
        prefixo = f"[{self.nivel}]"
        if self.jogador:
            return f"{prefixo} {self.jogador}: {self.mensagem}"
        return f"{prefixo} {self.mensagem}"


# --------------------------------------------------------------------------
# Leitura da aba Jogadores (fonte da verdade da shortlist, quando disponivel)
# --------------------------------------------------------------------------

def ler_jogadores(planilha: dict[str, pd.DataFrame], alertas: list[Alerta]) -> list[dict] | None:
    if ABA_JOGADORES not in planilha:
        return None

    df = planilha[ABA_JOGADORES]
    col_jogador = _acha_coluna(df.columns, "jogador", "nome", "player", "atleta")
    col_clube = _acha_coluna(df.columns, "clube", "clube atual", "clube_atual", "club")
    col_comp = _acha_coluna(df.columns, "competicao", "competicao atual", "liga", "competition")

    if col_jogador is None:
        alertas.append(Alerta("ERRO", None,
            f"aba '{ABA_JOGADORES}' nao tem coluna de nome do jogador reconhecivel."))
        return None

    conhecidas = {c for c in (col_jogador, col_clube, col_comp) if c}
    jogadores = []
    for _, linha in df.iterrows():
        nome = linha.get(col_jogador)
        if _vazio(nome):
            continue
        extra = {c: linha[c] for c in df.columns if c not in conhecidas and not _vazio(linha[c])}
        jogadores.append({
            "jogador": str(nome).strip(),
            "clube_atual": None if col_clube is None or _vazio(linha.get(col_clube)) else str(linha[col_clube]).strip(),
            "competicao_principal": None if col_comp is None or _vazio(linha.get(col_comp)) else str(linha[col_comp]).strip(),
            "referencias": {k: (str(v).strip() if not isinstance(v, (int, float)) else v) for k, v in extra.items()},
        })
    return jogadores


# --------------------------------------------------------------------------
# Parsing do bloco de metricas de UMA linha (Colunas_Metricas / Valores)
# --------------------------------------------------------------------------

def _parse_bloco_metricas(colunas_metricas, valores) -> tuple[dict, list[str], int]:
    labels = [] if _vazio(colunas_metricas) else [t.strip() for t in str(colunas_metricas).split("|")]
    labels = [l for l in labels if l != ""]
    valores_lista = [] if _vazio(valores) else [t.strip() for t in str(valores).split("|")]

    metricas: dict[str, str] = {}
    faltantes: list[str] = []
    for i, label in enumerate(labels):
        if i < len(valores_lista):
            metricas[label] = valores_lista[i]
        else:
            faltantes.append(label)
    excedente = max(0, len(valores_lista) - len(labels))
    return metricas, faltantes, excedente


# --------------------------------------------------------------------------
# Leitura + validacao de Performance_Sofascore (xlsx ou CSV avulso)
# --------------------------------------------------------------------------

def ler_performance(df: pd.DataFrame, alertas: list[Alerta]) -> dict[str, list[dict]]:
    col_jogador = _acha_coluna(df.columns, "jogador", "nome", "player")
    col_temp = _acha_coluna(df.columns, "ano_temporada", "temporada", "season")
    col_comp = _acha_coluna(df.columns, "competicao", "competition")
    col_cat = _acha_coluna(df.columns, "categoria", "category")
    col_metricas = _acha_coluna(df.columns, "colunas_metricas", "metricas", "metrica", "metric")
    col_valores = _acha_coluna(df.columns, "valores", "valor", "value")
    col_data_coleta = _acha_coluna(df.columns, "datahora", "data_coleta", "data hora", "collected_at")

    faltando = [nome for nome, col in [
        ("Jogador", col_jogador), ("Ano_Temporada", col_temp), ("Competicao", col_comp),
        ("Categoria", col_cat), ("Colunas_Metricas", col_metricas), ("Valores", col_valores),
    ] if col is None]
    if faltando:
        alertas.append(Alerta("ERRO", None,
            f"'{ABA_PERFORMANCE}' esta sem a(s) coluna(s) esperada(s): {', '.join(faltando)}."))
        return {}

    resultado: dict[str, list[dict]] = {}
    aliases_aplicados: set[str] = set()
    for idx, linha in df.iterrows():
        jogador = linha.get(col_jogador)
        if _vazio(jogador):
            alertas.append(Alerta("ALERTA", None,
                f"'{ABA_PERFORMANCE}' linha {idx + 2}: sem nome de jogador, linha ignorada."))
            continue
        jogador_bruto = str(jogador).strip()
        jogador = _nome_canonico(jogador_bruto)
        if jogador != jogador_bruto and jogador_bruto not in aliases_aplicados:
            aliases_aplicados.add(jogador_bruto)
            alertas.append(Alerta("INFO", jogador,
                f"nome '{jogador_bruto}' do Sofascore resolvido para '{jogador}' via NOME_ALIAS "
                "(junção por nome, ainda sem ID_Sofascore real)."))
        temporada = None if _vazio(linha.get(col_temp)) else str(linha[col_temp]).strip()
        competicao_bruta = None if _vazio(linha.get(col_comp)) else str(linha[col_comp]).strip()
        categoria = None if _vazio(linha.get(col_cat)) else str(linha[col_cat]).strip()
        data_coleta = None if col_data_coleta is None or _vazio(linha.get(col_data_coleta)) else str(linha[col_data_coleta])

        metricas, faltantes, excedente = _parse_bloco_metricas(linha.get(col_metricas), linha.get(col_valores))
        metricas = {k: _formata_valor(v) for k, v in metricas.items()}

        if excedente:
            alertas.append(Alerta("ALERTA", jogador,
                f"{temporada} / {competicao_bruta} / {categoria}: 'Valores' tem {excedente} item(ns) a mais do "
                "que 'Colunas_Metricas' -- linha suspeita, confira a exportacao original."))

        faltantes_aceitos = [f for f in faltantes if _normaliza(f) in METRICAS_GAP_ACEITO]
        faltantes_relevantes = [f for f in faltantes if _normaliza(f) not in METRICAS_GAP_ACEITO]
        if faltantes_relevantes:
            alertas.append(Alerta("ALERTA", jogador,
                f"{temporada} / {competicao_bruta} / {categoria}: metrica(s) sem valor correspondente na "
                f"exportacao (rotulo presente, valor ausente) -> {', '.join(faltantes_relevantes)}. "
                "Nao descartado -- ver 'metricas_faltantes' no JSON de saida."))

        tipo_linha = "total_temporada" if competicao_bruta and _normaliza(competicao_bruta) == TOTAL_ANO_LABEL else "competicao"
        resultado.setdefault(jogador, []).append({
            "temporada": temporada,
            "competicao": competicao_bruta,
            "tipo_linha": tipo_linha,
            "categoria": categoria,
            "metricas": metricas,
            "metricas_faltantes": faltantes,
            "metricas_faltantes_aceitas": faltantes_aceitos,
            "completa": len(faltantes_relevantes) == 0,
            "data_coleta": data_coleta,
        })

    return resultado


def nota_jogador_ausente(nomes_shortlist: list[str], performance: dict[str, list[dict]], alertas: list[Alerta]):
    for nome in nomes_shortlist:
        if nome in performance:
            continue
        alertas.append(Alerta("ALERTA", nome,
            f"nao encontrado em '{ABA_PERFORMANCE}'. Verifique grafia do nome / NOME_ALIAS / se o export "
            "desse jogador ja foi feito."))


# --------------------------------------------------------------------------
# Leitura + validacao de Transfermarkt (mercado/empresario)
# --------------------------------------------------------------------------

TRANSFERMARKT_COLUNAS = [
    "data_coleta", "jogador", "id_transfermarkt", "clube_atual",
    "valor_mercado_maximo_texto", "valor_mercado_texto", "data_nascimento_idade",
    "naturalidade", "nacionalidade", "altura_texto", "posicao", "pe",
    "contrato_inicio", "contrato_fim", "empresario",
]

_RE_VALOR = re.compile(r"€\s*([\d.,]+)\s*(mi|mil)", re.IGNORECASE)
_RE_ULTIMA_ALT = re.compile(r"[UÚ]ltima altera[cç][aã]o:\s*(\d{2}/\d{2}/\d{4})")
_RE_IDADE = re.compile(r"\((\d+)\)\s*$")


def _corrige_linha_bruta(linha: str) -> str:
    """O export do Transfermarkt vem com a linha inteira entre aspas extras
    (uma unica 'celula' contendo virgulas internas) -- remove essas aspas
    e desfaz o escape de aspas duplicadas antes do csv.reader processar."""
    linha = linha.strip()
    if linha.startswith('"') and linha.endswith('"'):
        linha = linha[1:-1].replace('""', '"')
    return linha


def _parse_data_br(txt: str | None) -> str | None:
    if not txt:
        return None
    try:
        return datetime.strptime(txt.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _parse_valor_mercado(texto: str | None) -> dict:
    """'€2.50 mi. Última alteração: 24/06/2026' ->
    {texto_original, valor_eur, ultima_alteracao}."""
    if not texto or _vazio(texto):
        return {"texto_original": None, "valor_eur": None, "ultima_alteracao": None}
    m = _RE_VALOR.search(texto)
    valor_eur = None
    if m:
        # "2.50" ja vem com ponto decimal; "400" e inteiro sem separador de milhar.
        numero = float(m.group(1))
        mult = 1_000_000 if m.group(2).lower() == "mi" else 1_000
        valor_eur = round(numero * mult)
    m2 = _RE_ULTIMA_ALT.search(texto)
    return {
        "texto_original": texto.strip(),
        "valor_eur": valor_eur,
        "ultima_alteracao": _parse_data_br(m2.group(1)) if m2 else None,
    }


def ler_transfermarkt(caminho: Path, alertas: list[Alerta]) -> dict[str, dict]:
    linhas_corrigidas = [
        _corrige_linha_bruta(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    leitor = csv.reader(io.StringIO("\n".join(linhas_corrigidas)))

    resultado: dict[str, dict] = {}
    for n, campos in enumerate(leitor, start=1):
        if len(campos) != len(TRANSFERMARKT_COLUNAS):
            alertas.append(Alerta("ALERTA", None,
                f"'{ABA_TRANSFERMARKT}' linha {n}: {len(campos)} campos, esperado {len(TRANSFERMARKT_COLUNAS)} "
                "(schema posicional pode ter mudado) -- linha ignorada."))
            continue
        row = dict(zip(TRANSFERMARKT_COLUNAS, [c.strip() if c.strip() != "" else None for c in campos]))
        jogador_bruto = row["jogador"] or ""
        jogador = _nome_canonico(jogador_bruto)

        valor = _parse_valor_mercado(row["valor_mercado_texto"])
        valor_maximo = _parse_valor_mercado(row["valor_mercado_maximo_texto"])
        if valor["valor_eur"] is None:
            alertas.append(Alerta("ALERTA", jogador,
                f"'{ABA_TRANSFERMARKT}': Valor_Mercado_Texto ausente ou nao reconhecido ('{row['valor_mercado_texto']}')."))
        if row["valor_mercado_maximo_texto"] is None:
            alertas.append(Alerta("INFO", jogador,
                "'{}': Valor_Mercado_Maximo_Texto vazio -- esperado, sem fonte confirmada ainda.".format(ABA_TRANSFERMARKT)))
        if row["empresario"] is None:
            alertas.append(Alerta("ALERTA", jogador, f"'{ABA_TRANSFERMARKT}': Empresario ausente."))

        idade_m = _RE_IDADE.search(row["data_nascimento_idade"] or "")
        data_nasc_txt = re.sub(r"\s*\(\d+\)\s*$", "", row["data_nascimento_idade"] or "").strip() or None

        altura_m = None
        if row["altura_texto"]:
            m = re.search(r"([\d,]+)\s*m", row["altura_texto"])
            if m:
                altura_m = float(m.group(1).replace(",", "."))

        if jogador in resultado:
            alertas.append(Alerta("ALERTA", jogador,
                f"'{ABA_TRANSFERMARKT}': mais de uma linha para o mesmo jogador -- mantendo a ultima, confira duplicidade."))

        resultado[jogador] = {
            "id_transfermarkt": row["id_transfermarkt"],
            "clube_atual": row["clube_atual"],
            "valor_mercado": valor,
            "valor_mercado_maximo": valor_maximo,
            "data_nascimento": _parse_data_br(data_nasc_txt),
            "idade": int(idade_m.group(1)) if idade_m else None,
            "naturalidade": row["naturalidade"],
            "nacionalidade": row["nacionalidade"],
            "altura_m": altura_m,
            "posicao": row["posicao"],
            "pe_preferido": row["pe"],
            "contrato_inicio": _parse_data_br(row["contrato_inicio"]),
            "contrato_fim": _parse_data_br(row["contrato_fim"]),
            "empresario": row["empresario"],
            "data_coleta": row["data_coleta"],
        }
    return resultado


# --------------------------------------------------------------------------
# Leitura + validacao de Performance_Season (Sofascore, "por jogo", + radar)
# --------------------------------------------------------------------------

def ler_performance_season(df: pd.DataFrame, alertas: list[Alerta]) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    col_jogador = _acha_coluna(df.columns, "jogador", "nome", "player")
    col_temp = _acha_coluna(df.columns, "ano_temporada", "temporada", "season")
    col_comp = _acha_coluna(df.columns, "competicao", "competition")
    col_cat = _acha_coluna(df.columns, "categoria", "category")
    col_metricas = _acha_coluna(df.columns, "colunas_metricas", "metricas", "metrica", "metric")
    col_valores = _acha_coluna(df.columns, "valores", "valor", "value")
    col_data_coleta = _acha_coluna(df.columns, "datahora", "data_coleta", "data hora", "collected_at")
    col_att = _acha_coluna(df.columns, "att")
    col_tec = _acha_coluna(df.columns, "tec")
    col_tac = _acha_coluna(df.columns, "tac")
    col_def = _acha_coluna(df.columns, "def")
    col_cre = _acha_coluna(df.columns, "cre")

    faltando = [nome for nome, col in [
        ("Jogador", col_jogador), ("Ano_Temporada", col_temp), ("Competicao", col_comp),
        ("Categoria", col_cat), ("Colunas_Metricas", col_metricas), ("Valores", col_valores),
    ] if col is None]
    if faltando:
        alertas.append(Alerta("ERRO", None,
            f"'{ABA_PERFORMANCE_SEASON}' esta sem a(s) coluna(s) esperada(s): {', '.join(faltando)}."))
        return {}, {}

    resultado: dict[str, list[dict]] = {}
    radar: dict[str, dict] = {}
    descartadas_por_jogador: dict[str, int] = {}

    for idx, linha in df.iterrows():
        jogador = linha.get(col_jogador)
        if _vazio(jogador):
            alertas.append(Alerta("ALERTA", None,
                f"'{ABA_PERFORMANCE_SEASON}' linha {idx + 2}: sem nome de jogador, linha ignorada."))
            continue
        jogador = _nome_canonico(str(jogador).strip())
        temporada = None if _vazio(linha.get(col_temp)) else str(linha[col_temp]).strip()
        competicao_bruta = None if _vazio(linha.get(col_comp)) else str(linha[col_comp]).strip()
        categoria = None if _vazio(linha.get(col_cat)) else str(linha[col_cat]).strip()

        if categoria and _normaliza(categoria) in CATEGORIA_DESCARTADA_SEASON:
            descartadas_por_jogador[jogador] = descartadas_por_jogador.get(jogador, 0) + 1
            continue

        chave_radar = (jogador, temporada)
        if chave_radar not in radar and col_att:
            valores_radar = {k: linha.get(c) for k, c in [("ATT", col_att), ("TEC", col_tec), ("TAC", col_tac),
                                                            ("DEF", col_def), ("CRE", col_cre)]}
            if not any(_vazio(v) for v in valores_radar.values()):
                radar[f"{jogador}::{temporada}"] = {
                    "temporada": temporada,
                    **{k: _formata_valor(v) for k, v in valores_radar.items()},
                }

        data_coleta = None if col_data_coleta is None or _vazio(linha.get(col_data_coleta)) else str(linha[col_data_coleta])
        metricas, faltantes, excedente = _parse_bloco_metricas(linha.get(col_metricas), linha.get(col_valores))
        metricas = {k: _formata_valor(v) for k, v in metricas.items()}

        if excedente:
            alertas.append(Alerta("ALERTA", jogador,
                f"'{ABA_PERFORMANCE_SEASON}' {temporada} / {categoria}: 'Valores' tem {excedente} item(ns) a mais "
                "do que 'Colunas_Metricas' -- linha suspeita."))
        if faltantes:
            alertas.append(Alerta("ALERTA", jogador,
                f"'{ABA_PERFORMANCE_SEASON}' {temporada} / {categoria}: metrica(s) sem valor correspondente -> "
                f"{', '.join(faltantes)}."))

        resultado.setdefault(jogador, []).append({
            "temporada": temporada,
            "competicao": competicao_bruta,
            "categoria": categoria,
            "metricas": metricas,
            "metricas_faltantes": faltantes,
            "completa": len(faltantes) == 0,
            "data_coleta": data_coleta,
        })

    for jogador, n in descartadas_por_jogador.items():
        alertas.append(Alerta("INFO", jogador,
            f"'{ABA_PERFORMANCE_SEASON}': {n} linha(s) de categoria 'Partidas' descartada(s) por regra "
            "(despejo bruto corrompido, nao e categoria real)."))

    return resultado, radar


# --------------------------------------------------------------------------
# Leitura + validacao de Lesoes (Transfermarkt)
# --------------------------------------------------------------------------

def ler_lesoes(caminho: Path, alertas: list[Alerta], id_to_nome: dict[str, str]) -> dict[str, list[dict]]:
    df = pd.read_csv(caminho)
    col_id = _acha_coluna(df.columns, "id", "id_transfermarkt")
    col_nome = _acha_coluna(df.columns, "nome", "jogador")
    if col_id is None:
        alertas.append(Alerta("ERRO", None, f"'{ABA_LESOES}' sem coluna de ID reconhecivel."))
        return {}

    resultado: dict[str, list[dict]] = {}
    for idx, linha in df.iterrows():
        id_bruto = str(linha[col_id]).strip() if not _vazio(linha.get(col_id)) else None
        jogador = id_to_nome.get(id_bruto)
        if jogador is None:
            nome_bruto = str(linha[col_nome]).strip() if col_nome and not _vazio(linha.get(col_nome)) else "?"
            alertas.append(Alerta("ALERTA", None,
                f"'{ABA_LESOES}' linha {idx + 2} ({nome_bruto}, ID {id_bruto}): ID nao encontrado no registro "
                f"vindo de '{ABA_TRANSFERMARKT}' -- linha ignorada (junção por ID falhou)."))
            continue

        def campo(col):
            v = linha.get(col)
            return None if _vazio(v) or str(v).strip() == "-" else str(v).strip()

        lesao = campo("Lesao")
        resultado.setdefault(jogador, []).append({
            "temporada": campo("Temporada"),
            "lesao": lesao,
            "de": campo("De"),
            "ate": campo("Ate"),
            "dias": int(linha["Dias"]) if "Dias" in df.columns and not _vazio(linha.get("Dias")) else None,
            "jogos_perdidos": int(linha["Jogos_Perdidos"]) if "Jogos_Perdidos" in df.columns and not _vazio(linha.get("Jogos_Perdidos")) else None,
            "data_extracao": campo("Data_Extracao"),
        })
    return resultado


# --------------------------------------------------------------------------
# Leitura + validacao de Rumores (Transfermarkt)
# --------------------------------------------------------------------------

RUMORES_COLUNAS = ["data_coleta", "jogador", "id_transfermarkt", "clube_interessado",
                    "data_mencao", "data_atualizacao", "extra"]


def ler_rumores(caminho: Path, alertas: list[Alerta], id_to_nome: dict[str, str]) -> dict[str, list[dict]]:
    linhas = [l for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]
    leitor = csv.reader(linhas)
    resultado: dict[str, list[dict]] = {}
    for n, campos in enumerate(leitor, start=1):
        if len(campos) != len(RUMORES_COLUNAS):
            alertas.append(Alerta("ALERTA", None,
                f"'{ABA_RUMORES}' linha {n}: {len(campos)} campos, esperado {len(RUMORES_COLUNAS)} -- linha ignorada."))
            continue
        row = dict(zip(RUMORES_COLUNAS, [c.strip() for c in campos]))
        jogador = id_to_nome.get(row["id_transfermarkt"])
        if jogador is None:
            alertas.append(Alerta("ALERTA", None,
                f"'{ABA_RUMORES}' linha {n} ({row['jogador']}, ID {row['id_transfermarkt']}): ID nao encontrado "
                f"no registro vindo de '{ABA_TRANSFERMARKT}' -- linha ignorada (junção por ID falhou)."))
            continue
        resultado.setdefault(jogador, []).append({
            "clube_interessado": row["clube_interessado"],
            "data_mencao": _parse_data_br(row["data_mencao"]),
            "data_atualizacao": _parse_data_br(row["data_atualizacao"]),
            "data_coleta": row["data_coleta"],
        })
    return resultado


# --------------------------------------------------------------------------
# Noticias (resultado ja pesquisado na web, ver README)
# --------------------------------------------------------------------------

def carrega_noticias(caminho: Path, data_ref: date, alertas: list[Alerta]) -> dict[str, dict]:
    if not caminho.exists():
        alertas.append(Alerta("ALERTA", None,
            f"arquivo de noticias '{caminho}' nao encontrado -- todos os jogadores ficarao sem noticia."))
        return {}

    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    resultado = {}
    for jogador, itens in bruto.items():
        processados = []
        for item in itens:
            if "data_publicacao" not in item or _vazio(item.get("data_publicacao")):
                alertas.append(Alerta("ALERTA", jogador,
                    f"item de noticia sem data_publicacao ('{item.get('titulo', '???')}') -- descartado, "
                    "data de publicacao e obrigatoria."))
                continue
            data_pub = datetime.strptime(item["data_publicacao"], "%Y-%m-%d").date()
            idade_dias = (data_ref - data_pub).days
            processados.append({
                **item,
                "idade_dias": idade_dias,
                "dentro_da_janela": 0 <= idade_dias <= JANELA_DIAS_NOTICIA,
            })
        processados.sort(key=lambda i: i["idade_dias"])
        dentro = [i for i in processados if i["dentro_da_janela"]]
        if dentro:
            itens_finais = dentro
        elif processados:
            # nada dentro da janela: nao inventa nada, mas mantem o mais
            # proximo como contexto, com a idade real explicita.
            itens_finais = [processados[0]]
        else:
            itens_finais = []

        resultado[jogador] = {
            "janela_dias": JANELA_DIAS_NOTICIA,
            "data_referencia": data_ref.isoformat(),
            "encontrada_na_janela": len(dentro) > 0,
            "itens": itens_finais,
        }
    return resultado


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--planilha", type=Path,
                     default=Path("~/scout-individual/dados/scout_individual_dados.xlsx").expanduser(),
                     help="xlsx com abas Jogadores/Performance_Sofascore/... (formato final combinado)")
    ap.add_argument("--performance-csv", type=Path, default=None,
                     help="CSV avulso so com Performance_Sofascore (export direto), usado antes de termos o xlsx final combinado")
    ap.add_argument("--transfermarkt-csv", type=Path, default=None,
                     help="CSV avulso so com Transfermarkt (export direto, sem cabecalho), usado antes de termos o xlsx final combinado")
    ap.add_argument("--performance-season-csv", type=Path, default=None,
                     help="CSV avulso com Performance_Season (dado por jogo + radar ATT/TEC/TAC/DEF/CRE)")
    ap.add_argument("--lesoes-csv", type=Path, default=None, help="CSV avulso com Lesoes (Transfermarkt)")
    ap.add_argument("--rumores-csv", type=Path, default=None, help="CSV avulso com Rumores (Transfermarkt)")
    ap.add_argument("--noticias", type=Path,
                     default=Path(__file__).resolve().parent.parent / "dados" / "noticias_manual.json")
    ap.add_argument("--saida", type=Path,
                     default=Path(__file__).resolve().parent.parent / "saida")
    ap.add_argument("--data-referencia", type=str, default=None,
                     help="AAAA-MM-DD; default = hoje (usado para calcular a janela de 15 dias das noticias)")
    args = ap.parse_args()

    data_ref = date.fromisoformat(args.data_referencia) if args.data_referencia else date.today()
    alertas: list[Alerta] = []

    planilha: dict[str, pd.DataFrame] = {}
    if args.planilha.exists():
        planilha = pd.read_excel(args.planilha, sheet_name=None)
    elif args.performance_csv is None:
        print(f"[ERRO] nem a planilha ({args.planilha}) nem --performance-csv foram encontrados.")
        raise SystemExit(1)

    # fonte da performance: CSV avulso tem prioridade quando informado
    # (e o formato que estamos recebendo antes do xlsx final combinado).
    if args.performance_csv is not None:
        if not args.performance_csv.exists():
            print(f"[ERRO] --performance-csv nao encontrado: {args.performance_csv}")
            raise SystemExit(1)
        df_performance = pd.read_csv(args.performance_csv)
    elif ABA_PERFORMANCE in planilha:
        df_performance = planilha[ABA_PERFORMANCE]
    else:
        alertas.append(Alerta("ERRO", None,
            f"aba '{ABA_PERFORMANCE}' nao encontrada na planilha e nenhum --performance-csv foi passado."))
        df_performance = pd.DataFrame()

    performance = ler_performance(df_performance, alertas) if not df_performance.empty else {}

    mercado: dict[str, dict] = {}
    if args.transfermarkt_csv is not None:
        if not args.transfermarkt_csv.exists():
            print(f"[ERRO] --transfermarkt-csv nao encontrado: {args.transfermarkt_csv}")
            raise SystemExit(1)
        mercado = ler_transfermarkt(args.transfermarkt_csv, alertas)
    elif ABA_TRANSFERMARKT in planilha:
        alertas.append(Alerta("ALERTA", None,
            f"leitura de '{ABA_TRANSFERMARKT}' a partir do xlsx combinado ainda nao implementada -- "
            "use --transfermarkt-csv por enquanto."))

    # ID_Transfermarkt -> nome canonico: unica junção por ID real que da pra
    # fazer hoje (Transfermarkt/Lesoes/Rumores compartilham esse ID).
    # Sofascore continua sem ID nos exports recebidos, entao performance e
    # performance_season seguem usando NOME_ALIAS.
    id_to_nome = {v["id_transfermarkt"]: k for k, v in mercado.items() if v.get("id_transfermarkt")}

    performance_season: dict[str, list[dict]] = {}
    radar: dict[str, dict] = {}
    if args.performance_season_csv is not None:
        if not args.performance_season_csv.exists():
            print(f"[ERRO] --performance-season-csv nao encontrado: {args.performance_season_csv}")
            raise SystemExit(1)
        performance_season, radar = ler_performance_season(pd.read_csv(args.performance_season_csv), alertas)

    lesoes: dict[str, list[dict]] = {}
    if args.lesoes_csv is not None:
        if not args.lesoes_csv.exists():
            print(f"[ERRO] --lesoes-csv nao encontrado: {args.lesoes_csv}")
            raise SystemExit(1)
        lesoes = ler_lesoes(args.lesoes_csv, alertas, id_to_nome)

    rumores: dict[str, list[dict]] = {}
    if args.rumores_csv is not None:
        if not args.rumores_csv.exists():
            print(f"[ERRO] --rumores-csv nao encontrado: {args.rumores_csv}")
            raise SystemExit(1)
        rumores = ler_rumores(args.rumores_csv, alertas, id_to_nome)

    jogadores = ler_jogadores(planilha, alertas)
    if jogadores is None:
        # aba Jogadores ainda nao existe nesta rodada (ex.: so recebemos o
        # CSV do Sofascore) -- deriva a lista dos nomes que apareceram na
        # performance, sem inventar clube/competicao.
        alertas.append(Alerta("INFO", None,
            f"aba '{ABA_JOGADORES}' nao disponivel nesta rodada -- lista de jogadores derivada de "
            f"'{ABA_PERFORMANCE}' + '{ABA_TRANSFERMARKT}'. Clube/competicao ficarao em branco ate a "
            "planilha final combinada."))
        nomes_unificados = list(dict.fromkeys([*performance.keys(), *mercado.keys()]))
        jogadores = [{"jogador": nome, "clube_atual": None, "competicao_principal": None, "referencias": {}}
                     for nome in nomes_unificados]

    nomes = [j["jogador"] for j in jogadores]
    nota_jogador_ausente(nomes, performance, alertas)
    for nome in nomes:
        if nome not in mercado:
            alertas.append(Alerta("ALERTA", nome, f"nao encontrado em '{ABA_TRANSFERMARKT}'."))
        if args.lesoes_csv is not None and nome not in lesoes:
            alertas.append(Alerta("ALERTA", nome, f"nao encontrado em '{ABA_LESOES}'."))
        if args.rumores_csv is not None and nome not in rumores:
            alertas.append(Alerta("INFO", nome,
                f"nenhum registro em '{ABA_RUMORES}' -- resultado real (sem clube interessado registrado), "
                "nao e erro de leitura."))
        if nome not in ARQUETIPOS:
            alertas.append(Alerta("ALERTA", nome,
                "sem arquetipo definido em ARQUETIPOS -- metricas-chave por arquetipo nao poderao ser montadas."))
    noticias = carrega_noticias(args.noticias, data_ref, alertas)

    args.saida.mkdir(parents=True, exist_ok=True)
    consolidado = []
    for jog in jogadores:
        nome = jog["jogador"]
        temporadas = performance.get(nome, [])
        categorias_season = performance_season.get(nome, [])
        radar_jogador = [
            {"temporada": v["temporada"], "ATT": v["ATT"], "TEC": v["TEC"], "TAC": v["TAC"],
             "DEF": v["DEF"], "CRE": v["CRE"]}
            for chave, v in radar.items() if chave.startswith(f"{nome}::")
        ]
        arquetipo = ARQUETIPOS.get(nome)
        registro = {
            "jogador": nome,
            "clube_atual": jog["clube_atual"],
            "competicao_principal": jog["competicao_principal"],
            "arquetipo": {"valor": arquetipo["arquetipo"], "fonte": arquetipo["fonte"]} if arquetipo else None,
            "referencias": jog["referencias"],
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "performance": {
                "fonte_aba": ABA_PERFORMANCE,
                "encontrado_na_aba": len(temporadas) > 0,
                "temporadas": temporadas,
            },
            "performance_season": {
                "fonte_aba": ABA_PERFORMANCE_SEASON,
                "encontrado_na_aba": len(categorias_season) > 0,
                "categorias": categorias_season,
            },
            "radar": {
                "fonte": "[Verificado] índice proprietário Sofascore (ATT/TEC/TAC/DEF/CRE) -- "
                         "NAO e contagem direta de evento, nao misturar com metrica de contagem.",
                "temporadas": radar_jogador,
            } if radar_jogador else None,
            "mercado": mercado.get(nome),
            "lesoes": lesoes.get(nome, []),
            "rumores": {
                "itens": rumores.get(nome, []),
                "tem_rumor": nome in rumores and len(rumores[nome]) > 0,
                "fonte": "[Especulação] Transfermarkt -- clube interessado noticiado, nao negociacao confirmada.",
            },
            "noticias": noticias.get(nome, {
                "janela_dias": JANELA_DIAS_NOTICIA,
                "data_referencia": data_ref.isoformat(),
                "encontrada_na_janela": False,
                "itens": [],
            }),
        }
        consolidado.append(registro)
        nome_arquivo = re.sub(r"[^a-z0-9]+", "_", _normaliza(nome)).strip("_") + ".json"
        (args.saida / nome_arquivo).write_text(
            json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    (args.saida / "consolidado.json").write_text(
        json.dumps(consolidado, ensure_ascii=False, indent=2), encoding="utf-8")

    ordem_nivel = {"ERRO": 0, "ALERTA": 1, "INFO": 2}
    alertas.sort(key=lambda a: ordem_nivel.get(a.nivel, 9))
    linhas_relatorio = [str(a) for a in alertas]
    texto_relatorio = "\n".join(linhas_relatorio) if linhas_relatorio else "Nenhuma inconsistencia encontrada."
    (args.saida / "relatorio_validacao.txt").write_text(texto_relatorio + "\n", encoding="utf-8")

    fonte_desc = str(args.performance_csv) if args.performance_csv else str(args.planilha)
    print(f"Fonte de performance lida: {fonte_desc}")
    print(f"Jogadores no resultado (Performance_Sofascore + Transfermarkt): {len(jogadores)}")
    if args.performance_season_csv:
        print(f"Performance_Season: {sum(len(v) for v in performance_season.values())} linhas validas, "
              f"{len(radar)} combinacoes jogador+temporada com radar ATT/TEC/TAC/DEF/CRE, "
              f"{len(performance_season)} jogadores")
    if args.lesoes_csv:
        print(f"Lesoes: {sum(len(v) for v in lesoes.values())} registro(s), {len(lesoes)} jogadores")
    if args.rumores_csv:
        print(f"Rumores: {sum(len(v) for v in rumores.values())} registro(s), {len(rumores)} jogadores com rumor")
    print(f"Saida gravada em: {args.saida} (passo 2: JSON por jogador agora combina performance + "
          "performance_season + radar + mercado + lesoes + rumores + noticias)")
    print()
    print("=== Relatorio de validacao ===")
    print(texto_relatorio)


if __name__ == "__main__":
    main()
