# 2026-09-19 試作環境と既存QAの確認

対象: V3.5 の S1 および既存 QA の証拠確認。

基準コミット: `7f045458ecd2cd9157ffa3995fd63230a993a4ba`

確認日: 2026-09-19（JST）

## 現在の結論（Mac mini 実機確認後）

ユーザーから `ssh macmini-lan` の接続先を受領し、物理 Pixel 7 Pro と iPhone 12 mini を確認した。**Android は USB 転送経由の初回表示・編集反映にPASS**。iPhone はペアリング・開発モード・画面取得経路を確認できたが、Expo Go が未導入で表示試験は未実行。全体は引き続き PARTIAL / BLOCKED（iOSのExpo Go導入待ち）。詳細と保存証拠は§8。以下の旧結論と§1〜7は、その時点の観測履歴であり、現在の端末不在を示すものではない。

## Mac mini 接続前の結論（履歴）

この作業単位は **PARTIAL / BLOCKED** である。既存 QA 17本の再実行と、6失敗の B31 分類は完了した。また、A0 の2試作は既存 lockfile から再現可能に依存を導入でき、型検査、Expo 公開設定の読み取り、Web 静的出力まで成功した。初回の Node `22.11.0` で検出した engine 警告は、共有既定値を変えず、導入済みの適合 Node `22.16.0` をコマンド局所で使う再検証により切り分けた。一方、V3.5 が必須とする物理 iOS・Android の A0 表示と変更反映は、利用可能な実機と接続経路をこのセッションで確認できなかったため取得できなかった。

メール認証、D4 の RLS 重試作、G6 exec も未実行である。G6 の事前条件は、親 `prototype-chapter` の依存復元、G3 の文体チェック、G5 の引用照合成功まで進んだ。G5 は初回に `embedmd` 不在で停止したが、既存契約が指定する v1.0.0 を `/tmp` の専用パスに限って導入し、原稿を書き換えずに3章すべてPASSした。計画上の合意、過去のシミュレータ成功、ローカルにスクリプトが存在することは、今回の実機成功の証拠に数えない。

## 1. 確認した実行環境

| 項目 | 観測値 | 判定 |
|---|---|---|
| OS | WSL2 / Linux x86_64 | macOS 固有の実行経路はこのホストでは使えない |
| Node.js / npm | Node `v22.11.0` / npm `10.9.0` | コマンド本体は利用可 |
| Python | `3.14.6` | 17本の QA を個別実行できた |
| Android 用道具 | `adb` は存在 | Windows ADB 経路は空。追加確認した WSL ADB 経路にはエミュレータのみ。物理 Android は未確認 |
| iOS 用道具 | `xcrun` は存在しない | WSL から iOS 実機を列挙・識別できない |
| Expo / Supabase CLI | グローバルコマンドは存在しない。導入後のローカル Expo CLI は `57.0.10` | Expo は試作内から実行可。Supabase CLI は依然として不在 |

`prototype-chapter/listings/expo-first-screen` と `live-reload` はどちらも `expo ~57.0.8` を宣言し、lockfileVersion 3 の `package-lock.json` は Expo `57.0.8` を固定している。プロジェクト自身に `preinstall` / `postinstall` / `prepare` はない。初回確認では `node_modules` が無く `npm ls --depth=0` が全依存を `UNMET DEPENDENCY` と報告した。その後、両方で `npm ci --no-audit --no-fund` を実行し、各496 package を既存 lockfile どおり導入した。`package.json` と lockfile の変更はない。

導入後の実測は以下のとおり。

| 検証 | `expo-first-screen` | `live-reload` |
|---|---|---|
| `npm ls --depth=0` | 宣言した8依存を解決 | 宣言した8依存を解決 |
| `npx tsc --noEmit` | PASS, exit 0 | PASS, exit 0 |
| `npx expo config --type public --json` | PASS, SDK `57.0.0`、platforms `ios/android/web` | PASS, SDK `57.0.0`、platforms `ios/android/web` |
| `CI=1 npx expo export --platform web` | PASS, 183 modules、JS 331,936 bytes | PASS, 183 modules、JS 332,149 bytes |

