#!/usr/bin/env python3
"""Passo 1 do "Mapeamento do Celeiro de Ases": le e valida
celeiro_de_ases_dados.xlsx (3 abas: Jogadores, Performance_Carreira,
Performance_Season). So le e valida -- NAO monta JSON combinado ainda
(isso e o passo 2). Ver dados/prompt-claude-code-celeiro-de-ases.md.

Formato confirmado das 3 abas (diferente do Scout Individual: aqui e
"formato longo" de verdade, uma linha = um metrica so, nao um bloco
pipe-delimitado):
    Jogadores: Nome, SofascoreID, Clube_Atual, Pais_Clube, Posicao,
        Arquetipo, Status, Nacionalidade, Data_Nascimento_Idade, Altura,
        Pe, Numero_Camisa, Valor_Mercado, Agente, Contrato_Ate,
        Jogos_ultimos_3_anos, Badge_Atividade, ATT, TEC, TAC, DEF, CRE
    Performance_Carreira / Performance_Season: Jogador, Temporada,
        Competicao, Categoria, Metrica, Valor

Junção já feita manualmente antes deste arquivo chegar (prompt do
usuário é explícito: "não refaça a junção de dados") -- os 34 nomes
batem exatamente entre as 3 abas, confirmado nesta rodada. Este script
só valida e reporta, não decide nada silenciosamente.

Cada uma das 3 abas termina com 1 linha em branco + 1 linha de nota do
autor da planilha (ex.: "Pais_Clube é [Inferência]..." na aba
Jogadores) -- não são dado real, descartadas por regra (linha sem
SofascoreID / sem Jogador).
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

CATEGORIA_DESCARTADA = {"partidas"}
TOTAL_ANO_LABEL = "total do ano"

MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
_RE_DATA_PT = re.compile(
    r"(\d{1,2})\s*de\s*([a-zçãáéíóúâêô]+)\.?\s*de\s*(\d{4})(?:\s*\((\d+)\))?", re.IGNORECASE
)
_RE_VALOR_KM = re.compile(r"([\d.,]+)\s*(K|M)\s*€", re.IGNORECASE)


def _normaliza(texto) -> str:
    if texto is None:
        return ""
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.lower()


def _vazio(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return str(v).strip() == ""


def _fmt(v):
    """Evita '19.0' quando a celula do Excel foi lida como float, e evita
    que celula vazia (NaN do pandas) vire a string literal 'nan'."""
    if _vazio(v):
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _parse_data_pt(texto: str | None) -> tuple[str | None, int | None]:
    """'31 de março de 1998 (28)' -> ('1998-03-31', 28).
    Aceita mes abreviado com ponto ('nov.') ou por extenso ('março')."""
    if not texto:
        return None, None
    m = _RE_DATA_PT.search(str(texto))
    if not m:
        return None, None
    dia, mes_txt, ano, idade = m.groups()
    mes_key = _normaliza(mes_txt)[:3]
    mes = MESES.get(mes_key)
    if mes is None:
        return None, int(idade) if idade else None
    try:
        iso = date(int(ano), mes, int(dia)).isoformat()
    except ValueError:
        return None, int(idade) if idade else None
    return iso, int(idade) if idade else None


def _parse_valor_mercado(texto: str | None) -> dict:
    """'420K €' / '2.2M €' -> {texto_original, valor_eur}."""
    if not texto or _vazio(texto):
        return {"texto_original": None, "valor_eur": None}
    m = _RE_VALOR_KM.search(str(texto))
    valor_eur = None
    if m:
        numero = float(m.group(1).replace(",", "."))
        mult = 1_000_000 if m.group(2).upper() == "M" else 1_000
        valor_eur = round(numero * mult)
    return {"texto_original": str(texto).strip(), "valor_eur": valor_eur}


class Alerta:
    def __init__(self, nivel: str, jogador: str | None, mensagem: str):
        self.nivel = nivel  # "ERRO" | "ALERTA" | "INFO"
        self.jogador = jogador
        self.mensagem = mensagem

    def __str__(self) -> str:
        prefixo = f"[{self.nivel}]"
        return f"{prefixo} {self.jogador}: {self.mensagem}" if self.jogador else f"{prefixo} {self.mensagem}"


# --------------------------------------------------------------------------
# Aba Jogadores
# --------------------------------------------------------------------------

def ler_jogadores(df: pd.DataFrame, alertas: list[Alerta]) -> list[dict]:
    resultado = []
    vistos: set[str] = set()
    for idx, linha in df.iterrows():
        # Linhas de nota/rodape da planilha nao tem SofascoreID -- descarte
        # estrutural, mesma logica da categoria "Partidas" no resto do
        # pipeline (despejo que nao e dado real).
        if _vazio(linha.get("SofascoreID")):
            if not _vazio(linha.get("Nome")):
                alertas.append(Alerta("INFO", None,
                    f"'Jogadores' linha {idx + 2}: sem SofascoreID (provavel nota de rodape da planilha, nao "
                    f"jogador) -- descartada. Conteudo: '{str(linha.get('Nome'))[:80]}'"))
            continue

        nome = str(linha["Nome"]).strip()
        if nome in vistos:
            alertas.append(Alerta("ALERTA", nome, "'Jogadores': nome duplicado na aba -- confira."))
        vistos.add(nome)

        pais_clube = None if _vazio(linha.get("Pais_Clube")) else str(linha["Pais_Clube"]).strip()
        if pais_clube is None:
            alertas.append(Alerta("INFO", nome,
                "sem Pais_Clube -- sem pais associado (estado esperado, nao erro: jogador sem clube no "
                "momento). Sinalizar explicitamente na pagina, nao omitir da lista."))

        status = None if _vazio(linha.get("Status")) else str(linha["Status"]).strip()
        arquetipo = None if _vazio(linha.get("Arquetipo")) else str(linha["Arquetipo"]).strip()
        if arquetipo is None:
            alertas.append(Alerta("ALERTA", nome, "sem Arquetipo -- metricas-chave nao poderao ser montadas."))

        radar_campos = ["ATT", "TEC", "TAC", "DEF", "CRE"]
        radar_valores = {c: _fmt(linha.get(c)) for c in radar_campos}
        tem_radar = all(v is not None for v in radar_valores.values())
        if not tem_radar and any(v is not None for v in radar_valores.values()):
            alertas.append(Alerta("ALERTA", nome,
                f"radar parcial -- alguns eixos ATT/TEC/TAC/DEF/CRE preenchidos e outros nao ({radar_valores}). "
                "Esperado era tudo-ou-nada."))
        if not tem_radar:
            alertas.append(Alerta("INFO", nome,
                "sem radar Sofascore (ATT/TEC/TAC/DEF/CRE) -- ausencia real (sem clube, sem volume minimo de "
                "minutos, ou ainda no U17), nao erro de captura."))

        nasc_iso, idade = _parse_data_pt(linha.get("Data_Nascimento_Idade"))
        if nasc_iso is None and not _vazio(linha.get("Data_Nascimento_Idade")):
            alertas.append(Alerta("ALERTA", nome,
                f"Data_Nascimento_Idade nao reconhecida: '{linha.get('Data_Nascimento_Idade')}'."))

        contrato_iso, _ = _parse_data_pt(linha.get("Contrato_Ate"))
        if contrato_iso is None and not _vazio(linha.get("Contrato_Ate")):
            alertas.append(Alerta("ALERTA", nome, f"Contrato_Ate nao reconhecido: '{linha.get('Contrato_Ate')}'."))

        valor_mercado = _parse_valor_mercado(linha.get("Valor_Mercado"))
        if _vazio(linha.get("Valor_Mercado")):
            alertas.append(Alerta("INFO", nome, "sem Valor_Mercado no Transfermarkt (campo vazio na fonte)."))
        elif valor_mercado["valor_eur"] is None:
            alertas.append(Alerta("ALERTA", nome,
                f"Valor_Mercado presente mas nao reconhecido: '{linha.get('Valor_Mercado')}'."))

        if nome == "Kauan":
            alertas.append(Alerta("INFO", nome,
                "unico goleiro da base -- categorias capturadas (Atacando/Passe/Defendendo) sao voltadas a "
                "jogador de linha, sem defesas/gols sofridos/clean sheets. Card estruturalmente mais magro, "
                "sinalizar explicitamente na pagina dele, nao como falha de captura."))

        def _inteiro(col):
            if _vazio(linha.get(col)):
                return None
            try:
                return int(float(linha[col]))
            except (TypeError, ValueError):
                alertas.append(Alerta("ALERTA", nome, f"{col} nao numerico: '{linha.get(col)}'."))
                return None

        jogos_3anos = _inteiro("Jogos_ultimos_3_anos")
        jogos_temporada = _inteiro("Jogos_Temporada_Atual")
        if "Jogos_Temporada_Atual" in df.columns and _vazio(linha.get("Jogos_Temporada_Atual")):
            alertas.append(Alerta("INFO", nome, "sem Jogos_Temporada_Atual na planilha (campo vazio na fonte)."))

        resultado.append({
            "jogador": nome,
            "sofascore_id": str(linha["SofascoreID"]).strip(),
            "clube_atual": None if _vazio(linha.get("Clube_Atual")) else str(linha["Clube_Atual"]).strip(),
            "pais_clube": {"valor": pais_clube, "fonte": "[Inferência] derivado do nome do clube -- conferir "
                           "antes de publicar"} if pais_clube else None,
            "posicao": None if _vazio(linha.get("Posicao")) else str(linha["Posicao"]).strip(),
            "arquetipo": arquetipo,
            "status": status,
            "nacionalidade": None if _vazio(linha.get("Nacionalidade")) else str(linha["Nacionalidade"]).strip(),
            "data_nascimento": nasc_iso,
            "idade": idade,
            "altura": None if _vazio(linha.get("Altura")) else str(linha["Altura"]).strip(),
            "pe_preferido": None if _vazio(linha.get("Pe")) else str(linha["Pe"]).strip(),
            "numero_camisa": _fmt(linha.get("Numero_Camisa")),
            "valor_mercado": valor_mercado,
            "agente": None if _vazio(linha.get("Agente")) else str(linha["Agente"]).strip(),
            "contrato_ate": contrato_iso,
            "jogos_temporada_atual": jogos_temporada,
            "jogos_ultimos_3_anos": jogos_3anos,
            "badge_atividade": None if _vazio(linha.get("Badge_Atividade")) else str(linha["Badge_Atividade"]).strip(),
            "radar": {
                "fonte": "[Verificado] índice proprietário Sofascore (ATT/TEC/TAC/DEF/CRE) -- NAO é contagem "
                         "direta de evento.",
                **{k: v for k, v in radar_valores.items()},
            } if tem_radar else None,
        })
    return resultado


# --------------------------------------------------------------------------
# Abas Performance_Carreira / Performance_Season (formato longo)
# --------------------------------------------------------------------------

def ler_performance_longa(df: pd.DataFrame, nome_aba: str, alertas: list[Alerta],
                           nomes_esperados: set[str]) -> dict[str, list[dict]]:
    linhas_validas = 0
    descartadas_categoria: dict[str, int] = {}
    agrupado: dict[tuple, dict] = {}
    ordem: list[tuple] = []

    for idx, linha in df.iterrows():
        jogador = linha.get("Jogador")
        temporada = None if _vazio(linha.get("Temporada")) else str(linha["Temporada"]).strip()
        competicao = None if _vazio(linha.get("Competicao")) else str(linha["Competicao"]).strip()
        categoria = None if _vazio(linha.get("Categoria")) else str(linha["Categoria"]).strip()
        metrica = None if _vazio(linha.get("Metrica")) else str(linha["Metrica"]).strip()
        valor = linha.get("Valor")

        # Linha em branco (Jogador vazio) ou nota de rodape da planilha
        # (Jogador tem texto, mas as demais colunas todas vazias -- mesmo
        # padrao da aba Jogadores sem SofascoreID) -- descarte estrutural.
        if _vazio(jogador):
            continue
        if temporada is None and competicao is None and categoria is None and metrica is None:
            alertas.append(Alerta("INFO", None,
                f"'{nome_aba}' linha {idx + 2}: sem Temporada/Competicao/Categoria/Metrica (provavel nota de "
                f"rodape da planilha, nao dado real) -- descartada. Conteudo: '{str(jogador)[:80]}'"))
            continue
        jogador = str(jogador).strip()

        if categoria and _normaliza(categoria) in CATEGORIA_DESCARTADA:
            descartadas_categoria[jogador] = descartadas_categoria.get(jogador, 0) + 1
            continue

        if metrica is None:
            alertas.append(Alerta("ALERTA", jogador,
                f"'{nome_aba}' linha {idx + 2}: sem nome de Metrica, linha ignorada."))
            continue

        linhas_validas += 1
        chave = (jogador, temporada, competicao, categoria)
        if chave not in agrupado:
            tipo_linha = ("total_temporada" if competicao and _normaliza(competicao) == TOTAL_ANO_LABEL
                          else "competicao")
            agrupado[chave] = {
                "temporada": temporada, "competicao": competicao, "tipo_linha": tipo_linha,
                "categoria": categoria, "metricas": {},
            }
            ordem.append(chave)
        agrupado[chave]["metricas"][metrica] = _fmt(valor) if not _vazio(valor) else "-"

    for jogador, n in descartadas_categoria.items():
        alertas.append(Alerta("INFO", jogador,
            f"'{nome_aba}': {n} linha(s) de categoria 'Partidas' descartada(s) por regra (despejo bruto "
            "corrompido, nao e categoria real) -- ja deveria vir descartado na exportacao, mantido como "
            "guarda-chuva."))

    resultado: dict[str, list[dict]] = {}
    for chave in ordem:
        jogador = chave[0]
        resultado.setdefault(jogador, []).append(agrupado[chave])

    faltando = nomes_esperados - set(resultado.keys())
    for nome in sorted(faltando):
        alertas.append(Alerta("ALERTA", nome, f"nao encontrado em '{nome_aba}'."))
    extra = set(resultado.keys()) - nomes_esperados
    for nome in sorted(extra):
        alertas.append(Alerta("ALERTA", nome,
            f"aparece em '{nome_aba}' mas nao esta na aba Jogadores -- nome sem cadastro mestre."))

    return resultado


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--planilha", type=Path,
                     default=Path(__file__).resolve().parent.parent / "dados" / "celeiro_de_ases_dados.xlsx")
    ap.add_argument("--saida", type=Path, default=Path(__file__).resolve().parent.parent / "saida")
    args = ap.parse_args()

    alertas: list[Alerta] = []
    planilha = pd.read_excel(args.planilha, sheet_name=None)
    for aba in ("Jogadores", "Performance_Carreira", "Performance_Season"):
        if aba not in planilha:
            alertas.append(Alerta("ERRO", None, f"aba '{aba}' nao encontrada na planilha."))

    jogadores = ler_jogadores(planilha["Jogadores"], alertas)
    nomes = {j["jogador"] for j in jogadores}
    print(f"Jogadores lidos da aba 'Jogadores': {len(jogadores)}")

    carreira = ler_performance_longa(planilha["Performance_Carreira"], "Performance_Carreira", alertas, nomes)
    season = ler_performance_longa(planilha["Performance_Season"], "Performance_Season", alertas, nomes)

    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / "jogadores_lidos.json").write_text(
        json.dumps(jogadores, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.saida / "performance_carreira_lida.json").write_text(
        json.dumps(carreira, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.saida / "performance_season_lida.json").write_text(
        json.dumps(season, ensure_ascii=False, indent=2), encoding="utf-8")

    ordem_nivel = {"ERRO": 0, "ALERTA": 1, "INFO": 2}
    alertas.sort(key=lambda a: (ordem_nivel.get(a.nivel, 9), a.jogador or ""))
    linhas_relatorio = [str(a) for a in alertas]
    texto_relatorio = "\n".join(linhas_relatorio) if linhas_relatorio else "Nenhuma inconsistencia encontrada."
    (args.saida / "relatorio_validacao.txt").write_text(texto_relatorio + "\n", encoding="utf-8")

    n_erro = sum(1 for a in alertas if a.nivel == "ERRO")
    n_alerta = sum(1 for a in alertas if a.nivel == "ALERTA")
    n_info = sum(1 for a in alertas if a.nivel == "INFO")
    print(f"Performance_Carreira: {sum(len(v) for v in carreira.values())} blocos categoria/competicao, "
          f"{len(carreira)} jogadores")
    print(f"Performance_Season: {sum(len(v) for v in season.values())} blocos categoria/competicao, "
          f"{len(season)} jogadores")
    print(f"Saida gravada em: {args.saida}")
    print()
    print(f"=== Relatorio de validacao: {n_erro} ERRO, {n_alerta} ALERTA, {n_info} INFO ===")
    print(texto_relatorio)


if __name__ == "__main__":
    main()
