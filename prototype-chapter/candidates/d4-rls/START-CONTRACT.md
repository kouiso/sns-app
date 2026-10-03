# D4 重い章候補 — 開始契約

> **NON_FORMAL_D4_START_CONTRACT_CANDIDATE**
> 本書はD4重い章を安全に実測するための開始条件候補である。正式なD4章、P1/G1通過、G6合格、B2/B10/B14/B111/B112/B119の決着を表明しない。

## 1. 対象と固定入力

D4の対象は、パートB相当のRLS章をD5の本番書式で通して作り、専用実装PRの着手から必要なG6証拠の取得までを測る作業である。過去のAuth試作、RLS試作、A0の所要時間はD4工数へ足さず、開始時刻を遡って補わない。

開始候補の固定入力は次の2点である。1 byteでも異なれば開始せず、変更理由、変更者、再レビュー対象を記録して新しいmanifestを作る。

| 入力 | 候補パス | SHA-256 | 扱い |
|---|---|---|---|
| 9テーブルRLS候補 | `supabase/migrations/20261003080326_d4_predecessor_candidate.sql` | `e4667d31b9beff022b56a030ef4f0c26f924224c1170b2285bdda823d2c109b4` | B27/U19/U20等を閉じない前段候補 |
| Auth SDK 57アプリ | `../auth-sdk57/App.tsx` | `31a1deb465120c77dbd1fcd0f38ab0b21b3adf35e1474f0801a5492b21617b20` | 正式教材ではない既存候補 |

スキーマ候補は9テーブル、`auth.users` から `public.users` を作るトリガー、RLS、列権限、限定RPCを持つ。Authトリガーは**適用後に作られたAuth利用者**にだけ働く。既存の `auth.users` を遡って `public.users` へ補完しない。既存アカウントを流用する場合は、対応行の有無を独立に検査し、欠けていれば流用を中止する。手作業のバックフィルを暗黙に行わない。

この候補では投稿作成後の直接UPDATEを公開しない。論理削除は `public.soft_delete_post(uuid)` のboolean結果を使う。過去の短い試作にあった「クライアントがpostsを直接UPDATEして削除する」手順を持ち込まない。

## 2. 開始前に全部そろえるもの

以下を満たすまで「最初の結果」の計時も、正式D4実装PRの時計も始めない。

1. 固定入力2点のパスとSHA-256を機械確認できるsource manifestがある。
2. Supabase環境の所有者、費用主体、用途、破棄条件、排他的lease ID、有効期限が記録されている。
3. 対象環境へ候補migrationを新規状態から適用でき、9テーブル、Authトリガー、24候補policy、table/column grants、function ACLを機械検査できる。
4. 互いに異なる通常のメール確認済み利用者A/Bがあり、両方とも通常のpassword sign-inでsessionを得られる。A/Bは`auth.users.id`もメールアドレスも異なる。
5. A/Bはmigration適用後に作る。既存ユーザーへの暗黙バックフィルに依存しない。
6. 実行体へ渡す公開設定はfrontend URLとpublishable key（ローカル互換時だけlegacy anon key）に限る。secret key、`service_role`、DB password、管理API tokenは渡さない。
7. A5用の宣言済み入力チャネル、reset tool、reset tests、DB独立照合tool、計測loggerが実行可能である。
8. reset toolのdry-runが、今回のleaseで所有する合成行だけを列挙し、A/BのAuth・profile identityを対象外にする。
9. 章開始時点のstarterからアプリを起動し、URL/keyの欠落時はfail closedになる。完成repoや設計書を参照しなくても章の手順を開始できる。
10. 実機を使う回は、端末、Mac、Linux、Metro、API proxyをその回の証拠で再確認する。
11. 開発ログ、画面証拠、DB照合結果がtoken、password、callback URL、raw JWTを保存しないことを事前検査する。
12. 本章で使う「独立DB照合」が、アプリと同じsessionの返り値を言い換えるだけでなく、別actorのread-only照合である。

不足は開始失敗であり、教材手順の途中で人が補う前提にしない。

## 3. 環境と責任境界

Supabaseのprovision、migration適用、排他的lease、A/B準備、reset、破棄は制作側/G6環境提供者の責任である。学習者へDocker、Supabase CLI、DB管理権限、管理キーを要求しない。B2/B111/B119が正式決定する前なので、本候補はホスト型採用やCI方式を確定しない。

現在使える制御環境はローカルSupabaseとMailpitである。Mailpitでの確認メール捕捉は、外部SMTP送信、実在受信箱への到達、DNS、配信上限を証明しない。B14を閉じず、D4では「制御されたローカル確認」と表示する。外部メールの証拠をD4の結果へ混ぜない。

