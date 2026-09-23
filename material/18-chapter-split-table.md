# 18. 章分割表

版: v35-draft-1

更新日: 2026-09-19

位置づけ: DRAFT / NON-G1

この表は、`15_カリキュラム骨子案.md` の A0〜E を章へ写した構成仮説である。A0 の iOS・Android
両実機試作が未完了なので、章数・所要時間・章境界は実測値ではなく、凍結していない。
教材本文、実装済み成果物、G1 承認済みの章一覧として扱わない。

全体ゲートは未通過である。A0 の iOS・Android 両実機確認、D4 の重い RLS 試作、Auth の
メール到達・リンク復帰・最終ログインの実測、B1 の未決整理、C8 の節目指定が必要である。
期限は既存どおり P1 / G1 より前とし、未通過のまま P1 / G1 へ進めない。

パートAの練習は、A0で動いた支給済みの `App.tsx` の値と処理を差し替える仮説である。
学習者が未学習の React Native 部品やコンポーネントを自作する前提にしない。React Native の
画面構造と Expo Router は `app-navigation` で初めて扱う。

## 試作から得た開始条件（章全体の実測とは別）

Android物理端末では、既存A0の一時コピーをUSB転送で表示し、文字の編集反映を確認した
（`decisions/20260919-prototype-env-and-qa-check.md` §8）。Node適合、Expo Go導入、
端末から開発サーバーへの到達と初回案内を、文字編集の学習より前の開始条件として分ける。
QR/Wi-Fi、iOS、初心者による章の実走は未確認。以下の「未実測」は章全体の到達・時間を指し、
Android技術試作の結果を章全体のPASSへ置き換えない。

## 章一覧

