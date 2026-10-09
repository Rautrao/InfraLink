# Public Works Transparency & Coordination Platform
## 24-Hour Hackathon Prompt Pack: Ambadas, Aayushya, Hitesh

Each person pastes **Section 3 (Shared Contract)** into their AI coding assistant first, then pastes **their own prompt** (Section 5, 6 or 7). Run the prompts in the order given in Section 2.

---

## 1. What we are building (one paragraph)

A web platform where municipal departments, utilities and contractors **register road/drain/pipeline works** (with map geometry, dates, contractor, contact), the system **detects overlaps and recently-resurfaced roads**, and residents see **a public map + list + detail page**, can **follow works**, and **give project-linked feedback** that **auto-escalates up the Indian engineering hierarchy** (JE → AE → EE → SE → CE → Commissioner). **Key adoption lever (from the reference study):** registering a work in the platform is a *precondition* for a road-cut permit (London Works / Street Manager idea). The data stays fresh because agencies need it to get permission.

### What we borrowed from each reference
| Reference | Borrowed idea |
|---|---|
| PM GatiShakti | Multi-agency layers on one map before work starts |
| DoT / Sanchar RoW portal | Single-window Right-of-Way permit for utilities with timelines |
| BBMP citizen view / Vigeye GPMS | Geo-tagged, timestamped photo evidence of progress |
| MCGM roads public dashboard | Contract-wise public status and progress |
| London Works / Street Manager | Permit-first registry, public map is a by-product |
| Swachh.city | Complaint ticket with reference number, SLA timer, auto-escalation upward |

### Features beyond the 8 must-haves (added because the problem statement needs them)
1. **Permit-gated registration** (road-cut / RoW permit, restoration deposit, Traffic Police closure NOC). Permit is held in `pending_coordination` while a conflict is undecided.
2. **Restoration Verified** status (a dug road is finished only when restoration is verified).
3. **Derived "Delayed"** status plus **"Update overdue"** badge (no update in N days).
4. **Resident "Still ongoing?" confirmations** as a cross-check on stale agency data.
5. **Repeat-dig metric**: road segments dug 2+ times in 12 months.
6. **Hash-chained append-only audit log** (tamper-evident).
7. **Bulk import** (CSV / GeoJSON) so agencies don't retype work orders.
8. **Field PWA**: offline photo queue, geotag, EXIF check.
9. **Privacy**: strip EXIF GPS from public photos, hide phone numbers, moderated public feedback.
10. **English + Hindi** UI toggle, low-bandwidth friendly, accessible (WCAG basics).
11. **Open data**: GeoJSON / CSV public API.
12. **Demo "time machine"** (`/dev/advance-time`) so the 3/7/14-day escalation can be shown live in 2 minutes.
13. **Per-city admin config** (buffer metres, lookback months, SLA days, reason codes).

---

## 2. Who runs what, and in what order (24-hour plan)

| Person | Owns | Why this split |
|---|---|---|
| **Ambadas** | Platform + Core backend (auth, orgs, works, schedule revisions, audit, events, seed, bulk import) **and** Staff Work Form + Field PWA | He builds the spine everyone else depends on, so he goes first |
| **Aayushya** | Coordination + Accountability backend (geo-conflict engine, permits, evidence upload, feedback + SLA escalation, notifications, reporting, open data API) **and** Staff Console pages (conflicts, permits, feedback inbox, staff dashboard) | Pure domain logic plus the staff screens that use it |
| **Hitesh** | **Entire public resident portal** (map, list, detail, feedback, follow, public dashboard, i18n, OTP login) | Largest UI surface; works against mock data until the APIs land |

### Timeline

| Hour | Who | Action |
|---|---|---|
| **H0 to H1** | **Ambadas** | Run **Prompt 5.0 (Scaffold)**: repo, docker, DB schema, auth stub, mock server, OpenAPI. Aayushya and Hitesh **do not code yet**; they read the contract, install tools, and pull the repo when Ambadas pushes. |
| **H1 to H9** | All three in parallel | Ambadas: **Prompt 5.1**. Aayushya: **Prompt 6.1**. Hitesh: **Prompt 7.1** |
| **H9** | All | **Checkpoint 1**: merge, run `docker compose up`, run the smoke test (Section 8) |
| **H9 to H17** | All three in parallel | Ambadas: **Prompt 5.2**. Aayushya: **Prompt 6.2**. Hitesh: **Prompt 7.2** |
| **H17 to H20** | All | **Checkpoint 2**: full integration, fix contract mismatches, seed data check |
| **H20 to H22** | Hitesh + Ambadas polish, Aayushya deploy | **Prompt 8 (Integration/Polish)** and **Prompt 9 (Deploy)** |
| **H22 to H24** | All | Demo rehearsal (Section 10), record backup video, README |

**Git rules:** trunk-based, branches `ambadas/*`, `aayushya/*`, `hitesh/*`, merge to `main` at least every 2 hours, never edit another person's folder (see ownership in contract).

---

## 3. SHARED CONTRACT (everyone pastes this first)

> Copy everything between the lines into your AI assistant as the first message, before your personal prompt.

