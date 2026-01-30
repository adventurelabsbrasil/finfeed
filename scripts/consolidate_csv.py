#!/usr/bin/env python3
"""
Consolida os CSVs Nubank em assets/ nos últimos 12 meses de despesas.

Uso:
  python scripts/consolidate_csv.py

Gera:
  - assets/consolidated_12m.json  (lançamentos filtrados e normalizados)
  - assets/consolidated_12m_expenses.csv  (apenas despesas, para inspeção)

Regras:
  - Considera apenas amount > 0 (despesas). Pagamentos e créditos (amount <= 0) são ignorados.
  - Período: últimos 12 meses a partir da data mais recente encontrada nos CSVs.
  - Remove duplicatas por (date, title, amount).
"""

import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ASSETS = Path(__file__).resolve().parent.parent / "assets"
OUT_JSON = ASSETS / "consolidated_12m.json"
OUT_CSV = ASSETS / "consolidated_12m_expenses.csv"


def parse_amount(s: str) -> float:
    s = (s or "").strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_all_csvs() -> list[dict]:
    rows = []
    for p in sorted(ASSETS.glob("Nubank_*.csv")):
        with open(p, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                date_s = (row.get("date") or "").strip()
                title = (row.get("title") or "").strip()
                amount = parse_amount(row.get("amount") or "0")
                if not date_s:
                    continue
                rows.append({"date": date_s, "title": title, "amount": amount})
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        key = (r["date"], r["title"], r["amount"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main():
    raw = load_all_csvs()
    raw = dedupe(raw)

    # Apenas despesas (amount > 0)
    expenses = [r for r in raw if r["amount"] > 0]

    if not expenses:
        print("Nenhuma despesa encontrada nos CSVs.")
        return

    dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in expenses]
    max_date = max(dates)
    cutoff = max_date - timedelta(days=365)
    last_12 = [r for r in expenses if datetime.strptime(r["date"], "%Y-%m-%d") >= cutoff]
    last_12.sort(key=lambda r: (r["date"], r["title"], r["amount"]))

    # Estatísticas por categoria (agrupando por título normalizado — exemplo simples)
    by_entity = defaultdict(float)
    for r in last_12:
        by_entity[r["title"]] += r["amount"]

    total = sum(r["amount"] for r in last_12)
    stats = {
        "period_months": 12,
        "cutoff_date": cutoff.strftime("%Y-%m-%d"),
        "max_date": max_date.strftime("%Y-%m-%d"),
        "total_expenses": round(total, 2),
        "transaction_count": len(last_12),
        "unique_entities": len(by_entity),
    }

    # Salvar JSON consolidado (para seed/API)
    payload = {
        "meta": stats,
        "expenses": last_12,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Salvar CSV de despesas (inspeção)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "title", "amount"])
        w.writeheader()
        w.writerows(last_12)

    print(f"Consolidação concluída: últimos 12 meses")
    print(f"  Período: {stats['cutoff_date']} a {stats['max_date']}")
    print(f"  Total despesas: R$ {stats['total_expenses']:,.2f}")
    print(f"  Lançamentos: {stats['transaction_count']}")
    print(f"  Estabelecimentos: {stats['unique_entities']}")
    print(f"  Arquivos gerados: {OUT_JSON.name}, {OUT_CSV.name}")


if __name__ == "__main__":
    main()