静的出力はリポジトリ外の `/tmp` に作成した。両方とも JS bundle、`index.html`、`metadata.json`、`favicon.ico` が出力された。これはソースの型整合と Web bundle 生成を証明するが、ブラウザでの視認や物理端末での表示・その場反映は証明しない。

`npm ci` は成功したが、React Native `0.86.0` と Metro `0.84.4` 系は Node `^20.19.4 || ^22.13.0 || ^24.3.0 || >=25.0.0` を要求し、初回の Node `22.11.0` に `EBADENGINE` 警告を出した。この警告は歴史として残す。

当該ホストに既に導入されていた Node `22.16.0`（npm `10.9.2`）を `mise exec node@22.16.0 -- ...` で各コマンドにだけ適用し、両試作を再検証した。共有の Node 既定値、`package.json`、lockfile は変更していない。

| 適合 Node `22.16.0` での再検証 | `expo-first-screen` | `live-reload` |
|---|---|---|
| `npm ls --depth=0` | PASS, exit 0 | PASS, exit 0 |
| `tsc --noEmit` | PASS, exit 0 | PASS, exit 0 |
| `expo config --type public --json` | PASS, SDK `57.0.0`、`ios/android/web` | PASS, SDK `57.0.0`、`ios/android/web` |
| `expo export --platform web` | PASS, JS 331,936 bytes | PASS, JS 332,149 bytes |

適合 Node での bundle は、Node `22.11.0` で得たものとファイル名（ハッシュを含む）とバイト数が一致した。Metro が表示する module 数は初回の各183から、キャッシュ後の再検証で153/141へ変わった。この数値は出力同一性の判定に使わない。合否は各コマンドの終了コード、Expo 設定値、生成 bundle のファイル名とバイト数で判定する。

この結果は「この lockfile の SDK 57 試作を現在の WSL で型検査し、Web へ出力できた」証拠である。物理 iOS/Android 互換性、現在の Expo Go との適合、SDK 54 との比較は未観測である。したがって、SDK 57 の製品採用も SDK 54 の継続採用もここでは決めない。

### G3/G5 事前条件の実測

親 `prototype-chapter/package-lock.json` も lockfileVersion 3 で、textlint 一式を固定している。親プロジェクトにも独自の `preinstall` / `postinstall` / `prepare` はない。Node `22.16.0` をコマンド局所で使い、`npm ci --no-audit --no-fund` で443 package を既存 lockfile から復元した。manifest と lockfile の変更はない。

| 検証 | 結果 | 証明する範囲 |
|---|---|---|
| `npm run gate:style:selftest` | PASS, exit 0。陽性 70/70 と 47/47 を検出、陰性の誤検知0 | prh/textlint の既知パターン検出が動く |
| `npm run gate:style` | PASS, exit 0。3章を検査 | **G3 の5検査中、文体チェック1項目だけ** |
| `npm run gate:quote`（初回） | BLOCKED, exit 1 | `embedmd` 不在のため引用照合は未判定 |
| `npm run gate:quote`（隔離復旧後） | PASS, exit 0。3章を照合 | 引用された範囲と `listings/` の現物にズレがない |
| `npm run gate`（隔離復旧後） | PASS, exit 0 | style 1項目と quote が同じ実行でPASS |

`gate:style` 自身が明記するとおり、G3 の構造チェック、開始状態の混入検査、方針同期チェック、開発ログの存在確認は未実装である。したがって `gate:style` の exit 0 を「G3通過」とは記録しない。

`embedmd` は当初 PATH、`${HOME}/go/bin`、ホーム配下の浅い既存実行ファイル検索では見つからなかった。既存 Go `1.25.1` を使い、`github.com/campoy/embedmd@v1.0.0` だけを `/tmp` 専用 `GOBIN` へ導入した。`go version -m` で module `github.com/campoy/embedmd`、version `v1.0.0` を確認し、絶対パスを `EMBEDMD` で対象コマンドにだけ渡した。

mise の Go shim が `GOBIN` を管理先の bin へ上書きすることも実測した。最初の試行で管理先に作られた `embedmd` は、導入前に存在しなかったことを確認済みで、`/tmp` 版の作成後に除去した。共有の Go/Node 既定値と管理 bin は元の状態である。

