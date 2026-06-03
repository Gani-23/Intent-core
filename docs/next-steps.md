# Next Steps

## Immediate

1. Prove runtime telemetry and drift paths on a customer-like live target, not just shipped sidecar services or the current public third-party proof matrix already covered by active target validation and target-validation governance
2. Add stronger external observability integration targets
3. Replace local-only secret indirection with a stronger target secret lifecycle if real customer targets need stored credentials
4. Harden org/team/project authz boundaries if product scope expands beyond one org
5. Polish the new admin/workspace surfaces:
   - tighter detail views for targets, assignments, soak telemetry, and removals
   - faster drilldown on the workspace operations page
   - final release packaging for the standalone frontend

## Near-term production path

1. Add fuller tenant-aware authz and RBAC if multi-org scope becomes real
2. Keep tightening the shipped operator UI for performance, consistency, and faster detail drilldown
3. Add stronger deployment/orchestration hardening
4. Run live workload validation at realistic noise/scale
5. Add production dashboard/alert integrations outside the app itself

## Breakout path

1. Prove one undeniable real-world drift catch on a live system
2. Turn that proof into a polished operator workflow
3. Make remediation and policy review feel faster and sharper than existing tooling
