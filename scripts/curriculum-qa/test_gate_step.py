#!/usr/bin/env python3
"""prototype-chapter/tools/gate-step.sh の退行テスト。

D1 §8-3: 走査対象が0件なら緑にしない、でも FAIL とも違う。その読み替え
（3 → 成功 + 警告表示）がラッパ1箇所に集約されていることを確認する。
ずれると未判定が FAIL としてジョブを止めるか、逆に静かに通り過ぎる。
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "prototype-chapter" / "tools" / "gate-step.sh"


def run(code: int, github_actions: bool = False) -> tuple[int, str]:
    """終了コード code を返す子プロセスを挟んでラッパを動かす。"""
    env = dict(os.environ)
    if github_actions:
        env["GITHUB_ACTIONS"] = "true"
    else:
        env.pop("GITHUB_ACTIONS", None)
    proc = subprocess.run(
        [str(WRAPPER), "sh", "-c", f"exit {code}"],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _write_min_chapter_table(root: Path) -> None:
    """check_g4_receipt.py が読む最小限の章分割表を一時ツリーに書く。

    検査に必要なのは「生きた章IDが1つ以上取れる」ことだけ。バックログ
    （未決ID の台帳）と証拠ファイルも実在しないと読み込み自体が失敗する
    ので、最小の形で一緒に置く。
    """
    material = root / "material"
    material.mkdir(parents=True)
    (material / "16_決定バックログ.md").write_text("| B1 | 仮 |\n", encoding="utf-8")
    (material / "ev.md").write_text("証拠\n", encoding="utf-8")
    ids = ["ch-a0", "ch-a", "ch-b", "ch-c", "ch-d", "ch-e"]
    parts = ["A0", "A", "B", "C", "D", "E"]
    frs = [["FR1", "FR2", "FR3"], ["FR4", "FR5", "FR6"], ["FR7", "FR8", "FR9"],
           ["FR10", "FR11", "FR12"], ["FR13", "FR14"], ["FR15"]]
    cols = ["章ID", "並び順", "パート", "章タイトル", "完成する状態", "前提とする前章成果",
            "supersedes", "状態", "節目", "地図", "見える変化", "最初の結果", "未決依存"]
    chapters = ["| " + " | ".join([c, str(i + 1), p, "題", "完了状態", "-", "-",
                "未着手", "非節目", "地図", "screen", "結果", "-"]) + " |"
                for i, (c, p) in enumerate(zip(ids, parts))]
    tcols = ["章ID", "FR", "画面", "SQL/RLS", "テスト", "前提知識", "証拠"]
    traces = ["| " + " | ".join([c, ",".join(fr), "画", "sql", "test", "pre",
              "material/ev.md"]) + " |" for c, fr in zip(ids, frs)]
    (material / "18-chapter-split-table.md").write_text(
        "版: v1\n\n位置づけ: DRAFT / NON-G1\n\n## 章一覧\n\n"
        + "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
        + "\n".join(chapters)
        + "\n\n## 対応表\n\n"
        + "| " + " | ".join(tcols) + " |\n|" + "---|" * len(tcols) + "\n"
        + "\n".join(traces) + "\n", encoding="utf-8")


def main() -> int:
    failed = 0
    total = 0

    def expect(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failed, total
        total += 1
        if not cond:
            failed += 1
            print(f"  ❌ {name} {detail}")

    if not WRAPPER.exists():
        print(f"❌ ラッパが無い: {WRAPPER}")
        return 2

    rc, out = run(0)
    expect("成功はそのまま 0", rc == 0, f"(rc={rc})")
    expect("成功では警告を出さない", "未判定" not in out, f"({out.strip()})")

    rc, out = run(3)
    expect("未判定(3)は 0 に読み替える", rc == 0, f"(rc={rc})")
    expect("未判定はローカルで ⏸️ を出す", "⏸️" in out, f"({out.strip()})")

    rc, out = run(3, github_actions=True)
    expect("Actions 上の未判定(3)も 0", rc == 0, f"(rc={rc})")
    expect("Actions 上では ::warning を出す", "::warning" in out, f"({out.strip()})")

    rc, _ = run(1)
    expect("違反(1)はそのまま 1", rc == 1, f"(rc={rc})")
    rc, _ = run(2)
    expect("使い方の誤り(2)はそのまま 2", rc == 2, f"(rc={rc})")

    # bash 3.2（macOS の /bin/bash）では空配列の "${arr[@]}" が set -u で
    # unbound variable になる。引数なしで各ラッパを素の /bin/bash で叩き、
    # この綴りの事故が起きないことを見る（bash が無い環境では飛ばす）。
    bash = Path("/bin/bash")
    if bash.exists():
        tools = WRAPPER.parent
        # g4-receipt.sh の rc3 は「受領証0件の未判定」。実リポジトリに
        # 依存すると最初の受領証が置かれた時点でこのテストが壊れるので、
        # 章分割表と空の g4/ を持つ一時ツリーで確かめる。
        with tempfile.TemporaryDirectory() as d:
            gtmp = Path(d)
            gtools = gtmp / "proto" / "tools"
            gtools.mkdir(parents=True)
            gscripts = gtmp / "scripts" / "curriculum-qa"
            gscripts.mkdir(parents=True)
            for w in ("g4-receipt.sh", "gate-step.sh"):
                shutil.copy(tools / w, gtools / w)
            for f in ("check_g4_receipt.py", "chapter_table.py", "markdown_scan.py"):
                shutil.copy(ROOT / "scripts" / "curriculum-qa" / f, gscripts / f)
            _write_min_chapter_table(gtmp)
            (gtmp / "material" / "reviews" / "g4").mkdir(parents=True)

            proc = subprocess.run(
                [str(bash), str(gtools / "g4-receipt.sh")],
                capture_output=True, text=True, cwd=gtmp / "proto",
            )
            expect("g4-receipt.sh は bash 3.2 でも引数なしで落ちない",
                   proc.returncode == 3 and "unbound" not in proc.stderr,
                   f"(rc={proc.returncode} {proc.stderr.strip()[:80]})")
            proc = subprocess.run(
                [str(bash), str(gtools / "gate-step.sh"), str(gtools / "g4-receipt.sh")],
                capture_output=True, text=True, cwd=gtmp / "proto",
            )
            expect("gate-step 経由なら未判定(3)が 0 に読み替わる",
                   proc.returncode == 0 and "unbound" not in proc.stderr,
                   f"(rc={proc.returncode} {proc.stderr.strip()[:80]})")

        # g3-style.sh の既定対象は curriculum/*.md（README 除く）。
        # フィクスチャを既定で読むと教材本文が永遠に文体検査から抜ける。
        # 実リポジトリの状態に依存しないよう、tools/ と textlint の置き場を
        # まねた一時ツリーを作って確かめる。
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            ttools = tmp / "proto" / "tools"
            ttools.mkdir(parents=True)
            shutil.copy(tools / "g3-style.sh", ttools / "g3-style.sh")
            stub_dir = tmp / "proto" / "node_modules" / ".bin"
            stub_dir.mkdir(parents=True)
            stub = stub_dir / "textlint"
            # textlint は起動した cwd の .textlintrc を拾うので、どこから
            # 起動されたかが本質。スタブは自分の cwd と受け取った引数を
            # そのまま表示するだけにする。
            stub.write_text(
                '#!/bin/sh\necho "TEXTLINT_CWD:$PWD"\necho "TEXTLINT:$*"\n',
                encoding="utf-8")
            stub.chmod(0o755)

            proc = subprocess.run(
                [str(bash), str(ttools / "g3-style.sh")],
                capture_output=True, text=True, cwd=tmp,
            )
            expect("文体の既定対象が0件なら未判定(3)",
                   proc.returncode == 3, f"(rc={proc.returncode} {proc.stderr.strip()[:80]})")

            (tmp / "curriculum").mkdir()
            (tmp / "curriculum" / "ch1.md").write_text("# 章\n", encoding="utf-8")
            (tmp / "curriculum" / "README.md").write_text("# 目次\n", encoding="utf-8")
            proc = subprocess.run(
                [str(bash), str(ttools / "g3-style.sh")],
                capture_output=True, text=True, cwd=tmp,
            )
            expect("文体の既定は curriculum の章を検査する",
                   proc.returncode == 0 and "ch1.md" in proc.stdout,
                   f"(rc={proc.returncode} {proc.stdout.strip()[:80]})")
            expect("README.md は文体の対象外",
                   "README" not in proc.stdout, f"({proc.stdout.strip()[:80]})")

            # textlint は proto/（実際に依存が入っている側）を cwd にして
            # 起動され、対象は絶対パスで渡ること。リポジトリ直下の cwd で
            # 起動すると休眠中のルート .textlintrc を拾って空振りする。
            expect("textlint は prototype-chapter を cwd にして起動する",
                   f"TEXTLINT_CWD:{tmp}/proto" in proc.stdout,
                   f"({proc.stdout.strip()[:120]})")
            expect("既定対象は絶対パスで渡る",
                   f"{tmp}/curriculum/ch1.md" in proc.stdout,
                   f"({proc.stdout.strip()[:120]})")

            # 呼び出し側の cwd がリポジトリ外（ここでは /）でも同じ結果になる
            proc = subprocess.run(
                [str(bash), str(ttools / "g3-style.sh")],
                capture_output=True, text=True, cwd="/",
            )
            expect("どの cwd からでも textlint は proto/ 起動で同じ対象を見る",
                   proc.returncode == 0
                   and f"TEXTLINT_CWD:{tmp}/proto" in proc.stdout
                   and f"{tmp}/curriculum/ch1.md" in proc.stdout,
                   f"(rc={proc.returncode} {proc.stdout.strip()[:120]})")

            # 明示した相対パスは呼び出し側の cwd から絶対パスに解決する
            (tmp / "custom.md").write_text("# 任意\n", encoding="utf-8")
            proc = subprocess.run(
                [str(bash), str(ttools / "g3-style.sh"), "custom.md"],
                capture_output=True, text=True, cwd=tmp,
            )
            expect("明示したファイルはそのまま検査する",
                   proc.returncode == 0 and "custom.md" in proc.stdout,
                   f"(rc={proc.returncode} {proc.stdout.strip()[:80]})")
            expect("相対指定は呼び出し側の cwd から絶対パスに解決する",
                   f"{tmp}/custom.md" in proc.stdout,
                   f"({proc.stdout.strip()[:120]})")

    # check_quality.sh の合否対象も教材本文だけ。CHAPTER_MDS の収集に
    # フィクスチャが混ざると、既知のフィクスチャ指摘で全体が赤くなる。
    quality = (ROOT / "scripts" / "curriculum-qa" / "check_quality.sh").read_text(
        encoding="utf-8")
    qlines = quality.splitlines()
    for n, line in enumerate(qlines):
        if "CHAPTER_MDS+=(" in line:
            head = "\n".join(qlines[max(0, n - 4):n + 1])
            expect("check_quality.sh の合否対象は curriculum のみ",
                   "prototype-chapter" not in head, f"(L{n + 1} 周辺)")
    expect("check_quality.sh はフィクスチャを参考扱いで回す",
           "FIXTURE_MDS" in quality and "|| true" in quality, "")

    if failed:
        print(f"❌ gate-step 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ gate-step 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
