#!/usr/bin/env python3
"""Read-only reconciliation for a retained D4 owned-run manifest.

An absent run must use a new run_id for any future seed. Partial, conflicting,
or stale-source manifests require manual review. This tool never repairs,
deletes, renames, or reseeds anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import reset_owned


EXPECTED_RESET_SOURCE_SHA256 = "6d01cba56da854ccb43ba747a74c1e5b70024004ec09f93f7c29a4de53c8e517"


def reconcile_source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def classify_post_state(existing: int, matching: int, conflicting: int) -> str:
    if min(existing, matching, conflicting) < 0 or matching + conflicting != existing or existing > 2:
        raise reset_owned.OwnedRunError("invalid_reconciliation_counts")
    if conflicting:
        return "conflict"
    if existing == 0:
        return "absent"
    if existing == 1 and matching == 1:
        return "partial"
    if existing == 2 and matching == 2:
        return "seeded"
    return "conflict"


def reconciliation_sql(document: dict[str, Any], run_id: str) -> str:
    post_a = document["posts"]["a"]
    post_b = document["posts"]["b"]
    actor_a = document["actors"]["a"]
    actor_b = document["actors"]["b"]
    marker_a = reset_owned.body_marker(run_id, "a")
    marker_b = reset_owned.body_marker(run_id, "b")
    return f"""
      begin transaction read only;
      select pg_try_advisory_xact_lock({reset_owned.ADVISORY_KEY_ONE},{reset_owned.ADVISORY_KEY_TWO});
      select jsonb_build_object(
        'existing', count(*),
        'matching', count(*) filter (where
          (id={reset_owned.sql_uuid(post_a)} and author_id={reset_owned.sql_uuid(actor_a)} and body='{marker_a}'
            and reply_to_post_id is null and repost_of_post_id is null) or
          (id={reset_owned.sql_uuid(post_b)} and author_id={reset_owned.sql_uuid(actor_b)} and body='{marker_b}'
            and reply_to_post_id is null and repost_of_post_id is null)
        ),
        'conflicting', count(*) filter (where not (
          (id={reset_owned.sql_uuid(post_a)} and author_id={reset_owned.sql_uuid(actor_a)} and body='{marker_a}'
            and reply_to_post_id is null and repost_of_post_id is null) or
          (id={reset_owned.sql_uuid(post_b)} and author_id={reset_owned.sql_uuid(actor_b)} and body='{marker_b}'
            and reply_to_post_id is null and repost_of_post_id is null)
        )),
        'references',
          (select count(*) from public.posts where id not in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)})
            and (reply_to_post_id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)})
              or repost_of_post_id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)}))) +
          (select count(*) from public.post_media where post_id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)})) +
          (select count(*) from public.likes where post_id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)})) +
          (select count(*) from public.notifications where post_id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)})) +
          (select count(*) from public.post_hashtags where post_id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)})) +
          (select count(*) from public.bookmarks where post_id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)}))
      )::text
      from public.posts
      where id in ({reset_owned.sql_uuid(post_a)},{reset_owned.sql_uuid(post_b)});
      rollback;
    """


def query_owned_state(document: dict[str, Any], run_id: str) -> dict[str, Any]:
    reset_owned.validate_foreign_key_contract()
    output = reset_owned.run_psql(reconciliation_sql(document, run_id))
    lines = output.splitlines()
    if len(lines) != 2 or lines[0] not in {"t", "f"}:
        raise reset_owned.OwnedRunError("reconciliation_output_rejected")
    if lines[0] != "t":
        raise reset_owned.OwnedRunError("lease_unavailable")
    try:
        counts = json.loads(lines[1])
    except json.JSONDecodeError as exc:
        raise reset_owned.OwnedRunError("reconciliation_output_rejected") from exc
    required = {"existing", "matching", "conflicting", "references"}
    if not isinstance(counts, dict) or set(counts) != required or any(
        not isinstance(counts[name], int) or counts[name] < 0 for name in required
    ):
        raise reset_owned.OwnedRunError("reconciliation_output_rejected")
    status = classify_post_state(counts["existing"], counts["matching"], counts["conflicting"])
    return {"status": status, **counts}


def reconcile(payload: dict[str, str]) -> dict[str, Any]:
    current_reset_sha = reset_owned.source_sha256()
    current_reconcile_sha = reconcile_source_sha256()
    if current_reset_sha != EXPECTED_RESET_SOURCE_SHA256:
        raise reset_owned.OwnedRunError("reset_source_changed")
    reset_owned.verify_dedicated_database()
    reset_owned.ensure_manifest_directory()
    path = reset_owned.manifest_path(payload["run_id"])
    document, _manifest_sha = reset_owned.read_manifest(path)
    if document["actors"] != {"a": payload["actor_a"], "b": payload["actor_b"]}:
        raise reset_owned.OwnedRunError("manifest_actor_mismatch")
    if document["source_sha256"] != current_reset_sha:
        raise reset_owned.OwnedRunError("manifest_source_mismatch")
    state = query_owned_state(document, payload["run_id"])
    return {
        "status": state["status"],
        "existing_posts": state["existing"],
        "matching_posts": state["matching"],
        "conflicting_posts": state["conflicting"],
        "references": state["references"],
        "source_current": 1,
        "reset_sha256": current_reset_sha,
        "reconcile_sha256": current_reconcile_sha,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        payload = reset_owned.parse_stdin_payload(sys.stdin.read(), args.run_id)
        print(json.dumps(reconcile(payload), sort_keys=True, separators=(",", ":")))
        return 0
    except reset_owned.OwnedRunError as exc:
        print(json.dumps({"status": "error", "code": exc.code}, sort_keys=True, separators=(",", ":")))
        return 2
    except Exception:
        print(json.dumps({"status": "error", "code": "internal_error"}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
