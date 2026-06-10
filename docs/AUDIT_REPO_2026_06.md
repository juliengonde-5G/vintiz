# Vintiz — Repository Audit & Improvement Plan (June 2026)

> **Date**: 2026-06-10 · **Scope**: full monorepo at `v1.0.0`+ (post go-live 03/06/2026)
> **Method**: direct code reading of security/fiscal/POS paths + systematic sweeps of
> backend services, both frontends, tests, dependencies and ops. Every finding cites
> `file:line` and was verified against source. Analysis only — no code was modified.
> **Prior art**: this repo already went through an audit cycle in April 2026
> (`docs/AUDIT_2026_04.md`, root `AUDIT_*.md`). Most of those findings were remediated;
> this audit covers the *current* state and does not re-report fixed items.

---

## 1. Executive Summary

**Overall health: C+.** The product is feature-rich and moving fast, the backend has a
genuinely strong test culture (~95 test files asserting real behavior on NF525, POS
idempotence, refunds, coupons), deployment is well-guarded, and secrets hygiene is clean.
But three structural problems undermine that foundation. First, a **Critical
customer-data exposure**: the public `/api/crm/account/*` endpoints hand out a client's
full purchase history and RGPD data export to anyone who knows their email — no
authentication, despite a working magic-link JWT system sitting unused beside them.
Second, **CI is decorative**: pytest, ruff, tsc and Alembic all run in non-blocking mode,
so the excellent test suite cannot actually stop a broken merge. Third, **process-model
hazards**: 2 uvicorn workers each start their own APScheduler (every cron runs twice,
including customer emails) and blocking I/O (`time.sleep`, `smtplib`, `pg_dump`) sits
inside async request paths serving the POS.

Top 3 risks: (1) unauthenticated personal-data access → CNIL/RGPD liability for a French
retailer; (2) test failures silently merged to `main` which auto-deploys to the live
boutique; (3) duplicate cron sends and POS latency stalls from the worker/scheduler model.
Top 3 opportunities: (1) flipping CI to blocking is nearly free and instantly converts the
existing test suite into a real safety net; (2) the magic-link auth already exists —
gating the account endpoints is wiring, not building; (3) extracting shared config/token
modules in the frontends removes most of the duplication at low cost.

---

## 2. Repo Map

**Purpose**: management software for a single premium second-hand boutique (Vernon, FR):
iPad POS with hardware (ESC/POS printer, Zebra labels, SumUp, cash drawer), inventory with
AI scoring/vision, CRM + loyalty + personal-shopper recommendations, NF525 fiscal
compliance, public site with customer space. Production since 2026-06-03, single VPS,
single store. Maturity: **young production system** (v1.0.0, ~1 week live).

**Stack**: FastAPI + SQLAlchemy 2 async + PostgreSQL 16 + Redis 7 + APScheduler;
2× Next.js 14 App Router (admin `apps/web`, public `apps/site`); Caddy 2; Docker Compose;
GitHub Actions → SSH deploy on push to `main`; Anthropic Claude for AI features.

| Area | Description |
|---|---|
| `apps/api/app/api/*` | 17 routers (auth, pos, crm, inventory, admin, …) — `pos/router.py` 3 035 lines, `admin/router.py` 2 648 |
| `apps/api/app/services/*` | ~90 service modules — clean service layer, a few god files (`sumup_service.py` 1 040) |
| `apps/api/app/core/*` | config, security (PyJWT + bcrypt), Redis rate-limiter, middleware (CSP, request-id), logging |
| `apps/api/app/models/*` | ~33 model modules; portable `JSONType` enables SQLite tests |
| `apps/api/alembic/` | 60 migrations — **not replayable from scratch** (schema comes from `create_all`) |
| `apps/api/tests/` | ~95 test files, SQLite in-memory, behavior-asserting |
| `apps/web` | admin + POS UI — `src/app/pos/page.tsx` is 3 693 lines; offline queue + connectivity detection |
| `apps/site` | public site + magic-link customer space |
| `docker/`, `scripts/` | prod compose (good isolation), `deploy.sh` (rollback, smoke tests), `go_live_reset.py` (guarded) |
| Repo root | **~20 MB of tracked binaries** (11.5 MB mockup PDF, store photos, `Dev-UX3/`), 4 stale audit docs |

