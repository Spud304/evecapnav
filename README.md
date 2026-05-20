# EVE CapNav

Capital ship jump route planner for EVE Online. No login required — plan safe routes through hostile space with fatigue tracking, fuel costs, threat intel, and safe spot analysis.

## Features

- **Bicriterion (cost + fatigue) multi-label Dijkstra pathfinder.** Each search label carries `(cost, fatigue, cooldown, …)`; non-dominated labels per system are retained so the search can trade "wait longer at X" against "different topology via Y." Single-criterion A* kept as a horizon seed and no-route fallback.
- **Routing modes**: Safe (avoids danger), Direct (shortest), POS Hopping (prefers moon-rich systems). Plus mixed JD + stargate routing (off / inter-regional shortcuts / all gates).
- **"Quickest ⇄ Least jumps" slider** controls the `wait_weight` parameter — tolerate fatigue waits to use fewer JD hops, or avoid waits and accept more total hops. Per-hop overhead scales with wait_weight so the search biases topology too, not just wait time.
- **Interactive star map** — canvas-rendered EVE galaxy with pan/zoom, region labels tinted by dominant sov holder, alliance/faction-colored system dots with security-band edge rings, hover tooltips, click-anywhere-to-pan, auto-zoom-to-fit on a planned route, and color-coded route overlay (cyan = gate hop, green = JD hop) with endpoint markers.
- **Search-and-pan-to-system** — picking an origin or destination from the autocomplete also pans the map there.
- **Total-hop breakdown** — the route summary distinguishes JD activations from stargate hops.
- **Dead-end system detection** — systems with only 1 stargate are flagged with a "Dead End" pill and penalized in safe mode (one entry/exit = easy to camp).
- **Advanced weight tuning** — configurable base system cost, distance exponent, danger/jumps/activity weights, wait weight, dead-end penalty, moon bonus.
- **Safe spot scoring** — finds the best celestial pair for mid-warp bookmarks, shows distance to nearest probe reference.
- **Sovereignty display** — alliance/faction ownership per system, route avoidance by alliance name.
- **zKillboard threat intel** — active PVPers, group kill ratio, hourly activity patterns per system.
- **Time zone awareness** — suggests quietest jump window based on historical kill patterns.
- **Fuel calculator** with Jump Fuel Conservation skill support.
- **Alternative system selection** — view and swap in different waypoints at each hop.
- **Route sharing** — copy route as text for Discord/Slack, open in Dotlan jump planner.
- **Optional 24h jump history** — uses aggregated jump data from a FastAPI service instead of ESI's hourly snapshot.

## How the pathfinder works

The route planner runs a multi-label Dijkstra over a state of `(system_id,
cost, time, fatigue, cooldown, jump_type, ...)`. At each system the search
keeps every non-dominated label (`A dominates B iff A.cost ≤ B.cost AND
A.fatigue ≤ B.fatigue`), so two distinct ways of reaching a system can
both survive if they trade off differently. This is what enables routes
like "take a longer LY jump now to avoid compounding fatigue later" or
"take a regional gate here to skip three JD hops."

Cost model per edge:

| Edge type | Cost contribution |
|---|---|
| Jump-drive (LY hop) | `distance^1.5` + danger + `wait_weight × fatigue_excess` + `wait_weight × HOP_OVERHEAD_FACTOR` |
| Stargate hop | `gate_edge_cost` (or `gate_unit_cost` for intra-region in interregional mode) + `wait_weight × HOP_OVERHEAD_FACTOR` |
| Cooldown wait (mandatory between JDs) | 0 — the JD edge already prices its fatigue contribution |
| Fatigue-decay wait (optional) | `wait_weight × wait_minutes` — emitted only when fatigue > 10 min and a JD is next |

`HOP_OVERHEAD_FACTOR` (defaults to 100 in `src/constants.py`) is what
makes the Quickest⇄Least-jumps slider actually bias topology: at high
wait_weight, every hop has a large fixed overhead so the search prefers
routes with fewer total hops; at low wait_weight, only edge base costs
matter.

Edges are gated by EVE mechanics: a JD edge is only valid when
`est_cooldown_min ≤ 0` (the search must take a cooldown wait first), and
gate hops don't change fatigue at all. See the
[`src/pathfinder/`](src/pathfinder) package: `multi_label.py` holds
`_find_route_multi_label` (the algorithmic core), `single_criterion.py`
holds the legacy A* fallback, and `dispatcher.py`'s `find_route` is the
public entry point that runs multi-label first and falls back to
single-criterion A* if no route is found.

## Project layout

The backend follows a layered architecture so each concern has one
obvious home:

```
src/
├── api/           Thin HTTP controllers — parse request, delegate, return JSON
├── services/      Orchestration + business logic, owns in-memory state
├── pathfinder/    Pathfinding algorithm package (multi_label, single_criterion,
│                  graph_builder, diagnostics, cost, types, dispatcher)
├── stores/        Data access — SDE reads + local cache.sqlite
├── clients/       External HTTP clients (ESI, zKillboard)
├── schemas/       Pure dataclasses (SystemInfo, RouteStep, ShipClass, …)
├── models/        SQLAlchemy ORM mapping for the EVE SDE
├── tasks/         Celery background jobs (hourly ESI polling)
├── constants.py   METERS_PER_LY, HOP_OVERHEAD_FACTOR, DEAD_END_PENALTY, …
├── application.py Flask app subclass
├── celery_app.py  Celery wiring
└── main.py        Entry point — builds app, registers blueprints, starts dev server
```

Dependency direction: `api → services → stores + clients + pathfinder →
schemas + models + constants`. `schemas/` imports nothing from `src.*`.
A handful of top-level shims (`systems.py`, `jump_graph.py`, `cache.py`,
`esi.py`, `zkill.py`, `routes.py`) re-export from the new layered paths
so older test imports keep working.

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
uvx ty check                                       # Type check (ty)
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
