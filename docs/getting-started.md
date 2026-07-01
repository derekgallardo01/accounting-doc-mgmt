# Getting started

## Install

```bash
pip install -e .
```

For production Graph:

```bash
pip install -e ".[graph]"
```

## Run the demo

```bash
accounting-docs demo
```

Walks the full workflow against the mock 10-client tenant:

1. List all existing matters
2. Provision a new audit matter for Ellis Photography (c-05)
3. Simulate the Power Automate approval flow on the seed workpaper
4. Answer 3 Copilot queries

## Run each command individually

```bash
accounting-docs list-matters
accounting-docs list-matters --json
accounting-docs validate-site
accounting-docs flow-export --out approval-flow.json
accounting-docs ask "What's the status of matter m-01-tax-2026?"
accounting-docs ask "Which matters are due in the next 60 days?"
accounting-docs ask "Show me unsigned documents for Ridgeway Bakery"
```

## Run the end-to-end sample app

```bash
python examples/onboard_client.py
```

Writes `client-onboarding-report.md` — a full new-client onboarding
report (validation + provisioning + approval flow + Copilot answers)
suitable for handing to the practice manager.

## Run tests + evals

```bash
python -m pytest -q     # 38 unit tests
python evals/run.py     # 7 golden eval cases
```