G5 のPASSは、引用した範囲が現物と一致することだけを証明する。`g5-quote.sh` 自身が明記するとおり、引用範囲の過不足や、コード全体の正しさは判定しない。

独立レビューも同じ `/tmp` の `embedmd` v1.0.0 と Node `22.16.0` で G5 を別実行し、3章PASSを再現した。この一時パスはセッションを超えた恒久配置ではない。現在の G5 合格証拠は有効だが、今後の再実行で v1.0.0 をどこに配置・復元するかは未決の運用事項として残す。

## 2. 物理実機 A0 の判定

| 対象 | 今回の結果 | 解除に要る資源 | 責任ロール | 次の操作 |
|---|---|---|---|---|
| 物理 Android | **BLOCKED**。Windows ADB は0件、WSL ADB はエミュレータのみ。表示・QR読み取り・文字編集後の反映は未観測 | Expo Go を利用できる物理 Android 1台、端末OS/Expo Go版の記録、PC と通信できる経路、lockfile に従って復元した試作 | 実機検証担当 | 隔離した試作で依存を復元し、クリーン起動→QR→初回表示→文字変更→その場反映を物理端末で記録する |
| 物理 iOS | **BLOCKED**。この WSL セッションから利用できる物理 iOS 端末を確認できず、`xcrun` も無い。表示・変更反映は未観測 | Expo Go を利用できる物理 iPhone 1台、端末OS/Expo Go版の記録、開発サーバーへ到達できる LAN または確認済み tunnel、lockfile に従って復元した試作 | 実機検証担当 | Android と同じ手順を物理 iPhone で独立に行う。シミュレータの過去証拠は代用しない |

片方の成功も、シミュレータの成功も、両 OS の完了へ外挿しない。開始時刻、終了時刻、実作業時間、手動で補った操作は端末ごとに分けて残す。

## 3. 既存 QA 17本の再実行

`PYTHONDONTWRITEBYTECODE=1 python3 scripts/curriculum-qa/test_*.py` をシェルの glob でひとまとめに起動せず、各ファイルを1本ずつ実行した。結果は **11 PASS / 6 FAIL** で、D14 の基準と一致した。

PASS した11本:

- `test_check_crossref.py`
- `test_check_ja_line_break.py`
- `test_check_jsx_marker.py`
- `test_check_procedure_order.py`
- `test_check_scaffold_alignment.py`
- `test_check_step_ref.py`
- `test_check_step_time.py`
- `test_check_variants.py`
- `test_check_why.py`
- `test_filepath_marker.py`
- `test_markdown_scan.py`

FAIL した6本は以下のとおり分類する。このレーンでは実装を修正しない。

| 自己テスト | 実測した失敗 | B31 推奨 | 残す検出能力 |
|---|---|---|---|
| `test_check_anchor.py` | 21件中2件が失敗。存在しない旧 `src/app/page.tsx` を「完成版に在る」と期待 | **手直し**。D1 の `app/` / `supabase/` と実測した Expo 構成へパス契約を更新 | コードブロック単体から貼り先が分かり、指示した実ファイルが存在すること |
| `test_check_false_success.py` | `check_tag_balance` → `sale_package` が無い `scripts/build-zip.sh` を読み失敗 | **手直し**。配布物依存を現行のパッケージ情報に差し替えた後に維持 | 構造が閉じていない時点の「これでエラーが出ない」という偽の成功宣言 |
| `test_check_tag_balance.py` | `sale_package` が無い `scripts/build-zip.sh` を読み失敗 | **手直し**。旧ZIP配布依存を外し、VFM と現行の開始状態で陽性・陰性例を再校正 | JSX/コード断片の開閉不整合と、配布済み開始状態を重複して数えないこと |
| `test_check_unused_image.py` | 本体のケースではなく、自己テストが無い `.github/workflows/material-gate.yml` を読み失敗 | **手直し**。本体の画像参照検査は維持し、配線検査を実際の G3/CI ジョブに合わせる | 本文から参照が消えた画像の残留と、画像拡張子追加時の CI 配線漏れ |
| `test_check_zip_reference.py` | 旧ZIPの中身を得る前に、無い `scripts/build-zip.sh` を読み失敗 | **作り直し**。EPUB のエントリと PDF のリンク注釈を別検査にする | 読者の手元に無いファイルとの照合を本文が求める事故。「違反なし」と「未判定」は別状態にする |
| `test_sale_package.py` | 無い `scripts/build-zip.sh` と旧 scaffold の構成が前提 | **作り直し**。旧 `sale_package.py` の ZIP parser は廃止し、EPUB のパッケージ内容と現行スターターを読むプロバイダーへ置換 | 配布物に実際に入るファイルと、受講者が開始時点で持つコードの一致 |

