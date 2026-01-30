# Finfeed — Gastos no Cartão Nubank

Dashboard de gastos no cartão de crédito Nubank (necessidades básicas), ano 2025.

## Ver na web (GitHub Pages)

Depois de ativar o GitHub Pages no repositório, o dashboard fica em:

**https://[seu-usuario].github.io/finfeed/**

### Como ativar o GitHub Pages

1. No repositório no GitHub: **Settings** → **Pages**.
2. Em **Build and deployment** → **Source**, escolha **GitHub Actions**.
3. Faça um push na branch `main` (o workflow vai gerar o dashboard e publicar).
4. Aguarde alguns minutos; a URL aparecerá em **Settings** → **Pages**.

## Rodar localmente

```bash
# Gerar CSV consolidado (a partir dos Nubank_*.csv em assets/)
python scripts/consolidate_csv.py

# Gerar o index.html do dashboard
python scripts/build_dashboard.py
```

Depois abra o arquivo `index.html` no navegador.