```
===== SHARED CONTRACT: DO NOT DEVIATE =====

PROJECT: Public Works Transparency & Coordination Platform for an Indian city (demo tenant "Demo City", Pune-like coordinates, center lat 18.5204, lng 73.8567). Hackathon: 24 hours, 3 developers (Ambadas, Aayushya, Hitesh). Prefer working, demoable code over perfection. No over-engineering. Everything must run with `docker compose up`.

PROBLEM: Residents don't know what road/drain/pipeline work is happening, who is responsible, or when it ends; departments dig the same road repeatedly because they don't coordinate; no easy way to follow up or hold anyone accountable.

---------- STACK (fixed) ----------
- DB: PostgreSQL 16 + PostGIS (image postgis/postgis:16-3.4). Geometry SRID 4326.
- Backend: Python 3.11, FastAPI, SQLAlchemy 2.0 (or psycopg + raw SQL where geo), Pydantic v2, APScheduler for background jobs (run inside the API process), Uvicorn. Modular monolith.
- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind, MapLibre GL JS (OSM raster tiles https://tile.openstreetmap.org/{z}/{x}/{y}.png), TanStack Query, mapbox-gl-draw-compatible drawing via @mapbox/mapbox-gl-draw (works with MapLibre) for drawing road segments. i18n: next-intl or a simple JSON dictionary (en, hi).
- Auth: JWT (HS256) in Authorization: Bearer. Staff = email+password. Resident = mobile OTP (dev OTP always 123456, printed in server log). No Keycloak in the hackathon.
- Files: local disk /data/uploads served at /files/*. (S3 adapter interface exists but local is used.)
- Events: in-process transactional OUTBOX table + background dispatcher + subscriber registry (see EVENTS).
- Everything under tenant_id (single tenant seeded, but every table carries tenant_id).

---------- REPO LAYOUT & OWNERSHIP ----------
/ (monorepo)
  docker-compose.yml, .env.example, README.md, Makefile
  /backend
    /app
      main.py                    [Ambadas]
      /core                      [Ambadas] config, db, security(JWT, RBAC deps), events (outbox+bus), audit, errors, pagination
      /modules
        /identity_access         [Ambadas]
        /organisations           [Ambadas]  (agencies, wards, zones, officers, escalation ladder)
        /project_registry        [Ambadas]  (works + status machine)
        /schedule_milestones     [Ambadas]  (milestones, date revisions, reason codes)
        /audit                   [Ambadas]
        /admin_config            [Ambadas]
        /imports                 [Ambadas]  (CSV/GeoJSON bulk)
        /geo_spatial             [Aayushya] (only module doing geometry maths; Ambadas calls its interface)
        /permits                 [Aayushya]
        /conflict_engine         [Aayushya]
        /evidence                [Aayushya]
        /citizen_feedback        [Aayushya]
        /notifications           [Aayushya]
        /reporting               [Aayushya]
        /public_api              [Aayushya] (open data GeoJSON/CSV)
    /seed                        [Ambadas]
    /sql/001_schema.sql          [Ambadas] (single source of truth for tables)
  /frontend
    /app/(public)/*              [Hitesh]  public portal
    /app/staff/*                 [Aayushya: conflicts, permits, feedback inbox, staff dashboard;  Ambadas: works form/list, import, audit, field PWA]
    /components/ui, /lib/api.ts, /lib/i18n  [Hitesh owns shared UI kit and api client]
  /mock                          [Ambadas] JSON-server style mock of the API for frontend to start on
RULE: do not edit a folder you don't own; ask the owner. Each module = router.py, service.py, schemas.py, repo.py, events.py.
RULE: modules never read another module's tables; call its service interface or react to events.

---------- ROLES & ACCESS ----------
Roles: admin, commissioner, chief_engineer(CE), superintending_engineer(SE), executive_engineer(EE), assistant_engineer(AE), junior_engineer(JE), utility_editor, contractor, auditor, traffic_police, resident.
Jurisdiction: Organisation -> Role -> Jurisdiction (ward_id / zone_id / division_id). RBAC for what, jurisdiction for where.
- JE edits works in own ward; EE sees own division; SE zone; CE/Commissioner whole city.
- utility_editor edits ONLY works of own agency, but can READ all geometries+dates (needed for conflict detection).
- contractor: submits progress + photos on assigned works; JE verifies.
- traffic_police: approves closure NOC. auditor: read-only everything + audit log.
- resident: OTP login; follow, feedback, "still ongoing?" confirm.
Escalation ladder (configurable): JE -> AE -> EE -> SE -> CE -> Commissioner.

---------- DATA MODEL (create in /backend/sql/001_schema.sql; Ambadas owns file, others request additions via PR) ----------
tenant(id uuid pk, name, slug, center geometry)
zone(id, tenant_id, name) ; ward(id, tenant_id, zone_id, name, boundary geometry(MultiPolygon,4326))
agency(id, tenant_id, name, type enum[municipal_roads, water_sewer, electricity, telecom, gas, metro, pwd_nhai, other], short_code)
app_user(id, tenant_id, agency_id null, name, email unique null, phone null, password_hash null, role, ward_id null, zone_id null, active)
escalation_level(id, tenant_id, agency_id null, level int, role) -- default ladder
work(id, tenant_id, ref_no text unique (WRK-2026-00001), title, purpose, category enum[road_cut, resurfacing, water_pipeline, sewer, drainage, electricity, telecom_duct, gas_pipeline, metro, footpath, other],
     status enum[planned, permitted, ongoing, paused, completed, restoration_verified, closed],
     agency_id, contractor_name, contractor_public bool default true, contact_name, contact_phone, contact_email, contact_channel,
     road_name, ward_id, geometry geometry(Geometry,4326) (LineString/Polygon), length_m,
     planned_start date, original_target_end date, current_target_end date, actual_start date, actual_end date,
     pct_complete int 0-100, disruption_type enum[none, restricted_access, partial_closure, full_closure], disruption_note,
     is_public bool default true, public_flags jsonb, resurfaced_on date null,
     last_update_at timestamptz, restoration_verified_at timestamptz null, created_by, created_at, updated_at)
work_milestone(id, work_id, name, planned_date, actual_date, pct int, sort int)
work_date_revision(id, work_id, old_target, new_target, reason_code, explanation, by_user, at)  -- NEVER overwritten
work_status_history(id, work_id, from_status, to_status, reason_code, explanation, by_user, at)
work_update(id, work_id, text, pct_complete, by_user, at, is_public bool default true)  -- progress notes
evidence(id, work_id, work_update_id null, file_path, public_path (EXIF-stripped), taken_at, lat, lon, exif_ok bool, uploaded_by, verified_by null, verified_at null, kind enum[progress, restoration, before, after])
permit(id, tenant_id, work_id, type enum[road_cut, row_utility, closure_noc], status enum[draft, submitted, pending_coordination, approved, rejected, held, expired],
       applied_at, approved_by, approved_at, deposit_amount numeric, deposit_status enum[none, held, released, forfeited], valid_from, valid_to, note)
conflict_alert(id, tenant_id, work_a, work_b, type enum[overlap, recent_resurfacing], overlap_days int null, days_since_resurfacing int null, distance_m numeric, status enum[open, resolved], detected_at, detected_by enum[submission, nightly_scan])
conflict_decision(id, alert_id, action enum[coordinate_dates, combine_work, reschedule, justify_both], note, decided_by, at)
feedback_ticket(id, tenant_id, ref_no (FB-2026-000123), work_id, resident_id, kind enum[question, complaint, observation, still_ongoing_yes, still_ongoing_no],
       text, photo_path null, lat null, lon null, status enum[open, acknowledged, in_progress, resolved, closed], current_level int default 1 (index into ladder),
       assigned_to, is_public bool default false, moderation enum[pending, approved, rejected], created_at, last_response_at null, escalated_at null)
ticket_event(id, ticket_id, status, responder_id null, message, is_public bool, at)
follow_subscription(id, resident_id, work_id null, ward_id null, channel enum[sms, whatsapp, email, push, console], active)
notification(id, user_id, work_id null, kind, title, body, link, channel, status enum[queued, sent, suppressed], dedupe_key, created_at, sent_at)
outbox_event(id bigserial, tenant_id, type text, version int, payload jsonb, created_at, published_at null)
audit_log(id bigserial, tenant_id, actor_id, action, entity, entity_id, before jsonb, after jsonb, at, prev_hash, hash)  -- hash = sha256(prev_hash || canonical json); append-only (no UPDATE/DELETE grants; trigger to block)
city_config(tenant_id pk, buffer_m default 15, lookback_months default 24, overdue_days default 7, sla_day_ae default 3, sla_day_ee default 7, sla_day_se default 14, sla_time_scale default 1, reason_codes jsonb, features jsonb)
Indexes: GiST on work.geometry and ward.boundary; GiST on daterange(planned_start, current_target_end) (expression index); btree on status, agency_id, ward_id.

REASON CODES (default list): weather, material_delay, contractor_delay, utility_clash, permit_delay, funds_delay, design_change, public_safety, court_order, force_majeure, other.

---------- STATUS STATE MACHINE (Ambadas enforces in project_registry) ----------
planned -> permitted -> ongoing -> completed -> restoration_verified -> closed
ongoing <-> paused (paused requires reason_code + explanation)
planned/permitted -> paused allowed. completed requires pct_complete=100. restoration_verified requires >=1 evidence of kind=restoration. closed only from restoration_verified.
"delayed" is DERIVED (never stored): today > current_target_end AND status NOT IN (completed, restoration_verified, closed).
"update_overdue" is DERIVED: now - last_update_at > overdue_days AND status IN (ongoing, permitted, paused).
Changing current_target_end after creation REQUIRES reason_code + explanation -> inserts work_date_revision; original_target_end is immutable; old dates always shown publicly.
Every state change -> work_status_history + audit_log + outbox event.

---------- EVENTS (versioned; written to outbox in SAME DB transaction as the change) ----------
WorkCreated.v1, WorkUpdated.v1, WorkStatusChanged.v1, WorkDatesRevised.v1, ClosureAdded.v1,
ConflictDetected.v1, ConflictResolved.v1, PermitSubmitted.v1, PermitApproved.v1, PermitHeld.v1,
FeedbackSubmitted.v1, FeedbackEscalated.v1, FeedbackResponded.v1, EvidenceAdded.v1, RestorationVerified.v1, UpdateOverdue.v1
Payload always includes: event_id, tenant_id, work_id (if any), actor_id, occurred_at, plus event-specific fields. New fields additive only.
Bus API (backend/app/core/events.py [Ambadas]):  emit(session, type, payload)  -> inserts outbox row;  @subscribe("WorkCreated.v1") def handler(event) ;  dispatcher runs every 2s, marks published_at.

---------- API (base /api/v1, JSON, ISO dates, GeoJSON for geometry; OpenAPI at /docs) ----------
Common: pagination ?page=1&page_size=20 -> {items, total, page, page_size}. Errors -> {error:{code,message,details}}.
AUTH [Ambadas]
 POST /auth/login {email,password} -> {access_token, user}
 POST /auth/otp/request {phone} ; POST /auth/otp/verify {phone, otp} -> {access_token, user}
 GET  /auth/me
REFERENCE [Ambadas]
 GET /wards ; GET /agencies ; GET /config/public (reason_codes, categories, statuses, city center)
 GET/PUT /admin/config (admin)
WORKS [Ambadas]  (public reads need no auth and only return is_public works with public fields)
 GET  /works?bbox=&ward_id=&road=&category=&agency_id=&status=&delayed=&q=&page=   -> list (+ derived flags delayed, update_overdue)
 GET  /works/geojson?same filters                                                 -> FeatureCollection for the map (props: id, ref_no, title, status, delayed, category, agency, last_update_at)
 GET  /works/{id}                                                                  -> full detail (see below)
 POST /works (staff)  ;  PATCH /works/{id} (staff)  ;  POST /works/{id}/status {to_status, reason_code?, explanation?}
 POST /works/{id}/dates {new_target_end, reason_code, explanation}                 -> creates revision
 POST /works/{id}/updates {text, pct_complete?}                                    -> progress note, bumps last_update_at
 POST /works/{id}/milestones ; PATCH /milestones/{id}
 GET  /works/{id}/history                                                          -> merged timeline: status history, date revisions, updates, evidence, decisions
 POST /works/import (multipart CSV|GeoJSON) ; GET /works/import/template
 GET  /audit?entity=&entity_id= (auditor/admin/commissioner) ; GET /audit/verify -> {valid:true|false, broken_at}
 WORK DETAIL shape: {id, ref_no, title, purpose, category, status, delayed, update_overdue, agency:{id,name}, contractor_name|null, contact:{name, phone_masked, email, channel},
    road_name, ward:{id,name}, geometry(GeoJSON), length_m, planned_start, original_target_end, current_target_end, date_revisions:[{old,new,reason_code,explanation,at}],
    pct_complete, milestones:[...], disruption:{type,note}, last_update_at, updates:[...], evidence:[{public_url,taken_at,kind}], permits:[summary], nearby_notices:[{kind:'coordinated'|'rescheduled', text, work_ids}],
    still_ongoing:{yes,no,last_confirmed_at}}
GEO [Aayushya]
 POST /geo/check {geometry, planned_start, target_end, exclude_work_id?} -> {conflicts:[...]}  (dry-run used by the staff form before submit)
 GET  /geo/segments/repeat?months=12 -> segments dug 2+ times
CONFLICTS [Aayushya]
 GET /conflicts?status=open|resolved&ward_id= (staff) ; GET /conflicts/{id} -> both works, agencies, schedules, overlap
 POST /conflicts/{id}/decision {action, note, new_dates?{work_id,start,end,reason_code}}
PERMITS [Aayushya]
 POST /permits {work_id,type,deposit_amount,valid_from,valid_to} ; GET /permits?status= ; POST /permits/{id}/submit|approve|reject|hold {note}
 POST /permits/{id}/noc (traffic_police) ; POST /permits/{id}/deposit/release (after restoration verified)
 RULE: POST /permits for road_cut/row_utility REQUIRES an existing registered work with geometry+dates. approve is blocked (409 PENDING_COORDINATION) if an open conflict_alert involves that work.
EVIDENCE [Aayushya]
 POST /works/{id}/evidence (multipart: file, kind, taken_at?, lat?, lon?) -> reads EXIF, strips GPS from public copy
 POST /evidence/{id}/verify (JE+) ; POST /works/{id}/restoration-verify (JE/EE+)
FEEDBACK [Aayushya]
 POST /works/{id}/feedback (resident) {kind,text,photo?,lat?,lon?} -> {ref_no,status}
 GET  /feedback/mine (resident) ; GET /feedback/{ref_no} (owner or staff) -> status history
 GET  /works/{id}/feedback/public -> only moderated public items + responses
 GET  /staff/feedback?status=&awaiting=true&level= ; POST /staff/feedback/{id}/respond {message,status,make_public?} ; POST /staff/feedback/{id}/moderate {approve:bool}
 POST /works/{id}/still-ongoing {value:true|false} (resident)
FOLLOW & NOTIFICATIONS [Aayushya]
 POST /follows {work_id|ward_id, channel} ; DELETE /follows/{id} ; GET /follows/mine
 GET /notifications/mine ; PATCH /notifications/{id}/read
REPORTING [Aayushya]
 GET /reports/summary -> {by_status:{}, by_ward:[], by_agency:[], delayed_count, overdue_updates_count, open_conflicts, repeat_dig_segments, feedback:{open,overdue}}
 GET /reports/delayed ; GET /reports/overdue-updates ; GET /reports/repeat-dig
 GET /staff/inbox -> {unresolved_conflicts:[], feedback_awaiting:[], overdue_updates:[], permits_pending:[]}
OPEN DATA [Aayushya]
 GET /open/works.geojson ; GET /open/works.csv ; GET /open/stats.json   (cached 60s, public fields only)
DEV [Ambadas]
 POST /dev/advance-time {days} -> shifts the app clock offset (core.clock.now()) so SLA escalation/overdue/notification timers can be demoed; POST /dev/reset-seed
 ALL code must use core.clock.now() / today() and never datetime.now() directly.

---------- CONFLICT ENGINE RULES (Aayushya implements; numbers must match) ----------
Spatial: buffer each geometry by city_config.buffer_m (default 15 m, use ST_Transform to EPSG:32643 for metres, then ST_Buffer, ST_Intersects). Date: overlap if ranges [planned_start, current_target_end] intersect; overlap_days = inclusive days.
Resurfacing: for a new/updated work, look for COMPLETED/restoration_verified works with category=resurfacing (or resurfaced_on set) intersecting its buffered geometry within lookback_months (default 24) before planned_start -> type recent_resurfacing, days_since_resurfacing.
Runs: synchronously on work create/update with geometry/date change and on permit submission (instant warning to submitter, never blocks creating the work), plus nightly scan job (and a /dev trigger).
It NEVER auto-cancels or auto-approves. It may put a permit to pending_coordination until a decision is recorded.
Reference example to seed and demo: Work A water board 400 m trench on MG Road 12 Jan-20 Feb; Work B telecom 150 m duct same stretch 10 Feb-5 Mar -> overlap 10 Feb-20 Feb = 11 days; Work C electricity proposed 1 Jun, road resurfaced 15 Mar = 78 days earlier, lookback 24 months -> recent_resurfacing. (Seed uses dates relative to "today" so the demo is live.)

---------- FEEDBACK ESCALATION (Aayushya) ----------
Day 0 ticket created, routed to work's responsible JE (assigned_to = ward JE of the work's agency/ward, fallback contact). Day 3 no staff response -> escalate to AE; day 7 -> EE; day 14 -> SE and flagged overdue on the public dashboard. Each escalation: ticket_event + FeedbackEscalated.v1 + notification to resident ("status changed") + appears in escalated officer's "awaiting response" inbox. Resident always sees full status history. Private text/contact never public; only moderated items published. SLA days come from city_config; sla_time_scale lets us compress time in demo. Scheduler job every 1 minute.

---------- NOTIFICATION RULES (Aayushya) ----------
Triggers (subscribe to events): work starting within 1 day (job), WorkDatesRevised, ClosureAdded / disruption change to closure, work completed/restoration verified, ConflictResolved(coordinated or rescheduled) near a followed area, FeedbackResponded/Escalated to the ticket owner. Each notification has project name, affected location, deep link /works/{id}. Anti-spam: ignore minor edits (typo, pct change <10) ; dedupe_key = user+work+kind+day ; max 1 digest/day per user for non-critical kinds; channels are adapters: console (default), email (SMTP stub), sms/whatsapp (stub logging "DLT template"), push (stub).

---------- PUBLIC vs INTERNAL FIELDS ----------
Public: title, purpose, category, status, derived flags, agency, contractor_name (if contractor_public), contact name + official channel (phone masked unless official), geometry, dates, revisions+reasons, milestones, public updates, public evidence (EXIF GPS stripped), moderated feedback, disruption.
Internal: created_by details, permit deposit amounts, internal notes, conflict decisions text (public gets only a simple "nearby work coordinated/rescheduled" notice), resident phone numbers, private feedback.

---------- SEED DATA (Ambadas builds; everyone uses the same) ----------
1 city, 4 zones/wards (polygons around Pune-like coords), 5 agencies (Municipal Roads Dept, Water & Sewer Board, DISCOM Electricity, FibreNet Telecom, Metro Rail), ~35 works across all statuses (planned/permitted/ongoing/paused/completed/restoration_verified), 4 planted conflicts (2 overlap, 1 recent_resurfacing, 1 near-duplicate repeated dig), 3 delayed works with revisions+reasons, 2 overdue-update works, ~15 feedback tickets in different SLA stages, staff users for every role (password demo1234; emails like je.ward1@demo.city, ee.roads@demo.city, utility.water@demo.city, auditor@demo.city, admin@demo.city), residents 9000000001..9000000005 (OTP 123456).

---------- UX RULES ----------
Mobile-first, readable on low bandwidth, plain-language labels (no jargon), status chips with color AND icon/text (not color-only), keyboard accessible, English+Hindi toggle on public portal, "Last updated: <relative + absolute>" on every list/detail/map, empty/loading/error states everywhere.

---------- DEFINITION OF DONE ----------
Feature works end-to-end in `docker compose up` with seed data; no console errors; has at least one test or a curl/HTTP-file demonstrating it; contract unchanged (if you must change the contract, tell the other two immediately in chat and update this block).
===== END SHARED CONTRACT =====
```

