# EVE CapNav

Capital ship jump route planner for EVE Online. No login required — plan safe routes through hostile space with fatigue tracking, fuel costs, threat intel, and safe spot analysis.

## Features

- **A* pathfinding** with multiple routing modes: Safe (avoids danger), Direct (shortest), POS Hopping (prefers moon-rich systems)
- **Jump fatigue simulation** with optimized wait time suggestions
- **Safe spot scoring** — finds the best celestial pair for mid-warp bookmarks, shows distance to nearest probe reference
- **Sovereignty display** — shows alliance/faction ownership per system, route avoidance by alliance name
- **zKillboard threat intel** — active PVPers, group kill ratio, hourly activity patterns per system
- **Time zone awareness** — suggests quietest jump window based on historical kill patterns
- **Fuel calculator** with Jump Fuel Conservation skill support
- **Alternative system selection** — view and swap in different waypoints at each hop
- **Route sharing** — copy route as text for Discord/Slack

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

## Stack

- **Backend:** Python 3.13, Flask, Flask-SQLAlchemy, SQLite (EVE SDE, read-only)
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS
- **Async:** Celery + Redis (hourly ESI polling)
- **Intel:** zKillboard Statistics API, ESI sovereignty/kills/jumps
- **Deps:** uv (Python), npm (frontend)
