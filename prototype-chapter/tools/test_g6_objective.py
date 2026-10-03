from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Mapping

from g6_broker import snapshot_digest
from g6_objective import (
    OBJECTIVE_SCOPE,
    OBSERVER_SCOPE,
    ObjectiveError,
    artifact_tree_digest,
    evaluate_objective,
    validate_artifact_stages_only,
    validate_broker_receipt_schema,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def tree_spec(root: Path) -> dict[str, object]:
    files: list[tuple[str, bytes]] = []
    directories: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            directories.append(relative)
        else:
            files.append((relative, path.read_bytes()))
    return {
        "files": [{"path": path, "sha256": sha(data)} for path, data in files],
        "directories": directories,
        "broker_snapshot_sha256": snapshot_digest(files),
        "tree_sha256": artifact_tree_digest(files, directories),
    }


class ObjectiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.inputs = self.base / "trusted-input"
        self.start = self.base / "start"
        self.text = self.base / "stage-text"
        self.style = self.base / "stage-style"
        self.restored = self.base / "stage-restored"
        self.capture = self.base / "trusted-capture"
        for path in (
            self.inputs,
            self.start,
            self.text,
            self.style,
            self.restored,
            self.capture,
        ):
            path.mkdir()
        prototype_root = Path(__file__).resolve().parent.parent
        self.chapter = (prototype_root / "chapter-live-reload.md").read_bytes()
        (self.inputs / "chapter-live-reload.md").write_bytes(self.chapter)
        self.start_app = (
            prototype_root / "listings" / "expo-first-screen" / "App.tsx"
        ).read_bytes()
        self.final_app = (
            prototype_root / "listings" / "live-reload" / "App.tsx"
        ).read_bytes()
        self.text_app = self.start_app.replace(
            b'      <StatusBar style="auto" />',
            (
                b"      <Text style={styles.note}>"
                b"\xe3\x81\x84\xe3\x81\xbe\xe6\x9b\xb8\xe3\x81\x8d\xe6\x8f\x9b\xe3\x81\x88\xe3\x81\x9f\xe3\x81\xa8\xe3\x81\x93\xe3\x82\x8d\xe3\x81\x8c\xe3\x80\x81"
                b"\xe3\x81\x99\xe3\x81\x90\xe3\x81\x93\xe3\x81\x93\xe3\x81\xab\xe5\x87\xba\xe3\x81\xbe\xe3\x81\x99</Text>\n"
                b'      <StatusBar style="auto" />'
            ),
        )
        (self.start / "App.tsx").write_bytes(self.start_app)
        (self.text / "App.tsx").write_bytes(self.text_app)
        (self.style / "App.tsx").write_bytes(self.final_app)
        (self.restored / "App.tsx").write_bytes(self.final_app)
        self.now = int(time.time())
        self.actions = [
            ("fixture-edit-text", "fixture-write-text", "write"),
            ("fixture-edit-style", "fixture-write-style", "write"),
            ("fixture-git-commit", "fixture-commit-app", "command"),
            ("fixture-temporary-edit", "fixture-write-temporary", "write"),
            ("fixture-git-restore", "fixture-restore-app", "command"),
        ]
        self.trace = self.make_trace()
        self.receipt = {
            "trace": self.trace,
            "trace_sha256": sha(canonical(self.trace)),
        }
        self.receipt_path = self.base / "broker-receipt.json"
        self.write_json(self.receipt_path, self.receipt)
        self.objective = self.make_objective()
        self.objective_path = self.base / "objective.json"
        self.write_json(self.objective_path, self.objective)
        self.observation_path = self.capture / "ui-receipt.json"
        self.observation = self.make_observation()
        self.write_json(self.observation_path, self.observation)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def action_trace(self, action_id: str, operation: str, kind: str) -> dict[str, Any]:
        value: dict[str, Any] = {"id": action_id, "operation": operation, "kind": kind}
        if kind == "write":
            value["content_sha256"] = sha(action_id.encode())
        elif kind == "command":
            value.update(
                {
                    "argv_sha256": sha(operation.encode()),
                    "exit_code": 0,
                    "stdout_sha256": sha(b""),
                    "stderr_sha256": sha(b""),
                }
            )
        return value

    def make_trace(self) -> dict[str, Any]:
        hashes = {
            "broker_source_sha256": sha(b"broker-source"),
            "probe_source_sha256": sha(b"probe-source"),
            "operation_table_sha256": sha(b"operation-table"),
            "bwrap_sha256": sha(b"bwrap"),
            "kernel_release_sha256": sha(b"kernel"),
            "sandbox_recipe_sha256": sha(b"recipe"),
        }
        return {
            "schema": "g6-broker-trace-v1",
            "scope": "G6_BROKER_PROBE_COMPONENT_NON_FORMAL",
            "claims": {
                "formal_g6_exec": False,
                "knowledge_isolation": False,
                "ui_validated": False,
                "a0_chapter_execution": False,
                "model_mcp_connected": False,
            },
            "artifact_id": "run-live-reload-001",
            "manifest_sha256": sha(b"manifest"),
            "chapter_sha256": sha(self.chapter),
            "start_snapshot_sha256": tree_spec(self.start)["broker_snapshot_sha256"],
            "artifact_snapshot_sha256": tree_spec(self.restored)[
                "broker_snapshot_sha256"
            ],
            "artifact_directories": tree_spec(self.restored)["directories"],
            "artifact_tree_sha256": tree_spec(self.restored)["tree_sha256"],
            **hashes,
            "preflight": {
                "clean_environment": True,
                "host_paths_hidden": True,
                "network_blocked": True,
                "pid_namespace": True,
                "private_home": True,
                "toolchain_read_only": True,
                "uts_namespace": True,
            },
            "actions": [self.action_trace(*action) for action in self.actions],
        }

    def stage(self, stage_id: str, after: str, final: bool, root: Path) -> dict[str, Any]:
        return {
            "id": stage_id,
            "after_action": after,
            "final": final,
            "must_differ_from_start": True,
            **tree_spec(root),
        }

    def make_objective(self) -> dict[str, Any]:
        return {
            "version": 1,
            "scope": OBJECTIVE_SCOPE,
            "run_id": "run-live-reload-001",
            "timing": {"not_before_epoch": self.now - 5, "max_age_seconds": 60},
            "chapter": {
                "id": "live-reload",
                "path": "chapter-live-reload.md",
                "sha256": sha(self.chapter),
            },
            "start": tree_spec(self.start),
            "broker": {
                field: self.trace[field]
                for field in (
                    "scope",
                    "manifest_sha256",
                    "broker_source_sha256",
                    "probe_source_sha256",
                    "operation_table_sha256",
                    "bwrap_sha256",
                    "kernel_release_sha256",
                    "sandbox_recipe_sha256",
                )
            },
            "expected_actions": [
                {"id": action_id, "operation": operation, "kind": kind}
                for action_id, operation, kind in self.actions
            ],
            "artifact_stages": [
                self.stage("text", "fixture-edit-text", False, self.text),
                self.stage("style", "fixture-edit-style", False, self.style),
                self.stage(
                    "git-restored", "fixture-git-restore", True, self.restored
                ),
            ],
            "observations": [
                {
                    "id": "saved-ui-changed",
                    "kind": "ui-live-reload-after-save",
                    "stage": "style",
                    "expectation_sha256": sha(
                        b"green note appears after save without device action"
                    ),
                }
            ],
        }

    def make_observation(self) -> dict[str, Any]:
        objective_observation = self.objective["observations"][0]
        return {
            "version": 1,
            "scope": OBSERVER_SCOPE,
            "observer_id": "controller-capture-stub",
            "run_id": self.objective["run_id"],
            "captured_at_epoch": self.now,
            "chapter_sha256": self.objective["chapter"]["sha256"],
            "start_snapshot_sha256": self.objective["start"][
                "broker_snapshot_sha256"
            ],
            "trace_sha256": self.receipt["trace_sha256"],
            "artifact_stage_hashes": {
                stage["id"]: stage["tree_sha256"]
                for stage in self.objective["artifact_stages"]
            },
            "observations": [
                {
                    "id": objective_observation["id"],
                    "kind": objective_observation["kind"],
                    "expectation_sha256": objective_observation[
                        "expectation_sha256"
                    ],
                    "evidence_sha256": sha(b"opaque-controller-capture"),
                    "status": "observed",
                }
            ],
        }

    def roots(self) -> dict[str, Path]:
        return {"text": self.text, "style": self.style, "git-restored": self.restored}

    def trusted_stub(
        self, path: Path, raw: bytes, receipt: Mapping[str, Any]
    ) -> bool:
        return (
            path.parent == self.capture
            and raw == self.observation_path.read_bytes()
            and receipt["observer_id"] == "controller-capture-stub"
        )

    def evaluate(self, **overrides: Any) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "objective_path": self.objective_path,
            "broker_receipt_path": self.receipt_path,
            "trusted_input_root": self.inputs,
            "start_root": self.start,
            "artifact_roots": self.roots(),
            "now_epoch": self.now,
        }
        arguments.update(overrides)
        return evaluate_objective(**arguments)

    def refresh(self) -> None:
        self.write_json(self.receipt_path, self.receipt)
        self.write_json(self.objective_path, self.objective)
        self.write_json(self.observation_path, self.observation)

    def test_artifact_stages_pass_but_formal_status_stays_not_ready(self) -> None:
        result = self.evaluate()
        self.assertEqual("NOT_READY", result["status"])
        self.assertEqual("UNSUPPORTED", result["checks"]["ui_observation"])
        self.assertEqual(
            {"text": "PASS", "style": "PASS", "git-restored": "PASS"},
            result["checks"]["artifact_stages"],
        )

    def test_actual_live_reload_app_files_support_artifact_only_validation(self) -> None:
        result = validate_artifact_stages_only(
            self.objective["start"],
            self.start,
            self.objective["artifact_stages"],
            self.roots(),
        )
        self.assertEqual("ARTIFACT_ONLY_VALIDATED_NON_FORMAL", result["status"])
        self.assertEqual(
            {"actions": False, "ui": False, "formal_g6_exec": False},
            result["claims"],
        )

    def test_real_root_broker_receipt_uses_the_supported_producer_schema(self) -> None:
        configured = os.environ.get("G6_CAPTURED_BROKER_RECEIPT")
        if configured is None:
            self.skipTest("G6_CAPTURED_BROKER_RECEIPT is not configured")
        receipt = Path(configured)
        if not receipt.is_file():
            self.fail("configured G6_CAPTURED_BROKER_RECEIPT is not a file")
        trace, trace_hash = validate_broker_receipt_schema(receipt)
        self.assertEqual("G6_BROKER_PROBE_COMPONENT_NON_FORMAL", trace["scope"])
        self.assertEqual(self.receipt_hash_from_file(receipt), trace_hash)

    def receipt_hash_from_file(self, receipt: Path) -> str:
        value = json.loads(receipt.read_text(encoding="utf-8"))
        digest = value["trace_sha256"]
        if not isinstance(digest, str):
            self.fail("real receipt trace hash is not a string")
        return digest

    def test_trusted_callback_verifies_binding_without_claiming_formal_pass(self) -> None:
        result = self.evaluate(
            observation_path=self.observation_path,
            observation_verifier=self.trusted_stub,
        )
        self.assertEqual("NOT_READY", result["status"])
        self.assertEqual(
            "VERIFIED_BY_TRUSTED_CALLBACK", result["checks"]["ui_observation"]
        )

    def test_missing_noop_or_out_of_order_actions_fail_closed(self) -> None:
        for index, actions in enumerate(
            ([], self.trace["actions"][:-1], list(reversed(self.trace["actions"])))
        ):
            self.trace["actions"] = actions
            self.receipt["trace"] = self.trace
            self.receipt["trace_sha256"] = sha(canonical(self.trace))
            self.refresh()
            with self.subTest(index=index), self.assertRaises(ObjectiveError):
                self.evaluate()
        self.trace = self.make_trace()

    def test_final_stage_must_be_last_and_follow_last_required_action(self) -> None:
        for final_index in (0, 1):
            candidate = copy.deepcopy(self.objective)
            for index, stage in enumerate(candidate["artifact_stages"]):
                stage["final"] = index == final_index
            self.write_json(self.objective_path, candidate)
            with self.subTest(final_index=final_index), self.assertRaisesRegex(
                ObjectiveError, "final artifact stage must be last"
            ):
                self.evaluate()

        candidate = copy.deepcopy(self.objective)
        candidate["artifact_stages"][-1]["after_action"] = "fixture-git-commit"
        self.write_json(self.objective_path, candidate)
        with self.assertRaisesRegex(ObjectiveError, "last required action"):
            self.evaluate()

    def test_manifest_hash_is_bound_to_the_objective(self) -> None:
        self.trace["manifest_sha256"] = sha(b"different-manifest")
        self.receipt["trace"] = self.trace
        self.receipt["trace_sha256"] = sha(canonical(self.trace))
        self.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(ObjectiveError, "manifest_sha256"):
            self.evaluate()

    def test_nested_mixed_paths_use_broker_path_order_for_tree_hash(self) -> None:
        root = self.base / "mixed-order"
        (root / "a").mkdir(parents=True)
        (root / "a.txt").write_bytes(b"flat")
        (root / "a" / "b.txt").write_bytes(b"nested")
        files = [
            (path.relative_to(root).as_posix(), path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]
        directories = [
            path.relative_to(root).as_posix()
            for path in sorted(root.rglob("*"))
            if path.is_dir()
        ]
        expected = sha(
            canonical(
                {
                    "files_sha256": snapshot_digest(files),
                    "directories": directories,
                }
            )
        )
        self.assertEqual(expected, artifact_tree_digest(list(reversed(files)), directories))

    def test_start_equals_final_and_stale_receipt_fail_closed(self) -> None:
        (self.restored / "App.tsx").write_bytes(self.start_app)
        final_spec = tree_spec(self.restored)
        self.objective["artifact_stages"][-1].update(final_spec)
        self.trace["artifact_snapshot_sha256"] = final_spec["broker_snapshot_sha256"]
        self.receipt["trace"] = self.trace
        self.receipt["trace_sha256"] = sha(canonical(self.trace))
        self.refresh()
        with self.assertRaisesRegex(ObjectiveError, "equals the start"):
            self.evaluate()

        (self.restored / "App.tsx").write_bytes(self.final_app)
        self.trace = self.make_trace()
        self.receipt = {"trace": self.trace, "trace_sha256": sha(canonical(self.trace))}
        self.objective = self.make_objective()
        self.observation = self.make_observation()
        self.refresh()
        old = self.now - 120
        os.utime(self.receipt_path, (old, old))
        with self.assertRaisesRegex(ObjectiveError, "stale"):
            self.evaluate()

    def test_unknown_fields_bool_fakes_and_broken_trace_hash_fail_closed(self) -> None:
        cases: list[tuple[str, Any]] = [
            ("extra", "ignored"),
            ("version", True),
        ]
        for key, value in cases:
            candidate = copy.deepcopy(self.objective)
            candidate[key] = value
            self.write_json(self.objective_path, candidate)
            with self.subTest(key=key), self.assertRaises(ObjectiveError):
                self.evaluate()
        self.write_json(self.objective_path, self.objective)
        self.receipt["trace_sha256"] = "0" * 64
        self.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(ObjectiveError, "trace hash"):
            self.evaluate()

    def test_duplicate_nan_recipe_binding_and_bool_exit_fail_closed(self) -> None:
        raw = self.objective_path.read_text(encoding="utf-8")
        self.objective_path.write_text(
            raw[:-1] + f',"scope":"{OBJECTIVE_SCOPE}"}}', encoding="utf-8"
        )
        with self.assertRaisesRegex(ObjectiveError, "duplicate JSON field"):
            self.evaluate()

        invalid_nan = copy.deepcopy(self.objective)
        invalid_nan["timing"]["max_age_seconds"] = float("nan")
        self.write_json(self.objective_path, invalid_nan)
        with self.assertRaisesRegex(ObjectiveError, "invalid JSON constant"):
            self.evaluate()

        self.write_json(self.objective_path, self.objective)
        self.trace["sandbox_recipe_sha256"] = "0" * 64
        self.receipt["trace"] = self.trace
        self.receipt["trace_sha256"] = sha(canonical(self.trace))
        self.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(ObjectiveError, "sandbox_recipe_sha256"):
            self.evaluate()

        self.trace = self.make_trace()
        self.trace["actions"][-1]["exit_code"] = True
        self.receipt = {
            "trace": self.trace,
            "trace_sha256": sha(canonical(self.trace)),
        }
        self.objective = self.make_objective()
        self.write_json(self.receipt_path, self.receipt)
        self.write_json(self.objective_path, self.objective)
        with self.assertRaisesRegex(ObjectiveError, "did not succeed"):
            self.evaluate()

    def test_artifact_mismatch_extra_file_and_symlink_fail_closed(self) -> None:
        (self.text / "App.tsx").write_bytes(b"wrong\n")
        with self.assertRaisesRegex(ObjectiveError, "tree differs"):
            self.evaluate()
        (self.text / "App.tsx").write_bytes(self.text_app)
        (self.style / "unexpected.txt").write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(ObjectiveError, "tree differs"):
            self.evaluate()
        (self.style / "unexpected.txt").unlink()
        (self.text / "link").symlink_to("App.tsx")
        with self.assertRaisesRegex(ObjectiveError, "symlink"):
            self.evaluate()

    def test_broker_final_directories_and_tree_must_match_actual_artifact(self) -> None:
        self.trace["artifact_directories"] = ["unexpected"]
        self.trace["artifact_tree_sha256"] = sha(
            canonical(
                {
                    "files_sha256": self.trace["artifact_snapshot_sha256"],
                    "directories": ["unexpected"],
                }
            )
        )
        self.receipt["trace"] = self.trace
        self.receipt["trace_sha256"] = sha(canonical(self.trace))
        self.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(ObjectiveError, "directories"):
            self.evaluate()

    def test_ui_receipt_inside_workspace_or_with_stale_binding_is_rejected(self) -> None:
        forged = self.restored / "ui-receipt.json"
        self.write_json(forged, self.observation)
        with self.assertRaisesRegex(ObjectiveError, "outside"):
            self.evaluate(
                observation_path=forged, observation_verifier=self.trusted_stub
            )
        forged.unlink()

        self.observation["trace_sha256"] = "0" * 64
        self.write_json(self.observation_path, self.observation)
        with self.assertRaisesRegex(ObjectiveError, "trace binding"):
            self.evaluate(
                observation_path=self.observation_path,
                observation_verifier=self.trusted_stub,
            )

        self.observation = self.make_observation()
        self.observation["captured_at_epoch"] = self.now - 120
        self.write_json(self.observation_path, self.observation)
        with self.assertRaisesRegex(ObjectiveError, "stale"):
            self.evaluate(
                observation_path=self.observation_path,
                observation_verifier=self.trusted_stub,
            )

    def test_schema_valid_ui_json_is_not_truth_without_trusted_callback(self) -> None:
        result = self.evaluate(observation_path=self.observation_path)
        self.assertEqual("UNSUPPORTED", result["checks"]["ui_observation"])
        with self.assertRaisesRegex(ObjectiveError, "trusted UI observer rejected"):
            self.evaluate(
                observation_path=self.observation_path,
                observation_verifier=lambda _path, _raw, _receipt: False,
            )


if __name__ == "__main__":
    unittest.main()