---

## 4. How to use the prompts (all three)

1. Paste the **Shared Contract** (Section 3).
2. Paste **your prompt part** (e.g. 5.1).
3. Tell the AI: *"Work in small commits. After each numbered step, show me what to run to verify it."*
4. If the AI suggests changing anything in the contract, **stop** and tell the other two.

---

## 5. AMBADAS: Platform + Core + Staff Work Form + Field PWA

### Prompt 5.0: Scaffold (RUN FIRST, H0 to H1; others wait for your push)

```
You are the lead engineer scaffolding the monorepo described in the Shared Contract. Build ONLY the skeleton so the other two developers can start in parallel in ~1 hour. Do the following in order and keep each step runnable.

1. Repo: create the layout in the contract (backend, frontend, mock, seed, sql), README with "docker compose up" quickstart, Makefile (up, down, seed, test), .env.example, .gitignore, CODEOWNERS mapping folders to owners (Ambadas / Aayushya / Hitesh as in the contract).
2. docker-compose.yml: services db (postgis/postgis:16-3.4, healthcheck), backend (uvicorn --reload, mounts ./backend, depends_on db), frontend (next dev, mounts ./frontend), volumes for pgdata and /data/uploads. Backend env: DATABASE_URL, JWT_SECRET, CORS_ORIGINS=http://localhost:3000.
3. /backend/sql/001_schema.sql: implement EXACTLY the data model in the contract (enums, tables, indexes incl. GiST, the audit_log append-only trigger that blocks UPDATE/DELETE). Backend auto-applies it on startup if tables are missing.
4. /backend/app/core: config.py, db.py (SQLAlchemy engine + session dependency), clock.py (now()/today() with an in-memory offset used by /dev/advance-time), errors.py (error envelope), pagination.py, security.py (JWT create/verify, password hashing with bcrypt, get_current_user, require_roles(...), jurisdiction check helper), events.py (emit(session,type,payload) writes to outbox_event; subscribe decorator; dispatcher started with APScheduler every 2 s; marks published_at), audit.py (write_audit(session, actor, action, entity, entity_id, before, after) with sha256 hash chaining over prev_hash + canonical JSON).
5. /backend/app/main.py: FastAPI app, CORS, include all module routers with prefix /api/v1 (empty routers for modules owned by others, each with a placeholder GET /{module}/ping), static mount /files, startup hooks (schema, scheduler).
6. Implement identity_access fully: POST /auth/login, /auth/otp/request, /auth/otp/verify, GET /auth/me, plus GET /wards, /agencies, /config/public. Seed script creates the city, wards, agencies, and one user per role (see Seed Data in contract).
7. /mock: a tiny mock API (json-server or a FastAPI file) on port 4000 returning realistic responses for the contract's GET /works, /works/geojson, /works/{id}, /reports/summary, /works/{id}/feedback/public, with ~10 hand-written works in Pune-like coordinates, so Hitesh can build UI before the real API exists. Document in README how to point the frontend at mock vs real (NEXT_PUBLIC_API_BASE).
8. Export OpenAPI JSON to /backend/openapi.json (make target) and commit it.
9. Frontend skeleton (minimal): Next.js 14 + Tailwind + TanStack Query project that boots and shows "Public Works Platform", with /lib/api.ts fetch wrapper (reads NEXT_PUBLIC_API_BASE, attaches JWT from localStorage, unwraps error envelope). Hitesh will own everything beyond this.
Deliver: all files, then a checklist to verify: `docker compose up` works, /docs loads, login works for je.ward1@demo.city / demo1234, resident OTP login works with 123456, mock server returns /works.
When done, tell me the exact commit message and the message to send Aayushya and Hitesh ("scaffold is pushed, branch main").
```