物理iPhone経路では、Mac miniのWi-Fiアドレス `192.168.11.11` とAPI候補ポート `8094` の組合せが過去に検証された。2026-10-03の開始契約作成時点では8094のlistenerは停止中である。IP、port、端末IPを推測せず、各runで再取得する。proxyはrun所有のPID、bind address、allowed peer、開始・終了時刻を記録し、終了時にそのPIDだけを止める。このLAN経路は開発用であり、本番可用性、公開URL、TLS、外部到達を約束しない。

## 4. A5を破らない入力チャネル

文脈ゼロ実行体へ渡せる知識は、その章までの教材と章開始starterだけである。一方、接続情報とA/B資格情報は実行に必要な環境入力なので、次の**宣言済み入力チャネル**へ分離する。

| チャネル | 内容 | 読み手 | 保存・表示 |
|---|---|---|---|
| `D4_PUBLIC_RUNTIME_INPUT` | frontend URL、publishable/legacy anon key、redirect base、run ID | アプリ起動harness | 値はsecret扱いしないが、run receiptにはhashとkey種別だけを書く |
| `D4_ACCOUNT_FIXTURE_INPUT` | A/Bの識別ラベルと通常ログイン資格情報 | 資格情報入力driverだけ | mode 0600相当、Git・教材・prompt・モデル出力・CLI引数へ置かない |
| `D4_PROVIDER_CONTROL_INPUT` | DB照合・resetに必要なprovider権限 | provider toolだけ | 実行体、アプリ、章本文、G6 read/execへ渡さない |

値はヒント文、モデルの記憶、過去会話、設計書の隠し読みから補わない。harnessは開始時に必須field名、供給元、受領時刻、値のhashだけをreceiptへ記録する。field欠落時は停止し、既定値やlocalhost推測へ退避しない。A5の実行体はprovider controlへ到達できないことを負例で検査する。

## 5. A/Bと合成データ

- Aは所有者、Bは他者役で、どちらも通常の確認済みアカウントである。
- A/Bのprofile rowがAuthトリガーで作られたことを確認する。手作業で行を足してトリガー成功と呼ばない。
- A/Bのidentityは1 runの途中で作り直さない。run内の投稿等はlease manifestでIDを追跡する。
- 教材と実行体にはfrontend URL、公開キー、通常ログイン操作だけを見せる。管理キーで確認済みsessionを直接生成しない。
- 制作側がローカルMailpitで確認リンクを扱った場合、その操作をprovider setupへ分類し、教材の外部メール成功に数えない。

B10の正式なseed方針は未決である。本候補のA/Bと合成行はD4測定fixtureであり、教材全体のseed契約へ昇格しない。

## 6. Reset契約

グローバルなAuth reset、プロジェクト全消去、共有行の掃除は行わない。resetは排他的leaseが所有する合成行だけに限定する。

reset toolは最低限、次の順序と検査を実装してから受入可能になる。

1. lease ID、対象project ref/URL hash、A/B user ID hash、作成した全row IDをmanifestから読む。
2. dry-runで削除候補をtable別に表示し、manifest外IDが1件でも混ざれば停止する。
3. `notifications` → `bookmarks` → `post_hashtags` → `post_media` → `likes` → run所有の`follows`の順に子行を消す。
4. run所有の`posts`は自己参照FKを満たす順序、または同一statementで対象集合を消す。集合外投稿を対象にしない。
5. runが新規作成した`hashtags`だけを、残る`post_hashtags`参照が0件であることを確認して消す。
6. A/Bの`public.users`と`auth.users`は保存する。別run、別利用者、共有fixtureを消さない。
7. reset後にmanifest対象行が0件、対象外のsentinel行が不変、A/Bが通常ログイン可能、profile IDが不変であることを検査する。

Auth sessionの後片付けはデータresetと分ける。端末のAsyncStorageやローカルsessionを消しても、既発行JWTのserver側失効を証明しない。`signOut`のscopeと実測結果を記録し、明示的なprovider-side revokeを行っていない限り「JWT失効」と書かない。A/B identityを保存するrunでは、全Auth利用者削除やAuth schema resetを使わない。

reset recipeは文章だけでは受け入れない。実行ファイル、dry-run、正例、manifest外行・sentinel・A/B identityを守る負例、失敗時の非破壊停止をテストし、そのhashをsource manifestへ追加する。

## 7. RLSを外す比較実験の境界

