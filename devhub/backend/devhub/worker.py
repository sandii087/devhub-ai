"""Leased, retryable outbox processing. Run with `python -m devhub.worker`."""

import argparse
from datetime import timedelta
import logging
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select

from devhub.db import SessionLocal, set_tenant
from devhub.github import fetch_repository, queue_sync
from devhub.github_models import Installation, Repository, WebhookDelivery
from devhub.models import Organization, OutboxEvent, utcnow

log = logging.getLogger("devhub.worker")


def process_one(org_id: str) -> bool:
    owner = str(uuid4())
    with SessionLocal.begin() as db:
        set_tenant(db, org_id)
        now = utcnow()
        job = db.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.org_id == org_id,
                OutboxEvent.next_retry_at <= now,
                or_(
                    OutboxEvent.state == "pending",
                    (OutboxEvent.state == "processing") & (OutboxEvent.lease_expires_at < now),
                ),
            )
            .order_by(OutboxEvent.next_retry_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        job.state, job.lease_owner, job.lease_expires_at = "processing", owner, now + timedelta(seconds=90)
        job.attempts += 1
        job_id, kind, payload = job.id, job.kind, dict(job.payload)
        repo = db.get(Repository, payload.get("repository_id")) if kind == "github.sync" else None
        installation = db.get(Installation, repo.installation_id) if repo else None
        target = (
            (repo.installation_id, repo.repository_id)
            if repo and installation and installation.enabled
            else None
        )
    # External work occurs after the lease transaction commits.
    result, failure, revoked = None, None, False
    if kind == "github.sync" and target:
        try:
            result = fetch_repository(*target)
        except HTTPException as exc:
            failure, revoked = exc.status_code, exc.status_code == 502
        except Exception:
            log.exception("Provider synchronization failed", extra={"job_id": job_id})
            failure = 503
    with SessionLocal.begin() as db:
        set_tenant(db, org_id)
        job = db.scalar(select(OutboxEvent).where(OutboxEvent.id == job_id).with_for_update())
        if not job or job.lease_owner != owner:
            return True
        repo = db.get(Repository, payload.get("repository_id")) if kind == "github.sync" else None
        installation = db.get(Installation, repo.installation_id) if repo else None
        if result and repo and installation and installation.enabled:
            # Prevent an earlier slow request from overwriting a newer completed sync.
            if not repo.last_synced_at or repo.last_synced_at <= now:
                for key, value in result.items():
                    setattr(repo, key, value)
                repo.last_synced_at, repo.sync_state = utcnow(), "ready"
        if failure:
            job.state = "dead" if job.attempts >= 6 else "pending"
            job.next_retry_at = utcnow() + timedelta(seconds=min(3600, 2**job.attempts * 10))
            if repo:
                repo.sync_state = "revoked" if revoked else "error"
        else:
            job.state = "done"
        job.lease_owner, job.lease_expires_at = None, None
    return True


def reconcile(org_id: str) -> None:
    with SessionLocal.begin() as db:
        set_tenant(db, org_id)
        rows = db.scalars(
            select(Repository)
            .join(Installation, Repository.installation_id == Installation.installation_id)
            .where(Repository.org_id == org_id, Installation.enabled.is_(True))
        ).all()
        for repo in rows:
            queue_sync(db, repo, f"reconcile:{repo.id}:{int(time.time()) // 300}")
        # Bounded debug retention and outbox history. Audit records are not swept here.
        from sqlalchemy import delete

        db.execute(
            delete(WebhookDelivery).where(
                WebhookDelivery.org_id == org_id, WebhookDelivery.received_at < utcnow() - timedelta(days=7)
            )
        )
        db.execute(
            delete(OutboxEvent).where(
                OutboxEvent.org_id == org_id,
                OutboxEvent.state == "done",
                OutboxEvent.created_at < utcnow() - timedelta(days=7),
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process one pass and exit")
    parser.add_argument("--interval", type=int, default=2, choices=range(2, 3601), metavar="SECONDS")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    last_reconcile = 0.0
    while True:
        with SessionLocal() as db:
            orgs = list(db.scalars(select(Organization.id)))
        due = time.monotonic() - last_reconcile > 300
        for org in orgs:
            if due:
                reconcile(org)
            for _ in range(100):
                if not process_one(org):
                    break
        if due:
            last_reconcile = time.monotonic()
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
