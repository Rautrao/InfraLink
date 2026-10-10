# Demo deployment

## Render (recommended)

1. Push this repository to GitHub and connect it to Render as a Blueprint using `render.yaml`.
2. Sync the Blueprint. It creates the PostGIS database, API, and Next.js web service; Render terminates HTTPS for each `onrender.com` URL.
3. Confirm service URLs. If Render assigns different names/URLs, update API `CORS_ORIGINS` to the exact frontend origin and frontend `API_SERVER_ORIGIN` to the API origin, then redeploy both. Keep `NEXT_PUBLIC_API_BASE=/api/v1` (same-origin browser requests proxy through Next.js).
4. Wait for `/healthz` on both services. The API startup runs schema setup and `make seed` before it accepts traffic. `make seed` is safe to rerun; the demo reset removes demo work activity and re-seeds it.
5. Use HTTPS URL for the portal. The app intentionally keeps `DEV_MODE=true` and `NEXT_PUBLIC_DEV=true` for this demo; the visible banner is the warning. Never expose real resident data or reuse demo passwords.

Render Postgres supports PostGIS. The Blueprint uses paid starter web instances, a small paid Postgres plan, and a persistent API upload disk; review the cost in Render before applying. Render Free services spin down after 15 idle minutes, lose local files, and Free Postgres expires after 30 days and does not provide backups; they are not appropriate for this persistent demo. [Render Free limitations](https://render.com/docs/free), [PostGIS extensions](https://render.com/docs/postgresql-extensions), and [Blueprints](https://render.com/docs/infrastructure-as-code).

## Environment variables

| Variable | Purpose | Demo value / guidance |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy database connection | Compose uses PostGIS; Render injects its internal PostgreSQL URL |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Local Compose database | Use a long random password outside local development |
| `JWT_SECRET` | Signs authentication tokens | Use a generated random secret; Render generates one |
| `CORS_ORIGINS` | Exact allowed browser origin(s) | `https://<your-frontend>.onrender.com`; no wildcard |
| `DEV_MODE` | Enables `/api/v1/dev/advance-time` and `/dev/reset-seed` | `true` only for the isolated demo; set `false` outside demo |
| `NEXT_PUBLIC_DEV` | Builds visible Demo mode banner and demo OTP hint | `true` for demo only |
| `NEXT_PUBLIC_API_BASE` | Browser API base | `/api/v1`; preserve same-origin proxying |
| `API_SERVER_ORIGIN` | Next.js server-side API rewrite target | Render API URL; Compose uses `http://backend:8000` |
| `UPLOAD_DIR` | Uploaded evidence/feedback files | `/data/uploads`; attach persistent storage in hosted deployments |
| `SITE_ADDRESS` | Caddy site address for Compose deployment | `:80` for plain HTTP; set a real domain for automatic HTTPS |

Render auto-provisions certificates for Render domains. For a single VPS, `compose.prod.yaml` includes Caddy: point DNS at the server, set `SITE_ADDRESS=demo.example.org`, and open ports 80/443; Caddy obtains and renews HTTPS certificates. If no domain is available, use `SITE_ADDRESS=:80` and HTTP only. Do not put a domain into CORS until DNS points to the frontend.

## Health, rate limits, logs, backup, reset

- `GET /healthz` checks API/database readiness; frontend `/healthz` checks the portal process.
- API responses include `X-Request-ID`; structured request logs include method, path, status, duration, and client address. Send a UUID `X-Request-ID` to correlate a request.
- In-memory per-instance limits: OTP request `5 / 15 minutes` per client address; feedback submission `10 / hour`. Keep one API instance for this demo (limits are not shared across replicas).
- Backup local Compose: `make backup` (custom-format `pg_dump` under `backups/`). For Render, run `DATABASE_URL='<external Render URL>' ./scripts/db_backup.sh backups/render.dump` from a machine with `pg_dump` installed; protect the external URL and dump. Render managed backup availability depends on the database plan.
- Reset in under 30 seconds: `make demo-reset` locally, or `DEMO_API_BASE=https://<api>.onrender.com/api/v1 sh ./scripts/demo_reset.sh`. The script calls the demo-only reset endpoint, clears demo activity, resets simulated time, and recreates seed records. It preserves city/reference setup and the audit chain. Keep it private; `DEV_MODE=true` intentionally does not require authentication for demo controls.

## One VPS alternative

Install Docker Engine and Compose, clone the repo, copy `.env.example` to `.env`, set strong `POSTGRES_PASSWORD`/`JWT_SECRET`, `DEV_MODE=true`, `NEXT_PUBLIC_DEV=true`, exact `CORS_ORIGINS`, and `SITE_ADDRESS`. Run `make prod-up`; the API waits for Postgres, initializes schema, and executes the seed command at startup. Caddy routes `/api`, `/files`, and `/healthz` to FastAPI and the rest to Next.js. Keep only ports 80/443 public; the database and app containers are not published.

## Backups and recovery

`make backup` (or `sh ./scripts/db_backup.sh <file>`) uses `pg_dump --format=custom`. Restore to a compatible PostGIS database with `pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" <file>`. Test a restore before relying on backups; file uploads live separately from PostgreSQL and need their own volume backup.
