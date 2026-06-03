# Open Gaps

## Still missing for a complete production product

- broader tenant/customer-grade authn/authz and fuller multi-org / multi-project RBAC if product scope expands beyond one org
- production observability integration beyond local metrics output:
  - dashboards
  - external alert rules
  - external log/trace shipping
- deployment hardening beyond Compose-level shaping
- real-world scale validation on messy live workloads
- customer-grade secret lifecycle and storage for real target credentials
- deeper org scoping across incident, review, and historical maintenance records
- final frontend polish and performance pass on the newer admin/workspace flows

## Highest-risk technical gaps

- runtime telemetry and drift flows still need proof on more customer-like live targets beyond the existing public/test profiles and shipped sidecar harnesses
- production observability still needs broader external integration proof
- real target auth needs stronger secret lifecycle beyond local env indirection

## “Breakout” gaps

- no undeniable public proof point on a real workload yet
- remediation/policy loop is useful, but not yet “must-talk-about-it” magical
- frontend still needs another polish/perf pass before it feels fully flagship-grade everywhere
