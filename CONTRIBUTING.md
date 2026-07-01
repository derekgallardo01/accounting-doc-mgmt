# Contributing

## Development setup

```bash
git clone https://github.com/derekgallardo01/accounting-doc-mgmt
cd accounting-doc-mgmt
pip install -e ".[graph]"
```

## Running tests

```bash
python -m pytest -q
```

## Running the golden evals

```bash
python evals/run.py
```

## Pull-request checklist

- [ ] All tests pass locally (`python -m pytest -q`)
- [ ] All evals pass locally (`python evals/run.py`)
- [ ] If you added a library, it has a required `matter_id` metadata column
- [ ] If you changed the approval flow, the Power Automate export still parses
- [ ] CHANGELOG.md updated
