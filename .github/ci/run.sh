#!/usr/bin/env bash
# なぜ: クラウドとローカルで教材の検査対象と未判定の扱いを揃える。
set -euo pipefail
entry=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/run.sh
root=$(cd -- "$(dirname -- "$entry")/../.." && pwd)
cd -- "$root"
export GITHUB_WORKSPACE="${GITHUB_WORKSPACE:-$root}"

ensure_dependency_link() {
  if [ -L "$2" ] && [ "$(readlink "$2")" = "$1" ]; then return; fi
  if [ -e "$2" ] || [ -L "$2" ]; then
    echo "::error::既存の依存ディレクトリは置き換えられません: $2" >&2
    return 1
  fi
  ln -s "$1" "$2"
}

case "${1:-checks}" in
  all|checks)
    result=0
    # なぜ: 通常の検査は最初の失敗で止める。教材ゲートは従来の !cancelled と同じく続ける。
    if [ "${1:-checks}" = all ]; then
      for phase in embedmd-install prototype-install; do
        if [ "$result" -eq 0 ]; then bash "$entry" "$phase" || result=$?; fi
      done
    fi
    for phase in qa-selftests g3-g6-selftests sdk57-candidate broker-probes auth-receiver auth-sdk57 d4-predecessor-safety d4-runtime d4-heavy profile-predecessor g3-trial; do
      if [ "$result" -eq 0 ]; then bash "$entry" "$phase" || result=$?; fi
    done
    for phase in material-style material-structure material-policy material-dev-log material-start-state material-receipts fixture-reference distribution quote; do
      status=0
      bash "$entry" "$phase" || status=$?
      if [ "$result" -eq 0 ]; then result=$status; fi
    done
    exit "$result"
    ;;
  embedmd-install)
go install github.com/campoy/embedmd@v1.0.0
    ;;
  prototype-install)
cd prototype-chapter
npm ci
    ;;
  qa-selftests)
failed=0
for t in scripts/curriculum-qa/test_*.py; do
  echo "=== $t"
  if ! python3 "$t"; then
    echo "❌ $t が落ちました"
    failed=1
  fi
done
exit $failed
    ;;
  g3-g6-selftests)
python3 -m unittest discover -s prototype-chapter/tools -p 'test_g3_checks.py'
python3 -m unittest discover -s prototype-chapter/tools -p 'test_g6_support.py'
python3 -m unittest discover -s prototype-chapter/tools -p 'test_g6_objective.py' -v
    ;;
  sdk57-candidate)
python3 prototype-chapter/tools/verify_sdk57_candidate.py prototype-chapter/candidates/sdk57
python3 -m unittest discover -s prototype-chapter/tools -p 'test_verify_sdk57_candidate.py' -v
bash prototype-chapter/tools/g3-structure.sh \
  prototype-chapter/candidates/sdk57/chapter-expo-first-screen.md \
  prototype-chapter/candidates/sdk57/chapter-live-reload.md \
  prototype-chapter/candidates/sdk57/controls/expo-first-screen/plain.md \
  prototype-chapter/candidates/sdk57/controls/expo-first-screen/intro-ablation.experimental.md \
  prototype-chapter/candidates/sdk57/controls/live-reload/plain.md
bash prototype-chapter/tools/g3-style.sh \
  prototype-chapter/candidates/sdk57/chapter-expo-first-screen.md \
  prototype-chapter/candidates/sdk57/chapter-live-reload.md
    ;;
  broker-probes)
if [ ! -x /usr/bin/bwrap ]; then
  echo "::warning title=未判定::実bwrap未導入。schema負例のみ実行し、OS probeを成功に数えない"
fi
python3 -m unittest discover -s prototype-chapter/tools -p 'test_g6_broker.py' -v
python3 -m unittest discover -s prototype-chapter/tools -p 'test_g6_live_reload.py' -v
    ;;
  auth-receiver)