| 章ID | 並び順 | パート | 章タイトル | 完成する状態 | 前提とする前章成果 | supersedes | 状態 | 節目 | 地図 | 見える変化 | 最初の結果 | 未決依存 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|
| expo-first-screen | 10 | A0 | はじめての画面をスマホに出す | ターミナル、エディタ、Node.js/npm、Git の基本操作で Expo プロジェクトを作り、開始画面を実機で開ける | - | - | 未着手 |  | 開始画面 | screen | 予定節: 実機に開始画面を出す（未実測） | B11,B15,B26,B102,B121 |
| live-reload | 20 | A0 | 書き換えをすぐスマホへ届ける | 文字と色の変更が実機へ即時反映される | expo-first-screen | - | 未着手 |  | 開始画面 | screen | 予定節: 保存した文字を実機で確認する（未実測） | B15,B26,B50 |
| ts-values-and-types | 30 | A | 投稿の値と型をつかむ | 支給済み画面の値を変数、定数、基本型、演算子で差し替えられる | live-reload | - | 未着手 |  | 投稿作成 | screen | 予定節: 型を付けた値を画面で確認する（未実測） | B50 |
| ts-collections | 40 | A | 投稿を配列とオブジェクトで並べる | 支給済み画面へユーザーと投稿のオブジェクト配列を渡せる | ts-values-and-types | - | 未着手 |  | タイムライン | screen | 予定節: 投稿配列が一覧に変わる（未実測） | B50 |
| ts-functions | 50 | A | 関数で表示用データを整える | 支給済み画面が使う値を引数、戻り値、型注釈付き関数で整形できる | ts-collections | - | 未着手 |  | 投稿カード | screen | 予定節: 関数の戻り値がカードへ反映される（未実測） | B50 |
| ts-branches-and-loops | 60 | A | 条件分岐とループで表示を変える | 支給済み画面の空表示、文字数、投稿一覧を条件分岐と反復で切り替えられる | ts-functions | - | 未着手 |  | タイムライン | screen | 予定節: 条件に応じて表示が切り替わる（未実測） | B50 |
| ts-classes-and-errors | 70 | A | クラスとエラーを読めるようになる | 支給済みコード中のクラスを読み、型エラーと実行時エラーを切り分けられる | ts-branches-and-loops | - | 未着手 |  | エラー表示 | screen | 予定節: エラー修正後に画面が戻る（未実測） | B50 |
| app-navigation | 80 | B | React Native の画面を行き来する | React Native の基本部品と Expo Router で主要画面を開き、戻れる | ts-classes-and-errors | - | 未着手 |  | 全画面図 | screen | 予定節: 2画面を往復する（未実測） | B1,B75,B87,B100,B114 |
| supabase-connection | 90 | B | アプリを Supabase につなぐ | 接続設定を読み込み、接続結果をアプリ画面で確認できる | app-navigation | - | 未着手 |  | 接続確認 | screen | 予定節: 接続結果を画面へ出す（未実測） | B2,B11,B94,B101 |
| auth-sign-up | 100 | B | アカウントを作る | 利用者行を作るトリガーと最初の RLS を入れ、登録後に確認待ち画面へ進める | supabase-connection | - | 未着手 |  | 新規登録,メール確認待ち | screen | 予定節: 登録後に確認待ち画面が出る（未実測） | B14,B18,B19,B62,B88,B98,B109 |
| auth-email-confirmation | 110 | B | メール確認を終えてアプリへ戻る | 確認メールを受け取り、リンクからアプリへ戻れる | auth-sign-up | - | 未着手 |  | メール確認待ち | screen | 予定節: リンクからアプリへ戻る（未実測） | B5,B14,B18,B88,B103,B109 |
| auth-session-and-profile-setup | 120 | B | ログイン状態と表示IDを整える | 再起動後も認証状態を復元し、初回プロフィールを保存できる | auth-email-confirmation | - | 未着手 |  | ログイン,プロフィール初期設定 | screen | 予定節: 表示ID保存後にタイムラインへ進む（未実測） | B19,B24,B25,B64,B78,B90,B91,B95,B96,B97,B107 |
| profile-view-and-edit | 130 | B | プロフィールを表示して編集する | 自分の表示名、自己紹介、アイコン、ヘッダーを表示・更新できる | auth-session-and-profile-setup | - | 未着手 |  | プロフィール,プロフィール編集 | screen | 予定節: 保存した表示名がプロフィールへ反映される（未実測） | B21,B24,B25,B66,B78,B84,B85,B91,B92,B104,B117 |
| text-post | 140 | B | 文章を投稿する | posts と同章の RLS を作り、280字以内の投稿を投稿詳細で確認できる | profile-view-and-edit | - | 未着手 |  | 投稿作成,投稿詳細 | screen | 予定節: 投稿した文章が詳細に出る（未実測） | B1,B63,B68,B71,B72,B76,B86,B91,B115 |
| image-post | 150 | B | 画像を添えて投稿する | post_media と Storage の同章の保護境界を作り、画像を最大4枚添えて投稿できる | text-post | - | 未着手 |  | 投稿作成,投稿詳細 | screen | 予定節: 選んだ画像が投稿詳細に出る（未実測） | B21,B66,B67,B70,B82,B84,B85,B104,B117 |
| follow-relations | 160 | B | フォロー関係を作る | follows と同章の RLS を作り、フォローと解除を一覧で確認できる | image-post | - | 未着手 |  | プロフィール,フォロー中一覧,フォロワー一覧 | screen | 予定節: フォロー後に一覧と件数が変わる（未実測） | B25,B65,B89,B105,B110 |
| following-timeline | 170 | B | フォロー中の投稿を読む | 対象投稿を新着順で追加読み込みし、空状態も判別できる | follow-relations | - | 未着手 |  | タイムライン | screen | 予定節: フォロー相手の投稿が一覧に出る（未実測） | B4,B10,B22,B23,B27,B60,B80,B106,B108,B122 |
| reply-and-repost | 180 | B | 会話とリポストを作る | posts の親参照ポリシーを足し、リプライ、無言リポスト、引用リポストを確認できる | following-timeline | - | 未着手 |  | 投稿詳細 | screen | 予定節: 返信がスレッドに出る（未実測） | B27,B72,B76,B86,B115 |
| likes | 190 | B | いいねを付け外しする | likes と同章の RLS を作り、いいねと解除を件数で確認できる | reply-and-repost | - | 未着手 |  | 投稿詳細 | screen | 予定節: いいね後に件数が変わる（未実測） | B22,B65,B76,B86 |
| realtime-notifications | 200 | B | 通知をリアルタイムで受け取る | notifications と同章の RLS・生成境界を作り、本人だけが通知を読み既読化できる | likes | - | 未着手 |  | 通知 | screen | 予定節: 別利用者の操作が通知に出る（未実測） | B7,B22,B28,B65,B74,B77,B78,B79,B80,B89,B106,B108 |
| password-reset | 210 | B | メールからパスワードを再設定する | 再設定メールのリンクから新しいパスワードを保存し、ログインできる | realtime-notifications | - | 未着手 |  | パスワード再発行,パスワード再設定 | screen | 予定節: 新しいパスワードでログインする（未実測） | B14,B18,B62,B88,B103,B109 |
| rls-denial-check | 220 | B | 他人のデータが守られることを確かめる | 既に導入した各 RLS について、他人の操作が拒否され本人の操作だけ成功することを画面とDB状態で確認できる | password-reset | - | 未着手 |  | 投稿詳細,プロフィール,通知 | screen | 予定節: 他人の更新を拒否して本人の更新を通す（未実測） | B27,B76,B81,B86,B90,B91,B107,B111,B112,B113,B115,B116,B118,B119,B120 |
| search-posts-and-users | 230 | C | 投稿とユーザーを検索する | 空文字を除外し、キーワードで投稿とユーザーを検索できる | rls-denial-check | - | 未着手 |  | 検索 | screen | 予定節: 検索結果が画面に出る（未実測） | B1,B25,B73,B81,B122 |
| hashtag-timeline | 240 | C | ハッシュタグで投稿をたどる | hashtags と post_hashtags の同章の RLS を作り、既存投稿を含むタグ別一覧を表示できる | search-posts-and-users | - | 未着手 |  | ハッシュタグ別一覧 | screen | 予定節: タグを選ぶと投稿一覧が出る（未実測） | B1,B61,B76,B83,B93 |
| private-bookmarks | 250 | C | 投稿を自分だけの一覧へ保存する | bookmarks と同章の RLS を作り、本人だけの一覧を表示できる | hashtag-timeline | - | 未着手 |  | ブックマーク一覧,投稿詳細 | screen | 予定節: 保存した投稿が一覧に出る（未実測） | B27,B61,B76,B86,B115 |
| camera-post | 260 | C | カメラで撮って投稿する | 権限の許可・拒否を扱い、撮影画像を投稿できる | private-bookmarks | - | 未着手 |  | 投稿作成 | screen | 予定節: 撮った画像が投稿プレビューに出る（未実測） | B5,B15,B21,B26,B67,B104,B114 |
| app-polish | 270 | C | SNS の見た目と失敗時の表示を整える | 読み込み、空、失敗、再試行の状態を主要画面で区別できる | camera-post | - | 未着手 |  | 全画面図 | screen | 予定節: 失敗表示から再試行できる（未実測） | B1,B25,B27,B87,B99,B100,B114 |
| web-first-run | 280 | D | 同じ SNS をブラウザで開く | Expo の Web 出力で SNS の主要画面を開ける | app-polish | - | 未着手 |  | Web版全画面 | screen | 予定節: ブラウザにタイムラインが出る（未実測） | B6,B11,B81,B94 |
| web-platform-fixes | 290 | D | Web と端末の違いを手当てする | 認証、画像、カメラの差異を整理し、主要動線を Web で完了できる | web-first-run | - | 未着手 |  | Web版主要動線 | screen | 予定節: Webで主要動線が最後まで通る（未実測） | B6,B18,B21,B84,B99,B103,B104 |
| sns-technology-map | 300 | E | 作った SNS の技術地図を描く | 画面、TypeScript、Supabase、RLS、端末、Web の関係を説明できる | web-platform-fixes | - | 未着手 |  | 全体地図 | screen | 予定節: 技術地図の線を完成させる（未実測） | C8 |
| one-minute-demo | 310 | E | 自分の SNS を1分で紹介する | 動く SNS を見せながら目的、機能、技術を1分で説明できる | sns-technology-map | - | 未着手 |  | 完成SNS | screen | 予定節: 1分の実演を録画する（未実測） | C8 |

