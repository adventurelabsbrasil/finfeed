"""
Lista única de categorias e blacklist compartilhados entre cartão e conta corrente.
"""

# Despesas a ocultar (match parcial, case-insensitive) — cartão e conta
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

# Categorias de despesa (saídas) — lista mestra
MASTER_CATEGORIES_DESPESA = [
    "Transporte",
    "Lazer",
    "Financiamento e consórcio",
    "Educação",
    "Saneamento básico",
    "Outro centro de custo (trabalho)",
    "Manutenção",
    "Impostos e taxas",
    "Comunicação",
    "Despesas esporádicas",
    "Esporte",
    "Assinaturas",
    "Desenvolvimento pessoal",
    "Eventos",
    "Presentes",
    "Higiene",
    "Saúde",
    "Academia",
    "Pedágio",
    "Lanche padaria e outros alimentos",
    "Manutenção veicular",
    "Restaurante",
    "Combustível",
    "Mercado",
    "Açougue",
    "Fruteira",
    "Loja e Bazar",
    "Vestuário e higiene pessoal",
    "Manutenção residencial",
    "Educação e Desenvolvimento pessoal",
    "Vestuário",
    "Pagamento cartão",
    "Investimentos",
    "Boletos e outros",
    "Pagamento de Fornecedores",
    "Outros",
]

# Categorias de entrada (receitas)
MASTER_CATEGORIES_ENTRADA = [
    "Salário / Transferência",
    "Recebimento de Clientes",
    "Investimentos (resgate)",
    "Outras entradas",
]

# Lista completa para dropdowns (despesa + entrada, sem duplicar "Outros")
MASTER_CATEGORIES = list(
    dict.fromkeys(MASTER_CATEGORIES_ENTRADA + MASTER_CATEGORIES_DESPESA)
)


def is_blacklisted(text: str) -> bool:
    t = (text or "").lower()
    return any(b in t for b in BLACKLIST)