**Surprises**: (a) the unauthenticated account endpoints coexist with a complete
magic-link JWT implementation; (b) CI runs a PostgreSQL service container that pytest
never uses (tests are SQLite); (c) CLAUDE.md contradicts the code in several places
(claims `python-jose` — code uses PyJWT `core/security.py:5`; claims "11 tests" — there
are ~95 files; claims "Plus de `?email=` dans les URLs" — `account.py` is built on them).

---

## 3. Audit Report

Severity legend: **C** Critical · **H** High · **M** Medium · **L** Low.
"Fact" = verified in code; "Judgment" = assessment.

### 3.1 Security

| # | Sev | Finding |
|---|---|---|
| S1 | **C** | **Unauthenticated access to customer data by email.** `GET /api/crm/account/data-export?email=` returns the full RGPD export to any caller (`apps/api/app/api/crm/account.py:297-315`); `GET /account/transactions?email=` returns full purchase history (`account.py:518-553`); `POST /account/deletion-request` lets anyone schedule deletion of any account (`account.py:317-349`); consents/loyalty/coupons likewise resolve via `_resolve_public_client` (`account.py:140-146`) with no token check. The 404-vs-200 split also enables email enumeration. The docstring itself admits "a future iteration will replace this with a magic-link confirmation flow" (`account.py:306`). `get_current_client` (`core/security.py:78-109`) exists and is unused here. *Fact. Consequence: any person knowing a customer's email reads their purchases — a direct GDPR Art. 5/32 problem and reputational risk.* |
| S2 | **H** | **JWTs in `localStorage`** in both apps: admin token (`apps/web/src/lib/api.ts:29`), client token + email (`apps/site/src/app/account/login/page.tsx:137-138`). Any XSS = token theft; admin tokens last 8 h (`config.py:25`). *Fact.* |
| S3 | **M** | Rate-limit key blindly trusts `X-Forwarded-For` (`core/rate_limit.py:134-139`). A client that can reach the API and set XFF (or rotate values through any hop that doesn't strip it) bypasses the login rate limit. *Fact; exploitability depends on Caddy config.* |
| S4 | **M** | Rate limiter silently degrades to **per-process memory** when Redis is down (`rate_limit.py:54`, `:118-120`); with `--workers 2` (`docker/Dockerfile.api:54`) the effective limit doubles, and degradation is invisible in prod. *Fact.* |
| S5 | **M** | `/auth/refresh` mints a fresh token from any still-valid token (`api/auth/router.py:87-109`) — no rotation, no revocation list, so a stolen token can be renewed indefinitely. *Fact.* |
| S6 | **L** | `get_current_user` never checks the `role` claim (`core/security.py:54-75`); manager-vs-client token separation rests only on UUID non-collision between `users` and `clients` tables. Defense-in-depth gap. *Fact.* |
| S7 | **L** | Brevo webhook token compared with `!=` (timing-unsafe) and accepted as a **query parameter** (`api/brevo/router.py:38-51`), so it lands in access logs. *Fact.* |
| S8 | **L** | CSRF: mitigated by Bearer-header auth today; becomes relevant the day S2 is fixed with cookies — plan them together. *Judgment.* |

Healthy: parameterized SQL throughout (no f-string SQL found), bcrypt passwords, prod
boot refuses default `SECRET_KEY` (`config.py:108-138`), security headers middleware,
DB/Redis/API have zero exposed ports in prod compose (only Caddy 80/443), no hardcoded
secrets anywhere, `.env` correctly ignored and never committed.

### 3.2 Correctness & code quality

| # | Sev | Finding |
|---|---|---|
| Q1 | **H** | **Every cron runs twice.** The lifespan starts an `AsyncIOScheduler` per process (`app/main.py:54-58`) and uvicorn runs `--workers 2` (`Dockerfile.api:54`); `app/jobs.py` has no lock/leader election. Anniversary emails, trend alerts, loyalty expiry, nightly backups, markdown runs all execute at-least-twice (some may self-deduplicate; email/SMS sends generally don't). *Fact (mechanism verified); per-job impact partially judgment.* |
| Q2 | **H** | **Blocking I/O inside async request paths**: retry `time.sleep` in email gateway (`services/email_gateway.py:253,259`), blocking `smtplib.SMTP(timeout=15)` (`email_gateway.py:314`), SMS retry sleep (`services/sms_gateway.py:390`, called from async magic-link `services/magic_link.py:237`), printer retry sleep (`services/escpos_service.py:639`), `subprocess.Popen` pg_dump on the event loop (`services/database_backup.py:79`). With 2 workers, one stuck email retry freezes half the POS capacity for seconds. *Fact.* |
| Q3 | **H** | **POS god component**: `apps/web/src/app/pos/page.tsx` is 3 693 lines with 9 `catch { /* silent */ }` blocks (e.g. `:625`, `:643`) and inconsistent `res.ok` handling (`:533`, `:1331`, `:1464` parses JSON without checking status). This is the single most business-critical screen. *Fact.* |
| Q4 | **M** | God routers: `api/pos/router.py` 3 035 lines, `api/admin/router.py` 2 648, `api/inventory/router.py` 1 867. `create_transaction` is ~250 lines (`services/pos.py:39-288`). Hard to review the exact code that moves money. *Fact (sizes), judgment (risk).* |
| Q5 | **M** | Swallowed/silent failures in money paths: SumUp refund response-parse failure collapses to a generic error (`services/sumup_service.py:884`) risking operator double-refund; accounting close failure is logged but never alerted (`api/pos/router.py:780`). *Fact.* |
| Q6 | **M** | N+1 in the weekly scoring cron: per-product `get_brand_score` + `get_or_refresh_estimate` inside the loop (`app/jobs.py:321-325`) → ~1 000 extra round-trips. Harmless today at 300 products; compounds with Q1. *Fact.* |
| Q7 | **M** | ~29 `any`/unsafe casts in `apps/web` (e.g. `reports/page.tsx:483`, `zones/[id]/page.tsx:150`, `components/ia/RecosDuJourTab.tsx:112,247`); enforced by nothing since `tsc --noEmit \|\| true`. `apps/site` is clean. *Fact.* |

### 3.3 Testing

| # | Sev | Finding |
|---|---|---|
| T1 | **C** | **CI gates are disabled.** `pytest tests/ -v --tb=short 2>/dev/null \|\| echo "Aucun test trouve"` (`.github/workflows/ci.yml:63`) — failures *and all output* are suppressed; ruff `\|\| true` (`:53`); `tsc --noEmit \|\| true` (`:111`, `:142`); Alembic "indicative" (`:55-60`). Only Next builds and Docker builds gate. A red test suite merges and auto-deploys to the live store. *Fact.* |
| T2 | **H** | **Zero frontend tests** — no jest/vitest/playwright config or test file in either app; the POS UI (Q3) ships on type-check-that-can't-fail plus a build. *Fact.* |
| T3 | **M** | Backend tests run on SQLite in-memory (`tests/conftest.py:14-33`) while prod is PostgreSQL; the Postgres service container in CI (`ci.yml:20-33`) is unused by pytest. Dialect-specific behavior (pgvector, JSONB, sequences, locking) is untested. *Fact.* |

Healthy: the suite itself is high quality — `test_nf525_chain.py` verifies tampering
detection across 100 transactions, `test_pos_idempotence.py` covers replay, stock and
dedup; tests assert behavior, not just execution.

### 3.4 Architecture & dependencies

| # | Sev | Finding |
|---|---|---|
| A1 | **H** | Schema is created by `Base.metadata.create_all` at every boot (`app/main.py:50-51`); the 60 Alembic migrations assume pre-existing tables and **cannot replay on an empty database** (acknowledged in `ci.yml:56-60`). Consequence: disaster-recovery onto a fresh DB depends on `create_all` matching 60 migrations' cumulative state — unverifiable drift; migration testing impossible. *Fact.* |
| A2 | **H** | **No Python lockfile**; all deps are `>=` lower bounds only (`apps/api/pyproject.toml:6-28`). Every Docker rebuild may pull different versions; prod builds are non-reproducible. *Fact.* |
| A3 | **M** | No shared code between the two frontends: `process.env.NEXT_PUBLIC_API_URL \|\| 'http://localhost:8000'` is copy-pasted **21×**; design tokens are inlined identically in both `tailwind.config.ts` while `design-package/tailwind.preset.ts` sits unused. *Fact.* |
| A4 | **L** | Node side is healthy: Next 14.2.35 pinned (not affected by CVE-2025-29927), lockfiles present, `npm ci` in CI. *Fact.* |

### 3.5 DevEx, operations, documentation

| # | Sev | Finding |
|---|---|---|
| O1 | **M** | API container has no Docker healthcheck (`docker/docker-compose.prod.yml:56-83`); DB and Redis have them. `deploy.sh` polls manually but `restart: unless-stopped` can't act on a hung-but-running API. *Fact.* |
| O2 | **M** | No error tracking (Sentry or similar) on either frontend; POS failures are visible only if the cashier reports them. Backend at least has request-id-correlated JSON logs. *Fact (absence), judgment (impact).* |
| O3 | **M** | **Stale docs that contradict code**: CLAUDE.md claims python-jose (uses PyJWT), "11 tests" (~95 files), and removed `?email=` URLs (S1 disproves). For a repo developed largely by AI agents reading CLAUDE.md, doc rot directly causes future bugs. *Fact.* |
| O4 | **L** | Repo hygiene: ~20 MB of tracked binaries at root (11.5 MB `Mockup page d'accueil Vintiz (1).pdf`, 2.8 MB `Caisses.jpeg`, `Photos/`, `Dev-UX3/` with duplicated logo sets), 4 superseded audit markdowns at root, `.codex/` stray dir; git pack already 41 MB. *Fact.* |
| O5 | **L** | `--workers 2` hardcoded rather than env-configurable (`Dockerfile.api:54`). *Fact.* |

### 3.6 Strengths (preserve these)

1. **Backend test culture** — ~95 behavior-asserting test files over the domains that
   matter (fiscal chain, idempotent POS, refunds, RGPD, coupons).
2. **Deployment story** — `deploy.sh` with placeholder checks, rollback file, migration
   step, health polling and post-deploy smoke tests; `go_live_reset.py` with dry-run,
   `--confirm`, and an inventory-count rollback guard.
3. **Prod network posture** — only Caddy is exposed; non-root containers; multi-stage
   builds; persistent volumes for DB/uploads/backups.
4. **Offline-first POS design** — IndexedDB queue + `client_uuid` server-side idempotence
   (`services/pos.py:69-77`) + dual-signal connectivity detection (`apps/web/src/lib/connectivity.ts:25-39`).
5. **Secrets hygiene** — nothing hardcoded, `.env` never committed, CI uses ephemeral
   values, GitHub environment-scoped deploy secrets.
6. **Sane error boundary** — domain-exception mapping + request-id-correlated 500s with
   CORS preserved (`app/main.py:94-150`), production message redaction.

---

## 4. Improvement Strategy

Four themes explain ~90 % of the findings.

**Theme 1 — The safety net exists but is unplugged (T1, T2, A2, Q7).**
Target: CI that *fails*. Principle: a test you can't fail is documentation, not a test.
Done = pytest/ruff/tsc exit codes gate merges; a deliberately broken test blocks a PR;
`pip install` resolves from a committed lockfile; one Playwright smoke test covers the
POS sale path.

**Theme 2 — Public surface trusts the caller (S1, S2, S3, S5).**
Target: every endpoint returning personal data requires a client JWT; tokens move toward
HttpOnly cookies. Principle: possession of an email address is not authentication.
Done = zero `/account/*` data endpoints callable without `Authorization`; pentest-style
curl checks added to `test_security.py`.

**Theme 3 — The process model fights the code (Q1, Q2, S4, O1).**
Target: exactly-once crons and a non-blocking event loop. Principle: in an async service,
anything that sleeps or opens a socket synchronously must run in a thread or another
process. Done = scheduler runs in exactly one place (verified by log assertion);
`grep -rn "time.sleep\|smtplib" app/services` returns nothing reachable from `async def`
without an executor; API has a Docker healthcheck.

**Theme 4 — Two sources of truth everywhere (A1, A3, O3, O4).**
Target: one schema source (Alembic), one config/token module per app, docs that match
code. Principle: duplication isn't the problem; *divergence* is, and divergence is
guaranteed without a single source. Done = `alembic upgrade head` builds the full schema
on an empty DB and `create_all` is dev/test-only; `API_URL` defined once per app;
CLAUDE.md corrected.

**Deliberately NOT fixing now** (effort vs. payoff at single-store scale):
- Splitting the 3 000-line routers into perfect modules — high churn risk on live POS;
  do it opportunistically per feature, not as a campaign.
- Real monorepo workspaces / shared npm package — Docker build contexts make this costly;
  the Tailwind preset + a copied `config.ts` is 90 % of the value.
- Switching tests from SQLite to Postgres wholesale — keep SQLite for speed; add a small
  Postgres-marked subset for dialect-sensitive paths (fiscal sequences, pgvector).
- Refresh-token rotation/revocation — worthwhile, but behind S1/S2 in priority; an 8 h
  manager token in a single-store LAN context is an acceptable interim risk.
- Kubernetes/observability stack — out of scale for one boutique on one VPS.

---

## 5. Task Plan

### Quick wins (do immediately — all S effort, high impact)

| ID | Task | Files |
|---|---|---|
| QW1 | Remove `\|\| true` / `\|\| echo` / `2>/dev/null` from pytest, ruff, tsc steps | `.github/workflows/ci.yml:53,63,111,142` |
| QW2 | Add API healthcheck to prod compose | `docker/docker-compose.prod.yml` |
| QW3 | `secrets.compare_digest` + header-only token for Brevo webhook | `api/brevo/router.py:31-51` |
| QW4 | Fix CLAUDE.md stale claims (PyJWT, test count, `?email=` status) | `CLAUDE.md` |
| QW5 | Move root binaries to `docs/assets/` or delete; archive root `AUDIT_*.md`, `Dev-UX3/`, `PHASE_1_CLOTURE.md` | repo root |
| QW6 | Make worker count env-configurable (`WEB_CONCURRENCY`) | `docker/Dockerfile.api:54` |

### Milestone 0 — Safety net (before touching behavior)

| ID | Task | Areas | Acceptance | Effort | Risk | Deps |
|---|---|---|---|---|---|---|
| M0.1 | **Blocking CI** (= QW1) + branch protection requiring the jobs | ci.yml | A PR with a failing test cannot merge | S | Low — may surface pre-existing red tests; fix or quarantine them explicitly | — |
| M0.2 | **Python lockfile**: generate with `uv pip compile`/pip-tools; install from it in CI + Dockerfile | pyproject, Dockerfile.api, ci.yml | Two clean builds a week apart produce identical `pip freeze` | M | Low | M0.1 |
| M0.3 | **Characterization tests for S1 surface**: assert current public behavior of `/account/*` before gating it (so M1.1 diffs are visible) | tests/ | Tests enumerate every `/account/*` endpoint and its auth status | S | None | M0.1 |
| M0.4 | API healthcheck (= QW2) + alert email on backup failure path verified | docker/, services/database_backup.py | `docker inspect` shows healthy; killing uvicorn flips status | S | Low | — |

### Milestone 1 — Critical fixes (security & correctness)

| ID | Task | Areas | Acceptance | Effort | Risk | Deps |
|---|---|---|---|---|---|---|
| M1.1 | **Gate `/account/*` behind client JWT** — see sketch §5.1 | api/crm/account.py, apps/site account pages | No personal data without valid `role=client` token whose `sub` matches the requested client; email-enumeration responses unified; `test_security.py` extended | L | **Medium** — breaks any site page not yet sending the token; coordinate front+back in one PR | M0.3 |
| M1.2 | **Single-scheduler guard** — see sketch §5.3 | app/main.py, app/jobs.py | Exactly one "scheduler started" log line across workers; a marker job writes one row/day, not two | M | Low | — |
| M1.3 | **Unblock the event loop**: wrap `send_email`, `send_sms`, ESC/POS `send_raw`, `pg_dump` in `anyio.to_thread.run_sync` (or async clients) | services/email_gateway.py, sms_gateway.py, escpos_service.py, database_backup.py | No `time.sleep`/`smtplib`/`subprocess` executed on the loop; POS p95 latency unchanged during a forced SMTP timeout | M | Medium — concurrency around retry counters; test with a stubbed slow SMTP | M0.1 |
| M1.4 | **Rate-limit hardening**: derive client IP from trusted-proxy config instead of raw XFF; log loudly (or fail closed in prod) when falling back to memory | core/rate_limit.py, Caddyfile | Spoofed XFF no longer rotates the bucket key; Redis outage emits ERROR-level log | M | Low | — |

### Milestone 2 — High-leverage improvements

| ID | Task | Areas | Acceptance | Effort | Risk | Deps |
|---|---|---|---|---|---|---|
| M2.1 | **Alembic baseline**: squash current schema into migration 0061 as base; `create_all` only when `ENVIRONMENT != production`; deploy.sh relies on `upgrade head` | alembic/, app/main.py, scripts/deploy.sh | Fresh empty DB + `alembic upgrade head` boots the API and passes smoke tests | L | **Medium** — must verify against a copy of prod schema (`pg_dump --schema-only` diff) | M0.2 |
| M2.2 | **HttpOnly cookie auth for the customer space** (site), CSRF strategy decided with it | apps/site, api/auth | Token absent from `localStorage`; XSS PoC can no longer read it | L | Medium | M1.1 |
| M2.3 | **Frontend config/auth modules**: `lib/config.ts` (API_URL) + `lib/auth-storage.ts` per app; replace 21 copies | apps/web/src, apps/site/src | `grep -rn "localhost:8000" src` → 1 hit per app | S | Low | — |
| M2.4 | **Playwright smoke suite**: login → scan/search → cart → cash sale → ticket modal; run in CI against compose | apps/web, ci.yml | The one flow that earns money is exercised on every PR | L | Low | M0.1 |
| M2.5 | **POS page error discipline**: replace 9 silent catches with a toast/log helper; audit every `res.json()` for `res.ok` | apps/web/src/app/pos/page.tsx | Zero `/* silent */` catches; failures visible to cashier | M | Low | M2.4 (tests first) |
| M2.6 | **Money-path alerting**: accounting-close failure (`pos/router.py:780`) and SumUp refund parse failure (`sumup_service.py:884`) notify ops via email gateway + flag on Z-report | api/pos, services/sumup_service.py | Forced failure produces an ops email within 1 min | M | Low | M1.3 |

### Milestone 3 — Quality & polish

| ID | Task | Areas | Effort |
|---|---|---|---|
| M3.1 | Batch the N+1 in weekly scoring (preload brand scores + estimates) — `jobs.py:321-325` | S | |
| M3.2 | Adopt `design-package/tailwind.preset.ts` in both apps (copy into each app at build if Docker context blocks imports) | M | |
| M3.3 | Burn down `any` in apps/web (29 sites), then enable `tsc` strict gate already made blocking in M0.1 | M | |
| M3.4 | Role claim check in `get_current_user` (reject `role=client`) + refresh-token rotation design | M | |
| M3.5 | Postgres-marked test subset (fiscal sequences, pgvector) running against the CI service container | M | |
| M3.6 | Frontend error tracking (Sentry, EU region, IP scrubbing for RGPD) | M | |
| M3.7 | Split `pos/router.py` and `pos/page.tsx` opportunistically (one sub-domain per touch — payments, vouchers, drawer) | XL → per-feature | |

### 5.1 Implementation sketch — M1.1 Gate `/account/*` (top priority)

1. Add a dependency `current_account_client = Depends(get_current_client)` to every
   data-returning endpoint in `account.py`; replace `_resolve_public_client(db, email)`
   with the JWT-resolved client, ignoring any email param (or 403 on mismatch).
2. Keep genuinely-public endpoints public: `register`, magic-link request/verify already
   live in `auth/router.py`. `deletion-request`/`deletion-cancel` move behind the token
   too (RGPD requests from non-logged users go through the DPO email, already documented).
3. Frontend: `apps/site` account pages already hold `vintiz_account_token`
   (`login/page.tsx:137`) — add the `Authorization` header in one shared fetch helper
   (created in M2.3); redirect to `/account/login` on 401.
4. Gotchas: the wallet-pass endpoints are fetched by Apple/Google agents that can't send
   the JWT — keep those on signed one-time URLs instead; magic-link emails deep-link into
   the space, so verify the token-exchange flow still lands authenticated.
5. Tests: extend `tests/test_security.py` — every `/account/*` route without a token →
   401; with token for client A requesting client B → 403/ignored.

### 5.2 Implementation sketch — M0.1/M0.2 CI gates + lockfile

1. `ci.yml`: drop `|| true` (ruff), drop `2>/dev/null || echo` (pytest), drop `|| true`
   (both tsc steps). Run the suite once locally first; fix or `xfail` (with linked issue)
   anything red so the first gated PR is green.
2. Lockfile: `uv pip compile pyproject.toml -o requirements.lock` (or pip-tools);
   `Dockerfile.api` and CI install `-r requirements.lock` then `-e . --no-deps`.
3. Add GitHub branch protection on `main` requiring the four jobs — without it, blocking
   steps still don't block merges.
4. Gotcha: `pip install -e ".[dev]" 2>/dev/null || pip install -e .` (`ci.yml:50`) also
   hides install errors — make it explicit.

### 5.3 Implementation sketch — M1.2 single scheduler

1. Smallest safe fix: PostgreSQL advisory lock at startup —
   `SELECT pg_try_advisory_lock(0x56494E54)`; only the winner starts APScheduler, on a
   dedicated long-lived connection (the lock dies with the session — auto-failover when
   that worker dies).
2. Alternative (more explicit): a `scheduler` service in compose running
   `python -m app.scheduler` with `--workers` removed from the equation; API never starts
   the scheduler. Cleaner, but one more container on the VPS.
3. Either way: add a startup log "scheduler: leader/standby" and a daily heartbeat row to
   assert exactly-once in prod; check whether any *already-duplicated* sends (anniversary
   coupons since 03/06) need cleanup via the coupons table.
4. Gotcha: admin "trigger manual" endpoints call job functions directly — they must keep
   working from non-leader workers (they do, since they don't go through the scheduler).

---

## 6. Open Questions

1. **S1 timeline**: the account endpoints are live on vintiz.fr today. Do you want the
   auth gate shipped as an emergency hotfix PR (M1.1 alone, ~1-2 days), accepting a brief
   forced re-login for customers?
2. **Duplicate-cron blast radius**: since go-live (03/06), have customers received
   duplicate anniversary/trend emails? If yes, M1.2 becomes urgent and a one-off coupon
   dedup may be needed.
3. **Wallet pass + magic-link UX**: gating `/account/*` requires deciding how
   wallet-refresh URLs authenticate (signed URL vs. token) — product call.
4. **Twilio fallback**: CLAUDE.md says it will be removed "once the migration prod is
   confirmed" — confirmed? Removing it deletes a chunk of `sms_gateway.py`.
5. **Root artifacts**: are the store photos / mockup PDF at the root needed by anything,
   or can they be deleted from history (BFG) to shrink the 41 MB pack? Deleting from HEAD
   only is the low-risk default.
6. **Frontend test appetite**: is Playwright-in-CI (M2.4) acceptable on runtime (~3-5 min
   per PR), or should it be main-only?

---

*Lighter-reviewed areas (flagged per the 80/20 rule): AI services (`ai_*.py`,
`personal_shopper*`, embeddings), merchandising/capsule/SEO services, the accounting/
Pennylane integration, and most admin UI pages. No critical findings expected there, but
they did not receive line-by-line review.*