6本を緑にするために、不採用の `build-zip.sh`、旧 `src/app/page.tsx`、旧 workflow 名を戻してはならない。それでは現行構成を検査せず、自己テストの期待値だけを満たす。

## 4. メール認証、D4、G6 の BLOCKED

| 枝 | 今回の結果 | 不足資源 | 責任ロール | 次の操作と解除条件 |
|---|---|---|---|---|
| メール認証 | **BLOCKED / 未実行**。追跡・非追跡の `.env*` や `supabase/config.toml`、Supabase/SMTP/Expo/EAS の環境変数名、Supabase CLI を確認できなかった。専用プロジェクトの所有・team・操作権限を立証できない | 所有者が明示された専用 Supabase プロジェクト、team範囲、自分のテスト宛先、送信方式と制限、復帰用実機 | 認証検証担当 | まず所有と宛先の対応表を残す。次に「メール生成」「外部到達」「リンクから端末復帰」「最終ログイン」を別々に測る。所有を確認できるまで SMTP・DNS・課金・共有設定は変えない |
| D4 RLS 重試作 | **BLOCKED / 未実行**。リポジトリには D4 専用の RLS/Auth 試作ファイルと、所有を確認できる DB 設定が無い | 専用の使い捨て Supabase プロジェクト、合成データ、所有者と他者の2ユーザー、plain/minus を含む重い章の材料、独立検証者 | RLS 試作担当＋独立検証者 | curriculum 外の使い捨て環境で、本人の許可操作成功と他者の不許可操作拒否を対照にする。応答と DB 状態を両方残し、構文エラー・別制約・0行更新を RLS 成功に数えない |
| G6 exec | **BLOCKED / 未実行**。`g6-run.sh`、対象章、`codex` コマンドは存在する。A0 試作と親 `prototype-chapter` の npm 依存は既存 lockfile から復元済み。G3 の文体チェックと G5 はPASSしたが、G3 の残り4検査は未実装。実機操作も行えない | G3 残り4検査の実装・合格、文脈を持たない独立実行体、実機手順の手動証拠 | G6 実走担当＋独立検証者 | G3 の文体以外を「合格済み」と扱わず、共有フックや共有設定を変えずに `exec` へ進む。全実行体の到達、補完、実行不能、手動端末操作を欠落させない |

過去の記録は G6 exec が共有フックによる `npm install` 拒否で止まったと述べる。今回は G6 自体とそのフックを実行せず、A0 と親の3つの lockfile 復元、G3文体、G5引用照合を独立して成功させた。したがって「現在も同じフックが原因」とは断定しない。現在の具体的な未了は、G3 の未実装4項目と実機証拠である。

## 5. 再開順序

1. 実機検証担当が、物理 Android と iPhone 各1台の利用可能時間、OS版、Expo Go版を固定する。
2. 現在の静的検証は適合 Node `22.16.0` でも成功したため、実機試作時に同じ実行版と lockfile を明示してクリーン起動する。これは実機試作の再現条件であり、製品の Node/SDK 採用判断とは分ける。
3. 両実機の初回表示と変更反映を別々に取得する。片方が無ければ限定単位は PARTIAL のままとする。
4. 所有を確認した専用 Supabase 資源を割り当て、メール認証と D4 RLS を独立枝として行う。
5. B31 で上記6本の推奨を実装し、17本を再実行する。新しい検査の緑と G0 全体の緑は分けて報告する。
6. G5 はPASS済み。G3 の残り4項目を実装・合格した後に G6 exec を実行する。未到達と教材外の補完を失敗として残す。

## 6. 証拠の境界