RLS無効化は通常手順ではなく、RLSの効果を見るためのprovider管理下の短いfault-injection sliceだけに限定する。学習者へ汎用的な`disable RLS`やreset commandを渡さない。

slice実行前に次をcatalogから保存する。

- 対象tableの`relrowsecurity` / `relforcerowsecurity`
- 対象tableの全policy名、command、role、`using`、`with check`
- table grantsとcolumn grants
- 関連functionのowner、security mode、EXECUTE ACL
- migration SHAと対象schema hash

provider toolは排他的leaseを確認し、対象tableと時間を固定し、必要最小の1操作だけを観測する。RLSを戻すだけで完了にせず、policy定義、table grants、column grants、function ACLを開始前snapshotと照合する。差分が1件でも残ればstackを隔離し、次runや正式計測に使わない。restoreの成否はアプリ応答ではなくcatalog before/afterと負例再実行で判定する。

この候補の投稿削除RPCは関数内で所有者を照合するため、RLSを切ってもBによる削除が成功しない。その挙動を「RLSが守った」と誤分類しない。RLS fault injectionの対象操作は、policyが直接守る操作として別に定義し、RPCの所有者検査と分離する。

## 8. 最初に見える結果

候補章の最初の結果は次の3点が同じrun IDでそろった時点とする。

1. Aが通常ログインし、自分名義の投稿を作り、画面にその投稿が見える。
2. Bの通常sessionから `public.soft_delete_post(P_A)` を呼び、boolean `false` を受け取る。直接posts UPDATE/DELETEへ置換しない。
3. アプリとは別actorのread-only DB照合で、`P_A.author_id = A`、`deleted_at is null`、投稿が1件だけ存在することを確認する。

画面だけ、RPCのbooleanだけ、DBだけでは達成にしない。Bの`false`は限定RPC内の所有者検査の結果であり、RLS拒否と呼ばない。別制約、構文エラー、接続失敗、0行を「他者削除を防いだ証拠」に数えない。

計時は文脈ゼロ実行体が章頭の開始操作を受け取った時刻から、上の3点がそろい画面証拠を得た時刻までとする。中断・再試行・失敗runを除外せず、各runの状態と理由を残す。

## 9. D5の7役割と実記録の出どころ

章は次の7役割を順に持つ。

1. タイトル、到達目標、前章からの接続、前提
2. 完成品SNSの地図と今回の範囲
3. 対話による概念導入、実行、最初に見える結果
4. `教材に載せる価値: 高` の実記録がある場合だけ、生徒のエラー体験と先生の解決
5. 生徒の復唱と先生の締め
6. 実記録に由来する「よくあるエラーと対処」
7. 演習問題。解答は別掲

要素4と6へ架空の失敗を作らない。各開発ログにはactor、UTC開始/終了、monotonic経過、操作、入力/出力hash、結果、再試行、friction種別（`beginner` / `ai-artifact` / `unobserved`）、教材価値を記録する。価値「高」は要素4へ1回だけ置き、それ以外とG6の詰まり・教材外補完は要素6へ置く。同じ事象を4と6へ重複させない。0件なら0件一致を記録し、節を埋めるために創作しない。

## 10. 独立実走・独立read・中央値

A5に従い、作者と同一contextの実行を独立証拠に数えない。独立実行体へ渡すのは章本文、章開始starter、§4の宣言済みruntime inputだけで、完成repo、設計書、開発ログ、以前の解答を渡さない。教材外知識で補った箇所は成功ではなく欠落として記録する。

計測候補は次のとおりである。

- D4重い章とA0相当の軽い章について、各3独立execを行う。
- 各runで章頭から最初の画面結果までの実時間、画面、失敗・再試行を残し、失敗runを捨てない。
- 3値が有効に観測できた章だけ中央値を算出する。欠測を0秒へ置換しない。
- `plain.md`（対話を抜く）と`minus.md`（価値高の詰まりだけを抜く）を用意し、独立readを2ラウンド行う。
- 価値高の詰まりが0件ならminus roundをN/Aとし、0件検査をreceiptへ残す。
- 本文を改訂したらplain/minusも同じ変更単位で更新し、3ファイルのhashをreceiptへ記録する。

上の「各3exec」はB50/D5の最初の結果の測定条件であり、正式G6 execの体数・失敗扱い・合否式ではない。B112は未決なので、3体の結果から正式G6合格を発明しない。G6 readの体数・過半数規則とexecを混同しない。B112が決まるまでは、独立execの証拠は**前提計測**として保存し、正式合否欄は`UNJUDGED_B112`とする。

## 11. 計測フェーズと正式D4時計

