#!/usr/bin/env python3
"""Etapa 1 do scout individual: le a planilha local, valida
Performance_Sofascore e combina com noticias ja pesquisadas na web.

Nao gera HTML, nao busca dados de mercado/empresario -- isso fica para
etapas futuras. Ver README.md nesta pasta para o formato dos arquivos
de entrada/saida.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
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

def _normaliza(texto: str) -> str:
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


def _formata_valor(valor) -> str:
    """Evita que um Valor inteiro vire '30.0' so porque a coluna do Excel
    foi lida como float (acontece quando todas as linhas sao numericas)."""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _vazio(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and pd.isna(valor):
        return True
    if pd.isna(valor) if not isinstance(valor, (list, dict)) else False:
        return True
    return str(valor).strip() == ""


# --------------------------------------------------------------------------
# Leitura da aba Jogadores (fonte da verdade da shortlist)
# --------------------------------------------------------------------------

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


def ler_jogadores(planilha: dict[str, pd.DataFrame], alertas: list[Alerta]) -> list[dict]:
    if ABA_JOGADORES not in planilha:
        alertas.append(Alerta("ERRO", None, f"aba '{ABA_JOGADORES}' nao encontrada na planilha."))
        return []

    df = planilha[ABA_JOGADORES]
    col_jogador = _acha_coluna(df.columns, "jogador", "nome", "player", "atleta")
    col_clube = _acha_coluna(df.columns, "clube", "clube atual", "clube_atual", "club")
    col_comp = _acha_coluna(df.columns, "competicao", "competicao atual", "liga", "competition")

    if col_jogador is None:
        alertas.append(Alerta("ERRO", None,
            f"aba '{ABA_JOGADORES}' nao tem coluna de nome do jogador reconhecivel."))
        return []

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
# Leitura + validacao da aba Performance_Sofascore
# --------------------------------------------------------------------------

def ler_performance(planilha: dict[str, pd.DataFrame], nomes_shortlist: list[str],
                     alertas: list[Alerta]) -> dict[str, list[dict]]:
    """Retorna {jogador: [linhas de temporada/competicao]}."""
    if ABA_PERFORMANCE not in planilha:
        alertas.append(Alerta("ERRO", None, f"aba '{ABA_PERFORMANCE}' nao encontrada na planilha."))
        return {}

    df = planilha[ABA_PERFORMANCE]
    col_jogador = _acha_coluna(df.columns, "jogador", "nome", "player")
    col_temp = _acha_coluna(df.columns, "temporada", "season")
    col_comp = _acha_coluna(df.columns, "competicao", "competition")
    col_cat = _acha_coluna(df.columns, "categoria", "category")
    col_metrica = _acha_coluna(df.columns, "metrica", "métrica", "metric")
    col_valor = _acha_coluna(df.columns, "valor", "value")
    col_data_coleta = _acha_coluna(df.columns, "data_coleta", "data coleta", "collected_at")

    faltando = [nome for nome, col in [
        ("Jogador", col_jogador), ("Temporada", col_temp), ("Competicao", col_comp),
        ("Categoria", col_cat), ("Metrica", col_metrica), ("Valor", col_valor),
    ] if col is None]
    if faltando:
        alertas.append(Alerta("ERRO", None,
            f"aba '{ABA_PERFORMANCE}' esta sem a(s) coluna(s) esperada(s): {', '.join(faltando)}."))
        return {}

    # 1a passada: monta o conjunto de rotulos "esperados" por categoria,
    # olhando a planilha inteira -- isso e o que permite detectar uma
    # metrica que sumiu por completo de um grupo (ex.: ASR na exportacao
    # de um jogador/temporada especifico), nao so um Valor vazio.
    rotulos_por_categoria: dict[str, set[str]] = defaultdict(set)
    for _, linha in df.iterrows():
        categoria = linha.get(col_cat)
        metrica = linha.get(col_metrica)
        if _vazio(categoria) or _vazio(metrica):
            continue
        rotulos_por_categoria[str(categoria).strip()].add(str(metrica).strip())

    # 2a passada: agrupa por Jogador+Temporada+Competicao+Categoria
    grupos: dict[tuple, dict] = {}
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
        metrica = None if _vazio(linha.get(col_metrica)) else str(linha[col_metrica]).strip()
        valor = linha.get(col_valor)
        data_coleta = None if col_data_coleta is None or _vazio(linha.get(col_data_coleta)) else str(linha[col_data_coleta])

        chave = (jogador, temporada, competicao_bruta, categoria)
        if chave not in grupos:
            tipo_linha = "total_temporada" if competicao_bruta and _normaliza(competicao_bruta) == TOTAL_ANO_LABEL else "competicao"
            grupos[chave] = {
                "temporada": temporada,
                "competicao": competicao_bruta,
                "tipo_linha": tipo_linha,
                "categoria": categoria,
                "metricas": {},
                "data_coleta": data_coleta,
            }

        if metrica is None:
            continue
        if _vazio(valor):
            alertas.append(Alerta("ALERTA", jogador,
                f"{temporada} / {competicao_bruta} / {categoria}: metrica '{metrica}' aparece na planilha mas sem Valor preenchido."))
            continue
        grupos[chave]["metricas"][metrica] = _formata_valor(valor)

    # calcula metricas_faltantes por grupo comparando com o esperado da categoria
    resultado: dict[str, list[dict]] = defaultdict(list)
    for (jogador, temporada, competicao_bruta, categoria), grupo in grupos.items():
        esperado = rotulos_por_categoria.get(categoria or "", set())
        presentes = set(grupo["metricas"].keys())
        faltantes = sorted(esperado - presentes)
        grupo["metricas_faltantes"] = faltantes
        grupo["completa"] = len(faltantes) == 0
        if faltantes:
            alertas.append(Alerta("ALERTA", jogador,
                f"{temporada} / {competicao_bruta} / {categoria}: metrica(s) presente(s) em outras linhas da mesma "
                f"categoria mas ausente(s) aqui -> {', '.join(faltantes)}. Nao descartado -- ver JSON de saida."))
        resultado[jogador].append(grupo)

    # jogadores da shortlist sem nenhuma linha na aba
    presentes_na_aba = set(resultado.keys())
    for nome in nomes_shortlist:
        if nome not in presentes_na_aba:
            if _normaliza(nome) == "rene":
                alertas.append(Alerta("INFO", nome,
                    f"nao encontrado em '{ABA_PERFORMANCE}' -- esperado, fonte de performance dele e FBref "
                    "(comp ID 24), fora do escopo desta etapa."))
            else:
                alertas.append(Alerta("ALERTA", nome,
                    f"nao encontrado em '{ABA_PERFORMANCE}'. Verifique grafia do nome na aba '{ABA_JOGADORES}' "
                    "vs. na aba de performance."))

    # caso Rene apareca mesmo assim, so um aviso informativo (nao e erro)
    for nome in presentes_na_aba:
        if _normaliza(nome) == "rene":
            alertas.append(Alerta("INFO", nome,
                f"apareceu em '{ABA_PERFORMANCE}' -- inesperado (fonte dele deveria ser FBref), "
                "mas nao tratado como erro; dado incluido no JSON."))

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
                     default=Path("~/scout-individual/dados/scout_individual_dados.xlsx").expanduser())
    ap.add_argument("--noticias", type=Path,
                     default=Path(__file__).resolve().parent.parent / "dados" / "noticias_manual.json")
    ap.add_argument("--saida", type=Path,
                     default=Path(__file__).resolve().parent.parent / "saida")
    ap.add_argument("--data-referencia", type=str, default=None,
                     help="AAAA-MM-DD; default = hoje (usado para calcular a janela de 15 dias das noticias)")
    args = ap.parse_args()

    data_ref = date.fromisoformat(args.data_referencia) if args.data_referencia else date.today()
    alertas: list[Alerta] = []

    if not args.planilha.exists():
        print(f"[ERRO] planilha nao encontrada em: {args.planilha}")
        raise SystemExit(1)

    planilha = pd.read_excel(args.planilha, sheet_name=None)
    jogadores = ler_jogadores(planilha, alertas)
    nomes = [j["jogador"] for j in jogadores]
    performance = ler_performance(planilha, nomes, alertas)
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

    print(f"Planilha lida: {args.planilha}")
    print(f"Jogadores na shortlist (aba '{ABA_JOGADORES}'): {len(jogadores)}")
    print(f"Saida gravada em: {args.saida}")
    print()
    print("=== Relatorio de validacao ===")
    print(texto_relatorio)


if __name__ == "__main__":
    main()