### Prompt 5.1: Core backend (H1 to H9)

```
Continue as Ambadas on the same repo. Implement these modules end-to-end with tests (pytest, at least a happy path + a permission failure per module). Respect the Shared Contract exactly.

A. organisations: GET /agencies, /wards, /zones, officer directory GET /officers?ward_id=&role=, escalation ladder table (default JE->AE->EE->SE->CE->Commissioner) with a helper service interface `get_assignee(work, level)` that Aayushya's feedback module will call (returns the user for that level by ward/zone/agency, falling back upward).

B. project_registry (core):
 - POST /works: validate geometry (GeoJSON LineString or Polygon inside the city), auto-compute length_m via PostGIS (geography), ward_id via ST_Contains/ST_Intersects on ward.boundary (call through the geo_spatial service interface; create a stub in geo_spatial named `locate_ward(geometry)` and `length_m(geometry)` that Aayushya will keep), ref_no generator, initial status planned, original_target_end = current_target_end, set last_update_at, jurisdiction check (JE own ward, utility_editor own agency), emit WorkCreated.v1, write audit.
 - PATCH /works/{id}: partial edit; if current_target_end changes, REJECT with 422 and message "use /works/{id}/dates" (dates only change via the revision endpoint). Emit WorkUpdated.v1 (include changed_fields). Detect disruption change to closure and emit ClosureAdded.v1.
 - GET /works with all filters (bbox, ward_id, road partial match, category, agency_id, status, delayed, q full-text on title/purpose/road via Postgres tsvector or ILIKE), plus derived flags delayed and update_overdue (computed in SQL using core.clock.now()). GET /works/geojson returns FeatureCollection with simplified props. Public (unauthenticated) callers only see is_public works with public fields; staff see more.
 - GET /works/{id} returns the exact WORK DETAIL shape in the contract (nearby_notices comes from conflict decisions via an interface Aayushya exposes; until then return []; contact phone masked for public).
 - Status machine endpoint POST /works/{id}/status with the exact transition rules, reason_code+explanation requirement for paused, completed requires pct=100, restoration_verified requires restoration evidence (call evidence service interface `has_restoration_evidence(work_id)`; stub returning True until Aayushya's module exists, behind a TODO). Writes work_status_history, audit, emits WorkStatusChanged.v1 (+ RestorationVerified handled by evidence module).
 - POST /works/{id}/updates (progress note; sets last_update_at; pct_complete optional; keeps pct monotonic unless explanation given).
 - GET /works/{id}/history: merged chronological timeline (status changes, date revisions, updates, evidence, conflict decisions as simple notices).

C. schedule_milestones: POST /works/{id}/milestones, PATCH /milestones/{id} (actual_date marks done; recompute work.pct_complete as the average of milestone pct when milestones exist), POST /works/{id}/dates {new_target_end, reason_code, explanation} which validates reason_code against city_config.reason_codes, inserts work_date_revision, updates current_target_end, emits WorkDatesRevised.v1 and audit. original_target_end is immutable (DB trigger or service guard). Explanation min 15 chars.

D. audit: GET /audit (filters, role-restricted) and GET /audit/verify which recomputes the hash chain and returns {valid, broken_at}. Add a test that tampering with a row (using a superuser connection) makes verify fail.

E. admin_config: GET/PUT /admin/config (admin only) for buffer_m, lookback_months, overdue_days, SLA days, sla_time_scale, reason_codes, feature flags.

F. core jobs: scheduler job every 5 minutes that finds works with update_overdue newly true and emits UpdateOverdue.v1 once per work per week (idempotent via a marker in public_flags or a small table).

G. dev endpoints: POST /dev/advance-time {days} (admin or when DEV_MODE=true), POST /dev/reset-seed.

H. Seed (backend/seed/seed.py): implement the Seed Data from the contract with ~35 works, planted conflicts (just create the works; Aayushya's engine will detect them on the nightly scan trigger), delayed works with revisions, overdue-update works, restoration_verified works, history rows, and ~15 feedback tickets inserted directly via SQL in different SLA ages. Dates relative to core.clock.today(). Include the MG Road example (A water trench, B telecom duct overlapping 11 days, C electricity 78 days after resurfacing). Make it idempotent (`make seed`).

Deliver code + tests + a Postman/HTTP file `backend/requests.http` covering every endpoint you built. Then give me a 10-line summary of exactly what is ready so I can notify Aayushya and Hitesh.
```