- この記録は、実際に実行したローカル確認の範囲だけを扱う。
- 実機、外部メール、Supabase DB、G6 の成功は主張しない。
- 資格情報の値は読み出しておらず、記録にも含めていない。
- A0 の2試作と親 `prototype-chapter` には、それぞれの既存 lockfile で依存を導入した。導入済み Node `22.16.0` はコマンド局所の検証にだけ使用し、`embedmd` v1.0.0 は `/tmp` の専用パスにだけ作成した。共有既定値、共有 binary、manifest/lockfile の変更、原稿の自動同期・修正、認証操作、SMTP/DNS/課金/共有設定の変更、QA 実装の修正は行っていない。

## 7. 継続検証: ネイティブ配信と実機経路（2026-09-19）

### Metro の配信確認

Node `22.16.0`、既存 lockfile、オフライン・localhost の Metro を使い、各試作の iOS / Android 用 manifest と、その manifest が指す同一ローカルサーバーの launchAsset を取得した。4件とも HTTP 200、manifest の SDK は `57.0.0`。各エントリにある表示文言の包含も確認した。

| 試作 | 対象 | bundle bytes | SHA-256 |
|---|---|---:|---|
| expo-first-screen | iOS | 3,802,389 | `42997e160c5550b12915d6f20707de05ef2174ce6fa1a79f603d49a3805c14df` |
| expo-first-screen | Android | 3,809,448 | `1a4170d6bd531e38b6aaa9b1cddb4e9d00d79f7f71fba9f6ab1eccba446fb914` |
| live-reload | iOS | 3,802,689 | `5ef89add6ba049163c7eeec924aa1676a1f73c294bbfdd669757e23e00016882` |
| live-reload | Android | 3,809,748 | `bcc85ea0e8ec0e6b4379c11a224b2735462aa8b1b4178058b30cac08f85a70a1` |

最初の文言検査は Metro 内の二重エスケープされた Unicode を扱えず未検出となった。生成物を確認して検査側を修正し、元文字列・JSON エスケープ・二重エスケープを区別して再確認した。これは検査側の修正であり、アプリの不具合修正や実機成功ではない。

初回表示試作は CI モード（リロード無効）、変更反映試作は通常モードで起動した。ソースは編集していない。**この結果はネイティブ JavaScript の生成・配信までで、Expo Go の受理、画面表示、編集反映を証明しない。** localhost は実機からの到達経路にもならない。使用したポート8091/8092のサーバーは終了し、待受が無いことと試作の追跡ファイルに差分が無いことを確認した。

### 端末経路の再確認

通常の `adb` は Windows ADB へのラッパーだった。Windows 経路は端末0件。既存 WSL ADB サーバーのポート5037/5040を個別に照会すると、両方に同じ `emulator-5554`（`sdk_gphone64_x86_64`）が現れた。従って「すべての ADB 経路が空」とはしない。この既存エミュレータは物理端末ではなく、操作・停止していない。

Windows の接続済み PnP 機器を電話関連名で絞った結果も、該当したのは Bluetooth 音声機器だけで、iPhone / Android / MTP 電話の接続証拠は得られなかった。これは LAN 上の電話の不在を証明しない。物理端末の利用可能性・接続経路は引き続き未確認である。

### SDK とストアの一次情報

確認日現在、公式資料間に不一致がある。資料の記載と端末の実測を混同しない。

