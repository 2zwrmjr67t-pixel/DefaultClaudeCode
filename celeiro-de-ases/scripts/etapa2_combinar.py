#!/usr/bin/env python3
"""Passo 2 do "Mapeamento do Celeiro de Ases": combina a saida ja lida e
validada do passo 1 (jogadores_lidos.json, performance_carreira_lida.json,
performance_season_lida.json) num JSON por jogador + consolidado.json.
Nao le nem revalida a planilha de novo -- so combina o que o passo 1 ja
produziu. Ver etapa1_pipeline.py e dados/prompt-claude-code-celeiro-de-ases.md.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


def _slug(nome: str) -> str:
    ascii_nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_nome.lower()).strip("_")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=Path(__file__).resolve().parent.parent / "saida")
    args = ap.parse_args()

    jogadores = json.loads((args.saida / "jogadores_lidos.json").read_text(encoding="utf-8"))
    carreira = json.loads((args.saida / "performance_carreira_lida.json").read_text(encoding="utf-8"))
    season = json.loads((args.saida / "performance_season_lida.json").read_text(encoding="utf-8"))

    consolidado = []
    for jog in jogadores:
        nome = jog["jogador"]
        blocos_carreira = carreira.get(nome, [])
        blocos_season = season.get(nome, [])
        registro = {
            **jog,
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "performance_carreira": {
                "fonte_aba": "Performance_Carreira",
                "encontrado_na_aba": len(blocos_carreira) > 0,
                "blocos": blocos_carreira,
            },
            "performance_season": {
                "fonte_aba": "Performance_Season",
                "encontrado_na_aba": len(blocos_season) > 0,
                "blocos": blocos_season,
            },
        }
        consolidado.append(registro)
        (args.saida / f"{_slug(nome)}.json").write_text(
            json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    (args.saida / "consolidado.json").write_text(
        json.dumps(consolidado, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Jogadores combinados: {len(consolidado)}")
    sem_carreira = [r["jogador"] for r in consolidado if not r["performance_carreira"]["encontrado_na_aba"]]
    sem_season = [r["jogador"] for r in consolidado if not r["performance_season"]["encontrado_na_aba"]]
    print(f"Sem Performance_Carreira: {sem_carreira or 'nenhum'}")
    print(f"Sem Performance_Season: {sem_season or 'nenhum'}")
    print(f"Saida gravada em: {args.saida} (consolidado.json + 1 JSON por jogador)")


if __name__ == "__main__":
    main()
