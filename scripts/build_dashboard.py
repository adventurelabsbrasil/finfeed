#!/usr/bin/env python3
"""
Gera o dashboard (index.html) com despesas consolidadas do ano 2025.

Uso:
  python scripts/build_dashboard.py

Requer: assets/consolidated_12m_expenses.csv (gerado por consolidate_csv.py)
Gera: index.html na raiz do projeto
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from typing import Optional

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CSV_PATH = ASSETS / "consolidated_12m_expenses.csv"
CONTA_JSON_PATH = ASSETS / "consolidated_conta_corrente_2025.json"
OUT_HTML = Path(__file__).resolve().parent.parent / "index.html"

# Teto orçamentário mensal (despesas básicas no cartão, exc. lazer, financiamento, limpeza, investimentos, educação, consórcio)
BUDGET_MONTHLY = 3125.0

# Despesas a ocultar (match parcial, case-insensitive)
BLACKLIST = [
    "xgrow",
    "saldo em rotativo",
    "saldo em atraso",
    "juros de dívida",
    "juros de divida",
    "multa de atraso",
    "juros do rotativo",
    "juros de rotativo",
    "iof rotativo",
    "iof de atraso",
]


def parse_amount(s: str) -> float:
    s = (s or "").strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def is_blacklisted(title: str) -> bool:
    t = (title or "").lower()
    return any(b in t for b in BLACKLIST)


def categorize(title: str) -> str:
    """Atribui categoria por palavras-chave no título (case-insensitive)."""
    t = (title or "").lower()
    if any(k in t for k in ["supermerc", "mercado", "hortifruti", "mercearia", "atacad", "fruteira", "carrefour"]):
        return "Alimentação / Supermercado"
    if any(k in t for k in ["posto", "gasbom", "gasolina", "abastece"]):
        return "Combustível"
    if any(k in t for k in ["uber", "via sul", "concessionaria", "concessionária", "pedágio"]):
        return "Transporte"
    if any(k in t for k in ["academia", "prime fit"]):
        return "Saúde / Academia"
    if any(k in t for k in ["farmacia", "farmácia", "panvel", "sao joao", "são joão"]):
        return "Saúde / Farmácia"
    if any(k in t for k in ["ricky", "xis", "lanches", "restaurante", "pizzaria", "buffon", "padaria", "lanchonete", "hamburguer", "minhocaburger", "rancho", "a lenha", "cia do sabor", "cremolatto", "delivery"]):
        return "Alimentação / Restaurante"
    if any(k in t for k in ["google", "youtube", "netflix", "assinatura", "juliocesar", "gemeascel", "conta vivo", "contavivo"]):
        return "Assinaturas / Serviços"
    if any(k in t for k in ["barbeiro", "xbeleza", "beleza", "barbearia"]):
        return "Beleza / Cuidados"
    if any(k in t for k in ["rede farroupilha", "estacionamento", "estacionamentos"]):
        return "Estacionamento / Pedágio"
    if any(k in t for k in ["bazar", "havan", "lojas americanas", "leroy", "amazon"]):
        return "Compras / Variedades"
    return "Outros"


def load_2025_expenses() -> list[dict]:
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            date_s = (row.get("date") or "").strip()
            if not date_s.startswith("2025-"):
                continue
            title = (row.get("title") or "").strip()
            if is_blacklisted(title):
                continue
            amount = parse_amount(row.get("amount") or "0")
            rows.append({
                "date": date_s,
                "title": title,
                "amount": round(amount, 2),
                "category": categorize(title),
            })
    return sorted(rows, key=lambda x: (x["date"], x["title"], x["amount"]))


def aggregate_by_title(expenses: list[dict]) -> list[dict]:
    by_title = defaultdict(float)
    for r in expenses:
        by_title[r["title"]] += r["amount"]
    out = [{"title": k, "total": round(v, 2), "count": sum(1 for e in expenses if e["title"] == k)}
           for k, v in by_title.items()]
    out.sort(key=lambda x: -x["total"])
    return out


def aggregate_by_month(expenses: list[dict]) -> list[dict]:
    by_month = defaultdict(float)
    for r in expenses:
        month = r["date"][:7]  # 2025-01
        by_month[month] += r["amount"]
    out = [{"month": k, "total": round(v, 2)} for k, v in sorted(by_month.items())]
    return out


def aggregate_by_category(expenses: list[dict]) -> list[dict]:
    by_cat = defaultdict(float)
    for r in expenses:
        by_cat[r["category"]] += r["amount"]
    out = [{"category": k, "total": round(v, 2)} for k, v in by_cat.items()]
    out.sort(key=lambda x: -x["total"])
    return out


def build_abc(by_title: list[dict], total: float) -> list[dict]:
    """Adiciona classe ABC (80/20) e % acumulado a by_title."""
    if total <= 0:
        return by_title
    cum = 0.0
    out = []
    for x in by_title:
        cum += x["total"]
        pct = (cum / total) * 100
        if pct <= 80:
            cls = "A"
        elif pct <= 95:
            cls = "B"
        else:
            cls = "C"
        out.append({**x, "cum_pct": round(pct, 1), "abc": cls})
    return out


def over_budget_months(by_month: list[dict]) -> list[dict]:
    """Meses em que o total ultrapassou o teto BUDGET_MONTHLY."""
    out = []
    for m in by_month:
        if m["total"] > BUDGET_MONTHLY:
            out.append({
                "month": m["month"],
                "total": m["total"],
                "over_amount": round(m["total"] - BUDGET_MONTHLY, 2),
            })
    return out


def load_conta_corrente() -> Optional[dict]:
    """Carrega dados da conta corrente se o JSON existir."""
    if not CONTA_JSON_PATH.exists():
        return None
    with open(CONTA_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_conta_payload(conta_data: dict) -> dict:
    """Monta payload para a aba Conta Corrente: by_month, by_entity_abc, by_category."""
    transactions = conta_data.get("transactions", [])
    meta = conta_data.get("meta", {})
    saidas = [t for t in transactions if t.get("amount", 0) < 0]
    # Por entidade (saídas): total em valor absoluto para ABC
    by_entity_sum = defaultdict(float)
    for t in saidas:
        ent = (t.get("entity") or "Outros").strip()
        by_entity_sum[ent] += abs(t["amount"])
    by_entity = [
        {"title": k, "total": round(v, 2)}
        for k, v in sorted(by_entity_sum.items(), key=lambda x: -x[1])
    ]
    total_saidas = sum(x["total"] for x in by_entity)
    by_entity_abc = build_abc(by_entity, total_saidas) if total_saidas > 0 else []

    # Por categoria (saídas)
    by_cat_sum = defaultdict(float)
    for t in saidas:
        cat = (t.get("category") or "Outros").strip()
        by_cat_sum[cat] += abs(t["amount"])
    by_category = [
        {"category": k, "total": round(v, 2)}
        for k, v in sorted(by_cat_sum.items(), key=lambda x: -x[1])
    ]

    # Por mês: entradas e saídas
    by_month_ent = defaultdict(float)
    by_month_sai = defaultdict(float)
    for t in transactions:
        month = (t.get("date") or "")[:7]
        if not month:
            continue
        amt = t.get("amount", 0)
        if amt > 0:
            by_month_ent[month] += amt
        else:
            by_month_sai[month] += abs(amt)
    months = sorted(set(by_month_ent) | set(by_month_sai))
    by_month = [
        {
            "month": m,
            "entradas": round(by_month_ent[m], 2),
            "saidas": round(by_month_sai[m], 2),
            "saldo": round(by_month_ent[m] - by_month_sai[m], 2),
        }
        for m in months
    ]

    all_categories = sorted({c["category"] for c in by_category} | {"Outros"})
    return {
        "year": 2025,
        "entradas_total": meta.get("entradas_total", 0),
        "saidas_total": meta.get("saidas_total", 0),
        "saldo_2025": meta.get("saldo_2025", 0),
        "count": len(transactions),
        "transactions": transactions,
        "by_entity": by_entity_abc,
        "by_category": by_category,
        "by_month": by_month,
        "all_categories": all_categories,
    }


def build_recommendations(
    by_category: list[dict],
    by_month: list[dict],
    over_budget: list[dict],
    total: float,
) -> list[str]:
    """Sugestões para controlar gastos em 2026 com base no histórico 2025."""
    lines = []
    if over_budget:
        n = len(over_budget)
        worst = max(over_budget, key=lambda x: x["over_amount"])
        mm = worst["month"]
        label = {"01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril", "05": "maio", "06": "junho",
                 "07": "julho", "08": "agosto", "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro"}.get(mm[-2:], mm)
        lines.append(f"Em {n} dos 12 meses o gasto no cartão ultrapassou o teto de R$ 3.125,00. O pior foi em {label}, com R$ {worst['over_amount']:.2f} acima do teto. Vale definir alertas ou revisar compras na segunda quinzena quando estiver se aproximando do limite.")
    if by_category:
        top3 = by_category[:3]
        names = [c["category"] for c in top3]
        lines.append(f"As categorias que mais pesaram no cartão em 2025 foram: {', '.join(names)}. Concentrar cortes ou limites nessas áreas tende a dar o maior efeito no total.")
    lines.append("Considerar um limite semanal (ex.: R$ 750) para despesas do cartão, além do teto mensal, ajuda a evitar picos no fim do mês.")
    lines.append("Manter este dashboard atualizado em 2026 e conferir semanalmente os totais por categoria e por mês ajuda a corrigir o curso antes de estourar o orçamento.")
    return lines


def main():
    if not CSV_PATH.exists():
        print(f"Arquivo não encontrado: {CSV_PATH}")
        print("Execute antes: python scripts/consolidate_csv.py")
        return

    expenses = load_2025_expenses()
    if not expenses:
        print("Nenhuma despesa de 2025 encontrada.")
        return

    by_title = aggregate_by_title(expenses)
    by_month = aggregate_by_month(expenses)
    by_category = aggregate_by_category(expenses)
    total_2025 = round(sum(e["amount"] for e in expenses), 2)
    months_with_data = len(by_month) or 1
    avg_monthly = round(total_2025 / months_with_data, 2)
    avg_weekly = round(total_2025 / 52, 2)
    by_title_abc = build_abc(by_title, total_2025)
    over_budget = over_budget_months(by_month)
    recommendations = build_recommendations(by_category, by_month, over_budget, total_2025)

    all_categories = sorted({c["category"] for c in by_category} | {"Outros"})
    payload = {
        "year": 2025,
        "budget_monthly": BUDGET_MONTHLY,
        "over_budget_months": over_budget,
        "recommendations": recommendations,
        "total": total_2025,
        "count": len(expenses),
        "avg_monthly": avg_monthly,
        "avg_weekly": avg_weekly,
        "expenses": expenses,
        "by_title": by_title_abc,
        "by_month": by_month,
        "by_category": by_category,
        "all_categories": all_categories,
        "months_count": months_with_data,
    }
    data_js = json.dumps(payload, ensure_ascii=False)

    conta_raw = load_conta_corrente()
    payload_conta = build_conta_payload(conta_raw) if conta_raw else None
    data_conta_js = json.dumps(payload_conta, ensure_ascii=False) if payload_conta else "null"

    # Consolidado: DRE (receitas - despesas) e DFC (fluxo mensal)
    receitas_consolidado = payload_conta["entradas_total"] if payload_conta else 0
    despesas_consolidado = (payload_conta["saidas_total"] if payload_conta else 0)  # saídas da conta já incluem pagamento fatura
    resultado_dre = round(receitas_consolidado - despesas_consolidado, 2)
    by_month_conta = payload_conta["by_month"] if payload_conta else []
    payload_consolidado = {
        "year": 2025,
        "receitas": receitas_consolidado,
        "despesas": despesas_consolidado,
        "resultado": resultado_dre,
        "by_month_fluxo": by_month_conta,
        "total_cartao": total_2025,
        "by_category_cartao": by_category,
        "by_category_conta": payload_conta["by_category"] if payload_conta else [],
    }
    data_consolidado_js = json.dumps(payload_consolidado, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Finfeed — Cartão, Conta Corrente e DRE 2025 - Rodrigo</title>
  <style>
    :root {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1419; color: #e6edf3; }}
    * {{ box-sizing: border-box; }}
    body {{ max-width: 1200px; margin: 0 auto; padding: 1.5rem; }}
    .tabs-nav {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 1px solid #30363d; padding-bottom: 0; }}
    .tabs-nav button {{ background: transparent; border: none; border-bottom: 2px solid transparent; color: #8b949e; padding: 0.6rem 1rem; font-size: 0.95rem; cursor: pointer; margin-bottom: -1px; }}
    .tabs-nav button:hover {{ color: #e6edf3; }}
    .tabs-nav button.active {{ color: #58a6ff; border-bottom-color: #58a6ff; }}
    .tab-pane {{ display: none; }}
    .tab-pane.active {{ display: block; }}
    h1 {{ font-size: 1.4rem; font-weight: 600; margin-bottom: 0.25rem; }}
    .subtitle {{ color: #8b949e; font-size: 0.9rem; margin-bottom: 0.5rem; }}
    .notice {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; font-size: 0.85rem; color: #8b949e; line-height: 1.5; }}
    .notice strong {{ color: #e6edf3; }}
    .over-teto {{ margin-bottom: 1.5rem; }}
    .over-teto ul {{ margin: 0; padding-left: 1.25rem; color: #f85149; }}
    .over-teto .none {{ color: #238636; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem; }}
    .card .label {{ color: #8b949e; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card .value {{ font-size: 1.15rem; font-weight: 600; margin-top: 0.25rem; }}
    .card .value.total {{ color: #f85149; }}
    section {{ margin-bottom: 2rem; }}
    section h2 {{ font-size: 1.1rem; color: #8b949e; margin-bottom: 0.75rem; font-weight: 600; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin-bottom: 1rem; }}
    .filters label {{ color: #8b949e; font-size: 0.85rem; }}
    .filters select {{ padding: 0.4rem 0.6rem; background: #161b22; border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: 0.9rem; }}
    .filters input[type="text"] {{ padding: 0.5rem 0.75rem; background: #161b22; border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: 0.9rem; width: 220px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #30363d; }}
    th {{ color: #8b949e; font-weight: 500; cursor: pointer; user-select: none; white-space: nowrap; }}
    th:hover {{ color: #e6edf3; }}
    th.sorted-asc::after {{ content: ' ▲'; font-size: 0.7em; }}
    th.sorted-desc::after {{ content: ' ▼'; font-size: 0.7em; }}
    td.amount {{ text-align: right; font-variant-numeric: tabular-nums; color: #f85149; }}
    .table-wrap {{ overflow-x: auto; }}
    .top-list {{ list-style: none; padding: 0; margin: 0; }}
    .top-list li {{ display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0; border-bottom: 1px solid #21262d; gap: 1rem; }}
    .top-list .name {{ flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }}
    .top-list .val {{ color: #f85149; font-variant-numeric: tabular-nums; }}
    .month-bars {{ position: relative; display: flex; align-items: flex-end; gap: 6px; height: 200px; margin-top: 0.5rem; padding-bottom: 24px; }}
    .month-bars .col {{ flex: 1; display: flex; flex-direction: column; align-items: center; min-width: 0; position: relative; }}
    .month-bars .bar {{ width: 100%; max-width: 36px; border-radius: 4px 4px 0 0; min-height: 4px; }}
    .month-bars .bar.under {{ background: #238636; }}
    .month-bars .bar.over {{ background: #da3636; }}
    .month-bars .label {{ font-size: 0.7rem; color: #8b949e; margin-top: 6px; }}
    .month-bars .label.over {{ color: #f85149; font-weight: 600; }}
    .month-bars .ref-line {{ position: absolute; left: 0; right: 0; bottom: 0; height: 2px; background: #9e6a03; opacity: 0.8; }}
    .budget-legend {{ font-size: 0.75rem; color: #8b949e; margin-top: 4px; }}
    .category-list {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }}
    .category-list span {{ background: #21262d; padding: 0.35rem 0.6rem; border-radius: 6px; font-size: 0.85rem; color: #8b949e; }}
    .category-list span strong {{ color: #f85149; margin-left: 4px; }}
    .abc-table {{ font-size: 0.85rem; }}
    .abc-table td {{ padding: 0.35rem 0.5rem; }}
    .abc-A {{ background: rgba(210, 80, 80, 0.15); }}
    .abc-B {{ background: rgba(210, 160, 80, 0.12); }}
    .abc-C {{ background: rgba(80, 120, 80, 0.1); }}
    .abc-badge {{ display: inline-block; width: 20px; text-align: center; font-weight: 700; font-size: 0.75rem; border-radius: 3px; }}
    .abc-badge.A {{ background: #da3636; color: #fff; }}
    .abc-badge.B {{ background: #9e6a03; color: #fff; }}
    .abc-badge.C {{ background: #238636; color: #fff; }}
    .abc-group {{ margin-bottom: 0.5rem; }}
    .abc-group-header {{ cursor: pointer; background: #21262d; padding: 0.5rem 0.75rem; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; font-weight: 600; user-select: none; }}
    .abc-group-header:hover {{ background: #30363d; }}
    .abc-group-header .toggle {{ font-size: 0.8rem; color: #8b949e; }}
    .abc-group-body {{ overflow: hidden; }}
    .abc-group-body.collapsed {{ display: none; }}
    .abc-group-body table {{ margin-top: 0; }}
    .conclusion {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem; margin-top: 2rem; }}
    .conclusion h2 {{ margin-top: 0; }}
    .conclusion ul {{ margin: 0.5rem 0 0 1.25rem; padding: 0; line-height: 1.6; color: #c9d1d9; }}
    td select {{ padding: 0.25rem 0.4rem; background: #161b22; border: 1px solid #30363d; border-radius: 4px; color: #e6edf3; font-size: 0.85rem; max-width: 100%; }}
    td select:focus {{ outline: none; border-color: #58a6ff; }}
    tr.hidden-row {{ opacity: 0.5; background: #0d1117; }}
    .donut-charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.5rem; margin-top: 1rem; }}
    .donut-wrap {{ display: flex; flex-direction: column; align-items: center; }}
    .donut-wrap .donut-outer {{ width: 200px; height: 200px; border-radius: 50%; position: relative; flex-shrink: 0; }}
    .donut-wrap .donut-hole {{ position: absolute; top: 50%; left: 50%; width: 55%; height: 55%; margin: -27.5% 0 0 -27.5%; background: #0f1419; border-radius: 50%; }}
    .donut-legend {{ list-style: none; padding: 0; margin: 0.75rem 0 0 0; font-size: 0.8rem; }}
    .donut-legend li {{ display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; }}
    .donut-legend .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
    .donut-legend .label {{ flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }}
    .donut-legend .val {{ color: #f85149; font-variant-numeric: tabular-nums; }}
  </style>
</head>
<body>
  <h1>Finfeed — Rodrigo · 2025</h1>
  <p class="subtitle">Cartão de crédito, Conta Corrente Nubank e DRE/DFC pessoal</p>
  <nav class="tabs-nav">
    <button type="button" class="tab-btn active" data-tab="tab-cartao">Cartão de Crédito</button>
    <button type="button" class="tab-btn" data-tab="tab-conta">Conta Corrente</button>
    <button type="button" class="tab-btn" data-tab="tab-consolidado">Consolidado (DRE + DFC)</button>
  </nav>

  <div id="tab-cartao" class="tab-pane active">
  <h2 style="font-size:1.1rem; color:#8b949e; margin-bottom:0.5rem;">Cartão de Crédito Nubank</h2>
  <p class="subtitle" style="margin-top:0;">Dedicado para necessidades básicas · Histórico 2025</p>

  <div class="notice">
    <strong>O que este relatório inclui</strong><br>
    Estes gastos <strong>não incluem</strong> todos os pagamentos de necessidades básicas: ficam de fora faturas externas (água, luz, telefone, manutenção, IPTU, jardinagem, lavagem de carro, internet) e movimentações em PIX, dinheiro e TED. Aqui consta apenas o que passou pelo <strong>cartão de crédito Nubank</strong>.
  </div>
  <div class="notice">
    <strong>Orçamento de referência</strong><br>
    O orçamento mensal considerado era de <strong>R$ 3.125,00</strong> para todas as despesas básicas no cartão, <em>exceto</em> lazer, financiamento do carro, limpeza e manutenção, investimentos, educação e consórcio.
  </div>

  <div class="cards">
    <div class="card">
      <div class="label">Total 2025</div>
      <div class="value total" id="total-year">—</div>
    </div>
    <div class="card">
      <div class="label">Média mensal</div>
      <div class="value" id="avg-monthly">—</div>
    </div>
    <div class="card">
      <div class="label">Média semanal</div>
      <div class="value" id="avg-weekly">—</div>
    </div>
    <div class="card">
      <div class="label">Lançamentos</div>
      <div class="value" id="count-year">—</div>
    </div>
  </div>

  <section>
    <h2>Total por mês (barras) · Teto R$ 3.125</h2>
    <div class="month-bars" id="month-bars"></div>
    <p class="budget-legend">Linha laranja = teto. Barras vermelhas = mês acima do teto.</p>
  </section>

  <section class="over-teto">
    <h2>Meses que ultrapassaram o teto de R$ 3.125</h2>
    <div id="over-budget-list"></div>
  </section>

  <section>
    <h2>Principais categorias</h2>
    <div class="category-list" id="by-category"></div>
  </section>

  <section>
    <h2>Gráficos rosca — Top 5</h2>
    <div class="donut-charts">
      <div class="donut-wrap">
        <h3 style="font-size:0.95rem; color:#8b949e; margin-bottom:0.5rem;">Por entidade (estabelecimento)</h3>
        <div id="donut-entity" class="donut-outer"></div>
        <ul id="donut-entity-legend" class="donut-legend"></ul>
      </div>
      <div class="donut-wrap">
        <h3 style="font-size:0.95rem; color:#8b949e; margin-bottom:0.5rem;">Por categoria</h3>
        <div id="donut-category" class="donut-outer"></div>
        <ul id="donut-category-legend" class="donut-legend"></ul>
      </div>
    </div>
  </section>

  <section>
    <h2>Mapa ABC (80/20) — onde estão os maiores gastos</h2>
    <p style="color:#8b949e; font-size:0.85rem; margin-bottom:0.75rem;">A = até 80% do total · B = 80–95% · C = resto. Clique no grupo para expandir/recolher.</p>
    <div id="abc-groups"></div>
  </section>

  <section>
    <h2>Principais gastos por estabelecimento</h2>
    <ul class="top-list" id="by-title"></ul>
  </section>

  <section>
    <h2>Tabela de despesas (2025)</h2>
    <p style="color:#8b949e; font-size:0.85rem; margin-bottom:0.75rem;">Altere a categoria no dropdown se não estiver correta. Use &quot;Contabilizar&quot; para ocultar ou mostrar o gasto nos totais e gráficos.</p>
    <div class="filters">
      <label>Mês:</label>
      <select id="filter-month"><option value="">Todos</option></select>
      <label>Categoria:</label>
      <select id="filter-category"><option value="">Todas</option></select>
      <input type="text" id="search" placeholder="Buscar por data, estabelecimento ou valor...">
    </div>
    <div class="table-wrap">
      <table id="expenses-table">
        <thead>
          <tr>
            <th data-sort="date">Data</th>
            <th data-sort="title">Estabelecimento</th>
            <th>Categoria</th>
            <th data-sort="amount">Valor (R$)</th>
            <th>Contabilizar</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </section>

  <section class="conclusion">
    <h2>Onde nos atentar mais para controlar melhor os gastos em 2026</h2>
    <p style="margin:0 0 0.5rem 0; color:#8b949e;">Este foi o histórico de 2025 no cartão. Com base nos dados:</p>
    <ul id="recommendations"></ul>
  </section>
  </div>

  <div id="tab-conta" class="tab-pane">
    <h2 style="font-size:1.1rem; color:#8b949e; margin-bottom:0.5rem;">Conta Corrente Nubank</h2>
    <p class="subtitle" style="margin-top:0;">Entradas e saídas 2025 · Por categorias e entidades</p>
    <div class="notice"><strong>O que este relatório inclui</strong><br>Movimentações da <strong>conta corrente Nubank</strong> em 2025: transferências recebidas e enviadas (PIX), pagamentos de fatura e boleto, resgates e aplicações RDB, compras no débito.</div>
    <div class="cards">
      <div class="card"><div class="label">Entradas 2025</div><div class="value" id="conta-entradas" style="color:#238636;">—</div></div>
      <div class="card"><div class="label">Saídas 2025</div><div class="value total" id="conta-saidas">—</div></div>
      <div class="card"><div class="label">Saldo 2025</div><div class="value" id="conta-saldo">—</div></div>
      <div class="card"><div class="label">Lançamentos</div><div class="value" id="conta-count">—</div></div>
    </div>
    <section>
      <h2>Fluxo por mês (entradas vs saídas)</h2>
      <div class="month-bars" id="conta-month-bars"></div>
    </section>
    <section>
      <h2>Principais categorias (saídas)</h2>
      <div class="category-list" id="conta-by-category"></div>
    </section>
    <section>
      <h2>Gráficos rosca — Top 5 (saídas)</h2>
      <div class="donut-charts">
        <div class="donut-wrap">
          <h3 style="font-size:0.95rem; color:#8b949e; margin-bottom:0.5rem;">Por entidade</h3>
          <div id="conta-donut-entity" class="donut-outer"></div>
          <ul id="conta-donut-entity-legend" class="donut-legend"></ul>
        </div>
        <div class="donut-wrap">
          <h3 style="font-size:0.95rem; color:#8b949e; margin-bottom:0.5rem;">Por categoria</h3>
          <div id="conta-donut-category" class="donut-outer"></div>
          <ul id="conta-donut-category-legend" class="donut-legend"></ul>
        </div>
      </div>
    </section>
    <section>
      <h2>Mapa ABC (80/20) — saídas por entidade</h2>
      <p style="color:#8b949e; font-size:0.85rem; margin-bottom:0.75rem;">A = até 80% do total · B = 80–95% · C = resto.</p>
      <div id="conta-abc-groups"></div>
    </section>
    <section>
      <h2>Principais saídas por entidade</h2>
      <ul class="top-list" id="conta-by-entity"></ul>
    </section>
    <section>
      <h2>Tabela de lançamentos (2025)</h2>
      <div class="filters">
        <label>Mês:</label><select id="conta-filter-month"><option value="">Todos</option></select>
        <label>Categoria:</label><select id="conta-filter-category"><option value="">Todas</option></select>
        <input type="text" id="conta-search" placeholder="Buscar por data, entidade ou valor...">
      </div>
      <div class="table-wrap">
        <table id="conta-expenses-table">
          <thead><tr><th data-sort="date">Data</th><th data-sort="entity">Entidade</th><th>Categoria</th><th data-sort="amount">Valor (R$)</th></tr></thead>
          <tbody id="conta-tbody"></tbody>
        </table>
      </div>
    </section>
  </div>

  <div id="tab-consolidado" class="tab-pane">
    <h2 style="font-size:1.1rem; color:#8b949e; margin-bottom:0.5rem;">Consolidado — DRE e DFC 2025</h2>
    <p class="subtitle" style="margin-top:0;">Receitas e despesas (conta corrente) · Fluxo de caixa mensal</p>
    <div class="notice"><strong>DRE pessoal</strong>: Receitas = entradas na conta; Despesas = saídas na conta (inclui pagamento de fatura do cartão). <strong>DFC</strong>: fluxo de caixa por mês (entradas − saídas na conta).</div>
    <div class="cards">
      <div class="card"><div class="label">Receitas 2025</div><div class="value" id="dre-receitas" style="color:#238636;">—</div></div>
      <div class="card"><div class="label">Despesas 2025</div><div class="value total" id="dre-despesas">—</div></div>
      <div class="card"><div class="label">Resultado (DRE)</div><div class="value" id="dre-resultado">—</div></div>
    </div>
    <section>
      <h2>DFC — Fluxo de caixa por mês</h2>
      <div class="month-bars" id="consolidado-month-bars"></div>
      <p class="budget-legend">Verde = saldo positivo no mês · Vermelho = saldo negativo.</p>
    </section>
    <section>
      <h2>Despesas por categoria (conta corrente — saídas)</h2>
      <div class="category-list" id="consolidado-by-category"></div>
    </section>
  </div>

  <script>
    const PAYLOAD = {data_js};
    const PAYLOAD_CONTA = {data_conta_js};
    const PAYLOAD_CONSOLIDADO = {data_consolidado_js};
    var OVERRIDES_KEY = 'finfeed_overrides_2025';

    function fmtMoney(n) {{
      return 'R$ ' + n.toLocaleString('pt-BR', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
    }}

    function escapeHtml(s) {{
      var div = document.createElement('div');
      div.textContent = s;
      return div.innerHTML;
    }}

    var monthNames = {{ '01':'Jan','02':'Fev','03':'Mar','04':'Abr','05':'Mai','06':'Jun','07':'Jul','08':'Ago','09':'Set','10':'Out','11':'Nov','12':'Dez' }};
    var budget = PAYLOAD.budget_monthly || 3125;
    var allCategories = PAYLOAD.all_categories || [];

    var overrides = {{}};
    try {{
      var saved = localStorage.getItem(OVERRIDES_KEY);
      if (saved) overrides = JSON.parse(saved);
    }} catch (e) {{}}

    function saveOverrides() {{ try {{ localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overrides)); }} catch (e) {{}} }}

    function getEffectiveExpenses() {{
      return PAYLOAD.expenses.map(function (r, i) {{
        var o = overrides[i];
        var cat = (o && o.category !== undefined) ? o.category : (r.category || 'Outros');
        var count = (o && o.count !== undefined) ? o.count : true;
        return {{ date: r.date, title: r.title, amount: r.amount, category: cat, _count: count, _idx: i }};
      }}).filter(function (r) {{ return r._count; }});
    }}

    function getRowCategory(idx) {{
      var r = PAYLOAD.expenses[idx];
      var o = overrides[idx];
      return (o && o.category !== undefined) ? o.category : (r.category || 'Outros');
    }}

    function getRowCount(idx) {{
      var o = overrides[idx];
      return (o && o.count !== undefined) ? o.count : true;
    }}

    function aggregateByMonth(expenses) {{
      var by = {{}};
      expenses.forEach(function (r) {{
        var m = r.date.slice(0, 7);
        by[m] = (by[m] || 0) + r.amount;
      }});
      return Object.keys(by).sort().map(function (m) {{ return {{ month: m, total: Math.round(by[m] * 100) / 100 }}; }});
    }}

    function aggregateByTitle(expenses) {{
      var by = {{}};
      expenses.forEach(function (r) {{ by[r.title] = (by[r.title] || 0) + r.amount; }});
      var arr = Object.keys(by).map(function (k) {{ return {{ title: k, total: Math.round(by[k] * 100) / 100 }}; }});
      arr.sort(function (a, b) {{ return b.total - a.total; }});
      var total = arr.reduce(function (s, x) {{ return s + x.total; }}, 0);
      var cum = 0;
      return arr.map(function (x) {{
        cum += x.total;
        var pct = total > 0 ? (cum / total) * 100 : 0;
        var cls = pct <= 80 ? 'A' : (pct <= 95 ? 'B' : 'C');
        return {{ title: x.title, total: x.total, cum_pct: Math.round(pct * 10) / 10, abc: cls }};
      }});
    }}

    function aggregateByCategory(expenses) {{
      var by = {{}};
      expenses.forEach(function (r) {{ by[r.category] = (by[r.category] || 0) + r.amount; }});
      var arr = Object.keys(by).map(function (k) {{ return {{ category: k, total: Math.round(by[k] * 100) / 100 }}; }});
      arr.sort(function (a, b) {{ return b.total - a.total; }});
      return arr;
    }}

    function recalc() {{
      var eff = getEffectiveExpenses();
      var total = eff.reduce(function (s, r) {{ return s + r.amount; }}, 0);
      var by_month = aggregateByMonth(eff);
      var by_title = aggregateByTitle(eff);
      var by_category = aggregateByCategory(eff);
      var monthsCount = by_month.length || 1;
      var over_budget_months = by_month.filter(function (m) {{ return m.total > budget; }}).map(function (m) {{
        return {{ month: m.month, total: m.total, over_amount: Math.round((m.total - budget) * 100) / 100 }};
      }});
      return {{
        total: Math.round(total * 100) / 100,
        count: eff.length,
        avg_monthly: Math.round((total / monthsCount) * 100) / 100,
        avg_weekly: Math.round((total / 52) * 100) / 100,
        by_month: by_month,
        by_title: by_title,
        by_category: by_category,
        over_budget_months: over_budget_months
      }};
    }}

    var DONUT_COLORS = ['#da3636', '#9e6a03', '#238636', '#58a6ff', '#a371f7'];

    function renderDonut(containerId, legendId, top5, labelKey) {{
      var container = document.getElementById(containerId);
      var legendEl = document.getElementById(legendId);
      container.innerHTML = '';
      legendEl.innerHTML = '';
      if (!top5 || top5.length === 0) {{ container.style.background = '#21262d'; return; }}
      var total = top5.reduce(function (s, x) {{ return s + x.total; }}, 0);
      var segs = [];
      var cum = 0;
      top5.forEach(function (x, i) {{
        var pct = total > 0 ? (x.total / total) * 100 : 0;
        segs.push(DONUT_COLORS[i % DONUT_COLORS.length] + ' ' + cum + '% ' + (cum + pct) + '%');
        cum += pct;
      }});
      container.style.background = 'conic-gradient(' + segs.join(', ') + ')';
      var hole = document.createElement('div');
      hole.className = 'donut-hole';
      container.appendChild(hole);
      top5.forEach(function (x, i) {{
        var li = document.createElement('li');
        li.innerHTML = '<span class="dot" style="background:' + DONUT_COLORS[i % DONUT_COLORS.length] + '"></span><span class="label">' + escapeHtml(x[labelKey]) + '</span><span class="val">' + fmtMoney(x.total) + '</span>';
        legendEl.appendChild(li);
      }});
    }}

    function renderAll() {{
      var data = recalc();

      document.getElementById('total-year').textContent = fmtMoney(data.total);
      document.getElementById('avg-monthly').textContent = fmtMoney(data.avg_monthly);
      document.getElementById('avg-weekly').textContent = fmtMoney(data.avg_weekly);
      document.getElementById('count-year').textContent = data.count.toLocaleString('pt-BR');

      var barsEl = document.getElementById('month-bars');
      barsEl.innerHTML = '';
      var maxVal = Math.max(budget, Math.max.apply(null, data.by_month.map(function (m) {{ return m.total; }})) || 1);
      var barMaxH = 160;
      data.by_month.forEach(function (m) {{
        var pct = maxVal > 0 ? (m.total / maxVal) * 100 : 0;
        var h = (pct / 100) * barMaxH;
        var over = m.total > budget;
        var label = monthNames[m.month.slice(5, 7)] || m.month.slice(5, 7);
        var col = document.createElement('div');
        col.className = 'col';
        col.innerHTML = '<span class="bar ' + (over ? 'over' : 'under') + '" style="height:' + Math.max(4, h) + 'px" title="' + fmtMoney(m.total) + (over ? ' (acima do teto)' : '') + '"></span><span class="label' + (over ? ' over' : '') + '">' + label + '</span>';
        barsEl.appendChild(col);
      }});
      var refLine = document.createElement('div');
      refLine.className = 'ref-line';
      refLine.style.bottom = (24 + (budget / maxVal) * barMaxH) + 'px';
      refLine.title = 'Teto R$ ' + budget.toLocaleString('pt-BR', {{ minimumFractionDigits: 2 }});
      barsEl.appendChild(refLine);

      var overList = document.getElementById('over-budget-list');
      overList.innerHTML = '';
      if (data.over_budget_months.length) {{
        var ul = document.createElement('ul');
        data.over_budget_months.forEach(function (m) {{
          var li = document.createElement('li');
          li.textContent = (monthNames[m.month.slice(5, 7)] || m.month) + ': ' + fmtMoney(m.total) + ' (+' + fmtMoney(m.over_amount) + ' acima do teto)';
          ul.appendChild(li);
        }});
        overList.appendChild(ul);
      }} else {{
        var p = document.createElement('p');
        p.className = 'none';
        p.textContent = 'Nenhum mês ultrapassou o teto de R$ 3.125,00.';
        overList.appendChild(p);
      }}

      var byCatEl = document.getElementById('by-category');
      byCatEl.innerHTML = '';
      data.by_category.forEach(function (c) {{
        var span = document.createElement('span');
        span.innerHTML = escapeHtml(c.category) + ' <strong>' + fmtMoney(c.total) + '</strong>';
        byCatEl.appendChild(span);
      }});

      var top5Entity = data.by_title.slice(0, 5);
      var top5Cat = data.by_category.slice(0, 5);
      renderDonut('donut-entity', 'donut-entity-legend', top5Entity, 'title');
      renderDonut('donut-category', 'donut-category-legend', top5Cat, 'category');

      var abcGroupsEl = document.getElementById('abc-groups');
      abcGroupsEl.innerHTML = '';
      var byClass = {{ A: [], B: [], C: [] }};
      data.by_title.forEach(function (r) {{ byClass[r.abc].push(r); }});
      ['A', 'B', 'C'].forEach(function (cls) {{
        var items = byClass[cls];
        var totalCls = items.reduce(function (sum, r) {{ return sum + r.total; }}, 0);
        var group = document.createElement('div');
        group.className = 'abc-group';
        var header = document.createElement('div');
        header.className = 'abc-group-header';
        header.innerHTML = '<span>Classe ' + cls + ' <span class="abc-badge ' + cls + '">' + cls + '</span> — ' + items.length + ' itens</span><span class="toggle">Total: ' + fmtMoney(totalCls) + ' ▶</span>';
        var body = document.createElement('div');
        body.className = 'abc-group-body collapsed';
        var table = document.createElement('table');
        table.className = 'abc-table';
        table.innerHTML = '<thead><tr><th>Estabelecimento</th><th>Total (R$)</th><th>% Acum.</th></tr></thead><tbody></tbody>';
        var tbody = table.querySelector('tbody');
        items.forEach(function (r) {{
          var tr = document.createElement('tr');
          tr.className = 'abc-' + r.abc;
          tr.innerHTML = '<td>' + escapeHtml(r.title) + '</td><td class="amount">' + fmtMoney(r.total) + '</td><td>' + r.cum_pct + '%</td>';
          tbody.appendChild(tr);
        }});
        body.appendChild(table);
        group.appendChild(header);
        group.appendChild(body);
        header.addEventListener('click', function () {{
          body.classList.toggle('collapsed');
          header.querySelector('.toggle').textContent = 'Total: ' + fmtMoney(totalCls) + (body.classList.contains('collapsed') ? ' ▶' : ' ▼');
        }});
        abcGroupsEl.appendChild(group);
      }});

      var byTitleEl = document.getElementById('by-title');
      byTitleEl.innerHTML = '';
      data.by_title.forEach(function (x) {{
        var li = document.createElement('li');
        li.innerHTML = '<span class="name">' + escapeHtml(x.title) + '</span><span class="val">' + fmtMoney(x.total) + '</span>';
        byTitleEl.appendChild(li);
      }});

      renderTable(data);
    }}

    function renderContaTab() {{
      if (!PAYLOAD_CONTA) {{
        var pane = document.getElementById('tab-conta');
        if (pane) pane.innerHTML = '<p class="notice">Execute <code>python scripts/consolidate_conta_corrente.py</code> e gere o dashboard novamente para ver os dados da conta corrente.</p>';
        return;
      }}
      var c = PAYLOAD_CONTA;
      document.getElementById('conta-entradas').textContent = fmtMoney(c.entradas_total || 0);
      document.getElementById('conta-saidas').textContent = fmtMoney(c.saidas_total || 0);
      document.getElementById('conta-saldo').textContent = fmtMoney(c.saldo_2025 || 0);
      document.getElementById('conta-saldo').style.color = (c.saldo_2025 || 0) >= 0 ? '#238636' : '#f85149';
      document.getElementById('conta-count').textContent = (c.count || 0).toLocaleString('pt-BR');

      var barsEl = document.getElementById('conta-month-bars');
      barsEl.innerHTML = '';
      var byMonth = c.by_month || [];
      var maxVal = 1;
      byMonth.forEach(function (m) {{ maxVal = Math.max(maxVal, m.entradas || 0, m.saidas || 0); }});
      var barMaxH = 160;
      byMonth.forEach(function (m) {{
        var hEnt = maxVal > 0 ? ((m.entradas || 0) / maxVal) * barMaxH : 0;
        var hSai = maxVal > 0 ? ((m.saidas || 0) / maxVal) * barMaxH : 0;
        var label = monthNames[m.month.slice(5, 7)] || m.month.slice(5, 7);
        var col = document.createElement('div');
        col.className = 'col';
        col.innerHTML = '<span class="bar under" style="height:' + Math.max(4, hEnt) + 'px; margin-bottom:2px;" title="Entradas ' + fmtMoney(m.entradas) + '"></span><span class="bar over" style="height:' + Math.max(4, hSai) + 'px" title="Saídas ' + fmtMoney(m.saidas) + '"></span><span class="label">' + label + '</span>';
        barsEl.appendChild(col);
      }});

      var byCatEl = document.getElementById('conta-by-category');
      byCatEl.innerHTML = '';
      (c.by_category || []).forEach(function (x) {{
        var span = document.createElement('span');
        span.innerHTML = escapeHtml(x.category) + ' <strong>' + fmtMoney(x.total) + '</strong>';
        byCatEl.appendChild(span);
      }});

      var top5Entity = (c.by_entity || []).slice(0, 5);
      var top5Cat = (c.by_category || []).slice(0, 5);
      renderDonut('conta-donut-entity', 'conta-donut-entity-legend', top5Entity, 'title');
      renderDonut('conta-donut-category', 'conta-donut-category-legend', top5Cat, 'category');

      var abcEl = document.getElementById('conta-abc-groups');
      abcEl.innerHTML = '';
      var byClass = {{ A: [], B: [], C: [] }};
      (c.by_entity || []).forEach(function (r) {{ byClass[r.abc].push(r); }});
      ['A', 'B', 'C'].forEach(function (cls) {{
        var items = byClass[cls];
        var totalCls = items.reduce(function (sum, r) {{ return sum + r.total; }}, 0);
        var group = document.createElement('div');
        group.className = 'abc-group';
        var header = document.createElement('div');
        header.className = 'abc-group-header';
        header.innerHTML = '<span>Classe ' + cls + ' <span class="abc-badge ' + cls + '">' + cls + '</span> — ' + items.length + ' itens</span><span class="toggle">Total: ' + fmtMoney(totalCls) + ' ▶</span>';
        var body = document.createElement('div');
        body.className = 'abc-group-body collapsed';
        var table = document.createElement('table');
        table.className = 'abc-table';
        table.innerHTML = '<thead><tr><th>Entidade</th><th>Total (R$)</th><th>% Acum.</th></tr></thead><tbody></tbody>';
        var tbody = table.querySelector('tbody');
        items.forEach(function (r) {{
          var tr = document.createElement('tr');
          tr.className = 'abc-' + r.abc;
          tr.innerHTML = '<td>' + escapeHtml(r.title) + '</td><td class="amount">' + fmtMoney(r.total) + '</td><td>' + r.cum_pct + '%</td>';
          tbody.appendChild(tr);
        }});
        body.appendChild(table);
        group.appendChild(header);
        group.appendChild(body);
        header.addEventListener('click', function () {{
          body.classList.toggle('collapsed');
          header.querySelector('.toggle').textContent = 'Total: ' + fmtMoney(totalCls) + (body.classList.contains('collapsed') ? ' ▶' : ' ▼');
        }});
        abcEl.appendChild(group);
      }});

      var byEntityEl = document.getElementById('conta-by-entity');
      byEntityEl.innerHTML = '';
      (c.by_entity || []).forEach(function (x) {{
        var li = document.createElement('li');
        li.innerHTML = '<span class="name">' + escapeHtml(x.title) + '</span><span class="val">' + fmtMoney(x.total) + '</span>';
        byEntityEl.appendChild(li);
      }});

      var txn = c.transactions || [];
      var filterMonthSel = document.getElementById('conta-filter-month');
      filterMonthSel.innerHTML = '<option value="">Todos</option>';
      var monthsSeen = {{}};
      txn.forEach(function (t) {{ monthsSeen[t.date.slice(0, 7)] = true; }});
      Object.keys(monthsSeen).sort().forEach(function (m) {{
        var opt = document.createElement('option');
        opt.value = m;
        opt.textContent = monthNames[m.slice(5, 7)] || m;
        filterMonthSel.appendChild(opt);
      }});
      var filterCatSel = document.getElementById('conta-filter-category');
      filterCatSel.innerHTML = '<option value="">Todas</option>';
      (c.all_categories || []).forEach(function (cat) {{
        var opt = document.createElement('option');
        opt.value = cat;
        opt.textContent = cat;
        filterCatSel.appendChild(opt);
      }});
      var contaSearchTerm = '';
      var contaFilterMonth = '';
      var contaFilterCat = '';
      function renderContaTable() {{
        var rows = txn.slice();
        if (contaSearchTerm) {{
          var q = contaSearchTerm.toLowerCase();
          rows = rows.filter(function (r) {{
            return (r.date && r.date.toLowerCase().includes(q)) || (r.entity && r.entity.toLowerCase().includes(q)) || (r.category && r.category.toLowerCase().includes(q)) || (r.amount && r.amount.toString().includes(q));
          }});
        }}
        if (contaFilterMonth) rows = rows.filter(function (r) {{ return r.date && r.date.slice(0, 7) === contaFilterMonth; }});
        if (contaFilterCat) rows = rows.filter(function (r) {{ return r.category === contaFilterCat; }});
        rows.sort(function (a, b) {{ return (a.date || '').localeCompare(b.date || '') || (a.amount - b.amount); }});
        var tbody = document.getElementById('conta-tbody');
        tbody.innerHTML = '';
        rows.forEach(function (r) {{
          var tr = document.createElement('tr');
          var amt = r.amount || 0;
          tr.innerHTML = '<td>' + (r.date || '') + '</td><td>' + escapeHtml(r.entity || '') + '</td><td>' + escapeHtml(r.category || '') + '</td><td class="amount" style="color:' + (amt >= 0 ? '#238636' : '#f85149') + '">' + fmtMoney(amt) + '</td>';
          tbody.appendChild(tr);
        }});
      }}
      renderContaTable();
      document.getElementById('conta-search').addEventListener('input', function () {{ contaSearchTerm = this.value.trim(); renderContaTable(); }});
      filterMonthSel.addEventListener('change', function () {{ contaFilterMonth = this.value; renderContaTable(); }});
      filterCatSel.addEventListener('change', function () {{ contaFilterCat = this.value; renderContaTable(); }});
    }}

    function renderConsolidadoTab() {{
      var co = PAYLOAD_CONSOLIDADO;
      if (!co) return;
      document.getElementById('dre-receitas').textContent = fmtMoney(co.receitas || 0);
      document.getElementById('dre-despesas').textContent = fmtMoney(co.despesas || 0);
      var res = co.resultado || 0;
      var resEl = document.getElementById('dre-resultado');
      resEl.textContent = fmtMoney(res);
      resEl.style.color = res >= 0 ? '#238636' : '#f85149';

      var barsEl = document.getElementById('consolidado-month-bars');
      barsEl.innerHTML = '';
      var byMonth = co.by_month_fluxo || [];
      var maxAbs = 1;
      byMonth.forEach(function (m) {{ maxAbs = Math.max(maxAbs, Math.abs(m.saldo || 0)); }});
      var barMaxH = 160;
      byMonth.forEach(function (m) {{
        var saldo = m.saldo || 0;
        var pct = maxAbs > 0 ? (Math.abs(saldo) / maxAbs) * 100 : 0;
        var h = (pct / 100) * barMaxH;
        var positive = saldo >= 0;
        var label = monthNames[(m.month || '').slice(5, 7)] || (m.month || '').slice(5, 7);
        var col = document.createElement('div');
        col.className = 'col';
        col.innerHTML = '<span class="bar ' + (positive ? 'under' : 'over') + '" style="height:' + Math.max(4, h) + 'px" title="Saldo ' + fmtMoney(saldo) + '"></span><span class="label' + (positive ? '' : ' over') + '">' + label + '</span>';
        barsEl.appendChild(col);
      }});

      var byCatEl = document.getElementById('consolidado-by-category');
      byCatEl.innerHTML = '';
      (co.by_category_conta || []).forEach(function (x) {{
        var span = document.createElement('span');
        span.innerHTML = escapeHtml(x.category) + ' <strong>' + fmtMoney(x.total) + '</strong>';
        byCatEl.appendChild(span);
      }});
    }}

    var sortKey = 'date';
    var sortDir = 1;
    var searchTerm = '';
    var filterMonthVal = '';
    var filterCatVal = '';

    function renderTable(data) {{
      var rows = PAYLOAD.expenses.map(function (r, i) {{
        return {{ date: r.date, title: r.title, amount: r.amount, category: getRowCategory(i), _count: getRowCount(i), _idx: i }};
      }});
      if (searchTerm) {{
        var q = searchTerm.toLowerCase();
        rows = rows.filter(function (r) {{
          return r.date.toLowerCase().includes(q) || r.title.toLowerCase().includes(q) || (r.category && r.category.toLowerCase().includes(q)) || r.amount.toString().includes(q);
        }});
      }}
      if (filterMonthVal) rows = rows.filter(function (r) {{ return r.date.slice(0, 7) === filterMonthVal; }});
      if (filterCatVal) rows = rows.filter(function (r) {{ return r.category === filterCatVal; }});
      rows.sort(function (a, b) {{
        var va = a[sortKey] !== undefined ? a[sortKey] : a.date, vb = b[sortKey] !== undefined ? b[sortKey] : b.date;
        if (sortKey === 'amount') return sortDir * (va - vb);
        if (sortKey === 'date') return sortDir * (va.localeCompare(vb));
        return sortDir * String(va || '').localeCompare(vb || '');
      }});
      var tbody = document.getElementById('tbody');
      tbody.innerHTML = '';
      rows.forEach(function (r) {{
        var tr = document.createElement('tr');
        if (!r._count) tr.classList.add('hidden-row');
        var cats = allCategories.indexOf(r.category) >= 0 ? allCategories : allCategories.concat([r.category]);
        var catOpts = cats.map(function (c) {{ return '<option value="' + escapeHtml(c) + '"' + (c === r.category ? ' selected' : '') + '>' + escapeHtml(c) + '</option>'; }}).join('');
        var catSelect = '<select data-idx="' + r._idx + '" class="cat-select">' + catOpts + '</select>';
        var countSelect = '<select data-idx="' + r._idx + '" class="count-select"><option value="1"' + (r._count ? ' selected' : '') + '>Sim</option><option value="0"' + (!r._count ? ' selected' : '') + '>Não</option></select>';
        tr.innerHTML = '<td>' + r.date + '</td><td>' + escapeHtml(r.title) + '</td><td>' + catSelect + '</td><td class="amount">' + fmtMoney(r.amount) + '</td><td>' + countSelect + '</td>';
        tbody.appendChild(tr);
      }});
      tbody.querySelectorAll('.cat-select').forEach(function (sel) {{
        sel.addEventListener('change', function () {{
          var idx = parseInt(sel.getAttribute('data-idx'), 10);
          overrides[idx] = overrides[idx] || {{}};
          overrides[idx].category = sel.value;
          saveOverrides();
          renderAll();
        }});
      }});
      tbody.querySelectorAll('.count-select').forEach(function (sel) {{
        sel.addEventListener('change', function () {{
          var idx = parseInt(sel.getAttribute('data-idx'), 10);
          overrides[idx] = overrides[idx] || {{}};
          overrides[idx].count = sel.value === '1';
          saveOverrides();
          renderAll();
        }});
      }});
    }}

    var filterMonth = document.getElementById('filter-month');
    PAYLOAD.by_month.forEach(function (m) {{
      var opt = document.createElement('option');
      opt.value = m.month;
      opt.textContent = monthNames[m.month.slice(5, 7)] || m.month;
      filterMonth.appendChild(opt);
    }});
    var filterCat = document.getElementById('filter-category');
    (PAYLOAD.by_category || []).forEach(function (c) {{
      var opt = document.createElement('option');
      opt.value = c.category;
      opt.textContent = c.category;
      filterCat.appendChild(opt);
    }});

    document.querySelectorAll('#expenses-table th[data-sort]').forEach(function (th) {{
      th.addEventListener('click', function () {{
        var key = th.getAttribute('data-sort');
        if (sortKey === key) sortDir = -sortDir; else {{ sortKey = key; sortDir = 1; }}
        document.querySelectorAll('#expenses-table th[data-sort]').forEach(function (h) {{ h.classList.remove('sorted-asc', 'sorted-desc'); }});
        th.classList.add(sortDir === 1 ? 'sorted-asc' : 'sorted-desc');
        renderAll();
      }});
    }});

    document.getElementById('search').addEventListener('input', function () {{ searchTerm = this.value.trim(); renderAll(); }});
    filterMonth.addEventListener('change', function () {{ filterMonthVal = this.value; renderAll(); }});
    filterCat.addEventListener('change', function () {{ filterCatVal = this.value; renderAll(); }});

    var recEl = document.getElementById('recommendations');
    (PAYLOAD.recommendations || []).forEach(function (text) {{
      var li = document.createElement('li');
      li.textContent = text;
      recEl.appendChild(li);
    }});

    document.querySelectorAll('.tab-btn').forEach(function (btn) {{
      btn.addEventListener('click', function () {{
        var tabId = btn.getAttribute('data-tab');
        document.querySelectorAll('.tab-pane').forEach(function (p) {{ p.classList.remove('active'); }});
        document.querySelectorAll('.tab-btn').forEach(function (b) {{ b.classList.remove('active'); }});
        var pane = document.getElementById(tabId);
        if (pane) pane.classList.add('active');
        btn.classList.add('active');
      }});
    }});

    renderAll();
    renderContaTab();
    renderConsolidadoTab();
  </script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Dashboard gerado: {OUT_HTML}")
    print(f"  Despesas 2025: {len(expenses)} | Total: R$ {total_2025:,.2f}")


if __name__ == "__main__":
    main()
