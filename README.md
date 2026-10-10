# Public Works Tracker

Public Works Tracker is a web application for making city infrastructure projects easier to find, understand, coordinate, and monitor. Residents can explore public works, follow projects, and send feedback. City staff can manage projects and permits, coordinate work between organizations, and track responses to residents.

This repository contains the resident website, staff console, field interface, API, database setup, and sample data for a Demo City.

## Live demo

- **Deployed website:** [Public Works Tracker](https://infra-link-three.vercel.app/.)
- **Demo video:** [Watch the project walkthrough](https://drive.google.com/file/d/15dTR383QvSFZUwbyqaa6qNokfG0CksrM/view?usp=sharing)

For a better audio experience, please use earphones while watching the demo video.

## Contents

- [What the project does](#what-the-project-does)
- [Who uses it](#who-uses-it)
- [Main features](#main-features)
- [Technology](#technology)
- [Run it from scratch](#run-it-from-scratch)
- [Demo accounts](#demo-accounts)
- [Useful links and commands](#useful-links-and-commands)
- [Project layout](#project-layout)
- [Data and demo behavior](#data-and-demo-behavior)
- [Troubleshooting](#troubleshooting)
- [Deployment and security](#deployment-and-security)

## What the project does

Cities often have several departments and utility organizations working on nearby streets. Residents may not know which organization is responsible, when work is scheduled to finish, or where to report a problem. City staff may also need to spot overlapping projects before they cause avoidable disruption.

This project provides a shared place to:

1. Publish public works, locations, schedules, progress, and disruptions.
2. Help residents discover projects and send reports or feedback.
3. Help staff track delivery, permits, evidence, and resident responses.
4. Flag projects that overlap in both location and time, and record how staff coordinate them.
5. Provide downloadable public data and city-wide summaries.

## Who uses it

### Residents

Residents can use the public website without signing in to browse projects and public information. Signing in enables resident actions such as following projects or wards and sending feedback.

### City and utility staff

Staff sign in at `/staff/login`. Their role controls which records and actions they can access. Roles in the demo include administrator, commissioner, engineering staff, utility editor, contractor, traffic police, and auditor. Some staff access is limited to a ward, zone, or organization.

### Field staff

The field interface at `/field` is designed for staff using the application away from a desk. It can cache work data and queue supported updates and evidence while offline, then synchronize the queue when a connection is available.

## Main features

### Public website

- **Home page:** City overview, summary figures, and links into the public project information.
- **Map and list:** Browse public works geographically or as a searchable list.
- **Search and filters:** Narrow projects by text, status, ward, work type, department, or delay where available.
- **Project details:** View project purpose, location, responsible department, contractor information intended for public display, dates, progress, milestones, updates, photos, and reported disruptions.
- **Schedule and progress history:** View project updates and date changes where they have been recorded.
- **Nearby coordination information:** See related nearby work or coordination notices when available.
- **Ward pages:** View work and summary information for a ward.
- **Public dashboard:** Review city-level counts, status summaries, and other public reporting.
- **Open data:** Download public works data as CSV or GeoJSON and view a JSON statistics feed.
- **Privacy page:** Read the service privacy information.
- **English and Hindi:** Switch the interface language using the language control.
- **Low data mode:** Hide selected data-heavy map or image content to make the site lighter to use.

### Resident account features

- **OTP login:** Residents sign in using their registered mobile number and a one-time code.
- **Follow projects or wards:** Subscribe to updates for selected work or locations.
- **Notifications:** View notifications related to followed items and mark them as read.
- **My feedback:** View reports and questions submitted by the signed-in resident.
- **Project feedback:** Send an observation, question, or complaint about a work. Optional photos and location details are supported where the form allows them.
- **Still ongoing confirmation:** Residents can report whether a project appears to still be active.

### Staff console

The staff workspace is under `/staff` and has its own sign-in page at `/staff/login`.

- **Operations dashboard:** Summary cards for delayed work, overdue updates, open conflicts, feedback awaiting action, and repeat-dig segments.
- **Charts and hotspots:** Review work by status or department and highlight repeat-dig road segments on a map.
- **Staff inbox:** Bring work, feedback, and conflict items needing attention together.
- **Project management:** Browse projects, create work records, update project details, post progress updates, and manage status and schedules according to staff permissions.
- **Milestones and date history:** Maintain project milestones and record schedule changes with reasons and notes.
- **Permits:** Review permits and record decisions. Permit status can be held while coordination is needed.
- **Conflict coordination:** Detect overlapping work and recently resurfaced roads, inspect related projects, and record decisions and explanations.
- **Feedback management:** Review resident reports, respond, moderate public feedback where appropriate, and follow escalation status.
- **Bulk import:** Download a works import template and upload project data for staff workflows.
- **Audit history:** Review and verify recorded administrative actions.
- **City configuration:** Authorized staff can manage selected city settings, such as coordination buffers and reporting configuration.
- **Role and jurisdiction checks:** Staff access is checked against their role and, for scoped roles, their ward, zone, or organization.

### Conflict detection and resolution

The conflict scanner looks for two main situations:

1. **Work overlap:** Two projects have intersecting schedules and their mapped work areas intersect or fall within the configured distance buffer.
2. **Recent resurfacing:** A new project is close to a recently resurfaced road within the configured lookback period.

An alert lets staff compare the projects and record one of these outcomes: coordinate dates, reschedule one project, combine work, or document why both should proceed. Decisions are stored with a note and appear in the conflict history. The system flags potential conflicts; it does not automatically choose which organization must move its work.

Conflict checks run after relevant project or permit events and in a nightly scan. Staff can also request a scan from the staff conflict workflow.

### Field interface

The field page at `/field` provides a work list, search and status filtering, cached work data, an offline indicator, and a synchronization queue for supported work updates and evidence. Browser storage is used for local caching and queued submissions. For best results, sign in and load the data while online before demonstrating offline use.

## Technology

| Part | Technology | Purpose |
| --- | --- | --- |
| Resident website and staff console | Next.js 14, React, TypeScript | User interface and browser application |
| Maps and charts | MapLibre GL, Recharts | Project maps, hotspot maps, and dashboard charts |
| API | Python 3.11, FastAPI, Pydantic | Authentication, project workflows, reports, and data endpoints |
| Database | PostgreSQL 16 with PostGIS | Project, account, audit, and geographic data |
| Local orchestration | Docker Compose | Starts the database, API, website, and mock API |
| Offline field storage | Browser IndexedDB | Cached works and queued field submissions |

## Run it from scratch

### Requirements

Install:

- Git
- Docker Desktop with Docker Compose enabled (Windows or macOS), or Docker Engine and the Compose plugin (Linux)
- A web browser

The standard local setup runs the frontend, backend, and database in Docker. You do not need to install Node.js or Python on your computer for this setup.

### 1. Get the project

Clone the repository and enter its folder:

```bash
git clone https://github.com/Rautrao/InfraLink.git
cd InfraLink
```

If you already have the project folder, open a terminal in that folder instead.

### 2. Create your local environment file

Copy the example environment file:

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**macOS or Linux**

```bash
cp .env.example .env
```

The example values are for local development. For a local demo, you can start with them. If you change the PostgreSQL password, update both `POSTGRES_PASSWORD` and the password in `DATABASE_URL` in `.env` so they match. Replace `JWT_SECRET` with a long random value before using the app outside a private local demo.

### 3. Build and start the services

From the repository root, run:

```bash
docker compose up --build
```

Keep this terminal open. The first build may take a few minutes while Docker downloads images and installs application dependencies. The API creates the database schema when it starts.

### 4. Add the sample city and demo accounts

Open a second terminal in the repository folder and run:

```bash
docker compose exec -T backend make -C /app seed
```

This adds sample organizations, wards, zones, staff and resident accounts, and public works. The seed command is designed to be safe to run again.

### 5. Open the application

- Resident website: [http://localhost:3000](http://localhost:3000)
- Staff login: [http://localhost:3000/staff/login](http://localhost:3000/staff/login)
- API health: [http://localhost:8000/healthz](http://localhost:8000/healthz)
- Interactive API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Mock API (optional): [http://localhost:4000/works](http://localhost:4000/works)

The API health endpoint should return `{"status":"ok"}` when the API can reach the database.

### 6. Stop the application

In the terminal running Docker Compose, press `Ctrl+C`. Then stop the containers with:

```bash
docker compose down
```

The normal `down` command preserves database and upload volumes, so your local data remains for the next run. To start again later, use `docker compose up`.

> **Warning:** `docker compose down -v` deletes the local database and uploaded files stored in Docker volumes. Use it only when you intentionally want to erase local demo data.

## Demo accounts

### Staff

Seeded staff accounts use the password `demo1234`:

| Account | Role / scope |
| --- | --- |
| `admin@demo.city` | Administrator |
| `commissioner@demo.city` | Commissioner |
| `ce.roads@demo.city` | Chief engineer |
| `se.roads@demo.city` | Superintending engineer, Zone 1 |
| `ee.roads@demo.city` | Executive engineer, Zone 1 |
| `ae.ward1@demo.city` | Assistant engineer, Ward 1 |
| `je.ward1@demo.city` through `je.ward4@demo.city` | Junior engineer, matching ward |
| `utility.water@demo.city` | Utility editor, Water & Sewer Board |
| `contractor@demo.city` | Contractor |
| `traffic.police@demo.city` | Traffic police |
| `auditor@demo.city` | Auditor |

Open `/staff/login` and use one of these accounts. Choose an account matching the workflow you want to demonstrate; scoped accounts may not see every record or action.

### Residents

The seed creates resident phone numbers `9000000001` through `9000000005`. Request an OTP on the resident login page and use `123456` in this local demo.

The OTP is hard-coded for demo use and is not suitable for production authentication.

## Useful links and commands

Run these commands from the repository root:

| Command | What it does |
| --- | --- |
| `docker compose up --build` | Build and start the local stack |
| `docker compose up` | Start the stack after it has already been built |
| `docker compose down` | Stop containers and preserve named data volumes |
| `docker compose exec -T backend make -C /app seed` | Add or refresh seeded demo/reference data |
| `docker compose exec backend pytest` | Run backend tests |
| `docker compose exec backend python -m app.export_openapi` | Regenerate `backend/openapi.json` |
| `make demo-reset` | Reset demo project activity and reseed data (requires `make` on the host) |
| `make backup` | Create a local database backup (requires `make` and the backup script's tools) |

If the host does not have `make`, use Docker Compose directly for seeding and tests as shown above. Deployment and backup details are in [DEPLOYMENT.md](DEPLOYMENT.md).

## Project layout

```text
.
├── backend/                 FastAPI API, SQL schema, seed data, and backend tests
│   ├── app/modules/         API features grouped by domain
│   ├── seed/                Demo city and account data
│   ├── sql/                 PostgreSQL/PostGIS schema
│   └── tests/               Backend tests
├── frontend/                Next.js public website, staff console, and field interface
│   ├── app/                  Routes and page components
│   ├── components/           Shared UI and staff navigation
│   └── lib/                  API client, language, and preferences
├── mock/                     Lightweight mock API service
├── scripts/                  Backup and demo reset helpers
├── docker-compose.yml        Local development stack
├── compose.prod.yaml         Single-server deployment stack
├── render.yaml               Render deployment blueprint
├── .env.example              Example local environment settings
├── Makefile                  Common development and operations shortcuts
└── DEPLOYMENT.md             Hosting, environment, backup, and deployment notes
```

The API is grouped into modules for identity, organizations, project registry, schedules and milestones, audit, city configuration, imports, geographic features, permits, conflict coordination, evidence, resident feedback, notifications, reports, and open data.

## Data and demo behavior

- The seed creates a Demo City tenant, departments, wards, zones, demo staff and resident accounts, and example projects.
- Some sample projects are deliberately arranged to demonstrate overlapping schedules, recent resurfacing, and repeat-dig reporting.
- The database and uploaded files are stored in Docker named volumes.
- `DEV_MODE=true` enables demo-only API controls for advancing simulated time and resetting demo data. Do not expose these controls on a public production service.
- `NEXT_PUBLIC_DEV=true` displays a demo-mode banner and the development OTP hint in the resident login interface.
- Demo accounts and passwords are public in this repository by design. Use only in a local or isolated demo environment.
- Public endpoints are intended to return public project information. Staff endpoints require an access token and enforce role or jurisdiction checks.

## Troubleshooting

### Docker says a port is already in use

Ports `3000`, `4000`, `5432`, and `8000` are used by the local services. Stop the application using the port, or update the corresponding port mapping in `docker-compose.yml`.

### The website opens, but there is no project data

Confirm the database and API containers are running, then run the seed command:

```bash
docker compose exec -T backend make -C /app seed
```

Refresh the page after the seed completes.

### Staff or resident login does not work

Confirm that seeding completed. Use one of the listed accounts exactly as shown. Staff use password `demo1234`; residents use one of the seeded phone numbers and OTP `123456` in local demo mode.

### The API is not ready

Check the service logs:

```bash
docker compose logs --tail=100 db backend
```

The backend waits for the database health check before starting. If database credentials were changed in `.env`, make sure `POSTGRES_PASSWORD` and `DATABASE_URL` still agree. If this is a fresh setup and old data is not needed, see the volume warning under [Stop the application](#6-stop-the-application).

### Rebuild after changing dependencies or Docker configuration

Stop the stack, then rebuild it:

```bash
docker compose down
docker compose up --build
```

## Deployment and security

For hosting instructions, environment variable details, HTTPS setup, backups, and deployment options, read [DEPLOYMENT.md](DEPLOYMENT.md).

The included credentials, fixed OTP, development defaults, and demo controls are for development and isolated demonstrations only. Before a real deployment, configure strong secrets, disable demo mode, use a production authentication and OTP delivery setup, protect backups and uploaded files, and review the deployment guidance.
