#!/usr/bin/env python3
"""開始状態混入検査（10 §4 G3 / §3 G0 / D17-1）。

「学習者の開始状態」（スターター）に、その先の章で読者が書くはずの
完成コードが混ざっていないかを見る。前作では販売ZIPに完成品が混入して
いた（10 §1 #1 / PR #296 事件）ので、本作では教材執筆の前に検査器を置く。

判定は2系統:
  1. 教材が読者に書かせる実ファイル（`// filepath:` が `app/` `supabase/` を
     指すコードブロックの書き込み先）が、開始状態に既に存在する → 違反。
     読者が書く前から完成済みなら写経する場面が消える。
  2. `listings/<章ID>/` にある完成品ファイルと同名・同内容のファイルが
     開始状態に入っている → 違反。内容一致で見るのは、開始状態に置くのが
     正しい下地ファイル（空の `app.json` 等）を、完成品と同じ名前だからと
     いって誤って止めないためである。

開始状態は G0 の未決チェック項目（10 §3 L76-77）なので置き場は決まっていない。
そのため `--starter <dir|manifest>` を必須の明示入力とする。指定が無いときは
「開始状態がまだ存在しない」= 判定不能として 3 を返す。決して PASS にはしない。

終了コード:
  0 = 判定でき、違反なし
  1 = 混入あり
  2 = 使い方の誤り（指定された starter や対象が読めない）
  3 = 未判定（--starter 未指定。開始状態自体がまだ無い）
"""

from __future__ import annotations

import sys
from pathlib import Path

from curriculum_blocks import iter_blocks
from sale_package import starter_paths

REPO_ROOT = Path(__file__).resolve().parents[2]

# 教材の走査対象。対照版（*-plain.md）は章単位の検査を二重に課さない決まり
# （D17-1）だが、写経ブロックがあれば同じ混入を起こすので通常版と同じく見る。
DEFAULT_TARGETS = ("curriculum/*.md", "prototype-chapter/chapter*.md")

# 開始状態に含めてはいけない作業物。旧チェック（check-sale-package.sh）でも
# 止めていた依存物と版管理物で、Expo 構成でも同じ理由で混入させない。
FORBIDDEN_PARTS = {"node_modules", ".git"}


def write_targets(paths: list[Path]) -> set[str]:
    """対象ファイル群が読者に書かせる実ファイルの集合を返す。"""
    targets: set[str] = set()
    for p in paths:
        for block in iter_blocks(p.read_text(encoding="utf-8"), p.name):
            if block.is_writing_target:
                targets.add(block.target)
    return targets


def listing_files(listings: Path) -> dict[str, Path]:
    """listings/ 配下の全ファイルを {相対パス: 実パス} で返す。"""
    out: dict[str, Path] = {}
    if not listings.is_dir():
        return out
    for p in sorted(listings.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rel = p.relative_to(listings)
            # 先頭の章IDの層を剥がして「読者が作る相対パス」に揃える。
            # 章IDの直下に無いファイル（深さ2未満）は完成品の置き方に
            # 従っていないので比較対象から外す。
            if len(rel.parts) < 2:
                continue
            out[str(Path(*rel.parts[1:]))] = p
    return out


def _same_content(a: Path, b: Path) -> bool:
    """内容が同じか。行末空白・改行コードの差は写経の揺れなので潰して比べる。"""
    def norm(path: Path) -> list[str]:
        return [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()]
    return norm(a) == norm(b)


def main(argv: list[str]) -> int:
    starter_arg: str | None = None
    targets: list[Path] = []
    listings_dirs: list[Path] = []
    it = iter(argv[1:])
    for a in it:
        if a == "--starter":
            starter_arg = next(it, "")
        elif a == "--listings":
            listings_dirs.append(Path(next(it, "")))
        else:
            targets.append(Path(a))

    if starter_arg is None:
        print("⏸ 未判定: 開始状態（--starter）が指定されていません。開始状態は G0 の未決項目です")
        return 3

    try:
        provided = starter_paths(Path(starter_arg))
    except (OSError, ValueError) as e:
        print(f"❌ 開始状態が読めません: {e}", file=sys.stderr)
        return 2
    if not provided:
        print(f"❌ 開始状態 {starter_arg} にファイルがありません", file=sys.stderr)
        return 2

    if not targets:
        for pat in DEFAULT_TARGETS:
            targets.extend(sorted(REPO_ROOT.glob(pat)))
        # README.md は目次・ナビ文書であり章本文ではないので対象外
        targets = [t for t in targets if t.name != "README.md"]
    if not listings_dirs:
        for cand in (REPO_ROOT / "listings", REPO_ROOT / "prototype-chapter" / "listings"):
            if cand.is_dir():
                listings_dirs.append(cand)

    starter_root = Path(starter_arg)
    problems: list[str] = []

    for rel in sorted(provided):
        if any(part in FORBIDDEN_PARTS for part in Path(rel).parts):
            problems.append(f"開始状態に入れてはいけないものが混入: {rel}")

    wanted = write_targets(targets)
    for rel in sorted(provided):
        if rel in wanted:
            problems.append(f"開始状態に、教材が書かせるファイルが既に存在: {rel}")

    for ldir in listings_dirs:
        for rel, lpath in listing_files(ldir).items():
            if rel not in provided:
                continue
            # starter がディレクトリのときだけ内容を比べられる。manifest は
            # パス一覧しか持たないので同名だけでは混同を疑いすぎる。
            candidate = starter_root / rel
            if candidate.is_file() and _same_content(candidate, lpath):
                problems.append(f"開始状態に完成品がそのまま混入: {rel}（{lpath.name} と同内容）")

    if problems:
        print(f"❌ 開始状態混入検査で {len(problems)} 件")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"✅ 開始状態 OK（{len(provided)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