### Prompt 5.2: Bulk import, Staff Work Form, Field PWA (H9 to H17)

```
Continue as Ambadas. Backend core is merged and the other two are consuming it. Now build (a) bulk import, and (b) the staff frontend for works and the field PWA. Frontend lives in /frontend/app/staff (works, import, audit) and /frontend/app/field. Use Hitesh's shared UI kit from /frontend/components/ui once it lands (pull main often); if it is not there yet, create thin local wrappers and swap later.

A. Backend /imports: POST /works/import accepts CSV (columns: title,purpose,category,agency_code,road_name,planned_start,original_target_end,contractor_name,contact_name,contact_phone,lat1,lng1,lat2,lng2) or GeoJSON FeatureCollection. Validate each row, return a dry-run report {valid:[...], invalid:[{row, errors}]} when ?dry_run=true, otherwise insert valid rows (single transaction per row, emit WorkCreated.v1 each), write audit. GET /works/import/template returns a sample CSV.

B. Staff console shell: /staff layout with login page (/staff/login using /auth/login), role-based nav (hide menu items the role can't use), top bar with user + role + ward, logout. Aayushya will add pages under /staff/conflicts, /staff/permits, /staff/feedback, /staff/dashboard; leave nav slots for these.

C. /staff/works list: table with filters (ward, status, agency, delayed, overdue), "My works" default, badges for Delayed and Update overdue, quick action menu (add update, change status, revise date).

D. /staff/works/new and /staff/works/[id]/edit: the work submission form with sections: Basics (title, plain-language purpose, category, agency auto-filled for utility_editor), Location (MapLibre with drawing tool to draw a line/polygon or click-two-points; shows computed length and ward after drawing), Schedule (planned start, target end, add milestones rows), People (contractor, contact name/phone/email/channel, a toggle "show contractor publicly"), Impact (disruption type + note), Attachments (photo upload that calls Aayushya's POST /works/{id}/evidence after work creation; if not ready, hide behind a feature flag). BEFORE submit, call POST /geo/check (Aayushya) and, if conflicts come back, show a prominent non-blocking "Possible conflicts" panel listing the other works (title, agency, dates, overlap days) with a "Submit anyway" button. Handle API not ready with a graceful fallback.

E. /staff/works/[id]: control room page with tabs: Overview, Updates (post progress note + pct), Status (transition buttons that only show valid next states; reasons modal enforcing reason_code dropdown + min 15 char explanation for pause/delay), Dates (revise target date with mandatory reason, shows full revision list), History (timeline from /works/{id}/history), Evidence.

F. /staff/import: upload CSV/GeoJSON, show dry-run validation table with row errors, confirm to import, download template.

G. /staff/audit (auditor/admin): searchable log with a "Verify integrity" button calling /audit/verify and showing a green "chain intact" or red "tampered at #id".

H. Field PWA (/field): installable (manifest + service worker), mobile-first, for contractor/JE: list of assigned works, tap a work -> "Add progress photo": opens camera input, captures GPS via navigator.geolocation, timestamps, queues the upload in IndexedDB if offline and syncs when online (Background Sync or on-online event), shows pending/synced state, and a "Post quick update" form. Uploads call POST /works/{id}/evidence and POST /works/{id}/updates. Show a clear offline banner. Add a "Mark restoration done" button that creates evidence of kind=restoration.

Deliver the code, then a 2-minute manual test script I can follow (login as utility.water@demo.city, create a work overlapping an existing one, see the conflict panel, submit, revise date with reason, post update with photo).
```

