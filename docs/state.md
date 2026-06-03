# Current State

## Product shape

Living Systems Auditor is no longer a thin prototype. It is a production-shaped backend and control plane for:

- intent snapshot ingestion
- runtime trace collection and normalization
- drift detection and remediation reporting
- operator-facing job, worker, alert, on-call, maintenance, and cutover workflows

## Runtime architecture

- API surface: FastAPI
- frontend surface: separate Vite + React app in `dashboard/`
- operator surface: CLI mirrors most maintenance and governance flows
- primary runtime backend contract: `LSA_DATABASE_URL`, with Postgres auto-activating when configured
- optional explicit Postgres runtime override: `LSA_POSTGRES_RUNTIME_DATABASE_URL`
- worker modes:
  - embedded worker for single-process/dev use
  - standalone worker for split API/worker deployment

## What is solid today

- snapshots, audits, jobs, workers, leases, and maintenance events persist durably
- worker heartbeats, stale-worker takeover, history retention, and rollups are implemented
- analytics, metrics, alerts, silences, reminders, escalations, and on-call routing are implemented
- governed on-call changes support approvals, review queues, assignment, and environment-aware policy
- maintenance mode, backup/restore, schema inspection/migration, and cutover runbooks exist
- Postgres cutover preparation, bootstrap packaging, inspection, rehearsal, readiness, and promotion gates exist
- runtime smoke, rehearsal, validation, cadence tracking, dedicated runtime-proof alerts, and runtime-proof review queues exist
- live workload drift proof is now first-class backend evidence with validation, cadence tracking, readiness gating, analytics, metrics, alerts, health coverage, and operational-validation coverage
- live workload target profiles now support real target request shaping:
  - explicit validation/proof URLs
  - custom HTTP methods
  - expected status codes
  - env-backed auth headers
  - per-profile timeout
  - organization / team / project / environment metadata
- API authz now supports actor-aware role enforcement and privileged API audit logging
- service-level maintenance and cutover records now carry actor context, not just raw `changed_by`
- organization-aware actor scope exists in backend authz
- admin/workspace now exposes the org operating layer:
  - teams
  - projects
  - memberships
  - removal ledger with reason
  - assignments
  - assignment comments
  - scoped target profiles
  - soak telemetry for the active org/team/project slice
- remediation can now use a real provider-backed runtime with rule-based fallback
- observability exports are first-class backend evidence with validation, retention, analytics, metrics, health, readiness, and operational-validation coverage
- split frontend/backend deployment is now supported with:
  - `dashboard/.env.example` via `VITE_API_BASE_URL`
  - backend CORS via `LSA_API_ALLOWED_ORIGINS`
  - cinematic landing page and `/command` control center
  - anime.js motion, Lenis smooth scroll, and React Three Fiber hero scene
  - live health, readiness, analytics, queue, and alert wiring
  - direct frontend actions for runtime rehearsal, operational validation, and alert emission

## Current backend transition posture

- live app runtime uses one shared backend bundle for snapshots, audits, and jobs
- Postgres is a real primary runtime path, not only a cutover artifact
- shadow sync exists for maintenance metadata, jobs, workers, heartbeats, lease events, alerts, on-call state, and governance state
- live split-stack Postgres proof now passes:
  - operational validation
  - runtime rehearsal
  - live noisy multi-session workload drift proof
  - external-target noisy workload drift proof
  - backup rehearsal
  - backup export validation
  - observability export validation
  - queue drill
  - workload drill
  - stale-worker / expired-lease recovery
  - deployment readiness
  - worker restart and API restart failure drills

## Important repo surfaces

- API: [lsa/api/main.py](../lsa/api/main.py)
- CLI: [lsa/cli/main.py](../lsa/cli/main.py)
- storage/runtime bundle: [lsa/storage/files.py](../lsa/storage/files.py)
- analytics: [lsa/services/analytics_service.py](../lsa/services/analytics_service.py)
- alerts: [lsa/services/control_plane_alert_service.py](../lsa/services/control_plane_alert_service.py)
- runtime validation: [lsa/services/control_plane_runtime_validation_service.py](../lsa/services/control_plane_runtime_validation_service.py)
- runtime validation reviews: [lsa/services/control_plane_runtime_validation_review_service.py](../lsa/services/control_plane_runtime_validation_review_service.py)
- roadmap: [docs/roadmap.md](roadmap.md)
- frontend app: [dashboard/README.md](../dashboard/README.md)

## Latest important milestone

- live Postgres operational validation now passes end to end on the split API/worker stack
- live Postgres failure drills now pass for worker restart, API restart, queue recovery, and readiness re-checks
- noisy multi-session live workload drift proof now passes locally and on the live Postgres split stack
- external sidecar target drift proof now passes live with `target_mode=external`
- public third-party drift proof profile is now supported with `target_profile=public-echo-pair`
- second public third-party target profile is now supported with `target_profile=public-httpbin-bingo-pair`
- named file-backed target profiles are now supported through `LSA_WORKLOAD_TARGET_PROFILES_PATH`
- live workload target probing is now first-class backend evidence with explicit target validation for the active profile
- target validation now has freshness cadence, scheduled execution, dedicated alerting, readiness/cutover enforcement, and recorded-evidence reads instead of live probes on health/readiness paths
- one-shot operational validation now also executes and validates live workload drift proof end to end
- external proof matrix harness now exercises both public target profiles end to end through target validation, drift proof, and operational validation
- customer-target runner now exists for named profiles or explicit URL pairs
- named customer/public target profiles now have first-class validation, drift-proof, and operational-validation execution paths in both CLI and API
- portable live workload proof bundles now export current target validation, drift proof, operational validation, available profiles, and supporting maintenance events
- proof bundles now carry SHA-256 + size metadata and can be inspected for required evidence fields
- proof bundles now have retention prune/delete lifecycle controls instead of only export/list/inspect
- timestamp and JSON serialization paths are hardened for real Postgres row types instead of only SQLite-shaped data
- AWS EC2 backend hardening path now exists with Docker bootstrap, deploy, validation, and reboot persistence scripts
- live AWS EC2 proof now passes on a real split API/worker/Postgres stack, including hardening validation and failure drills
- worker recovery validation regression on live Postgres is fixed
- worker container health is now real and healthy instead of inheriting the API HTTP probe
- worker now refreshes operational proof automatically on cadence without recursively queueing validation jobs
- live AWS soak validation passed across repeated iterations with health, readiness, and worker-recovery checks staying green
- soak validation is now a first-class backend surface with persisted evidence, CLI/API execution, status reporting, and health exposure instead of only ad-hoc shell loops
- trust score and incident narrative are now first-class backend surfaces with CLI/API access and live frontend command-center wiring
- target profiles now support one-shot canary verification that chains target validation, drift proof, runtime rehearsal, and readiness into a promotion verdict
- target registry and intel now expose scope ownership and request-shaping configuration directly in the frontend
- completed constrained-target long soak passed `24/24` iterations with zero failures and now contributes directly to trust scoring
- API now ships browser-facing security headers by default and supports trusted-host enforcement via `LSA_API_TRUSTED_HOSTS`
- local backend boot now raises file-descriptor limits before starting uvicorn to reduce macOS polling exhaustion
- landing page now conditionally loads the heavy 3D scene only on larger non-reduced-motion devices and uses an animated fallback elsewhere
- backend proof gap is now mostly real-world workload breadth, not missing control-plane plumbing
