#!/usr/bin/env python3
"""
Consolida os extratos da Conta Corrente Nubank (NU_26372425_*.csv) para 2025.

Uso:
  python scripts/consolidate_conta_corrente.py

Gera:
  - assets/consolidated_conta_corrente_2025.json

Colunas nos CSVs: Data (DD/MM/YYYY), Valor (+ entrada, - saída), Identificador, Descrição.
"""

import csv
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from categories import BLACKLIST

ASSETS = Path(__file__).resolve().parent.parent / "assets"
OUT_JSON = ASSETS / "consolidated_conta_corrente_2025.json"


def is_blacklisted_conta(desc: str) -> bool:
    d = (desc or "").lower()
    return any(b in d for b in BLACKLIST)


def parse_amount(s: str) -> float:
    s = (s or "").strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(dd_mm_yyyy: str) -> str:
    """Converte DD/MM/YYYY para YYYY-MM-DD."""
    s = (dd_mm_yyyy or "").strip()
    if not s:
        return ""
    parts = s.split("/")
    if len(parts) != 3:
        return ""
    try:
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        return ""


def extract_entity(desc: str) -> str:
    """Extrai entidade da coluna Descrição."""
    d = (desc or "").strip()
    if not d:
        return "Desconhecido"

    # Transferência Recebida - NOME - ...
    m = re.match(r"Transferência Recebida\s*-\s*(.+?)\s*-\s*", d, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Transferência enviada/recebida pelo Pix - ENTIDADE - (CNPJ ou •••)
    m = re.match(r"Transferência (?:enviada|recebida) pelo Pix\s*-\s*(.+?)\s*-\s*", d, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Pagamento de boleto efetuado - NOME
    m = re.match(r"Pagamento de boleto efetuado\s*-\s*(.+)", d, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Pagamento de fatura
    if re.search(r"Pagamento de fatura", d, re.IGNORECASE):
        return "Pagamento de fatura"

    # Resgate RDB / Aplicação RDB
    if re.search(r"Resgate RDB", d, re.IGNORECASE):
        return "Resgate RDB"
    if re.search(r"Aplicação RDB", d, re.IGNORECASE):
        return "Aplicação RDB"

    # Compra no débito - ESTABELECIMENTO
    m = re.match(r"Compra no débito\s*-\s*(.+)", d, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return d[:80] if len(d) > 80 else d


def categorize_conta(desc: str, amount: float, entity: str = "") -> str:
    """Atribui categoria por entidade/descrição; só categorias da lista mestra (sem Transferências/PIX)."""
    d = (desc or "").lower()
    ent = (entity or "").lower()

    # Entradas — categorias de receita
    if amount > 0:
        if "transferência recebida" in d or "transferência recebida pelo pix" in d:
            if "rodrigo ribas" in d or "nu pagamentos" in d:
                return "Salário / Transferência"
            return "Recebimento de Clientes"  # PIX de terceiros
        if "resgate rdb" in d:
            return "Investimentos (resgate)"
        return "Outras entradas"

    # Saídas — categorias da lista mestra
    if "pagamento de fatura" in d:
        return "Pagamento cartão"
    if "receita federal" in d or "ipva" in d or "sefaz" in d or "receita federal" in ent:
        return "Impostos e taxas"
    if "telefonica" in d or "tel3" in d or "tel3 telecom" in ent:
        return "Comunicação"
    if "cia estadual de distribui" in d or "cia riograndense de saneamento" in d:
        return "Saneamento básico"
    if "aplicação rdb" in d or "aplicacao rdb" in d:
        return "Investimentos"
    if "pagamento de boleto" in d:
        if "consorcio" in d or "consórcio" in d or "consorcio" in ent:
            return "Financiamento e consórcio"
        return "Boletos e outros"
    if "compra no débito" in d or "compra no debito" in d:
        if "posto" in d or "gasolina" in d:
            return "Combustível"
        if "supermerc" in d or "mercado" in d or "hortifruti" in d:
            return "Mercado"
        if "restaurante" in d or "lanch" in d or "padaria" in d:
            return "Restaurante" if "restaurante" in d or "lanch" in d else "Lanche padaria e outros alimentos"
        return "Outros"
    # PIX enviado — inferir por entidade
    if "transferência enviada pelo pix" in d:
        if "•••" in (desc or ""):
            return "Presentes"  # PIX pessoal; usuário pode editar para Despesas esporádicas etc.
        if "mercadopago" in d or "pagseguro" in d:
            return "Outros"  # pagamentos online; usuário pode categorizar
        if "consorcio" in d or "consórcio" in d:
            return "Financiamento e consórcio"
        if "nubank" in d:
            return "Outros"
        if "edison" in d or "fornecedor" in ent or "kirsten" in d:
            return "Pagamento de Fornecedores"
        return "Outros"
    return "Outros"


def load_all_conta_corrente() -> list[dict]:
    rows = []
    for p in sorted(ASSETS.glob("NU_26372425_*.csv")):
        with open(p, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                data_str = (row.get("Data") or "").strip()
                date_iso = parse_date(data_str)
                if not date_iso.startswith("2025-"):
                    continue
                valor = parse_amount(row.get("Valor") or "0")
                desc = (row.get("Descrição") or row.get("Descricao") or "").strip()
                if is_blacklisted_conta(desc):
                    continue
                entity = extract_entity(desc)
                category = categorize_conta(desc, valor, entity)
                tipo = "entrada" if valor >= 0 else "saida"
                rows.append({
                    "date": date_iso,
                    "amount": round(valor, 2),
                    "entity": entity,
                    "description": desc,
                    "category": category,
                    "type": tipo,
                })
    return sorted(rows, key=lambda x: (x["date"], x["amount"], x["description"]))


def main():
    transactions = load_all_conta_corrente()
    if not transactions:
        print("Nenhuma transação de 2025 encontrada nos NU_*.csv")
        return

    entradas = sum(t["amount"] for t in transactions if t["amount"] > 0)
    saidas = sum(-t["amount"] for t in transactions if t["amount"] < 0)
    saldo = round(entradas - saidas, 2)

    payload = {
        "meta": {
            "year": 2025,
            "transaction_count": len(transactions),
            "entradas_total": round(entradas, 2),
            "saidas_total": round(saidas, 2),
            "saldo_2025": saldo,
        },
        "transactions": transactions,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Conta Corrente 2025 consolidada: {OUT_JSON}")
    print(f"  Lançamentos: {len(transactions)}")
    print(f"  Entradas: R$ {entradas:,.2f} | Saídas: R$ {saidas:,.2f} | Saldo: R$ {saldo:,.2f}")


if __name__ == "__main__":
    main()
