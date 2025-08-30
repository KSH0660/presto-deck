Good System Guidelines

- Clarity: Single-purpose endpoints with typed inputs/outputs.
- Observability: Metrics for steps and LLM usage (tokens, latency).
- Reliability: Graceful fallbacks for optional deps (Redis off by default).
- Testability: Fast tests with mocks; avoid network in CI.
- Extensibility: Storage abstraction; modular plan/select/render pipeline.
- Safety: Input validation via Pydantic; bounded concurrency; timeouts.

Flow Targets
- Step 1: Session creation supports prompt + file uploads.
- Step 2: Return DeckPlan; user can edit common fields and per-slide specs.
- Step 3: Render from confirmed DeckPlan; allow natural-language edits.

Operational Notes
- Prometheus endpoint at `/metrics` exposes counters/histograms.
- LLM callbacks log token usage by op: plan/select/render.
- Redis storage can be enabled via env `USE_REDIS=true` and `REDIS_URL`.