過去作業を遡及計上しないため、2段階に分ける。

### Phase P — 前提計測

本書、source manifest、provider harness、reset tool/tests、A/B、接続、RLS fault-injectionの復元検査、最初の結果の試走を作る。開始はPhase P receiptを新規発行した時刻とし、過去のAuth/RLS試作時刻を入れない。ここで得た時間は「前提整備」として別集計し、正式D4章の実装時間へ混ぜない。

### Phase D4 — 正式計測

§2の全条件とPhase Pの受入がそろった後、D4専用実装PRを作り、そのPRの最初の対象変更を開始したUTC/monotonic時刻を時計の起点にする。起点commit、actor、入力hashをreceiptへ固定する。終了は本番書式の章、実装、実記録、必要な独立exec/read、plain/minus、DB照合、画面、G3〜G6の必要証拠がそろった時だけである。

B112など未決のため正式G6判定ができない場合、Phase D4を「完了」とせず、到達済み区間と待ち条件を分けて記録する。開始時刻をPhase Pや過去試作へ後から移動しない。

## 12. Source manifestと受入前の実装物

manifestは少なくとも次を固定する。

- migration、Auth App、starter、章本文、plain、minusの相対pathとSHA-256
- package/lock、Expo/Supabase CLI/Nodeの実使用版
- provider環境識別子のhash、lease ID、有効期限
- schema/policy/grant/function ACL snapshot hash
- A/B identity hash、fixture manifest hash
- reset tool/test hash、DB照合tool hash、計測logger hash
- 実機、Expo Go build、Metro/API/proxy経路、run所有PID
- 各receipt、画面、sanitized logのhash

本書にreset recipeを書いたことだけでは開始条件を満たさない。manifest生成、reset、catalog snapshot/restore比較、DB独立照合、secret漏えい検査を行う実行可能toolと、その正負テストが必要である。ツールがまだ無い状態は`CANDIDATE_INPUTS_UNFROZEN`とする。

## 13. 未凍結入力と候補フラグ

| フラグ | 意味 | 解消条件 |
|---|---|---|
| `CANDIDATE_INPUTS_UNFROZEN` | manifest/reset/照合toolとtestsが未完成 | 実行物、正負テスト、hashをmanifestへ固定 |
| `CANDIDATE_SCHEMA_NOT_APPLIED` | 候補migrationを対象環境で未検証 | 専用leaseで適用しschema/policy/grant/ACLを照合 |
| `CANDIDATE_ACCOUNTS_UNPROVEN` | A/Bの通常確認・distinct identity・trigger生成を未証明 | 通常sign-inと独立DB照合 |
| `CANDIDATE_NETWORK_STOPPED` | 8094 proxyは現在停止 | run所有proxyを再取得したIP/peerで起動しhealth確認 |
| `CANDIDATE_MAIL_LOCAL_ONLY` | Mailpitは外部配送の証拠ではない | D4内では解消しない。B14証拠と分離 |
| `UNJUDGED_B2_B10_B111_B119` | 配置、seed、provider/CI/secret境界が正式未決 | 各正本の決定と実装証拠 |
| `UNJUDGED_B112` | G6 exec体数・失敗扱い・合否式が未決 | B112の正式決定 |
| `NON_FORMAL_D4` | 本書と候補は正式章ではない | 正式工程・承認・全受入証拠 |

これらをPASSへ読み替えない。候補フラグを残したままでもPhase Pの安全な作業は進められるが、正式D4完了やG6合格は宣言できない。

## 14. 停止条件

次のどれかが起きたrunは停止し、失敗証拠を残す。

- source hash、schema snapshot、grant/ACLが期待と不一致
- project/lease所有が不明、または他runが同じ環境を使用中
- secret/admin権限がアプリ、実行体、教材、prompt、ログへ出た
- reset dry-runにmanifest外の行、A/B identity、sentinelが入った
- RLS fault-injection後にpolicy/grant/ACLが完全復元しない
- A/Bがdistinctでない、未確認、通常sign-in不能、profile row欠落
- URL/IP/portを推測しないと接続できない
- 独立実行体が完成repo、設計書、開発ログ、過去解答を参照した
- response、0行、boolean、DB状態の原因を区別できない

停止はD4全体の失敗確定ではない。原因、変更、再試行の開始条件を記録し、新しいrun IDでやり直す。同じ証拠を成功runとして再利用しない。

## 15. この候補が参照した入力

