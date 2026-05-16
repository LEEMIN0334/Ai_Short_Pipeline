# AI Shorts Studio

Backend and automation workspace for an AI shorts production pipeline.

## Branches

- `main`: integrated development baseline
- `CJLee`: CJLee development branch
- `LeeMin`: LeeMin development branch

## Development

```bash
cd packages/core
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src/
```
