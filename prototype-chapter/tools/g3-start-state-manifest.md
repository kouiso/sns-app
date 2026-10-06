# G3 開始状態 manifest（暫定仕様）

`g3_checks.py` の開始状態混入検査は、上流で確定した開始スナップショットを推測しない。
`--start-state-manifest` で `g3-start-state.schema.json` に沿う JSON を渡す。

各章には次を記録する。

- `snapshot.revision`: 開始スナップショットを一意に指すタグ、コミット、または
  試作の非凍結候補であることを明記した識別子
- `snapshot.source_root`: manifest の場所を基準にした開始ソースの相対パス
- `snapshot.status`: 空の試作開始なら `declared-empty-trial`、凍結済みsnapshotが無く
  listingsを参照候補にするなら `unfrozen-reference-candidate`
- `snapshot.tracked_files`: 追跡ファイルの相対パスと SHA-256。空の開始状態は
  `allow_empty: true` を明示し、偶然の0件と区別する
- `allowed_state_contract`: 開始時点で学習者が持つ状態を説明する空でない文
- `forbidden_paths`: その章の開始時点には無く、教材へ先取り混入させてはいけないパス
- `forbidden_patterns`: 同じ目的の正規表現

`forbidden_paths` と `forbidden_patterns` が両方0件なら FAIL にする。開始状態が未定義なのか、
禁止対象が本当に無いのかを機械だけでは区別できないためである。

`source_root` と各 tracked file はシンボリックリンクを解決した後も manifest のある
ディレクトリ配下に収まる必要がある。範囲外のファイルを禁止パターン走査で読まないための入力境界である。

この検査が保証するのは、manifest の tracked file 一覧と、その一覧が指す現在の開始ソースに、
指定した禁止パス・パターンが混入していないことだけである。教材本文にはその章でこれから
追加するコードが出るため、開始状態混入の判定材料には使わない。

`tracked_files` に記録した SHA-256 が現在の開始ソースと一致するか、一覧外のファイルが無いか、
許可したファイルの内容が正しいか、章末スナップショットや PDF / EPUB の配布物が契約どおりかは
検査しない。

`package-lock.json` は追跡ファイル一覧と禁止パス検査には含めるが、禁止パターンの本文走査からは
外す。直接採用していない任意peer dependency名も含む生成物であり、方針違反のコード利用と
区別できないためである。直接依存の採否は `package.json` を走査する。
そのため manifest は `scope: chapter-content-mixing-only` と
`snapshot_conformance_checked: false` を必須にし、PASS 時にも保証外を表示する。

plain / minus 対照版は構造・文体・方針同期だけを検査する。開始状態混入と
`dev-logs/<章ID>.md` の存在は同じ章の本物側で1回だけ検査する。
