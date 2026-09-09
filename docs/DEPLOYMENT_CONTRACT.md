# Deployment Contract

## Decision

Helm is the target and only approved **future** production deployment contract
for CistaFirma. It models the complete runtime: backend, frontend, one Celery
Beat scheduler, workers for `ruz_full`, `orsr`, `financials`, `insurance`, and
`celery`, plus optional backing services and backups.

The currently deployed GitLab path still applies Kustomize. It must not be
switched to Helm until every cutover prerequisite below is recorded and
accepted. This prevents a release from silently connecting to a different or
empty PostgreSQL instance.

## CI runtime contract

GitLab CI renders the Helm chart for both dev and prod values. The rendered
output is checked for:

- backend and frontend deployments;
- exactly one Celery Beat deployment;
- exactly one worker deployment for every declared Celery queue; and
- a worker command whose `-Q` value matches its declared queue.

This validation detects an incomplete async runtime before deployment. It does
not prove the target cluster's Secret values, PVCs, or external database.

## Mandatory Helm cutover checklist

Do not deploy the Helm release before all items are completed:

1. Record the exact target namespace and `HELM_RELEASE` name. Helm resource
   names are release-scoped and differ from the current Kustomize resource
   names.
2. Inspect the existing target Secret without exposing values in source control.
   `DATABASE_URL`, `REDIS_URL`, Celery broker/result URLs, and `SECRET_KEY` must
   remain present and point to the intended services.
3. Decide whether PostgreSQL and Redis are managed externally or by Helm. For
   an existing durable database, do not enable a new Helm PostgreSQL StatefulSet
   as a replacement. Set the chart backing service to disabled only after the
   external connection contract is validated.
4. If Helm manages a stateful service, explicitly map its existing PVC and
   follow the database engine's supported migration path. Never rely on an
   automatically created new PVC to preserve data.
5. Run `helm upgrade --install --dry-run --debug` against the target values and
   a server-side dry-run in a non-production namespace.
6. Confirm every worker and Beat is Running, queues are consumed, the backup
   job has a successful artifact, and source freshness remains unchanged.
7. Keep the prior deployment available for application rollback. Database
   restores remain a last resort and require the procedure in
   [`DATA_PROTECTION.md`](DATA_PROTECTION.md).

## Transitional state

Kustomize remains the live deployment mechanism only until the checklist is
complete. Its lack of Celery workers and Beat is a release-blocking discrepancy;
do not treat a successful backend/frontend rollout as proof that ingestion and
notifications are operational.
