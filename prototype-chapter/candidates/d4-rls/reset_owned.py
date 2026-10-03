#!/usr/bin/env python3
"""Seed or reset exactly two posts owned by one dedicated D4 trial run.

The fixed local database is reached only through docker exec/psql stdin. This
tool never owns Auth users, profiles, follows, hashtags, or child rows. Reset
aborts if any row references either owned post.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


DATABASE_CONTAINER = "supabase_db_sns-trio-local"
DATABASE_PORT = "5432/tcp"
EXPECTED_HOST_IP = "127.0.0.1"
EXPECTED_HOST_PORT = "54322"
ADVISORY_KEY_ONE = 53453
ADVISORY_KEY_TWO = 4434524
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{16,64}$")
EXPECTED_INPUT_KEYS = frozenset({"run_id", "actor_a", "actor_b"})
EXPECTED_POST_FOREIGN_KEYS = (
    "public.bookmarks.post_id->public.posts.id",
    "public.likes.post_id->public.posts.id",
    "public.notifications.post_id->public.posts.id",
    "public.post_hashtags.post_id->public.posts.id",
    "public.post_media.post_id->public.posts.id",
    "public.posts.reply_to_post_id->public.posts.id",
    "public.posts.repost_of_post_id->public.posts.id",
)


class OwnedRunError(Exception):
    """An expected rejection with a fixed, non-sensitive output code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def persistent_state_directory() -> Path:
    """Return the real user's persistent state directory without trusting env."""
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, TypeError) as exc:
        raise OwnedRunError("persistent_home_rejected") from exc
    if not home.is_absolute():
        raise OwnedRunError("persistent_home_rejected")
    return home / ".local" / "state"


def persistent_manifest_directory() -> Path:
    return persistent_state_directory() / "sns-d4-owned-runs"


MANIFEST_DIRECTORY = persistent_manifest_directory()


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def validate_run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_PATTERN.fullmatch(value):
        raise OwnedRunError("invalid_run_id")
    return value


def validate_uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise OwnedRunError("invalid_actor")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise OwnedRunError("invalid_actor") from exc
    if str(parsed) != value.lower():
        raise OwnedRunError("invalid_actor")
    return str(parsed)


