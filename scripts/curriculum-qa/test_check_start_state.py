#!/usr/bin/env python3
"""check_start_state.py の退行テスト。

止めるもの（開始状態に書かせるファイル・完成品・node_modules が混入）と、
止めてはいけないもの（下地だけの開始状態、完成品と同名でも中身が違う
編集対象の下地）の両方を置く。片方だけでは、全部を止める検査でも
全部を通す検査でも緑になってしまう。

未判定の扱いも検査する: --starter を付けない呼び出しは 3 を返さなければ
「開始状態が無い」を PASS と取り違える。
"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_start_state  # noqa: E402

CHAPTER = """# 章

```tsx
// filepath: app/index.tsx
export default function Page() {
  return <Text>はじめての画面</Text>;
}
```
"""

LISTING_BODY = "export default function App() {\n  return <Text>hi</Text>;\n}\n"


def run_main(args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return check_start_state.main(["check_start_state.py", *args])


def main() -> int:
    failed = 0
    total = 0

    def expect(name, want, got):
        nonlocal failed, total
        total += 1
        if got != want:
            failed += 1
            print(f"  ❌ {name}: 終了コード {want} を期待、実際 {got}")

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        chapter = root / "chapter.md"
        chapter.write_text(CHAPTER, encoding="utf-8")

        # 下地だけの開始状態。読者が書く app/index.tsx は無い。
        starter = root / "starter"
        (starter / "assets").mkdir(parents=True)
        (starter / "package.json").write_text("{}\n", encoding="utf-8")
        (starter / "app.json").write_text("{}\n", encoding="utf-8")

        expect("開始状態が下地だけなら通す", 0,
               run_main(["--starter", str(starter), str(chapter), "--listings", str(root / "none")]))

        # 読者が書くはずのファイルが開始状態に混入。
        (starter / "app").mkdir()
        (starter / "app" / "index.tsx").write_text("export default function Page() {}\n", encoding="utf-8")
        expect("書かせるファイルの混入は止める", 1,
               run_main(["--starter", str(starter), str(chapter), "--listings", str(root / "none")]))
        (starter / "app" / "index.tsx").unlink()

        # node_modules の混入。
        (starter / "node_modules").mkdir()
        (starter / "node_modules" / "x.js").write_text("x", encoding="utf-8")
        expect("node_modules の混入は止める", 1,
               run_main(["--starter", str(starter), str(chapter), "--listings", str(root / "none")]))
        (starter / "node_modules" / "x.js").unlink()
        (starter / "node_modules").rmdir()

        # 完成品（listings）と同内容のファイルが混入。
        listings = root / "listings"
        (listings / "some-chapter").mkdir(parents=True)
        (listings / "some-chapter" / "App.tsx").write_text(LISTING_BODY, encoding="utf-8")
        (starter / "App.tsx").write_text(LISTING_BODY, encoding="utf-8")
        expect("完成品と同内容の混入は止める", 1,
               run_main(["--starter", str(starter), str(chapter), "--listings", str(listings)]))

        # 同名でも中身が違えば下地（後で編集するファイル）なので通す。
        (starter / "App.tsx").write_text("// 空の下地\n", encoding="utf-8")
        expect("同名でも中身が違う下地は通す", 0,
               run_main(["--starter", str(starter), str(chapter), "--listings", str(listings)]))
        (starter / "App.tsx").unlink()

        # マニフェスト（1行1パス）でも同じ判定になる。
        manifest = root / "starter.txt"
        manifest.write_text("package.json\napp/index.tsx\n", encoding="utf-8")
        expect("マニフェスト経由でも混入を止める", 1,
               run_main(["--starter", str(manifest), str(chapter), "--listings", str(root / "none")]))
        manifest.write_text("package.json\napp.json\n", encoding="utf-8")
        expect("マニフェスト経由で下地だけなら通す", 0,
               run_main(["--starter", str(manifest), str(chapter), "--listings", str(root / "none")]))

        expect("--starter 未指定は未判定(3)", 3, run_main([str(chapter)]))
        expect("指定した starter が無ければ 2", 2,
               run_main(["--starter", str(root / "absent"), str(chapter)]))

        # 開始状態はあるのに写経対象の章が0件 → 検査0件は緑にしない
        # （D1 §8-3）。REPO_ROOT を curriculum/ の無い一時ディレクトリに
        # 差し替えると既定の走査対象が空になる。
        saved = check_start_state.REPO_ROOT
        check_start_state.REPO_ROOT = root / "empty-repo"
        (root / "empty-repo").mkdir()
        try:
            expect("対象章が0件なら未判定(3)", 3,
                   run_main(["--starter", str(starter)]))
        finally:
            check_start_state.REPO_ROOT = saved

    if failed:
        print(f"❌ check_start_state 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_start_state 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
