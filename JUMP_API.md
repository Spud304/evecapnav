# EVE System Jump History API

REST API serving historical and current EVE Online system jump data. Runs on my homelab via systemd, accessible to any device on the Tailscale network.
Purpose of this is to allow other users to try and create their own historical data repo that can plug into this tool by having the spec it conforms to

**Base URL:** `http://<tailscale-host>:8001`

Source: [evesystemhistoricaldata](../evesystemhistoricaldata/)

## Configuration

Set these environment variables in evecapnav to use this API instead of ESI:

```env
JUMP_DATA_SOURCE=fastapi
JUMP_API_URL=http://<tailscale-host>:8001
```

Default is `JUMP_DATA_SOURCE=esi` (direct ESI calls, no change to existing behavior).

---

## Endpoints

### `GET /api/jumps/current`

Returns the most recent hourly snapshot. This is the endpoint evecapnav calls when `JUMP_DATA_SOURCE=fastapi`.

**Response Headers:**
- `X-Snapshot-Timestamp` — ISO 8601 UTC timestamp of the snapshot

**Response Body:**
```json
{
  "30000142": 1666,
  "30002187": 56,
  "30003045": 789
}
```

String-keyed system IDs mapping to integer jump counts. evecapnav converts these to `dict[int, int]` via `fetch_system_jumps_from_api()`.

---

### `GET /api/jumps/history`

Returns hourly jump snapshots over a time window.

**Query Parameters:**

| Parameter | Type | Required | Values | Default |
|-----------|------|----------|--------|---------|
| `window` | string | No | `24h`, `72h`, `week` | `24h` |

**Response Body:**
```json
{
  "window": "24h",
  "snapshots": [
    {
      "timestamp": "2026-03-23T04:44:32+00:00",
      "systems": {
        "30000142": 1666,
        "30002187": 56
      }
    },
    {
      "timestamp": "2026-03-23T05:44:28+00:00",
      "systems": {
        "30000142": 1432,
        "30002187": 71
      }
    }
  ]
}
```

- `snapshots` — array of hourly snapshots, sorted oldest-first
- Each snapshot contains all systems with non-zero jumps for that hour
- `window=24h` returns up to 24 snapshots, `72h` up to 72, `week` up to 168

---

### `GET /api/jumps/system/{system_id}`

Returns hourly jump history for a single system.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `system_id` | integer | EVE solar system ID (e.g. `30000142` for Jita) |

**Query Parameters:**

| Parameter | Type | Required | Values | Default |
|-----------|------|----------|--------|---------|
| `window` | string | No | `24h`, `72h`, `week` | `24h` |

**Response Body:**
```json
{
  "system_id": 30000142,
  "window": "24h",
  "data": [
    {"timestamp": "2026-03-23T04:44:32+00:00", "ship_jumps": 1666},
    {"timestamp": "2026-03-23T05:44:28+00:00", "ship_jumps": 1432}
  ]
}
```

---

## Data Source

- **Current data:** Polled hourly from ESI `GET /v1/universe/system_jumps/` via cron
- **Historical data:** Bulk imported from [EVE Ref](https://data.everef.net/system-jumps/) (2017–present)
- **Storage:** SQLite (WAL mode) — concurrent reads are not blocked by writes
- **Typical snapshot:** ~4,700 systems with non-zero jumps per hour
