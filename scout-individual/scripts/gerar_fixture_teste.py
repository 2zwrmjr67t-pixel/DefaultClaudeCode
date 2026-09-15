#!/usr/bin/env python3
"""Gera uma planilha .xlsx SINTETICA (numeros inventados) com a mesma
estrutura esperada de scout_individual_dados.xlsx, para testar
etapa1_pipeline.py sem depender da planilha real do usuario.

Bugs propositalmente inseridos, para provar que a validacao funciona:
- Andre Clovis / 2025-26 / Liga Portugal 2: falta a metrica ASR (a mesma
  que o usuario relatou ter sumido numa exportacao real do Sofascore).
- Thauan Lara: uma linha "Total do Ano" (agregado), alem da linha da
  competicao real -- para testar que o script nao trata isso como liga.
- Rene: propositalmente AUSENTE desta aba (comportamento esperado, fonte
  dele e FBref, fora do escopo desta etapa).
"""
from pathlib import Path

import pandas as pd

SAIDA = Path(__file__).resolve().parent.parent / "dados" / "_fixture_teste.xlsx"

jogadores = pd.DataFrame([
    {"Jogador": "André Clóvis", "Clube": "Académico de Viseu", "Competicao": "Liga Portugal Betclic",
     "Sofascore_ID": "TESTE-929680"},
    {"Jogador": "Thiago Ocampo", "Clube": "Nueva Chicago", "Competicao": "Primera Nacional",
     "Sofascore_ID": "TESTE-1801874"},
    {"Jogador": "Thauan Lara", "Clube": "Portimonense", "Competicao": "Liga Portugal 2",
     "Sofascore_ID": "TESTE-1312749"},
    {"Jogador": "Renê", "Clube": "Vitória", "Competicao": "Brasileirão Série A",
     "FBref_ID": "TESTE-comp24"},
])

# formato longo: uma metrica por linha. Grupo = Jogador+Temporada+Competicao+Categoria
linhas_performance = []


def add(jogador, temporada, competicao, categoria, metricas: dict, data_coleta="2026-09-01"):
    for metrica, valor in metricas.items():
        linhas_performance.append({
            "Jogador": jogador, "Temporada": temporada, "Competicao": competicao,
            "Categoria": categoria, "Metrica": metrica, "Valor": valor, "Data_Coleta": data_coleta,
        })


# André Clóvis: categoria "Geral" tem o conjunto completo MP|MIN|GLS|AST|ASR
# em uma temporada, mas na 2025/26 falta ASR (bug proposital).
add("André Clóvis", "2024/25", "Liga Portugal 2", "Geral",
    {"MP": "30", "MIN": "2450", "GLS": "15", "AST": "3", "ASR": "1.2"})
add("André Clóvis", "2025/26", "Liga Portugal 2", "Geral",
    {"MP": "34", "MIN": "2347", "GLS": "20", "AST": "5"})  # ASR sumiu de propósito

# Thiago Ocampo: normal, sem bug.
add("Thiago Ocampo", "2026", "Primera Nacional", "Geral",
    {"MP": "17", "MIN": "890", "GLS": "2", "AST": "3", "ASR": "0.6"})

# Thauan Lara: linha de competicao real + linha "Total do Ano" (agregado).
add("Thauan Lara", "2025/26", "Liga Portugal 2", "Geral",
    {"MP": "18", "MIN": "1150", "GLS": "1", "AST": "1", "ASR": "0.4"})
add("Thauan Lara", "2025/26", "Total do Ano", "Geral",
    {"MP": "21", "MIN": "1340", "GLS": "1", "AST": "1", "ASR": "0.5"})

# Rene: propositalmente sem nenhuma linha aqui.

performance = pd.DataFrame(linhas_performance)

with pd.ExcelWriter(SAIDA, engine="openpyxl") as writer:
    jogadores.to_excel(writer, sheet_name="Jogadores", index=False)
    performance.to_excel(writer, sheet_name="Performance_Sofascore", index=False)
    # abas fora do escopo desta etapa, mas presentes na planilha real -- so pra
    # garantir que o pipeline as ignora sem quebrar.
    pd.DataFrame([{"Jogador": "André Clóvis", "Nota": "aba fora de escopo nesta etapa"}]).to_excel(
        writer, sheet_name="Transfermarkt", index=False)
    pd.DataFrame([{"Jogador": "André Clóvis", "Nota": "cache manual opcional, fora de escopo nesta etapa"}]).to_excel(
        writer, sheet_name="Noticias", index=False)

print(f"Fixture de teste gravada em: {SAIDA}")
