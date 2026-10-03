"""Verify SDK57 candidate integrity; never grant curriculum approval."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any


class CandidateError(ValueError):
    """Candidate bytes or declarations are inconsistent."""


SCOPE = "SDK57_A0_CANDIDATE_NON_FORMAL"
MANIFEST_FIELDS = {
    "chapter_entries",
    "claims",
    "file_sha256",
    "formal_start_frozen",
    "manifest_self_hash",
    "observations",
    "phase0_approval_changed",
    "provenance",
    "r2_status",
    "scope",
    "shared_start_source",
    "version",
}
CLAIMS = {
    "beginner_flow_observed",
    "formal_curriculum",
    "formal_r2_available",
    "g3_passed",
    "g6_passed",
    "sdk57_adopted",
}
HASH = re.compile(r"[0-9a-f]{64}\Z")
# Filled from the reviewed, immutable 14-file starter; the candidate manifest
# cannot authorize different source bytes by merely updating its own hashes.
START_HASHES: dict[str, str] = {
    "start-source/.gitignore": "5936b94a73a28b6735de672b54c2c058a33c9ae1edb62d87d6a4418e14447805",
    "start-source/App.tsx": "5c7d8b989dc7a6a70e4a6be61ec95b1c5a1562e8a510efb3aa6b8cbe94033190",
    "start-source/LICENSE": "fb3ca4a837f5779e83cef89b78253a8949cfb9429c340309f62d0465ec6610b4",
    "start-source/app.json": "8c84324e2e1650a62a2b592a2e0b36668ec37965b02ae63dcfd12cdee9cd5be4",
    "start-source/assets/android-icon-background.png": "fb139c2dee362ebf2070e23b96da6fc0d43f8492de38b8af1fd7223e19b5861d",
    "start-source/assets/android-icon-foreground.png": "9e3d0315a33c6799de601dd34cd8bf8cc3a8d16f3bf75592baec2ceb7240b391",
    "start-source/assets/android-icon-monochrome.png": "6371fc2c12e33ad2215a86c281db3d682a81bebe7c957a842c13b8bf00cceb83",
    "start-source/assets/favicon.png": "a4e030697a7571b3e95d31860e4da55d2f98e5e861e2b55e414f45a8556828ba",
    "start-source/assets/icon.png": "119462bb78eb240a65c869fc067ee599639b3cb5a41953f25c07b17d2a8c7e0f",
    "start-source/assets/splash-icon.png": "5f4c0a732b6325bf4071d9124d2ae67e037cb24fcc9c482ef82bea742109a3b8",
    "start-source/index.ts": "5c157f4d44972d9c84415e1e4bda595b3abcd8cf733f8a9cd20935bec3eccc42",
    "start-source/package-lock.json": "ceaef42805134421829a322d114e5b12d46c6c450d2a4d8de2ee246bb357131d",
    "start-source/package.json": "fa499830a8bf57bf29aadeab3261371684046ef496761b2add2e8271a511bc32",
    "start-source/tsconfig.json": "712583ff9cdb4b4e4f9b000a4a56d68db8dc1921cbfbc36d490a3a9f2be3dd72",
}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CandidateError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise CandidateError(f"non-finite JSON constant: {value}")


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or value == "." or "\\" in value:
        raise CandidateError("unsafe relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(char) < 32 for char in value)
    ):
        raise CandidateError("unsafe relative path")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CandidateError(f"{label} must be an object")
    return value


def _regular(path: Path) -> bytes:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise CandidateError("expected regular non-symlink file")
    return path.read_bytes()


def _control_content(text: str, note: str) -> list[str]:
    return [
        line for line in text.splitlines() if line.strip() and not line.startswith(note)
    ]


def _verify_controls(root: Path) -> None:
    for identifier in ("expo-first-screen", "live-reload"):
        body = _regular(root / f"chapter-{identifier}.md").decode("utf-8")
        plain = _regular(root / f"controls/{identifier}/plain.md").decode("utf-8")
        expected = [
            line
            for line in body.splitlines()
            if line.strip() and not re.fullmatch(r"(?:阿部|磯貝)「.*」", line)
        ]
        if _control_content(plain, "> **対照版メモ**") != expected:
            raise CandidateError("plain control changed non-dialogue content")
    body = _regular(root / "chapter-expo-first-screen.md").decode("utf-8")
    experimental = _regular(
        root / "controls/expo-first-screen/intro-ablation.experimental.md"
    ).decode("utf-8")
    lines = body.splitlines()
    removed = 0
    expected = []
    for line in lines:
        if removed < 2 and re.fullmatch(r"(?:阿部|磯貝)「.*」", line):
            removed += 1
        elif line.strip():
            expected.append(line)
    if removed != 2 or _control_content(experimental, "> **実験版メモ**") != expected:
        raise CandidateError("experimental intro ablation changed other content")


def validate(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise CandidateError("candidate root must be a non-symlink directory")
    manifest = _mapping(
        json.loads(
            _regular(root / "candidate-manifest.json").decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        ),
        "manifest",
    )
    if set(manifest) != MANIFEST_FIELDS:
        raise CandidateError("unsupported manifest fields")
    if manifest["r2_status"] != "unavailable_until_classified_high_friction_exists":
        raise CandidateError("formal R2 is unavailable for this candidate")
    if type(manifest.get("version")) is not int or manifest["version"] != 1:
        raise CandidateError("unsupported manifest version")
    if manifest.get("scope") != SCOPE:
        raise CandidateError("unsupported candidate scope")
    for field in ("formal_start_frozen", "phase0_approval_changed"):
        if manifest.get(field) is not False:
            raise CandidateError("formal approval declarations must stay false")
    if manifest.get("manifest_self_hash", "missing") is not None:
        raise CandidateError("manifest self hash must be null")
    claims = _mapping(manifest.get("claims"), "claims")
    if set(claims) != CLAIMS or any(value is not False for value in claims.values()):
        raise CandidateError("candidate claims must be boolean false")
    files = _mapping(manifest.get("file_sha256"), "file hashes")
    expected_files = set(START_HASHES) | {
        "README.md",
        "answers.md",
        "chapter-expo-first-screen.md",
        "chapter-live-reload.md",
        "completed-live/App.tsx",
        "controls/expo-first-screen/plain.md",
        "controls/live-reload/plain.md",
        "controls/expo-first-screen/intro-ablation.experimental.md",
    }
    for key, value in files.items():
        _path(key)
        if not isinstance(value, str) or not HASH.fullmatch(value):
            raise CandidateError("invalid file SHA-256")
    if set(files) != expected_files:
        raise CandidateError("candidate file set differs from the reviewed layout")
    if "candidate-manifest.json" in files:
        raise CandidateError("manifest must not hash itself")
    actual: dict[str, str] = {}
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            directories.add(relative)
        elif stat.S_ISREG(mode):
            if relative != "candidate-manifest.json":
                actual[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            raise CandidateError("symlinks and special entries are forbidden")
    if actual != files:
        raise CandidateError("candidate file closure or hash mismatch")
    expected_directories = {
        parent.as_posix()
        for name in files
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }
    if directories != expected_directories:
        raise CandidateError("candidate directory closure mismatch")
    source = {
        key: value for key, value in files.items() if key.startswith("start-source/")
    }
    if source != START_HASHES:
        raise CandidateError("reviewed 14-file starter mismatch")
    shared = _mapping(manifest.get("shared_start_source"), "shared start source")
    if (
        shared.get("path") != "start-source"
        or type(shared.get("file_count")) is not int
    ):
        raise CandidateError("shared start source declaration mismatch")
    if shared["file_count"] != 14 or shared.get("files") != START_HASHES:
        raise CandidateError("shared start source declaration mismatch")
    entries = manifest.get("chapter_entries")
    if not isinstance(entries, list) or len(entries) != 2:
        raise CandidateError("expected two chapter entries")
    seen: set[str] = set()
    for value in entries:
        entry = _mapping(value, "chapter entry")
        identifier = entry.get("id")
        if (
            not isinstance(identifier, str)
            or identifier not in {"expo-first-screen", "live-reload"}
            or identifier in seen
        ):
            raise CandidateError("unknown or duplicate chapter entry")
        seen.add(identifier)
        if entry.get("start_source") != "start-source":
            raise CandidateError("chapter start source mismatch")
        expected_kind = (
            "bootstrap"
            if identifier == "expo-first-screen"
            else "previous_chapter_completion"
        )
        if entry.get("start_state_kind") != expected_kind:
            raise CandidateError("chapter start state kind mismatch")
        references = [entry.get("chapter"), entry.get("exercise_answers")]
        controls = entry.get("controls")
        if not isinstance(controls, list):
            raise CandidateError("chapter controls must be a list")
        references.extend(controls)
        experimental = entry.get("experimental_controls", [])
        if not isinstance(experimental, list):
            raise CandidateError("experimental controls must be a list")
        references.extend(experimental)
        if "expected_app" in entry:
            references.append(entry["expected_app"])
        for reference in references:
            if _path(reference) not in files:
                raise CandidateError("chapter reference is unlisted")
    _verify_controls(root)
    return {
        "scope": SCOPE,
        "status": "INTEGRITY_COMPONENT_PASS",
        "formal_g6": False,
        "formal_start_frozen": False,
        "file_count": len(actual),
        "shared_start_file_count": len(source),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_sdk57_candidate.py CANDIDATE_DIRECTORY", file=sys.stderr)
        return 2
    try:
        result = validate(Path(sys.argv[1]))
    except (CandidateError, OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
