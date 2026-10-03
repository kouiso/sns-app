"""Reconstruct the disclosed chapter listing from the frozen Auth predecessor.

This proves text/source consistency only. It never launches a model, network,
Metro, UI, or database and is not an independent chapter execution receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path

from g6_broker import BrokerError, _read_regular, _safe_path, snapshot_digest

EXPECTED_CHAPTER_SHA256 = "93145b45bf929d867bbcee35b022d83e521510f9b54c4f31f0400f24fa340d37"
EXPECTED_AUTH_APP_SHA256 = "31a1deb465120c77dbd1fcd0f38ab0b21b3adf35e1474f0801a5492b21617b20"
EXPECTED_START_SHA256 = "9d6d508750d8341faf5a3ac7cd05434ba1c181ef127d8dbfa932b3e28fff99d5"
EXPECTED_FINAL_SHA256 = "681aea8e3273ff1197cc51136e7db6f819711b0178773cd328201ded50f37024"
EXPECTED_COMPONENT_SHA256 = "bb545fb408b491fea9b20bd0a345f91eb1a4596893e23faacdee9ef7ed904961"


class BuildVerificationError(ValueError):
    pass


def _closed_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BuildVerificationError("duplicate manifest key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise BuildVerificationError("non-JSON manifest constant")


def _reconstruct_from_chapter(candidate: Path) -> tuple[dict[str, bytes], dict[str, object]]:
    try:
        manifest = json.loads(_read_regular(candidate, "start-manifest.json", "start manifest"),
                              object_pairs_hook=_closed_pairs, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BuildVerificationError("invalid manifest JSON") from exc
    expected = {"version": 1, "scope": "NON_FORMAL_D4_CHAPTER_BUILD_START",
                "formal_start_frozen": False, "contains_rls_trial": False,
                "inherited_auth_app_sha256": EXPECTED_AUTH_APP_SHA256,
                "source": "auth-sdk57 tracked predecessor19 only"}
    if not isinstance(manifest, dict) or set(manifest) != set(expected) | {"files", "start_snapshot_sha256"}:
        raise BuildVerificationError("invalid manifest fields")
    if any(type(manifest[k]) is not type(value) or manifest[k] != value for k, value in expected.items()):
        raise BuildVerificationError("unreviewed manifest semantics")
    if manifest.get("start_snapshot_sha256") != EXPECTED_START_SHA256:
        raise BuildVerificationError("unreviewed start snapshot")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 19:
        raise BuildVerificationError("start must contain predecessor19")
    start = candidate / "start"
    files: dict[str, bytes] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise BuildVerificationError("invalid file entry")
        if not isinstance(entry["path"], str) or not isinstance(entry["sha256"], str):
            raise BuildVerificationError("invalid file entry values")
        name = _safe_path(entry["path"], "start path")
        if name in files:
            raise BuildVerificationError("duplicate start path")
        content = _read_regular(start, name, "start file")
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise BuildVerificationError("start file changed")
        files[name] = content
    actual_paths = set()
    expected_directories = {str(parent) for name in files for parent in Path(name).parents if str(parent) != "."}
    for path in start.rglob("*"):
        if path.is_symlink():
            raise BuildVerificationError("symlink in start")
        relative = str(path.relative_to(start))
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            actual_paths.add(relative)
        elif not stat.S_ISDIR(mode) or relative not in expected_directories:
            raise BuildVerificationError("undeclared directory or special start node")
    if actual_paths != set(files) or snapshot_digest(sorted(files.items())) != EXPECTED_START_SHA256:
        raise BuildVerificationError("start inventory or digest changed")
    original_app = files["App.tsx"].decode()
    if "RlsTrial" in original_app or "components/RlsTrial.tsx" in files:
        raise BuildVerificationError("start contains target UI")
    chapter_bytes = _read_regular(candidate, "chapter-build.md", "chapter")
    if hashlib.sha256(chapter_bytes).hexdigest() != EXPECTED_CHAPTER_SHA256:
        raise BuildVerificationError("unreviewed chapter text")
    chapter = chapter_bytes.decode()
    blocks = re.findall(r"^### コード (\d+)\n\n```tsx\n(.*?)^```", chapter, re.M | re.S)
    if [number for number, _ in blocks] != [str(i) for i in range(1, 16)]:
        raise BuildVerificationError("listing parts missing, duplicated, or reordered")
    component = "".join(text for _, text in blocks).encode()
    if hashlib.sha256(component).hexdigest() != EXPECTED_COMPONENT_SHA256:
        raise BuildVerificationError("disclosed component changed")
    hookup_start = "## サインイン後の画面につなぐ\n"
    hookup_end = "## 型を検査する\n"
    if chapter.count(hookup_start) != 1 or chapter.count(hookup_end) != 1:
        raise BuildVerificationError("hookup section headings missing or duplicated")
    start_offset = chapter.index(hookup_start) + len(hookup_start)
    end_offset = chapter.index(hookup_end)
    if start_offset > end_offset:
        raise BuildVerificationError("hookup section headings reordered")
    hookup = chapter[start_offset:end_offset]
    snippets = re.findall(r"^```tsx\n(.*?)^```", hookup, re.M | re.S)
    if len(snippets) != 3:
        raise BuildVerificationError("hookup requires import, old, new snippets")
    import_text, old, new = (snippet.rstrip("\n") for snippet in snippets)
    if import_text != "import { RlsTrial } from './components/RlsTrial';":
        raise BuildVerificationError("unreviewed import")
    expected_old = (
        "          ) : (\n"
        "            <Text style={styles.body}>メール確認済みのセッションです。"
        "SNS のプロフィール機能は次の実装範囲です。</Text>\n"
        "          )}"
    )
    expected_new = (
        "          ) : (\n"
        "            userId\n"
        "              ? <RlsTrial key={userId} client={client} userId={userId} />\n"
        "              : <Text style={styles.body}>ログイン状態をもう一度確認してください。</Text>\n"
        "          )}"
    )
    if old != expected_old or new != expected_new:
        raise BuildVerificationError("unreviewed UI hookup")
    if original_app.count(old) != 1:
        raise BuildVerificationError("replacement must match one predecessor context")
    changed = import_text + "\n" + original_app.replace(old, new, 1)
    result = dict(files)
    result["App.tsx"] = changed.encode()
    result["components/RlsTrial.tsx"] = component
    final_digest = snapshot_digest(sorted(result.items()))
    if final_digest != EXPECTED_FINAL_SHA256:
        raise BuildVerificationError("unreviewed final source snapshot")
    receipt = {
        "scope": "CHAPTER_TEXT_RECONSTRUCTION_NOT_INDEPENDENT_EXEC",
        "start_files": 19,
        "final_files": 20,
        "chapter_sha256": hashlib.sha256(chapter_bytes).hexdigest(),
        "start_snapshot_sha256": EXPECTED_START_SHA256,
        "final_snapshot_sha256": final_digest,
        "component_sha256": EXPECTED_COMPONENT_SHA256,
        "changed_paths": ["App.tsx", "components/RlsTrial.tsx"],
        "model_or_UI_run": False,
    }
    return result, receipt


def reconstruct_from_chapter(candidate: Path) -> tuple[dict[str, bytes], dict[str, object]]:
    try:
        return _reconstruct_from_chapter(candidate)
    except BuildVerificationError:
        raise
    except (BrokerError, OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise BuildVerificationError("invalid candidate source or manifest") from exc