| 一次情報 | 確認内容と限界 |
|---|---|
| [SDK 57 版の公式リファレンス](https://docs.expo.dev/versions/v57.0.0/) | SDK 57 は React Native 0.86、最低 Node 22.13.x。ネイティブ対象は iOS 16.4+ / Android 7+。この対象表はストア版 Expo Go の互換性証明ではない |
| [Expo Go version mismatch](https://docs.expo.dev/troubleshooting/expo-go-version-mismatch/) | プロジェクトと Expo Go の SDK 一致を要求。一方、App Store は SDK 54 までとする記載は下記の現在のストア表示と一致しない |
| [日本の App Store](https://apps.apple.com/jp/app/expo-go/id982107779) / [米国の App Store](https://apps.apple.com/us/app/expo-go/id982107779) | Expo Go 57.0.9、React Native 0.86、iOS 16.4以降と表示。日本版は2026-09-02更新。実際の端末へのインストールと QR 起動は未確認 |
| [Google Play](https://play.google.com/store/apps/details?id=host.exp.exponent) | 2026-08-17更新と表示。公開ページだけでは配布バージョン・内包 SDK・最低 Android 版を確定できなかった |
| [SDK 57 リリース](https://expo.dev/changelog/sdk-57) | 2026-06-30時点の配布案内であり、現在のストア配布状況の代用にはならない |

iOS のストア記載は SDK 57 適合の可能性を示すが、これは推測に留まる。「SDK 57 は実機で不可能」「SDK 54 は利用不可」のどちらも断定しない。B16/B17の過去判断は変更せず、B11/B26の照合材料とする。次の実機試験ではストア地域、実際に導入された Expo Go 版、端末 OS、候補 SDK、開始状態と接続経路を併記し、初回表示と編集反映を OS ごとに観測する。

### 再開監査（同日・継続3ターン目）

元の V3.5 の限定完了条件を再読し、両物理端末の表示・編集反映が必須であることを再確認した。Windows ADB の再照会では、先の0件から `emulator-5554 offline` に変化していた。WSL ADB（5037）は同じエミュレータが device 状態で、物理端末の接続証拠は依然得られなかった。既存エミュレータには介入していない。上の0件は前回観測として保持する。

章表の現物を共通 parser で読み直し、構造有効・宣言したゲート入力は未充足・構造エラー0を確認した。S0の対応記録、QA分類、各試験の不足資源・担当・次操作は保存済み。両実機の利用経路という同じ阻害条件が3ターン連続で残り、候補試作のローカル検証を重ねても必須証拠は増やせない。従って目標は完了ではなく BLOCKED とする。端末資源の回答またはアクセス経路の変化があれば、§5の手順から再開する。

## 8. Mac mini 経由の物理 Android A0（2026-09-19）

### 環境と開始状態

ユーザーが明示した `macmini-lan` に SSH 接続し、物理 Pixel 7 Pro（Android 17 / API 37、ADB USB device）と物理 iPhone 12 mini（iOS 26.5.2、paired / wired、Developer Mode enabled）を識別した。既存のエミュレータは対象から外した。Mac は macOS 26.1、Node 22.22.2、npm 10.9.7。

リポジトリの試作2件を Mac の専用一時ディレクトリ `/tmp/sns-v35-device.itSEXk` にコピーし、各既存 lockfile から `npm ci`（各495 package）を実行した。WSLの各496 packageとの差はホストが異なる導入結果であり、lockfile は変更していない。実機で走らせたのは `expo-first-screen` の一時コピーで、Expo 57.0.8 / SDK 57.0.0 / React Native 0.86.0。`live-reload` 専用試作は依存復元までで、今回の表示証拠は同試作のPASSへ転用しない。

両端末とも Expo Go は未導入だった。Android には、導入済み Expo CLI の版照会が返した[公式 Expo Go 57.0.9 APK](https://github.com/expo/expo-go-releases/releases/download/Expo-Go-57.0.9/Expo-Go-57.0.9.apk)を取得して新規導入した。端末上でも versionName 57.0.9 / versionCode 444 を照合した。APKのハッシュと端末・ホストの実測値は [environment.json](../evidence/20260919-a0-android/environment.json) に保存。端末シリアルはハッシュ化して記録した。

Macの有線側IPへのAndroidのpingには応答がなく、同一LAN接続を確認できなかった。共有ネットワークを変更せず、対象物理端末だけに `adb reverse tcp:8093 tcp:8093` を追加し、localhostで起動したMetroへ `exp://127.0.0.1:8093` をADBのVIEW intentで渡した。これはUSBによる補助手順であり、QR読取・Wi-Fi経路の成功ではない。Metroの開始時にキャッシュを消去した。ログにmanifest assets解決の警告が出たが、今回の文字画面は表示できた。画像・フォント解決の成功へ外挿しない。

### 初回試験と計時した再確認

初回は13:34:28 UTCにCOLD起動。Expo Go初回案内のContinueを押し、後続の誤タップでPerformance monitorを開いたため閉じた。13:35:05に元の表示、13:35:15.194にソース編集、13:35:27に変更後表示を画面とUI情報で確認した。アプリを再起動したりreloadを送ったりせず反映した。初回の導入・調査全体の実作業時間は分離計測していない。

手動案内処理済みの状態で、計時した確認を別に実行した。新規インストールからの時間ではなく、Expo Goをforce-stopして元ソースからCOLD起動する範囲である。

| 観測 | UTC | 開始からの経過 |
|---|---|---:|
| 再確認開始 | 13:37:30.215 | 0秒 |
| 元の本文をUI情報とPNGで取得 | 13:37:34.179 | 3.964秒 |
| 一時コピーの本文文字列を編集 | 13:37:34.180 | 3.965秒 |
| 変更後本文をUI情報とPNGで取得 | 13:37:37.221 | 7.006秒 |
| 一時コピーのソースを復元 | 13:37:37.222 | 7.007秒 |

対象文字列は「ここから SNS を作っていきます」から「Android 実機で変更が反映されました」。再確認でも編集後の再launch・reload操作はしていない。画像取得まで約3.04秒であり、端末が更新した正確な瞬間ではなく観測上限である。

自動コマンドの処理時間合計6.995秒（ADB待機込み）、経過7.007秒。人間の能動作業時間・初心者学習時間は未測定で、この値から推定しない。開始状態、補助操作、初回と再確認の違いを取り除いて「7秒で環境構築できる」とは扱わない。

- [開始画面](../evidence/20260919-a0-android/initial.png) / [同UI情報](../evidence/20260919-a0-android/initial.xml)
- [編集後画面](../evidence/20260919-a0-android/edited.png) / [同UI情報](../evidence/20260919-a0-android/edited.xml)
- [起動結果](../evidence/20260919-a0-android/launch.txt) / [計時記録](../evidence/20260919-a0-android/measurement.json) / [証拠ハッシュ](../evidence/20260919-a0-android/sha256.json)

初回証拠の独立レビューは、Android物理A0の表示・編集反映に限定してAPPROVE。QR、Wi-Fi、初心者工数、iOS、製品SDK採用の証明ではないとの制約を維持した。ソースは元のハッシュへ復元し、リポジトリ内の試作ソース・lockfileは無変更。

### iPhone の現在地と章構成への反映

iPhoneのDeveloper Disk Imageは既に利用可能で、既存の `pymobiledevice3 developer dvt screenshot --tunnel` による実機画面取得に成功した。旧 `idevicescreenshot` は利用できなかったが、この代替経路がある。Expo Go は未導入で、ユーザーにApp Storeからの導入を依頼済み。Macの既存ipatoolも非対話のアカウント確認に成功しなかったため、資格情報や共有設定を変更していない。導入後は `devicectl` のpayload URLで試作を開き、実際の到達性、初回表示、編集反映を確認する。USB開発トンネルをExpo GoのHTTP経路と同一視しない。

この試験で章の境界へ戻せる知見は、Node適合・Expo Go導入・端末から開発サーバーへの到達・初回案内を、文字編集の学習と分けて開始条件に明示する必要があること。USBの補助手順で成功したことから、初心者向けQR経路の説明が十分とは判断できない。章の数・順序・所要時間を凍結せず、iOS確認と既定の独立実走を残す。

終了時には今回のMetroサーバーを停止し、8093の待受がないことを確認した。追加したADB reverse 8093だけを除去し、元からあった転送は保持した。Expo Goは停止したが、導入した57.0.9と一時試作は再開用に残した。

## 9. iPhoneのApp Store導入操作（2026-09-23）

SSH経由で、既存の実機用WebDriverAgentを起動し、専用ローカルポート18103からiPhone 12 mini（iOS 26.5.2）を操作できた。既存8100のサーバーは別のシミュレータであることを確認し、変更していない。端末のApp StoreでExpo Goの商品ページを開き、「入手」、続いて「インストール」を押した。その結果、Apple Accountのパスワード入力を求める確認画面へ到達した。

従来の「未導入だからユーザーが最初から操作する必要がある」という判断は早計だった。商品ページへの移動と導入開始はリモートで実行可能だった。現在の具体的な阻害は、端末上のApple Account認証である。本人に端末上での入力を依頼し、チャットでのパスワード提供は求めていない。アカウントを含む画面画像はリポジトリへ保存しない。認証後に導入済み版を確認し、A0の表示・編集反映へ進む。