node --check prototype-chapter/auth-return-trial/auth_return.mjs
node --check prototype-chapter/auth-return-trial/local_adapter.mjs
node --test prototype-chapter/auth-return-trial/test_auth_return.mjs
    ;;
  auth-sdk57)
cd prototype-chapter/candidates/auth-sdk57
npm ci --ignore-scripts --no-audit --no-fund
npm run test:auth
npm run typecheck
    ;;
  d4-predecessor-safety)
python3 - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
base = Path('prototype-chapter/candidates/d4-rls')
manifest = json.loads((base / 'SOURCE-MANIFEST.json').read_text())
assert manifest['scope'] == 'NON_FORMAL_D4_PUBLIC_SOURCE_ONLY'
tracked = subprocess.check_output(['git', 'ls-files', '--', str(base)], text=True).splitlines()
expected = {str(Path(path).relative_to(base)) for path in tracked} - {'SOURCE-MANIFEST.json'}
listed = [entry['path'] for entry in manifest['files']]
assert len(listed) == len(set(listed)) and set(listed) == expected
for entry in manifest['files']:
    path = base / entry['path']
    assert path.is_file() and not path.is_symlink()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], entry['path']
print('D4 public source manifest matched')
PY
node --check prototype-chapter/rls-trial/measure_sdk.mjs
node --check prototype-chapter/candidates/d4-rls/measure_sdk.mjs
python3 -m unittest discover -s prototype-chapter/candidates/d4-rls -p 'test_*owned.py' -v
cmp prototype-chapter/candidates/auth-sdk57/package.json prototype-chapter/candidates/d4-rls/app/package.json
cmp prototype-chapter/candidates/auth-sdk57/package-lock.json prototype-chapter/candidates/d4-rls/app/package-lock.json
ensure_dependency_link ../../auth-sdk57/node_modules prototype-chapter/candidates/d4-rls/app/node_modules
prototype-chapter/candidates/auth-sdk57/node_modules/.bin/tsc --noEmit --project prototype-chapter/candidates/d4-rls/app/tsconfig.json
bash prototype-chapter/tools/g3-structure.sh prototype-chapter/candidates/d4-rls/chapter.md prototype-chapter/candidates/d4-rls/plain.md
bash prototype-chapter/tools/g3-style.sh prototype-chapter/candidates/d4-rls/chapter.md
    ;;
  d4-runtime)
export D4_TEST_DEPENDENCIES="$GITHUB_WORKSPACE/prototype-chapter/candidates/auth-sdk57/node_modules"
D4_TEST_TARGETS="$(python3 -c 'import json,os; print(json.dumps([os.environ["D4_TEST_DEPENDENCIES"]]))')"
export D4_TEST_TARGETS
if [ -x /usr/bin/bwrap ]; then
  export D4_REQUIRE_REAL_TOOLCHAIN=1
else
  echo "::warning title=未判定::D4実隔離toolchain未導入。明示skipを実型検査成功に数えない"
fi
python3 -m unittest discover -s prototype-chapter/tools -p 'test_d4_*.py' -v
python3 -m unittest discover -s prototype-chapter/tools -p 'test_verify_d4_chapter_build.py' -v
PYTHONPATH=prototype-chapter/tools python3 - <<'PY'
import subprocess, tempfile
from pathlib import Path
from verify_d4_chapter_build import reconstruct_from_chapter
files, receipt = reconstruct_from_chapter(Path('prototype-chapter/candidates/d4-runtime'))
dependencies = Path('prototype-chapter/candidates/auth-sdk57/node_modules').resolve()
with tempfile.TemporaryDirectory(prefix='sns-d4-chapter-') as temporary:
    root = Path(temporary)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / 'node_modules').symlink_to(dependencies, target_is_directory=True)
    subprocess.run([str(dependencies / '.bin/tsc'), '--noEmit', '--project', str(root / 'tsconfig.json')], check=True)
    subprocess.run(['node', 'prototype-chapter/tools/verify_d4_hookup.cjs', str(root / 'App.tsx'), str(dependencies / 'typescript')], check=True)