---

## 6. AAYUSHYA: Coordination + Accountability + Staff Console pages

### Prompt 6.1: Conflict engine, permits, evidence, geo (H1 to H9)

```
You are Aayushya. The scaffold is pushed by Ambadas (pull main). You own backend modules geo_spatial, permits, conflict_engine, evidence, citizen_feedback, notifications, reporting, public_api (open data) and the staff frontend pages for conflicts/permits/feedback/dashboard. Respect the Shared Contract exactly. Begin with Wave 1 backend below; commit often; write pytest tests (use the seed MG Road example).

1. geo_spatial (the ONLY module doing geometry maths). Public service interface used by others:
   locate_ward(geometry)->ward_id, length_m(geometry)->float, buffered_intersections(geometry, buffer_m, exclude_work_id)->work ids with distance_m, nearest_segment_key(geometry). Use ST_Transform to EPSG:32643 for metre buffers. Endpoints: POST /geo/check {geometry, planned_start, target_end, exclude_work_id?} (dry-run, returns list of potential conflicts with other works: type, work summary, agency, dates, overlap_days or days_since_resurfacing, distance_m), GET /geo/segments/repeat?months=12 (road segments/clusters with 2+ distinct works whose geometry intersects within the window, returning count, works list, agencies).
2. conflict_engine: implement the rules in the contract precisely.
   - Overlap: buffered ST_Intersects AND date ranges intersect -> overlap_days inclusive. Resurfacing: previous completed/restoration_verified resurfacing (category=resurfacing or resurfaced_on set) intersecting within lookback_months before planned_start -> days_since_resurfacing.
   - Subscribers: on WorkCreated.v1 and WorkUpdated.v1 (only if geometry/dates/category changed) run detection and upsert conflict_alert (unique on the pair+type while open) -> emit ConflictDetected.v1. Also on PermitSubmitted.v1 re-check. Nightly scan job (APScheduler, plus POST /conflicts/scan for demo) over all active works for bulk-imported/edited data.
   - GET /conflicts (status, ward filter; staff only; EE sees own division/ward scope, cross-agency visibility for the two agencies involved), GET /conflicts/{id} (both works, agencies, schedules, overlap visual data: both geometries and overlap date range), POST /conflicts/{id}/decision {action in coordinate_dates|combine_work|reschedule|justify_both, note>=15 chars, new_dates optional (for reschedule/coordinate the system calls schedule service POST dates on the chosen work with a reason_code utility_clash)} -> resolves alert, emits ConflictResolved.v1, audit. Never auto-cancel/auto-approve.
   - Public "nearby_notices": expose a service function `nearby_notices(work_id)` returning simple plain-language notices ("Nearby water pipeline work was rescheduled to avoid repeat digging") ONLY for coordinate/reschedule/combine decisions. Ambadas' /works/{id} calls this; tell him the function name.
3. permits (the adoption lever): POST /permits (requires a registered work with geometry+dates else 422 "Register the work first"), lifecycle draft->submitted->(pending_coordination if an open conflict involves the work)->approved/rejected/held, approve blocked with 409 PENDING_COORDINATION until conflicts on that work are resolved; on ConflictResolved.v1 auto-move held permits back to submitted. Closure NOC type approved only by traffic_police; deposit fields and POST /permits/{id}/deposit/release only after the work is restoration_verified. On approve, move work status planned->permitted via the status service (not direct SQL) and emit PermitApproved.v1; PermitHeld.v1 when held. Role rules: utility_editor submits, EE/AE approves road_cut within their division, traffic_police approves closure_noc.
4. evidence: POST /works/{id}/evidence (multipart) using Pillow: read EXIF (DateTimeOriginal, GPS), store original privately, create a public copy with ALL EXIF/GPS stripped; exif_ok = true if GPS within 300 m of the work geometry and taken within last 48h of the upload, else false (still accepted but flagged "needs verification"). Fields lat/lon/taken_at can be passed by the client when EXIF is absent (PWA case). Emit EvidenceAdded.v1, bump work.last_update_at through the registry service. POST /evidence/{id}/verify (JE+), POST /works/{id}/restoration-verify (JE/EE; requires >=1 evidence kind=restoration verified) -> calls status service to restoration_verified and emits RestorationVerified.v1. Implement the interface `has_restoration_evidence(work_id)` Ambadas calls and tell him to remove his stub.
Deliver code, tests, and `backend/requests_aayushya.http`. Then summarise the endpoints now live so Hitesh and Ambadas can wire them.
```

### Prompt 6.2: Feedback+SLA, notifications, reporting, open data, staff console (H9 to H17)

```
Continue as Aayushya. Wave 1 is merged. Now build the accountability backend and the staff console pages.

BACKEND
1. citizen_feedback (Swachh.city-style):
   - POST /works/{id}/feedback (resident JWT; rate-limit 5/hour per user; CAPTCHA stub header accepted): kind question|complaint|observation, text<=500 chars, optional photo (EXIF stripped), optional lat/lon. Creates ticket with ref_no FB-YYYY-NNNNNN, status open, current_level=1, assigned_to = organisations.get_assignee(work, 1) (JE), is_public=false, moderation=pending. First ticket_event "Received". Emit FeedbackSubmitted.v1.
   - GET /feedback/mine, GET /feedback/{ref_no} (owner or staff) with full status history (ticket_event list, public messages only for resident).
   - Staff: GET /staff/feedback (filters status, awaiting=true meaning no staff response yet, level, ward), POST /staff/feedback/{id}/respond {message,status,make_public?} (sets last_response_at, creates ticket_event, emits FeedbackResponded.v1), POST /staff/feedback/{id}/moderate {approve} (only approved + is_public items appear in GET /works/{id}/feedback/public along with their public responses; strip phone/email/name, show only first name initial or "Resident").
   - POST /works/{id}/still-ongoing {value} (resident; one per user per work per 24h) stored as ticket kinds still_ongoing_yes/no, aggregated in work detail as still_ongoing {yes,no,last_confirmed_at}; if 3+ "no" votes in a week while status ongoing, create an internal flag (staff inbox "possibly stale data").
   - SLA escalation job every minute using core.clock.now() and city_config: no staff response by day 3 -> level 2 (AE), day 7 -> level 3 (EE), day 14 -> level 4 (SE) and mark overdue_public=true. Each escalation: ticket_event, set escalated_at, reassign via organisations.get_assignee(work, level), FeedbackEscalated.v1 event, notification to the resident (status changed). Apply sla_time_scale so demo time can be compressed. Idempotent (never escalate the same level twice). Tests that use /dev/advance-time to prove 3/7/14.
2. notifications: subscribers to events per the contract rules. follow endpoints (POST/DELETE/GET /follows with work_id or ward_id), a job that creates "starting tomorrow" notifications, minor-edit suppression (ignore pct change <10 and text-only edits), dedupe_key, one daily digest for non-critical kinds, and adapters: ConsoleAdapter (writes to the notification table + logs), EmailAdapter (SMTP via env, stub if missing), SmsAdapter/WhatsAppAdapter (log "DLT template id: ..."). GET /notifications/mine, PATCH /notifications/{id}/read. Every notification has project name, affected location (road_name, ward), deep link /works/{id}.
3. reporting: implement /reports/summary, /reports/delayed, /reports/overdue-updates, /reports/repeat-dig, /staff/inbox exactly per contract (all derived flags computed in SQL with core.clock.now()). Cache summary for 30 s. Staff inbox is jurisdiction-scoped.
4. public_api (open data): /open/works.geojson, /open/works.csv, /open/stats.json — public fields only (no phones/emails/deposits), 60 s cache, CORS open, `Last-Modified`.

FRONTEND (/frontend/app/staff/..., use Hitesh's UI kit components; pull main often)
- /staff/conflicts: list of open alerts (type chip: Overlap / Recently resurfaced, overlap days, agencies, dates) and detail page showing a MapLibre map with BOTH geometries in different colours with buffer outlines, side-by-side cards for both projects (agency, schedule, contact), a decision panel (4 actions + note + optional new dates with reason code), history of decision. Resolved tab.
- /staff/permits: tabs Draft / Submitted / Pending coordination / Approved; permit detail with work summary, conflict warning banner that explains why approval is blocked, approve/reject/hold with notes, NOC flow for traffic_police, deposit display and release after restoration verified. Also a utility "Apply for permit" form that starts from a registered work.
- /staff/feedback: inbox of tickets awaiting response sorted by SLA age with level chip (JE/AE/EE/SE) and "escalated" markers, detail drawer with resident message, work link, respond form, make-public toggle, moderation approve/reject.
- /staff/dashboard: KPI cards (open conflicts, delayed, overdue updates, tickets awaiting, repeat-dig segments), the staff inbox lists, and a small chart of works by status and by agency (recharts), plus a "Repeat-dig hotspots" table with a map highlight.
Deliver code, tests for escalation timing and notification dedupe, and a demo script: submit feedback as resident 9000000001, call /dev/advance-time days=3 then 7 then 14 and show escalation on the staff inbox for AE, EE, SE.
```

