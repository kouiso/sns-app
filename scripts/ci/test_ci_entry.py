"""共有入口を実行し、教材やアプリの実データを使わず制御契約を検査する。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[2]


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.log = self.root / 'calls.jsonl'
        entry = SOURCE / '.github/ci/run.sh'
        self.assertTrue(entry.is_file(), 'shared executable CI entry must exist')
        (self.root / '.github/ci').mkdir(parents=True)
        shutil.copyfile(entry, self.root / '.github/ci/run.sh')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        tool = '''#!INTERPRETER
import json, os, pathlib, sys
name = os.environ.get('MOCK_NAME', pathlib.Path(sys.argv[0]).name)
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as log:
    log.write(json.dumps([name, args, str(pathlib.Path.cwd().relative_to(os.environ['FIXTURE_ROOT']))]) + '\\n')
if name == 'pr-target-chapters.sh':
    print(os.environ.get('TARGET_IDS', ''))
if name == 'python3' and args[:1] == ['-c']:
    print('[]')
if name == 'go' and args[:1] == ['env']:
    print('/unused')
if name == 'python3' and args and 'check_structure.py' in args[0]:
    print('  fixture.md:1 advisory')
needle = os.environ.get('FAIL_AT', '')
if needle and needle in name + ' ' + ' '.join(args):
    sys.exit(int(os.environ.get('FAIL_CODE', '37')))
'''.replace('INTERPRETER', sys.executable)
        self.write(self.bin / 'mock', tool)
        for name in ['python3', 'node', 'npm', 'go', 'cmp']:
            self.write(self.bin / name, tool)
        for name in ['g3-style.sh', 'g3-structure.sh', 'g3-policy.sh', 'g3-dev-log.sh', 'g3-start-state.sh', 'g4-receipt.sh', 'pr-target-chapters.sh']:
            self.write(self.root / 'prototype-chapter/tools' / name, '#!/usr/bin/env bash\nMOCK_NAME=' + name + ' exec "$FIXTURE_ROOT/bin/mock" "$@"\n')
        gate = self.root / 'prototype-chapter/tools/gate-step.sh'
        gate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / 'prototype-chapter/tools/gate-step.sh', gate)
        gate.chmod(0o755)
        self.write(self.root / 'prototype-chapter/candidates/auth-sdk57/node_modules/.bin/tsc', tool)
        (self.root / 'prototype-chapter/candidates/d4-rls/app').mkdir(parents=True)
        (self.root / 'prototype-chapter/candidates/d4-predecessor').mkdir(parents=True)
        (self.root / 'scripts/curriculum-qa').mkdir(parents=True)
        (self.root / 'scripts/curriculum-qa/test_a.py').touch()
        (self.root / 'scripts/curriculum-qa/test_b.py').touch()
        (self.root / 'prototype-chapter/chapter-fixture.md').touch()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        CALLS=str(self.log), FIXTURE_ROOT=str(self.root))
        for name in ['GITHUB_WORKSPACE', 'CI_EVENT_NAME', 'CI_PR_BASE_SHA', 'D4_REQUIRE_REAL_TOOLCHAIN', 'FAIL_AT', 'FAIL_CODE']:
            self.env.pop(name, None)

    def write(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        path.chmod(0o755)

    def run_entry(self, phase, **env):
        return subprocess.run(['bash', str(self.root / '.github/ci/run.sh'), phase],
                              cwd=self.temporary.name, env=dict(self.env, **env),
                              text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_full_runs_all_workflow_families_and_bootstraps(self):
        run = self.run_entry('all')
        self.assertEqual(run.returncode, 0, run.stderr)
        calls = self.calls()
        text = json.dumps(calls)
        for required in ['campoy/embedmd@v1.0.0', 'test_a.py', 'test_b.py', 'test_g3_checks.py', 'test_g6_support.py', 'test_g6_objective.py', 'verify_sdk57_candidate.py', 'test_verify_sdk57_candidate.py', 'test_g6_broker.py', 'test_g6_live_reload.py', 'test_auth_return.mjs', 'test:auth', 'typecheck', 'test_*owned.py', 'test_d4_*.py', 'test_verify_d4_chapter_build.py', 'd4-heavy/chapter-rls-denial-check.md', 'test-profile-flow.mjs', 'gate:g3:trial', 'g3-dev-log.sh', 'g3-start-state.sh', 'g4-receipt.sh', 'check_epub_reference.py', 'check_pdf_links.py', 'check_unused_image.py', 'gate:quote']:
            self.assertIn(required, text)
        self.assertIn(['npm', ['ci'], 'prototype-chapter'], calls)
        self.assertIn(['npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund'], 'prototype-chapter/candidates/auth-sdk57'], calls)

    def test_checks_uses_same_checks_without_bootstrap_and_is_repeatable(self):
        for _ in range(2):
            run = self.run_entry('checks')
            self.assertEqual(run.returncode, 0, run.stderr)
        calls = self.calls()
        self.assertNotIn(['npm', ['ci'], 'prototype-chapter'], calls)
        self.assertIn(['npm', ['run', 'gate:quote'], 'prototype-chapter'], calls)
        self.assertEqual((self.root / 'prototype-chapter/candidates/d4-rls/app/node_modules').readlink(), Path('../../auth-sdk57/node_modules'))

    def test_default_failure_stops_candidates_but_runs_material_and_preserves_first_failure(self):
        run = self.run_entry('checks', FAIL_AT='test_g3_checks.py')
        self.assertEqual(run.returncode, 37, run.stderr)
        text = json.dumps(self.calls())
        self.assertNotIn('verify_sdk57_candidate.py', text)
        self.assertNotIn('gate:g3:trial', text)
        self.assertIn('g3-style.sh', text)
        self.assertIn('g4-receipt.sh', text)
        self.assertIn('check_unused_image.py', text)
        self.assertIn('gate:quote', text)

    def test_material_failure_does_not_hide_later_gate_results(self):
        run = self.run_entry('checks', FAIL_AT='g3-policy.sh')
        self.assertEqual(run.returncode, 37)
        self.assertIn('g4-receipt.sh', json.dumps(self.calls()))
        self.assertIn('gate:quote', json.dumps(self.calls()))

    def test_undecided_material_status_keeps_existing_warning_translation(self):
        run = self.run_entry('material-style', FAIL_AT='g3-style.sh', FAIL_CODE='3')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('未判定', run.stdout)

    def test_pr_receipts_receive_all_changed_chapters_and_exact_base(self):
        run = self.run_entry('material-receipts', CI_EVENT_NAME='pull_request', CI_PR_BASE_SHA='abc123', TARGET_IDS='chapter-one\nchapter-two')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn(['pr-target-chapters.sh', ['abc123'], 'prototype-chapter'], self.calls())
        self.assertIn(['g4-receipt.sh', ['chapter-one', 'chapter-two'], 'prototype-chapter'], self.calls())
        failed = self.run_entry('material-receipts', CI_EVENT_NAME='pull_request', CI_PR_BASE_SHA='bad', FAIL_AT='pr-target-chapters.sh')
        self.assertEqual(failed.returncode, 37)

    def test_pr_without_base_fails_before_receipt_check(self):
        run = self.run_entry('material-receipts', CI_EVENT_NAME='pull_request')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_dependency_link_never_overwrites_existing_local_directory(self):
        target = self.root / 'prototype-chapter/candidates/d4-rls/app/node_modules'
        target.mkdir()
        marker = target / 'user-file'
        marker.write_text('preserve')
        run = self.run_entry('d4-predecessor-safety')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(marker.read_text(), 'preserve')
        self.assertFalse((target / 'node_modules').exists())

    def test_setup_failure_preserves_status_and_still_runs_material(self):
        run = self.run_entry('all', FAIL_AT='campoy/embedmd')
        self.assertEqual(run.returncode, 37)
        self.assertNotIn('test_a.py', json.dumps(self.calls()))
        self.assertIn('gate:quote', json.dumps(self.calls()))

    def test_qa_suites_all_run_and_retain_aggregate_failure(self):
        run = self.run_entry('qa-selftests', FAIL_AT='test_a.py')
        self.assertEqual(run.returncode, 1)
        self.assertIn('test_b.py', json.dumps(self.calls()))

    def test_declared_input_serialization_failure_is_not_masked(self):
        run = self.run_entry('d4-runtime', FAIL_AT='python3 -c')
        self.assertEqual(run.returncode, 37)
        self.assertNotIn('test_d4_*.py', json.dumps(self.calls()))

    def test_unknown_phase_fails_without_running_tools(self):
        run = self.run_entry('invalid')
        self.assertEqual(run.returncode, 2)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__':
    unittest.main()
