# EVE CapNav

Capital ship jump route planner for EVE Online. No login required — plan safe routes through hostile space with fatigue tracking, fuel costs, threat intel, and safe spot analysis.

## Features

- **A* pathfinding** with multiple routing modes: Safe (avoids danger), Direct (shortest), POS Hopping (prefers moon-rich systems)
- **Fatigue-aware routing** — distance exponent in cost function penalizes long jumps proportionally to fatigue impact
- **Dead-end system detection** — systems with only 1 stargate are flagged and preferred in safe mode
- **Advanced weight tuning** — configurable base system cost, distance exponent, danger/jumps weights, dead-end bonus, and moon bonus
- **Jump fatigue simulation** with optimized wait time suggestions
- **Safe spot scoring** — finds the best celestial pair for mid-warp bookmarks, shows distance to nearest probe reference
- **Sovereignty display** — shows alliance/faction ownership per system, route avoidance by alliance name
- **zKillboard threat intel** — active PVPers, group kill ratio, hourly activity patterns per system
- **Time zone awareness** — suggests quietest jump window based on historical kill patterns
- **Fuel calculator** with Jump Fuel Conservation skill support
- **Alternative system selection** — view and swap in different waypoints at each hop
- **Route sharing** — copy route as text for Discord/Slack, open in Dotlan jump planner
- **Optional 24h jump history** — uses aggregated jump data from a FastAPI service instead of ESI's hourly snapshot

## Quick Start

```bash
uv sync
cd frontend && npm install && npm run build
uv run python src/main.py                     # http://localhost:6001
```

The app requires `sqlite-latest.sqlite` (EVE SDE, March 2026+ schema) in `src/instance/`.

## Docker

```bash
docker compose up --build     # app + Redis + Celery worker/beat
```

## Frontend Development

```bash
cd frontend
npm install
npm run dev          # Vite dev server on :5173, proxies /api to :6001
npm run build        # Production build → src/static/
```

## Development

```bash
uv run ruff check src/                            # Lint
uv run ruff format --check src/                    # Format check
uv run --group test pytest tests/unit/ -x -q       # Unit tests
```

## Tests

Two suites — both run from a fresh `uv sync --group test`:

### Unit tests

Fast, no browser, ESI mocked. Use an in-memory SQLite seeded with a handful of systems.

```bash
uv run --group test pytest tests/unit/ -x -q
```

### Playwright FE regression suite

The integration suite spawns its own Flask server on a free port (no `docker compose up` needed) backed by an in-memory SDE that's seeded with a 4-system fork topology. Each test reseeds `cache.sqlite` from a named scenario in `tests/seeds/scenarios.py` to verify the threat-weighting knobs (`danger_weight`, `jumps_weight`, `activity_weight`) actually change the chosen path — not just that the FE renders.

First-time setup — install the Chromium binary Playwright drives:

```bash
uv run --group test playwright install chromium
```

The FE bundle must be built before running the suite (the integration server serves `src/static/`):

```bash
cd frontend && npm install && npm run build && cd ..
```

Then run:

```bash
uv run --group test pytest tests/integration/ -x -q
```

Layout:

- `tests/seeds/topology.py` — 4 systems wired so the direct origin→dest hop is out of Carrier range; the planner must pick one of two two-hop branches.
- `tests/seeds/scenarios.py` — named threat-data fixtures (`empty`, `kills_on_danger`, `jumps_on_danger`, `activity_on_danger`, `zkill_intel`).
- `tests/seeds/build_cache.py` — writes a fresh `cache.sqlite` for a scenario; tests call `reseed("scenario_name")` between assertions.
- `tests/integration/` — Playwright tests grouped by concern (smoke, route render, swap, threat weighting, threat modal).

To run a single test:

```bash
uv run --group test pytest tests/integration/test_threat_weighting.py::test_kills_reroute_via_safe_at_default_weight -x
```

Debug a failing test interactively (headed browser, slow-mo):

```bash
PWDEBUG=1 uv run --group test pytest tests/integration/test_fe_swap.py -x
```

## Stack

- **Backend:** Python 3.13, Flask, Flask-SQLAlchemy, SQLite (EVE SDE, read-only)
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS
- **Async:** Celery + Redis (hourly ESI polling)
- **Intel:** zKillboard Statistics API, ESI sovereignty/kills/jumps
- **Deps:** uv (Python), npm (frontend)