def parse_stdin_payload(raw: str, cli_run_id: str) -> dict[str, str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OwnedRunError("invalid_input_json") from exc
    if not isinstance(payload, dict) or frozenset(payload) != EXPECTED_INPUT_KEYS:
        raise OwnedRunError("invalid_input_shape")
    run_id = validate_run_id(payload.get("run_id"))
    if run_id != validate_run_id(cli_run_id):
        raise OwnedRunError("run_id_mismatch")
    actor_a = validate_uuid(payload.get("actor_a"))
    actor_b = validate_uuid(payload.get("actor_b"))
    if actor_a == actor_b:
        raise OwnedRunError("actors_must_differ")
    return {"run_id": run_id, "actor_a": actor_a, "actor_b": actor_b}


def manifest_path(run_id: str, base_directory: Path = MANIFEST_DIRECTORY) -> Path:
    valid = validate_run_id(run_id)
    candidate = base_directory / f"{valid}.json"
    if candidate.parent != base_directory or candidate.name != f"{valid}.json":
        raise OwnedRunError("invalid_manifest_path")
    return candidate


def validate_database_binding(bindings: Any) -> None:
    if not isinstance(bindings, dict) or set(bindings) != {DATABASE_PORT}:
        raise OwnedRunError("database_binding_rejected")
    entries = bindings.get(DATABASE_PORT)
    if not isinstance(entries, list) or len(entries) != 1:
        raise OwnedRunError("database_binding_rejected")
    entry = entries[0]
    if not isinstance(entry, dict) or entry.get("HostIp") != EXPECTED_HOST_IP or entry.get("HostPort") != EXPECTED_HOST_PORT:
        raise OwnedRunError("database_binding_rejected")


def run_command(arguments: list[str], *, stdin: str | None = None) -> str:
    completed = subprocess.run(
        arguments,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise OwnedRunError("local_command_rejected")
    return completed.stdout.strip()


def verify_dedicated_database() -> None:
    running = run_command(["docker", "ps", "--format", "{{.Names}}"])
    if DATABASE_CONTAINER not in running.splitlines():
        raise OwnedRunError("dedicated_database_not_running")
    raw = run_command([
        "docker", "inspect", "--format", "{{json .HostConfig.PortBindings}}", DATABASE_CONTAINER,
    ])
    try:
        bindings = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OwnedRunError("database_binding_rejected") from exc
    validate_database_binding(bindings)


def run_psql(sql: str) -> str:
    return run_command(
        [
            "docker", "exec", "-i", DATABASE_CONTAINER,
            "psql", "-X", "-qAt", "-U", "postgres", "-d", "postgres",
            "-v", "ON_ERROR_STOP=1", "-f", "-",
        ],
        stdin=f"{sql.strip()}\n",
    )


def sql_uuid(value: str) -> str:
    return f"'{validate_uuid(value)}'::uuid"


def body_marker(run_id: str, actor_label: str) -> str:
    valid = validate_run_id(run_id)
    if actor_label not in {"a", "b"}:
        raise OwnedRunError("invalid_actor_label")
    return f"d4-owned-run:{valid}:actor-{actor_label}"


def validate_profiles(actor_a: str, actor_b: str) -> None:
    count = run_psql(
        f"select count(*) from public.users where id in ({sql_uuid(actor_a)},{sql_uuid(actor_b)});"
    )
    if count != "2":
        raise OwnedRunError("profiles_missing")


def foreign_key_contract_sql() -> str:
    return """
      select coalesce(string_agg(
        child_ns.nspname || '.' || child.relname || '.' || child_att.attname ||
        '->' || parent_ns.nspname || '.' || parent.relname || '.' || parent_att.attname,
        '|' order by child_ns.nspname, child.relname, child_att.attname
      ), '')
      from pg_constraint con
      join pg_class child on child.oid=con.conrelid
      join pg_namespace child_ns on child_ns.oid=child.relnamespace
      join pg_class parent on parent.oid=con.confrelid
      join pg_namespace parent_ns on parent_ns.oid=parent.relnamespace
      join lateral unnest(con.conkey) with ordinality child_key(attnum, ord) on true
      join lateral unnest(con.confkey) with ordinality parent_key(attnum, ord)
        on parent_key.ord=child_key.ord
      join pg_attribute child_att on child_att.attrelid=child.oid and child_att.attnum=child_key.attnum
      join pg_attribute parent_att on parent_att.attrelid=parent.oid and parent_att.attnum=parent_key.attnum
      where con.contype='f' and con.confrelid='public.posts'::regclass
    """


def validate_foreign_key_contract() -> None:
    actual = tuple(filter(None, run_psql(foreign_key_contract_sql()).split("|")))
    if actual != EXPECTED_POST_FOREIGN_KEYS:
        raise OwnedRunError("unknown_post_relationship")


def _validate_owned_directory(path: Path, *, private: bool) -> None:
    try:
        details = path.lstat()
    except OSError as exc:
        raise OwnedRunError("manifest_directory_rejected") from exc
    if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid():
        raise OwnedRunError("manifest_directory_rejected")
    if private and stat.S_IMODE(details.st_mode) != 0o700:
        raise OwnedRunError("manifest_directory_rejected")


def _create_owned_directory(path: Path, *, private: bool) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    except OSError as exc:
        raise OwnedRunError("manifest_directory_rejected") from exc
    _validate_owned_directory(path, private=private)


def ensure_manifest_directory(base_directory: Path | None = None) -> None:
    if base_directory is not None:
        _create_owned_directory(base_directory, private=True)
        return
    state_directory = persistent_state_directory()
    home = state_directory.parent.parent
    _validate_owned_directory(home, private=False)
    _create_owned_directory(home / ".local", private=False)
    _create_owned_directory(state_directory, private=False)
    _create_owned_directory(persistent_manifest_directory(), private=True)


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise OwnedRunError("manifest_directory_rejected") from exc
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def manifest_document(payload: dict[str, str], post_a: str, post_b: str) -> dict[str, Any]:
    return {
        "source_sha256": source_sha256(),
        "actors": {"a": validate_uuid(payload["actor_a"]), "b": validate_uuid(payload["actor_b"])},
        "posts": {"a": validate_uuid(post_a), "b": validate_uuid(post_b)},
    }


def reserve_manifest(path: Path, document: dict[str, Any]) -> tuple[int, str]:
    encoded = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise OwnedRunError("manifest_exists") from exc
    try:
        offset = 0
        while offset < len(encoded):
            offset += os.write(descriptor, encoded[offset:])
        os.fsync(descriptor)
        details = os.fstat(descriptor)
        if stat.S_IMODE(details.st_mode) != 0o600:
            raise OwnedRunError("manifest_mode_rejected")
        inode = details.st_ino
        digest = hashlib.sha256(encoded).hexdigest()
    except Exception:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        fsync_directory(path.parent)
        raise
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
    fsync_directory(path.parent)
    return inode, digest


def read_private_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except (FileNotFoundError, OSError) as exc:
        raise OwnedRunError("manifest_unavailable") from exc
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
            raise OwnedRunError("manifest_rejected")
        raw = os.read(descriptor, 64 * 1024)
        if os.read(descriptor, 1):
            raise OwnedRunError("manifest_rejected")
        return raw
    finally:
        os.close(descriptor)


def read_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = read_private_bytes(path)
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OwnedRunError("manifest_rejected") from exc
    validate_manifest(document)
    return document, hashlib.sha256(raw).hexdigest()


def validate_manifest(document: Any) -> None:
    if not isinstance(document, dict) or set(document) != {"source_sha256", "actors", "posts"}:
        raise OwnedRunError("manifest_rejected")
    if not re.fullmatch(r"[0-9a-f]{64}", document["source_sha256"]):
        raise OwnedRunError("manifest_rejected")
    if not isinstance(document["actors"], dict) or set(document["actors"]) != {"a", "b"}:
        raise OwnedRunError("manifest_rejected")
    if not isinstance(document["posts"], dict) or set(document["posts"]) != {"a", "b"}:
        raise OwnedRunError("manifest_rejected")
    actor_a = validate_uuid(document["actors"]["a"])
    actor_b = validate_uuid(document["actors"]["b"])
    post_a = validate_uuid(document["posts"]["a"])
    post_b = validate_uuid(document["posts"]["b"])
    if actor_a == actor_b or post_a == post_b:
        raise OwnedRunError("manifest_rejected")


def validate_manifest_source(document: dict[str, Any]) -> str:
    current = source_sha256()
    # Deliberate incompatibility: tool changes require an explicit reviewed
    # manifest migration, rather than silently trusting stale ownership data.
    if document["source_sha256"] != current:
        raise OwnedRunError("manifest_source_mismatch")
    return current


def advisory_lock_guard_sql() -> str:
    return f"""
      if not pg_try_advisory_xact_lock({ADVISORY_KEY_ONE},{ADVISORY_KEY_TWO}) then
        raise exception 'owned run lease unavailable';
      end if;
    """


def seed(payload: dict[str, str]) -> dict[str, Any]:
    verify_dedicated_database()
    validate_profiles(payload["actor_a"], payload["actor_b"])
    validate_foreign_key_contract()
    ensure_manifest_directory()
    path = manifest_path(payload["run_id"])
    post_a = str(uuid.uuid4())
    post_b = str(uuid.uuid4())
    document = manifest_document(payload, post_a, post_b)
    _inode, manifest_sha = reserve_manifest(path, document)
    marker_a = body_marker(payload["run_id"], "a")
    marker_b = body_marker(payload["run_id"], "b")
    try:
        run_psql(f"""
          begin;
          do $owned$
          begin
            {advisory_lock_guard_sql()}
            if (select count(*) from public.users where id in (
              {sql_uuid(payload['actor_a'])},{sql_uuid(payload['actor_b'])}
            )) <> 2 then
              raise exception 'owned run profiles missing';
            end if;
            if exists (
              select 1 from public.posts
              where id in ({sql_uuid(post_a)},{sql_uuid(post_b)})
                 or body in ('{marker_a}','{marker_b}')
            ) then
              raise exception 'owned run collision';
            end if;
          end
          $owned$;
          insert into public.posts(id,author_id,body) values
            ({sql_uuid(post_a)},{sql_uuid(payload['actor_a'])},'{marker_a}'),
            ({sql_uuid(post_b)},{sql_uuid(payload['actor_b'])},'{marker_b}');
          do $owned$
          begin
            if (select count(*) from public.posts where
              (id={sql_uuid(post_a)} and author_id={sql_uuid(payload['actor_a'])} and body='{marker_a}') or
              (id={sql_uuid(post_b)} and author_id={sql_uuid(payload['actor_b'])} and body='{marker_b}')
            ) <> 2 then
              raise exception 'owned run seed verification failed';
            end if;
          end
          $owned$;
          commit;
        """)
    except Exception as exc:
        # The child process may have disconnected after COMMIT. Retain the
        # manifest so reconciliation can prove whether the posts exist.
        raise OwnedRunError("seed_requires_database_reconciliation") from exc
    return {
        "status": "seeded",
        "posts": 2,
        "manifest_sha256": manifest_sha,
        "source_sha256": document["source_sha256"],
    }


def reset(payload: dict[str, str]) -> dict[str, Any]:
    verify_dedicated_database()
    ensure_manifest_directory()
    path = manifest_path(payload["run_id"])
    document, manifest_sha = read_manifest(path)
    if document["actors"] != {"a": payload["actor_a"], "b": payload["actor_b"]}:
        raise OwnedRunError("manifest_actor_mismatch")
    current_source_sha = validate_manifest_source(document)
    validate_profiles(payload["actor_a"], payload["actor_b"])
    validate_foreign_key_contract()
    post_a = document["posts"]["a"]
    post_b = document["posts"]["b"]
    marker_a = body_marker(payload["run_id"], "a")
    marker_b = body_marker(payload["run_id"], "b")
    expected_fks = "|".join(EXPECTED_POST_FOREIGN_KEYS)
    run_psql(f"""
      begin;
      do $owned$
      declare deleted_rows integer;
      begin
        {advisory_lock_guard_sql()}
        if ({foreign_key_contract_sql()}) <> '{expected_fks}' then
          raise exception 'unknown post relationship';
        end if;
        if (select count(*) from public.users where id in (
          {sql_uuid(payload['actor_a'])},{sql_uuid(payload['actor_b'])}
        )) <> 2 then
          raise exception 'owned run profiles missing';
        end if;
        if (select count(*) from public.posts where
          (id={sql_uuid(post_a)} and author_id={sql_uuid(payload['actor_a'])} and body='{marker_a}'
            and reply_to_post_id is null and repost_of_post_id is null) or
          (id={sql_uuid(post_b)} and author_id={sql_uuid(payload['actor_b'])} and body='{marker_b}'
            and reply_to_post_id is null and repost_of_post_id is null)
        ) <> 2 then
          raise exception 'owned post identity mismatch';
        end if;
        if exists (
          select 1 from public.posts
          where id not in ({sql_uuid(post_a)},{sql_uuid(post_b)})
            and (reply_to_post_id in ({sql_uuid(post_a)},{sql_uuid(post_b)})
              or repost_of_post_id in ({sql_uuid(post_a)},{sql_uuid(post_b)}))
        ) or exists (select 1 from public.post_media where post_id in ({sql_uuid(post_a)},{sql_uuid(post_b)}))
          or exists (select 1 from public.likes where post_id in ({sql_uuid(post_a)},{sql_uuid(post_b)}))
          or exists (select 1 from public.notifications where post_id in ({sql_uuid(post_a)},{sql_uuid(post_b)}))
          or exists (select 1 from public.post_hashtags where post_id in ({sql_uuid(post_a)},{sql_uuid(post_b)}))
          or exists (select 1 from public.bookmarks where post_id in ({sql_uuid(post_a)},{sql_uuid(post_b)})) then
          raise exception 'owned posts have foreign references';
        end if;
        delete from public.posts where id in ({sql_uuid(post_a)},{sql_uuid(post_b)});
        get diagnostics deleted_rows = row_count;
        if deleted_rows <> 2 then
          raise exception 'owned post delete count mismatch';
        end if;
      end
      $owned$;
      commit;
    """)
    return {
        "status": "reset",
        "posts": 2,
        "manifest_sha256": manifest_sha,
        "source_sha256": current_source_sha,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--seed", action="store_true")
    action.add_argument("--reset", action="store_true")
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        payload = parse_stdin_payload(sys.stdin.read(), arguments.run_id)
        result = seed(payload) if arguments.seed else reset(payload)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except OwnedRunError as exc:
        print(json.dumps({"status": "error", "code": exc.code}, sort_keys=True, separators=(",", ":")))
        return 2
    except Exception:
        print(json.dumps({"status": "error", "code": "internal_error"}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
