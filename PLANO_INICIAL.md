# Finfeed — Plano inicial

Documento de referência do plano do projeto. Baseado em `start.txt` e nas decisões iniciais.

---

## Objetivo

App simples **mobile-first** para upload de CSV da fatura de cartão de crédito Nubank, com leitura, categorização e visualização consolidada dos **últimos 12 meses** de despesas.

---

## Funcionalidades

### Upload de dados
- **Upload semanal** de um arquivo CSV da fatura (fluxo principal).
- **Importação inicial / bulk**: subir vários CSVs de uma vez (ex.: pasta `assets/`) para popular os últimos 12 meses desde o primeiro uso.
- Formato CSV: colunas `date`, `title`, `amount` (Nubank). Positivo = despesa, negativo = pagamento.

### Processamento
- Ler dados e **categorizar** (por título/estabelecimento ou regras configuráveis).
- Ignorar "Pagamento recebido" e créditos (`amount` ≤ 0) nas despesas.

### Visualizações
- Gráficos de custo **por categoria** e **por entidade** (estabelecimento).
- **Top 5 despesas** (por valor ou frequência).
- **Tabela dinâmica** para visualizar e filtrar lançamentos.
- **Filtros de período**: 7 dias, 30 dias, 90 dias, 12 meses, intervalo custom.

### Consolidação 12 meses
- Backend mantém histórico de pelo menos os **últimos 12 meses**.
- Dashboards com filtro "últimos 12 meses", totais e comparativos.

### Autenticação
- Login por usuário e senha.
- Dados isolados por usuário.

---

## Stack técnica (plano)

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js (App Router), TypeScript, Tailwind, mobile-first |
| Backend / DB | Supabase (auth + Postgres) ou Firebase |
| Deploy | Vercel |
| Revisão | Regras do Cursor para revisar antes de commit/deploy |

---

## Consolidação dos CSVs (12 meses)

### Script
- `scripts/consolidate_csv.py`
- Lê todos `Nubank_*.csv` em `assets/`
- Considera apenas despesas (`amount` > 0)
- Filtra últimos 12 meses a partir da data mais recente
- Remove duplicatas por `(date, title, amount)`

### Arquivos gerados
- `assets/consolidated_12m.json` — estrutura para seed no backend ou ingest via API
- `assets/consolidated_12m_expenses.csv` — despesas consolidadas para inspeção

### Uso
- **Seed inicial**: ler `consolidated_12m.json` e inserir no Supabase/Firebase.
- **UI**: "Importar CSVs em lote" aplicando a mesma lógica e persistindo no backend.
- **Upload semanal**: um CSV por vez; backend acumula histórico.

### Execução
```bash
python3 scripts/consolidate_csv.py
```

---

## Etapas de implementação (checklist)

1. [ ] **Scaffold Next.js** (Vercel) + Tailwind + Supabase
2. [ ] **Schema Supabase**: tabelas `expenses`, categorias; seed com `consolidated_12m.json`
3. [ ] **Auth**: login/senha e upload CSV (único + lote)
4. [ ] **Dashboard**: gráficos por categoria/entidade, top 5, tabela dinâmica, filtros de período
5. [ ] **Regra Cursor** para revisão pré-commit

---

## Estrutura atual do projeto

```
finfeed/
├── assets/           # CSVs Nubank + consolidated_12m.*
├── scripts/
│   └── consolidate_csv.py
├── start.txt         # Especificação original
├── PLANO_INICIAL.md  # Este arquivo
└── ...
```

---

## Referências

- Especificação detalhada: `start.txt`
- Dados consolidados: `assets/consolidated_12m.json`
