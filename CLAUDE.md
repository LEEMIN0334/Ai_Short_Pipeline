# AI Tool Guidance

Follow the implementation plan in `docs/person-b-work-plan.md`.

Core rules:
- Keep schemas, adapters, agents, orchestration, and storage responsibilities separate.
- Use type hints for all Python functions.
- Keep external API calls behind adapters.
- Record cost information for paid or quota-bound external calls.