| 入力 | 参照箇所 | 読取時SHA-256 |
|---|---|---|
| `material/decisions/20261003-D4重い章の受入条件.md` | D4範囲、必須証拠、計時契約 | `8e02253c1867036cfea32975cedd5d049c7c85db02abca29aa8d6693a3e4aa01` |
| `material/decisions/D5_章の骨格.md` | 7役割、各3exec、中央値 | `9ab4089b712b2f7225959d71158c163df0e59dcb3e577f4726a3a63324722ddf` |
| `material/16_決定バックログ.md` | A5、B2/B10/B14/B111/B112/B119 | `725a449fecfd9bec0221ce2d836b4f28571c83ee4580aac134620c2b458b6eea` |
| `material/08_テスト計画書.md` | A/B、G6環境、公開キーと管理キーの境界 | `860420f63a28952991d6396784abde33b89db53fea34950c28a0587d2bd39770` |

最初の入力は作成時点で別作業ツリーにある未完了の正本参照であり、この候補によって正式化・移植・承認された扱いにはしない。統合時は参照先の存在とhashを再確認する。

## 追加測定による訂正

20261003080326の適用履歴は保持し、20261003081350の追加移行（SHA-256 5684db307ec7f1cf873032465fa9cbb9f7f14dd264effbbd509792a51c2795c4）で不要な親確認definerを削除しました。この時点の入力は2本のSQLでした。追加測定で見つかった通知のUPDATE可視性を20261003081937_d4_align_notification_update_visibility.sql（SHA-256 b493ec015eaf4f98a1ddb453ceb839caa232ee17b6043cfe3b7cc0cef5f75f7b）で修正し、現在の入力は3本です。

Auth Appの31a1deは継承元であり、D4 app/App.tsxはRlsTrial追加で異なります。`inherited-auth-source.json` は継承元、終了状態の参照実装はapp配下です。正式開始ソースと混同しません。

子行の追加拒否は、削除がコミット済みで並行書き込みがないケースに限定します。2セッション競合で削除済み親のリプライといいねの残存を観測しており、並行性の正式要件・対策は未確定です。既存Authアカウントの一括backfillやAuth個別削除は実施しません。

## 現在の前提測定と正式開始の差

上記は正式開始へ進むための条件候補です。条件の列挙は実装済みを意味しません。現在の限定実装は終了状態を使い、A/Bの投稿2件だけをproviderが準備します。

- `EXPO_PUBLIC_RLS_TRIAL_POST_IDS`に今回の互いに異なる投稿IDを2件渡し、一覧はこの集合に限定します。未指定・不正ならグローバルな一覧へ退避しません。並び順はcreated_at降順とid昇順です。
- `reset_owned.py`はmanifest所有の投稿2件だけを消します。子行や外部参照があれば停止し、§6の汎用的な子行清掃を実装した扱いにはしません。Auth・profileは保存します。
- seed/reset/reconcileのadvisory lockは各DBトランザクションの範囲です。実機操作全体を覆うleaseは未実装で、現在は制作側が操作を直列化しています。正式A5のbrokerと入力境界の負例を証明したことにはしません。
- 3 migration適用後の実SDK計測は69/69項目を通りました。通常利用者のSDK応答と管理側のDB状態を分けて照合しています。正式DB13やG6合格へは読み替えません。
- 制御実iPhoneの通常系は15/15項目を通りました。Metroのversion 2のreload送信に加え、端末からの新しいposts取得を観測し、Aの論理削除状態とBの表示が復元することを確認しました。独立した章頭実行、外部メール配送、正式D4/G6は測っていません。
- source manifestは公開ソースの整合用です。private fixture manifest、Auth資格情報、DB権限、端末の生画面は含めません。source manifestの存在だけでは§2の全条件を充足しません。

正式時計は開始していません。環境用意、終了状態のSDK・実機試走、レビューの時間を、専用PR着手からの正式D4所要時間へ遡って足しません。

現在の所有記録はpasswd homeの`~/.local/state/sns-d4-owned-runs`に保存します。旧/tmp記録はallowlistとread-only DB照合を通る明示移行だけを許可し、元bytesを残します。15ユニットテストと実DBの移行8/seed-reset12/照合5項目は限定tool証拠で、実WSL再起動やUI全期間leaseは証明していません。

通常系と2つの故障注入を合わせた制御実機v6は25/25項目を通りました。未転送とDB更新済み・応答保留を区別し、60秒の応答保留より前に結果不明・操作回復を観測しました。WDAを含む観測時間は各約22秒で、15秒を厳密な実測値としては表示しません。DB状態、手動再取得、後片付けも照合しています。全UI競合・全故障・正式G6の証明へは拡張しません。
