#!/usr/bin/env python3
"""prototype-chapter/tools/pr-target-chapters.sh の退行テスト。

D15-8-2「教材PRの対象章に受領証が存在すること」を CI で効かせるために、
PR の差分から curriculum/<章ID>.md の章IDだけを拾うスクリプト。
README や curriculum 以外の変更、章の削除まで拾うと、受領証を
要求する必要のないPRまで G4 が赤くなる。
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "prototype-chapter" / "tools" / "pr-target-chapters.sh"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=GIT_ENV,
                   check=True, capture_output=True)


def make_repo(files: dict[str, str]) -> Path:
    """files をコミット済みのリポジトリを作り、ベースSHAを返す。"""
    repo = Path(tempfile.mkdtemp())
    git(repo, "init", "-q")
    for name, body in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    return repo


def run(repo: Path, base: str) -> tuple[int, str]:
    proc = subprocess.run(
        [str(SCRIPT), base], cwd=repo, env=GIT_ENV,
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout.strip()


def base_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=GIT_ENV,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def commit(repo: Path, msg: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg)


def put(repo: Path, name: str, body: str) -> None:
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def main() -> int:
    failed = 0
    total = 0

    def expect(name: str, want_rc: int, want_out: str, got: tuple[int, str]) -> None:
        nonlocal failed, total
        total += 1
        rc, out = got
        if rc != want_rc or out != want_out:
            failed += 1
            print(f"  ❌ {name}: 期待 rc={want_rc} out={want_out!r} / 実際 rc={rc} out={out!r}")

    if not SCRIPT.exists():
        print(f"❌ スクリプトが無い: {SCRIPT}")
        return 2

    # curriculum の章を追加・変更するPR → その章IDが出る
    repo = make_repo({"curriculum/README.md": "# readme\n"})
    base = base_sha(repo)
    put(repo, "curriculum/expo-first-screen.md", "# 章\n")
    put(repo, "material/x.md", "資料\n")
    commit(repo, "pr")
    expect("章の追加で章IDが出る", 0, "expo-first-screen", run(repo, base))

    # 既存の章の変更も対象
    repo = make_repo({"curriculum/live-reload.md": "# 章 v1\n"})
    base = base_sha(repo)
    (repo / "curriculum" / "live-reload.md").write_text("# 章 v2\n", encoding="utf-8")
    commit(repo, "pr")
    expect("章の変更で章IDが出る", 0, "live-reload", run(repo, base))

    # README.md だけのPR → 何も出ない
    repo = make_repo({"curriculum/README.md": "# v1\n"})
    base = base_sha(repo)
    (repo / "curriculum" / "README.md").write_text("# v2\n", encoding="utf-8")
    commit(repo, "pr")
    expect("READMEだけのPRでは何も出ない", 0, "", run(repo, base))

    # curriculum 以外だけのPR → 何も出ない
    repo = make_repo({"app/x.tsx": "v1\n"})
    base = base_sha(repo)
    put(repo, "app/x.tsx", "v2\n")
    put(repo, "material/x.md", "資料\n")
    commit(repo, "pr")
    expect("curriculum以外では何も出ない", 0, "", run(repo, base))

    # 章の削除は受領証を要求しない
    repo = make_repo({"curriculum/old-chapter.md": "# 章\n"})
    base = base_sha(repo)
    (repo / "curriculum" / "old-chapter.md").unlink()
    commit(repo, "pr")
    expect("章の削除では何も出ない", 0, "", run(repo, base))

    # サブディレクトリの .md は章IDではない
    repo = make_repo({"curriculum/README.md": "# readme\n"})
    base = base_sha(repo)
    put(repo, "curriculum/assets/note.md", "補足\n")
    commit(repo, "pr")
    expect("curriculum直下以外のmdは拾わない", 0, "", run(repo, base))

    # 存在しないベースSHA → 2（使い方/環境の誤り）
    repo = make_repo({"x.txt": "x\n"})
    expect("ベースが取れなければ 2", 2, "", run(repo, "0" * 40))

    if failed:
        print(f"❌ pr-target-chapters 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ pr-target-chapters 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
