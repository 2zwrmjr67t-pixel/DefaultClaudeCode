#!/usr/bin/env python3
"""Etapa 1 do scout individual: le performance (planilha/CSV local do
Sofascore) e combina com noticias ja pesquisadas na web.

Nao gera HTML, nao busca dados de mercado/empresario -- isso fica para
etapas futuras. Ver README.md nesta pasta para o formato dos arquivos
de entrada/saida.

Formato real confirmado do export do Sofascore (uma linha = um "bloco"
de metricas de uma Categoria, para um Jogador+Ano_Temporada+Competicao):
    DataHora, Jogador, Categoria, Ano_Temporada, Competicao,
    Colunas_Metricas ("MP | MIN | GLS | AST | ASR"),
    Valores ("25 | 1788 | 4 | 3")
Quando Valores tem menos itens que Colunas_Metricas, os rotulos sem valor
correspondente (da direita para a esquerda, na ordem em que aparecem) sao
a metrica que sumiu na exportacao -- e o bug real que o Sofascore comete
de vez em quando. Um valor "-" presente (contagem batendo) e uma
proporcao indefinida do proprio Sofascore (ex.: CA% quando ACR=0), nao um
bug de exportacao.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ABA_JOGADORES = "Jogadores"
ABA_PERFORMANCE = "Performance_Sofascore"
JANELA_DIAS_NOTICIA = 15
TOTAL_ANO_LABEL = "total do ano"


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
    for idx, linha in df.iterrows():
        jogador = linha.get(col_jogador)
        if _vazio(jogador):
            alertas.append(Alerta("ALERTA", None,
                f"'{ABA_PERFORMANCE}' linha {idx + 2}: sem nome de jogador, linha ignorada."))
            continue
        jogador = str(jogador).strip()
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

        if faltantes:
            alertas.append(Alerta("ALERTA", jogador,
                f"{temporada} / {competicao_bruta} / {categoria}: metrica(s) sem valor correspondente na "
                f"exportacao (rotulo presente, valor ausente) -> {', '.join(faltantes)}. "
                "Nao descartado -- ver 'metricas_faltantes' no JSON de saida."))

        tipo_linha = "total_temporada" if competicao_bruta and _normaliza(competicao_bruta) == TOTAL_ANO_LABEL else "competicao"
        resultado.setdefault(jogador, []).append({
            "temporada": temporada,
            "competicao": competicao_bruta,
            "tipo_linha": tipo_linha,
            "categoria": categoria,
            "metricas": metricas,
            "metricas_faltantes": faltantes,
            "completa": len(faltantes) == 0,
            "data_coleta": data_coleta,
        })

    for jogador, linhas in resultado.items():
        if _normaliza(jogador) == "rene":
            alertas.append(Alerta("INFO", jogador,
                f"apareceu em '{ABA_PERFORMANCE}' -- inesperado (fonte dele deveria ser FBref), "
                "mas nao tratado como erro; dado incluido no JSON."))

    return resultado


def nota_rene_ausente(nomes_shortlist: list[str], performance: dict[str, list[dict]], alertas: list[Alerta]):
    for nome in nomes_shortlist:
        if nome in performance:
            continue
        if _normaliza(nome) == "rene":
            alertas.append(Alerta("INFO", nome,
                f"nao encontrado em '{ABA_PERFORMANCE}' -- esperado, fonte de performance dele e FBref "
                "(comp ID 24), fora do escopo desta etapa."))
        else:
            alertas.append(Alerta("ALERTA", nome,
                f"nao encontrado em '{ABA_PERFORMANCE}'. Verifique grafia do nome / se o export desse "
                "jogador ja foi feito."))


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

    jogadores = ler_jogadores(planilha, alertas)
    if jogadores is None:
        # aba Jogadores ainda nao existe nesta rodada (ex.: so recebemos o
        # CSV do Sofascore) -- deriva a lista dos nomes que apareceram na
        # performance, sem inventar clube/competicao.
        alertas.append(Alerta("INFO", None,
            f"aba '{ABA_JOGADORES}' nao disponivel nesta rodada -- lista de jogadores derivada de "
            f"'{ABA_PERFORMANCE}'. Clube/competicao ficarao em branco ate a planilha final combinada."))
        jogadores = [{"jogador": nome, "clube_atual": None, "competicao_principal": None, "referencias": {}}
                     for nome in performance.keys()]

    nomes = [j["jogador"] for j in jogadores]
    nota_rene_ausente(nomes, performance, alertas)
    noticias = carrega_noticias(args.noticias, data_ref, alertas)

    args.saida.mkdir(parents=True, exist_ok=True)
    consolidado = []
    for jog in jogadores:
        nome = jog["jogador"]
        temporadas = performance.get(nome, [])
        registro = {
            "jogador": nome,
            "clube_atual": jog["clube_atual"],
            "competicao_principal": jog["competicao_principal"],
            "referencias": jog["referencias"],
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "performance": {
                "fonte_aba": ABA_PERFORMANCE,
                "encontrado_na_aba": len(temporadas) > 0,
                "temporadas": temporadas,
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
    print(f"Jogadores no resultado: {len(jogadores)}")
    print(f"Saida gravada em: {args.saida}")
    print()
    print("=== Relatorio de validacao ===")
    print(texto_relatorio)


if __name__ == "__main__":
    main()