subprocess.run(['node', 'prototype-chapter/tools/test_verify_d4_hookup.cjs', str(dependencies / 'typescript')], check=True)
subprocess.run(['node', 'prototype-chapter/tools/test_verify_d4_origin.cjs', str(dependencies / 'typescript')], check=True)
print(receipt)
PY
bash prototype-chapter/tools/g3-structure.sh prototype-chapter/candidates/d4-runtime/chapter-build.md
bash prototype-chapter/tools/g3-style.sh prototype-chapter/candidates/d4-runtime/chapter-build.md
    ;;
  d4-heavy)
bash prototype-chapter/tools/g3-structure.sh prototype-chapter/candidates/d4-heavy/chapter-rls-denial-check.md prototype-chapter/candidates/d4-heavy/answers.md
bash prototype-chapter/tools/g3-style.sh prototype-chapter/candidates/d4-heavy/chapter-rls-denial-check.md prototype-chapter/candidates/d4-heavy/answers.md
bash prototype-chapter/tools/g3-policy.sh prototype-chapter/candidates/d4-heavy/chapter-rls-denial-check.md prototype-chapter/candidates/d4-heavy/answers.md
python3 - <<'PY'
import hashlib, json, re
from collections import Counter
from pathlib import Path
base = Path('prototype-chapter/candidates/d4-heavy')
matrix = json.loads((base / 'rls-checks.json').read_text())
cases = matrix['cases']
assert len({case['id'] for case in cases}) == len(cases)
counts = Counter(case['current_status'] for case in cases)
assert set(counts) <= {'CANDIDATE_EVIDENCE_ONLY', 'NOT_READY'}
assert matrix['summary']['total_cases'] == len(cases)
assert matrix['summary']['accepted_cases'] == 0
assert all(matrix['summary'][key] == value for key, value in counts.items())
sources = {source['source_id']: source for source in matrix['provenance_sources']}
assert len(sources) == len(matrix['provenance_sources'])
for source in sources.values():
    assert re.fullmatch(r'[0-9a-f]{64}', source['sha256'])
    if source['file'] is None:
        assert source['unpublished_reason']
    else:
        path = Path(source['file'])
        assert not path.is_absolute() and '..' not in path.parts
        assert source['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
for case in cases:
    assert all(ref == sources[ref['source_id']] for ref in case['provenance'])
assert (base / 'assets/full-sns-map.svg').is_file()
print('draft matrix:', len(cases), dict(counts), 'accepted: 0')
PY
    ;;
  profile-predecessor)
cmp prototype-chapter/candidates/auth-sdk57/package.json prototype-chapter/candidates/d4-predecessor/package.json
cmp prototype-chapter/candidates/auth-sdk57/package-lock.json prototype-chapter/candidates/d4-predecessor/package-lock.json
cmp prototype-chapter/candidates/auth-sdk57/lib/auth-return.mjs prototype-chapter/candidates/d4-predecessor/lib/auth-return.mjs
ensure_dependency_link ../auth-sdk57/node_modules prototype-chapter/candidates/d4-predecessor/node_modules
node --check prototype-chapter/candidates/d4-predecessor/lib/profile-flow.mjs
node --test prototype-chapter/candidates/d4-predecessor/test-auth-return.mjs prototype-chapter/candidates/d4-predecessor/test-profile-flow.mjs
prototype-chapter/candidates/auth-sdk57/node_modules/.bin/tsc --noEmit --project prototype-chapter/candidates/d4-predecessor/tsconfig.json
    ;;
  g3-trial)
cd prototype-chapter
npm run gate:g3:trial
    ;;
  material-style)
cd prototype-chapter
tools/gate-step.sh tools/g3-style.sh
    ;;
  material-structure)