## 対応表

| 章ID | FR | 画面 | SQL/RLS | テスト | 前提知識 | 証拠 |
|---|---|---|---|---|---|---|
| expo-first-screen | - | 開始画面 | N/A（DB未使用） | Node/npm確認、Git保存・巻き戻し、iOS・Android実機起動、QR接続 | PC基本操作、アプリ導入 | - |
| live-reload | - | 開始画面 | N/A（DB未使用） | 両実機の即時反映、再接続 | expo-first-screenの起動手順 | - |
| ts-values-and-types | - | 支給済みA0練習画面 | N/A（DB未使用） | 型一致、演算結果、文字数表示 | live-reloadの編集と保存 | - |
| ts-collections | - | 支給済みA0練習画面 | N/A（DB未使用） | 配列順、空配列、オブジェクト項目 | 変数、定数、基本型、演算子 | - |
| ts-functions | - | 支給済みA0練習画面 | N/A（DB未使用） | 引数、戻り値、型エラー | 配列、オブジェクト | - |
| ts-branches-and-loops | - | 支給済みA0練習画面 | N/A（DB未使用） | 分岐、反復、空表示、境界値 | 関数、配列 | - |
| ts-classes-and-errors | - | 支給済みA0練習画面 | N/A（DB未使用） | 型エラーと実行時エラーの再現・復旧 | 変数、型、配列、オブジェクト、関数、分岐、反復 | - |
| app-navigation | - | 主要画面の仮ページ | N/A（DB未接続） | React Native基本部品、画面遷移、戻る操作、不明経路 | TypeScript基礎全範囲 | - |
| supabase-connection | - | 接続確認 | 接続設定のみ、RLS未導入 | 設定欠落、接続成功、秘密情報非混入 | Expo Router、環境設定 | - |
| auth-sign-up | FR1,FR13 | 新規登録,メール確認待ち | auth.usersトリガーでusers作成、RLS有効、本人SELECT、クライアントINSERT不可、UPDATEは後章 | 登録成功、users行作成、重複、入力不備、他人SELECT拒否、クライアントINSERT拒否、確認前制限 | Supabase接続、入力状態 | - |
| auth-email-confirmation | FR13 | メール確認待ち | 確認済み利用者の書込条件 | 外部メール到達、リンク復帰、再送、上限、期限切れ | 新規登録、ディープリンク | - |
| auth-session-and-profile-setup | FR1,FR2 | ログイン,プロフィール初期設定 | users本人SELECT/UPDATE | ログイン、ログアウト、再起動復元、他人更新拒否、重複ID | メール確認、認証状態 | - |
| profile-view-and-edit | FR2 | プロフィール,プロフィール編集 | users本人UPDATE、他人SELECT、Storage境界 | 表示、編集、他人更新拒否、画像差替え | セッション、プロフィール初期設定 | - |
| text-post | FR3 | 投稿作成,投稿詳細 | posts INSERT/SELECT/UPDATE/DELETE | 280字境界、空投稿、作成、本人削除、他人削除拒否 | プロフィール、入力状態 | - |
| image-post | FR3 | 投稿作成,投稿詳細 | post_media親所有者RLS、Storage境界 | 画像0〜4枚、形式、容量、途中失敗、孤児行 | 文章投稿、非同期処理 | - |
| follow-relations | FR8 | プロフィール,フォロー中一覧,フォロワー一覧 | follows作成、RLS有効、本人INSERT/DELETE | フォロー、解除、自己フォロー、他人なりすまし、一覧差 | プロフィール、複数利用者 | - |
| following-timeline | FR4 | タイムライン | followsを使うposts SELECT | 対象集合、新着順、重複・欠落、追加読込、空状態 | 投稿、フォロー関係、一覧表示 | - |
| reply-and-repost | FR5,FR6 | 投稿詳細 | posts親参照RLS、論理削除境界 | 親子順、無言・引用、同時指定、削除親 | タイムライン、投稿詳細 | - |
| likes | FR7 | 投稿詳細 | likes作成、RLS有効、本人INSERT/DELETE | いいね、解除、二重いいね、他人なりすまし | 投稿詳細、複数利用者 | - |
| realtime-notifications | FR9 | 通知 | notifications本人SELECT、既読更新、生成境界 | 4種通知、他人閲覧拒否、列改変拒否、再接続 | いいね、リプライ、リポスト、フォロー | - |
| password-reset | FR14 | パスワード再発行,パスワード再設定 | Auth管理、RLS対象外 | メール到達、リンク復帰、新旧パスワード、期限切れ | メール確認、ディープリンク | - |
| rls-denial-check | - | 投稿詳細,プロフィール,通知 | users/posts/post_media/likes/follows/notificationsの正負RLS、Storage境界 | FR1,FR2,FR3,FR5,FR6,FR7,FR8,FR9を人が照合、本人成功、他人失敗、DB状態、0行と構文失敗の識別 | 認証とパートB全操作 | - |
| search-posts-and-users | FR10 | 検索 | users/posts検索、索引候補 | 投稿検索、利用者検索、空文字、0件 | 投稿、プロフィール | - |
| hashtag-timeline | FR11 | ハッシュタグ別一覧 | hashtags/post_hashtags親所有者RLS | 正規化、重複、他人結付け拒否、既存投稿バックフィル | 検索、投稿 | - |
| private-bookmarks | FR12 | ブックマーク一覧,投稿詳細 | bookmarks本人SELECT/INSERT/DELETE | 保存、解除、他人閲覧拒否、削除投稿 | 投稿詳細、複数利用者 | - |
| camera-post | FR3,FR15 | 投稿作成 | post_media親所有者RLS、Storage境界 | 権限許可・拒否、撮影、アップロード、投稿反映 | 画像投稿、端末権限 | - |
| app-polish | - | 全画面 | 既存SQL/RLSの回帰確認 | FR1〜FR15の読込、空、入力失敗、操作失敗、取得失敗、再試行を人が照合 | パートB・C全成果 | - |
| web-first-run | - | Web版主要画面 | 既存SQL/RLSをWebクライアントから利用 | FR1〜FR14の主要画面を人が照合、Web起動、秘密情報非混入 | 完成したモバイル版SNS | - |
| web-platform-fixes | - | Web版主要動線 | 既存SQL/RLSのWeb回帰確認 | FR1〜FR14の主要動線を人が照合、認証復帰、画像選択、端末専用機能の代替 | Web起動、モバイルとの差異 | - |
| sns-technology-map | - | 全体地図 | N/A（新規DB変更なし） | FR1〜FR15と画面・データ・保護境界を人が照合 | モバイル版とWeb版の全成果 | - |
| one-minute-demo | - | 完成SNS | N/A（新規DB変更なし） | FR1〜FR15の主要動線を人が照合、1分説明、質問への応答 | 技術地図、完成SNS | - |

## 未完了の条件

この DRAFT の作業単位が完了しても、G1 合格または制作準備完了を意味しない。A0 両実機、D4、
Auth、B1、C8 と各未決依存を閉じ、対応する直接証拠を得た後に、章境界・並び順・節目を再評価する。
