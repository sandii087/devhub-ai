#!/bin/sh
# Install at /opt/devhub/release.sh on an operator-provisioned host.
# The account must already be authenticated to GHCR and have Docker permission.
set -eu
cd /opt/devhub
test "$#" -eq 2
case "$1" in ghcr.io/*@sha256:*) ;; *) exit 2 ;; esac
case "$2" in ghcr.io/*@sha256:*) ;; *) exit 2 ;; esac
export DEVHUB_API_IMAGE="$1" DEVHUB_WEB_IMAGE="$2"
docker pull "$DEVHUB_API_IMAGE"
docker pull "$DEVHUB_WEB_IMAGE"
# migrations.env is a protected file with the dedicated migration credential.
docker run --rm --env-file migrations.env "$DEVHUB_API_IMAGE" alembic -c backend/alembic.ini upgrade head
docker run --rm --env-file migrations.env "$DEVHUB_API_IMAGE" python scripts/provision_roles.py
docker compose -f compose.production.yaml up -d --wait --wait-timeout 120
umask 077
printf 'DEVHUB_API_IMAGE=%s\nDEVHUB_WEB_IMAGE=%s\n' "$DEVHUB_API_IMAGE" "$DEVHUB_WEB_IMAGE" > release.env
# Keep previous image digests outside this file for schema-compatible rollback.