cd prototype-chapter
tools/gate-step.sh tools/g3-structure.sh
    ;;
  material-policy)
cd prototype-chapter
tools/gate-step.sh tools/g3-policy.sh
    ;;
  material-dev-log)
cd prototype-chapter
tools/gate-step.sh tools/g3-dev-log.sh
    ;;
  material-start-state)
cd prototype-chapter
tools/gate-step.sh tools/g3-start-state.sh
    ;;
  material-receipts)
cd prototype-chapter
# D15-8-2「教材PRの対象章に受領証が存在すること」。
# PR では差分で触れた curriculum/<章ID>.md の受領証を要求する。
# push では今ある受領証の検査だけ（差分の起点が無い）。
if [ "${CI_EVENT_NAME:-push}" = "pull_request" ]; then
  # ベースSHAが取れないときスクリプトは 2 を返す。$() の代入は
  # その終了コードを引き継ぐので set -e でここで止まり、
  # 「要求すべき章を拾えなかったのに緑」にはならない。
  targets="$(tools/pr-target-chapters.sh "${CI_PR_BASE_SHA:?PR base SHA is required}")"
  if [ -n "$targets" ]; then
    ids=()
    while IFS= read -r id; do ids+=("$id"); done <<< "$targets"
    tools/gate-step.sh tools/g4-receipt.sh "${ids[@]}"
  else
    tools/gate-step.sh tools/g4-receipt.sh
  fi
else
  tools/gate-step.sh tools/g4-receipt.sh
fi
    ;;
  fixture-reference)
set +e
total=0
for c in check_structure check_policy_sync; do
  echo "=== ${c}（フィクスチャ。合否に数えない）"
  out=$(python3 "scripts/curriculum-qa/$c.py" prototype-chapter/chapter*.md 2>&1)
  rc=$?
  printf '%s\n' "$out"
  if [ "$rc" -ge 2 ]; then
    echo "::warning::$c が終了コード ${rc}（未判定/環境異常）。フィクスチャの指摘は数えられない"
  fi
  # 指摘行は `  <ファイル>:<行> <内容>` の形。末尾の助言行
  # （2スペース開始だが :行番号 を持たない）は数えない。
  n=$(printf '%s\n' "$out" | grep -cE '^  [^ ]+:[0-9]+')
  total=$((total + n))
done
# 文体もフィクスチャには参考として回す。対照版（*-plain.md）も
# 含める（D17-1 で対照版は文体ゲート内に戻った）。指摘は参考。
fixture=()
for f in prototype-chapter/chapter*.md; do
  [ -e "$f" ] || continue
  fixture+=("$f")
done
if [ ${#fixture[@]} -gt 0 ]; then
  echo "=== 文体（フィクスチャ。合否に数えない）"
  prototype-chapter/tools/g3-style.sh "${fixture[@]}"
  style_rc=$?
  if [ $style_rc -ne 0 ]; then
    echo "::warning::フィクスチャの文体チェックが終了コード ${style_rc}（参考。合否に数えない）"
  fi
fi
echo "::warning::捨て試作フィクスチャの構造・方針同期 指摘 ${total} 件（参考。合否に数えない）"
exit 0
    ;;
  distribution)
rc_all=0
for t in scripts/curriculum-qa/check_epub_reference.py \
         scripts/curriculum-qa/check_pdf_links.py \
         scripts/curriculum-qa/check_unused_image.py; do
  echo "=== $t"
  prototype-chapter/tools/gate-step.sh python3 "$t" || rc_all=$?
done
exit $rc_all
    ;;
  quote)
cd prototype-chapter
# setup-go は GOPATH を $HOME/go に置く。両方を見て解決する。
if [ ! -x "${EMBEDMD:-}" ]; then EMBEDMD="$(go env GOPATH)/bin/embedmd"; fi
export EMBEDMD
npm run gate:quote
    ;;
  *) echo "Unknown CI phase: $1" >&2; exit 2 ;;
esac