---

## 7. HITESH: Entire Public Resident Portal

### Prompt 7.1: Public portal core (H1 to H9)

```
You are Hitesh. Ambadas pushed the scaffold (Next.js skeleton + /lib/api.ts + mock server on :4000). You own the entire public resident portal and the shared UI kit in /frontend/components/ui. Start against the mock (NEXT_PUBLIC_API_BASE=http://localhost:4000/api/v1) and switch to the real API (http://localhost:8000/api/v1) once endpoints land. Respect the Shared Contract exactly (field names, statuses, derived flags). Design for Indian mobile users: mobile-first, fast, minimal JS, readable fonts, WCAG AA contrast, large touch targets.

Build in this order:

1. Design system / UI kit (/frontend/components/ui): Button, Input, Select, Textarea, Badge/StatusChip (planned=blue, permitted=indigo, ongoing=amber, paused=grey, completed=green, restoration_verified=teal, delayed=red, plus an icon + text on every chip so it never relies on colour alone), Card, Tabs, Modal/Drawer, Toast, Skeleton, EmptyState, ErrorState, LastUpdated (shows "Updated 2 days ago · 07 Oct 2026, 4:12 pm"), Timeline, ProgressBar, Pagination, Map wrapper (MapLibre with OSM tiles, geolocate control, zoom, "reset view"). Also publish the components to Aayushya and Ambadas by documenting them in /frontend/components/ui/README.md as soon as the first version is in main (do this within the first 90 minutes, they depend on it).
2. i18n: English + Hindi dictionary (simple JSON + useT hook), language toggle in header persisted in localStorage, all public strings translated (status names, button labels, form labels). Date formatting in en-IN / hi-IN.
3. Layout: header (logo "Public Works Tracker", links Map / List / Dashboard / Open data / My follows, language toggle, login/OTP), footer (about, open data, grievance links: CM helpline, CPGRAMS, RTI as external links "linked, not replaced"), skip-to-content, a low-bandwidth toggle (hides map tiles/images, shows list only).
4. Home /: hero search ("Search your road, ward or project"), quick stat tiles (ongoing, delayed, completed this month from /reports/summary), and CTA buttons to Map and List.
5. Works map + list /works (the must-have #1):
   - Map view: loads /works/geojson with current filters, draws LineString/Polygon segments coloured by status (delayed in red with dashed outline), cluster markers when zoomed out, click opens a preview card with title, agency, status, last updated, and "View details". Fit-to-results, bbox query on map move (debounced).
   - Filters panel (drawer on mobile): ward/neighbourhood, road name search, work type (category), department (agency), status (planned/ongoing/delayed/paused/completed/restoration verified), "delayed only", and keyword; filters stored in the URL query string (shareable links).
   - List view toggle: cards with title, road, ward, agency chip, status chip, delayed/overdue badges, planned vs revised end date, last updated, pagination. List and map share the same filters; a "Near me" button using geolocation sorts by distance.
   - Show "Data last updated" for the whole dataset and per-item.
6. Project detail /works/[id] (must-have #2): sections in this order: Title + plain-language purpose; status chip + delayed badge + "update overdue" badge; mini map with work boundary + road/area; responsible department (with link to filter by it) and contractor if provided; contact (name, official channel, masked phone) with a "Call/Email" button; progress (percentage bar + milestones list with planned vs actual); dates card: Planned start, Original target, Revised target (strike through the original when revised); disruption box (closure/restricted access with note, highlighted); "Recent updates" feed and "Progress photos" gallery with dates (lightbox, alt text); "Nearby work coordinated/rescheduled" notices; "Still ongoing?" Yes/No buttons with counts (requires login); share button; Follow button; Give feedback button; JSON-LD structured data for SEO.
7. Delay & date history component (must-have #5) on the detail page: a vertical Timeline combining status changes, date revisions ("Target moved from 20 Feb to 5 Mar · Reason: Material delay · explanation text"), updates and notices; never hides previous dates; labels each entry with date and who (department, not personal name).
Deliver working pages against the mock, with Storybook-free manual verification steps. Tell Ambadas and Aayushya when the UI kit README is in main.
```

### Prompt 7.2: Resident engagement, dashboard, polish (H9 to H17)

```
Continue as Hitesh. The real API is now available on :8000 (switch NEXT_PUBLIC_API_BASE). Fix any contract mismatches by messaging the owner (don't change backend code). Now build:

1. Resident login (OTP): modal/page: enter mobile number -> POST /auth/otp/request -> enter OTP (dev hint "Use 123456" shown only when NEXT_PUBLIC_DEV=true) -> POST /auth/otp/verify; store JWT; show a consent checkbox (DPDP Act: purpose = project updates and feedback; link to privacy page), plus a /privacy page explaining data use and deletion request.
2. Project-linked feedback (must-have #6): on the detail page "Ask / Report" opens a form: type (Question / Complaint / Observation), description (max 500 chars with counter), optional photo (client-side compress to <1 MB, preview), optional location (use my location / tap on map / use work location), consent note that private details are not published. Submit -> POST /works/{id}/feedback -> success screen with reference number (copy button) and link to track. Show the "Public feedback & responses" tab on the detail page from /works/{id}/feedback/public.
3. My feedback /me/feedback: list of my tickets with reference no, status chip, work link, "escalated to Assistant/Executive Engineer" label when level > 1; ticket page /feedback/[ref_no] with the status history timeline (Received -> Acknowledged -> Escalated -> Resolved, with dates and responder department) and a SLA hint ("Expected first response by <date>").
4. Follow & notifications (must-have #7): Follow button on the detail page (choose channel: console/email/SMS/WhatsApp stubs) and on a ward page; /me/follows to manage; a bell icon with unread notifications from /notifications/mine (title, project, location, link), mark as read; settings for "only important alerts" (digest) vs "all changes".
5. Public accountability dashboard /dashboard (must-have #8): KPI cards (total works, ongoing, delayed, update overdue, completed this month), charts (works by status, by ward, by department using recharts), "Most delayed works" table (days late, reason), "Updates overdue" table, "Repeat-dig hotspots" (roads dug 2+ times in 12 months with agencies and a map highlight), "Open overlap alerts detected" count with plain-language examples, and "Feedback response performance" (open vs overdue tickets, average first-response time) from /reports/summary. Each table links to detail pages. Add a "Download CSV/GeoJSON" button linking to /open/works.csv and /open/works.geojson and a short API docs page /open-data.
6. Ward page /wards/[id]: map of that ward's works, counts, follow-the-ward button.
7. Accessibility and performance pass: keyboard focus rings, aria labels on map controls and chips, alt text on photos, lang attribute switching, prefers-reduced-motion, lazy-load map and charts, image sizing, Lighthouse >= 90 mobile on /works and /works/[id] (report numbers), 404/500 pages, offline-friendly caching of static assets.
8. Empty/loading/error states everywhere, skeletons for lists, retry on network errors.
Deliver code and a QA checklist I can tick through at Checkpoint 2.
```

