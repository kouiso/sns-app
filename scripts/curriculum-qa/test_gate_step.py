#!/usr/bin/env python3
"""prototype-chapter/tools/gate-step.sh の退行テスト。

D1 §8-3: 走査対象が0件なら緑にしない、でも FAIL とも違う。その読み替え
（3 → 成功 + 警告表示）がラッパ1箇所に集約されていることを確認する。
ずれると未判定が FAIL としてジョブを止めるか、逆に静かに通り過ぎる。
"""

import os
import subprocess
import sys
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

    if failed:
        print(f"❌ gate-step 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ gate-step 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