---

## 8. Checkpoint smoke test (H9 and H17), all three together

Run in this order and tick each:

1. `docker compose up --build` is clean; `make seed` is OK.
2. Public: `/works` shows ~35 works on the map, filter by status and ward, list view works, "Last updated" appears.
3. Open the MG Road work detail page; contractor, contact, dates, revisions and photos are visible.
4. Staff: log in as `utility.water@demo.city`, create a work overlapping an existing one, and the **Possible conflicts** panel appears.
5. Staff EE: `/staff/conflicts` shows the alert with both works on a map; record a decision; the resident-facing notice appears on the detail page.
6. Permit: apply for a road-cut permit on a work with an open conflict; approval returns 409 until the decision is recorded.
7. Revise a target date **without** a reason; it fails. With a reason, both dates show publicly.
8. Resident (9000000001, OTP 123456): submit feedback, get a reference number; call `/dev/advance-time` to day 3, 7 and 14 and watch escalation and the resident's timeline update.
9. Follow a work, then change its dates; exactly one notification arrives; minor edits do not notify.
10. `/dashboard` shows counts, delayed, overdue updates and repeat-dig; CSV and GeoJSON download work.
11. `/audit/verify` returns valid; (optional) tamper with a row to show it turns invalid.
12. Field PWA: turn offline, add a photo, go online, and it syncs.

---

## 9. Prompt 8 (Integration/Polish, H17 to H20, each runs on their own area) and Prompt 9 (Deploy, Aayushya)

### Prompt 8: Everyone

```
We are at integration checkpoint 2 of a 24-hour hackathon. Here is the failing smoke-test item list: <paste failures>. Read the Shared Contract. For each failure, determine whether the bug is in my module (owner: <your name>) or in another module (then write me a precise message to the owner with request, expected vs actual JSON, and curl). Fix only my module. Then: (1) remove any TODO stubs I left for other modules and replace them with the real service interfaces, (2) add loading/empty/error states for every screen I own, (3) make sure all dates come from core.clock and all user-visible strings in the public portal are translated en+hi, (4) run the linter and tests, (5) list remaining known issues in priority order so we can decide what to cut.
```

### Prompt 9: Aayushya (deployment and demo hardening)

```
Prepare a demo deployment of the monorepo: production docker-compose (Caddy or Nginx reverse proxy with HTTPS if a domain exists, otherwise plain), env var docs, `make seed` on first boot, healthcheck endpoints (/healthz), DB backup command, basic request logging with correlation IDs, rate limiting on /auth/otp/request and feedback endpoints, security headers, CORS locked to the deployed origin, DEV_MODE=true kept ON for the demo only (so /dev/advance-time works) with a visible banner "Demo mode". Provide the steps for Render/Railway/a single VPS (pick the simplest) and a one-page README (what it is, how to run, demo accounts, architecture diagram in Mermaid, module ownership table). Also produce a script `demo_reset.sh` that resets seed data to a clean state in under 30 seconds.
```

---

## 10. Demo script (5 minutes, for judges)

1. **Problem (30 s):** same road dug 3 times in 4 months; nobody knows why or when it ends.
2. **Resident view (60 s):** open the map, filter to your ward, open an ongoing work, and show the purpose, department, contractor, original vs revised dates with reason, the disruption, and the photos.
3. **Coordination (90 s):** log in as the water board, draw a trench overlapping a telecom duct, see the conflict warning with the 11-day overlap, then log in as the EE, open the conflict, pick "coordinate dates", and the permit is released from hold. Show the resident's notice: "nearby work coordinated".
4. **Accountability (60 s):** the resident submits feedback and gets a reference number; click time forward and show it escalate JE to AE to EE to SE; show the public dashboard with delayed works, overdue updates and repeat-dig hotspots.
5. **Trust and scale (30 s):** audit chain verification, the open data CSV and GeoJSON, English and Hindi toggle, field PWA offline photo sync, and "permit requires registration" as the reason agencies will keep data fresh.

**Say this line:** *"If the platform is only a display layer, agencies won't update it. We made registration a precondition for the road-cut permit, so keeping data current is in the agency's own interest."*

---

## 11. Coverage matrix: your 8 must-haves, plus extras

| # | Requirement | Where it's built |
|---|---|---|
| 1 | Public map + list, filters, last-updated | Hitesh 7.1 (#5), Ambadas 5.1 (B), Aayushya open data |
| 2 | Project detail page with all fields | Hitesh 7.1 (#6), Ambadas 5.1 (B detail shape) |
| 3 | Agency work submission + who-changed-what | Ambadas 5.2 (D, E), audit module, import |
| 4 | Overlap + recent-resurfacing detection, staff decision, resident notice | Aayushya 6.1 (#1, #2), 6.2 conflicts UI, Hitesh notices |
| 5 | Progress and delay history, mandatory reasons, overdue flags | Ambadas 5.1 (C), Hitesh 7.1 (#7), derived flags |
| 6 | Resident feedback tied to project, ref no, status history, routing, privacy | Aayushya 6.2 (#1), Hitesh 7.2 (#2, #3) |
| 7 | Follow + notifications without spam | Aayushya 6.2 (#2), Hitesh 7.2 (#4) |
| 8 | Public dashboard, repeat work, staff unresolved view | Aayushya 6.2 (reporting + staff dashboard), Hitesh 7.2 (#5) |
| + | Permit-gated registration, closure NOC, deposit | Aayushya 6.1 (#3) |
| + | Restoration verified, evidence EXIF checks, EXIF strip | Aayushya 6.1 (#4) |
| + | Field PWA offline photos | Ambadas 5.2 (H) |
| + | Hash-chained audit | Ambadas 5.1 (D) |
| + | Still-ongoing cross-check, repeat-dig, hindi, accessibility, open data, demo time-machine | Aayushya, Hitesh, Ambadas as listed |

**Out of scope (don't build):** payroll, tender bidding, contractor payments, full asset management, traffic simulation, AI completion prediction, a generic complaint system.

---

## 12. If time runs short, cut in this order (last first)

1. Field PWA offline sync (keep the basic upload form)
2. WhatsApp/SMS/email adapters (keep console + in-app bell)
3. Hindi on non-public pages (keep the public portal Hindi)
4. Bulk import UI (keep the API)
5. Repeat-dig map highlight (keep the table)

**Never cut:** map + detail page, conflict detection with decision, date revision with reason, feedback with escalation, public dashboard.
