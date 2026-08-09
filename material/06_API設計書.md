# 06. API設計書

ステータス: **ドラフト（Phase 1）。凍結していない。**

改訂: 2026-08-09。スタブ（目次予定のみ）から本文へ書き下ろした。
同日、レビュー指摘15件を処置した（エラー分類の記号を 04 の E1〜E3 と衝突しない X1〜X6 へ変更し
§6.2 に対応表を新設、Realtime のパブリケーション追加を §4.1 に追加、`likes` の DELETE 購読の契約を
§4.2 で分離、§2.7 案2 を `security definer` へ訂正、§1.4 と U15〜U17 を新設）。
目次は 2026-07-26 の構成振り直し（Expo + Supabase）で置いた6項目をそのまま章立てにしている。

## 0. 着手条件と、本書がいまどの状態にあるか

### 0.1 着手条件（スタブから引き継ぐ）

`03_基本設計書.md`（画面一覧・ユースケース）と `05_DB設計書.md`（テーブル定義）の
両方が確定した時点で着手する。アプリが Supabase をどう叩くかは、DBスキーマと画面要求の
両方に依存するため、どちらか一方が未確定な状態で先に書くと手戻りが起きる。

### 0.2 着手条件は満たしていない。それでも書いた理由と、その代償

**03 も 05 も局長レビュー待ちのドラフトである。**よって本書は着手条件を満たしていない。
本書は両書のドラフトを入力として先に書き下ろした版であり、次の扱いにする。

- 03・05 が承認時に変わったら、**同じPRで本書も直す**。
- 本書の凍結は 03・05 の承認後。それまで本書を「確定した契約」として引用しない。
- 03・05 に無い事項を本書で新たに決めることはしない。決める必要が出た箇所は
  **§7 に未決定として期限つきで並べた**（`16_決定バックログ.md` A3「タイミングの無い先送りは禁止」）。
  16 への起票は本書では行わない（台帳の追記は別作業）。

**先に書いた理由**: `08_テスト計画書.md` の着手条件が「04 と 06 の確定」であり、
本書が空のままだと 08 が動けない。着手条件の連鎖は 03/05 → 06 → 08、03 → 04 → 08 の
2本立てで、06 は 08 側の唯一の入り口になっている。

### 0.3 本書は「教材の章を書くための設計図」である

本書は製品の設計書ではない。**各項目は、学習者にどのパートでどう書かせるかを併記する。**
章ID・章分割は未凍結（`16_決定バックログ.md` B1）なので、**パート単位までしか書けない**。
パートは `15_カリキュラム骨子案.md` §1 の A0 / A / B / C / D / E を使う。

- **パートB**: 認証・投稿・タイムライン・いいね・フォロー・プロフィール＋RLS＋
  メール確認・パスワード再発行
- **パートC**: 検索・ハッシュタグ・ブックマーク・カメラ
- **パートD**: Web 出力

RLS は **テーブルを作る章でそのテーブルのポリシーも一緒に書く**（05 §5 の決定）。
本書 §2 をテーブル単位で並べてあるのは、そのまま章の単位に写せるようにするためである。
RLS を扱う章は「アプリを改造して他人の行を触ろうとすると DB に拒否される」実演で終える
（`15_カリキュラム骨子案.md` パートB、`11_ターゲット・ペルソナ・UX定義.md` の体験マイルストーン）。
各テーブルの節に **「章末で確かめること」** を1行ずつ置いたのは、この実演の材料である。

### 0.4 本書で扱わないもの

次は前提ごと消滅している。復活させない。**出どころは1つの文書ではない**ので、項目ごとに書く。

- 自前 API のエンドポイント一覧 / `openapi.yaml` を正本に置く方式（`02_技術選定書.md` §6。
  同§が「OpenAPI 照合コンパレータ」も不要と書いている）
- Authorization ヘッダーとリフレッシュトークンのローテーション手順
  （02 §6「自前 JWT + リフレッシュトークンの実装が消滅」）
- 自前 WebSocket のイベント発行契約（`03_基本設計書.md` §1「旧構成から消えたもの」、
  `01_要件定義書.md` FR9「自前の WebSocket サーバーは作らない」。**02 §6 には無い**）

性能の目安値も本書には書かない（`01_要件定義書.md` §3 と 16 B23。**推測で数値を置かない**）。
同じ理由で、ポリシー式の最適化（`auth.uid()` を副問い合わせで包む等）も本書では採らない。
実測していないため、素の `auth.uid()` で書く。

---

## 1. データアクセス一覧

### 1.1 画面の番号の扱い（先に断っておく）

`03_基本設計書.md` §2 の画面一覧は連番 #1〜#15 に **#13-2 を挟んだ16行**である。
本書は 03 の番号をそのまま引くが、**参照の主は画面名**にし、番号は補助として括弧に入れる。

理由: 飛び番（13-2）を節番号や章分割表の行に持ち込むと、並べ替えのたびに番号が破綻する。
`decisions/D1_教材の置き場と章IDの規約.md` D1-3 が章IDで連番を禁じた理由
（「名前に順序を密輸入させない」）は、画面IDにもそのまま当たる。
**画面IDを振り直すか、番号を捨てて名前で参照するかは決まっていない**（§7 U1）。

### 1.2 一覧

**読み方**: 「操作」は SQL の種別（select / insert / update / delete）で書く。
「効くポリシー」は §2（Storage は §5.2）で定義するポリシー名。Auth と Storage は DB の
テーブルポリシーではないのでその旨を書く。「依存する未決定」が埋まっている行は、
**その未決定が片づくまで実装の章を書けない**。

**この表の行の粒度は仮である。**`04_詳細設計書.md` §1.1 の【未決・要起票】
「各画面のコンポーネント分割と状態の置き場」が埋まるまで、1行をどこまで細かく割るか
（画面ごとか、部品ごとか）が決まらない。04 は「06 §1 のデータアクセス一覧の粒度も
これに従属する」と明記しているので、**本表は粒度未確定のまま書いた側である**（§7.2 U15）。

| 画面（03 §2） | 何をするとき | 対象 | 操作 | 効くポリシー | 依存する未決定 |
|---|---|---|---|---|---|
| ログイン（#1） | メールとパスワードで入る | Supabase Auth | — | RLS 対象外 | — |
| 新規登録（#2） | アカウントを作る | Supabase Auth（＋トリガーが `users` に1行） | — | `users` は INSERT ポリシーを持たない。行はトリガーが作る（§3.1） | B14（メール送信の上限） |
| タイムライン（#3） | フォロー中の投稿を新着順に取る | `posts` / `users` / `post_media` / `likes` / `follows` | select | `posts_select`, `users_select`, `post_media_select`, `likes_select`, `follows_select` | B4（プッシュ型／プル型）、B27（削除済みの隠し方）、B25（表示ID未設定の見せ方） |
| タイムライン（#3） | 新着を即時に受け取る | `posts`（Realtime） | select 相当の配信 | `posts_select`（購読も RLS を通るかは §4.4 で要実測） | B22（取りこぼし）、§7 U6 |
| 投稿作成（#4） | 画像を上げる | Storage `post-media` バケット | insert | `post_media_objects_write_own`（§5.2） | B21（MIME・容量をサーバー側で止めるか） |
| 投稿作成（#4） | 投稿を作る | `posts` | insert | `posts_insert_own` | B19（既定値を誰が入れるか）、05 §4 課題3・課題4 |
| 投稿作成（#4） | 画像の行を作る | `post_media` | insert | `post_media_insert_own_post` | 05 §4 課題2（最大4枚をDB層でどう保証するか） |
| 投稿作成（#4） | 本文からタグを取り出して結ぶ | `hashtags` / `post_hashtags` | insert | `hashtags_insert_authenticated`, `post_hashtags_insert_own_post` | §7 U9（タグ本体の正規化）、§2.8 の取得経路 |
| 投稿作成（#4） | カメラで撮る（FR15） | 端末（`expo-camera`） | — | RLS 対象外 | — |
| 投稿詳細（#5） | 本文とリプライのスレッドを取る | `posts` / `users` / `post_media` / `likes` | select | 同上 | B27 |
| 投稿詳細（#5） | リプライする | `posts`（`reply_to_post_id` 付き） | insert | `posts_insert_own` | 05 §4 課題4 |
| 投稿詳細（#5） | リポスト・引用リポストする | `posts`（`repost_of_post_id` 付き） | insert | `posts_insert_own` | 05 §4 課題3・課題4 |
| 投稿詳細（#5） | いいねする／外す | `likes` | insert / delete | `likes_insert_own`, `likes_delete_own` | — |
| 投稿詳細（#5） | ブックマークする／外す | `bookmarks` | insert / delete | `bookmarks_insert_own`, `bookmarks_delete_own` | — |
| 投稿詳細（#5） | 自分の投稿を消す | `posts`（`deleted_at` を立てる update） | update | `posts_update_own`。**delete は誰にも許可しない** | B27 |
| プロフィール（#6） | 本人・他人のプロフィールと投稿を取る | `users` / `posts` / `follows` | select | `users_select`, `posts_select`, `follows_select` | B24・B25（表示IDの必須化と未設定時の見せ方） |
| プロフィール（#6） | フォローする／外す | `follows` | insert / delete | `follows_insert_own`, `follows_delete_own` | — |
| プロフィール編集（#7） | 表示名・bio を保存する | `users` | update | `users_update_own` | — |
| プロフィール編集（#7） | アバター・ヘッダーを上げる | Storage `avatars` バケット | insert / update | `avatars_objects_write_own` / `avatars_objects_update_own`（§5.2） | B21 |
| フォロー中一覧 / フォロワー一覧（#8） | 一覧を取る | `follows` / `users` | select | `follows_select`, `users_select` | B25、§7 U1（1画面か2画面か） |
| 通知（#9） | 自分宛の通知を取る | `notifications` / `users` / `posts` | select | `notifications_select_own` | B7・B28（通知の作成範囲） |
| 通知（#9） | 既読にする | `notifications.read_at` | update | `notifications_update_own` ＋ **列単位の権限**（§2.7） | §7 U4（列単位 GRANT か専用関数か） |
| 通知（#9） | 新着通知を即時に受け取る | `notifications`（Realtime） | 配信 | `notifications_select_own` | B22 |
| 検索（#10） | 投稿・ユーザーを探す | `posts` / `users` | select | `posts_select`, `users_select` | **05 §4 課題5（検索方式と索引）**。決まるまでこの行は書けない |
| ハッシュタグ一覧（#11） | タグの投稿を取る | `post_hashtags` / `hashtags` / `posts` | select | `post_hashtags_select`, `hashtags_select`, `posts_select` | §7 U9 |
| ブックマーク一覧（#12） | 保存した投稿を取る | `bookmarks` / `posts` | select | `bookmarks_select_own`, `posts_select` | B27 |
| メール確認待ち（#13） | 案内と再送 | Supabase Auth | — | RLS 対象外 | B14・B18（リダイレクト先の作り方） |
| メール確認待ち（#13） | **確認前の書き込みを止める** | Supabase Auth または `posts` ほかの全書き込み | — | **未確定。§1.4 を見よ** | **§7 U16（Auth の設定か RLS か）** |
| プロフィール初期設定（#13-2） | 表示IDと表示名を入れる | `users` | update | `users_update_own`。重複は **UNIQUE 制約違反がそのまま返る**（05 users 節） | B24・B25 |
| パスワード再発行の申請（#14） | 再設定メールを送る | Supabase Auth | — | RLS 対象外 | B14 |
| パスワード再設定（#15） | 新しいパスワードを入れる | Supabase Auth | — | RLS 対象外 | B18 |

### 1.3 この表から読み取れること（教材の組み立てに効く）

1. **RLS 対象外の画面が5つある**（#1 / #2 / #13 / #14 / #15）。これらは Supabase Auth の
   呼び出しだけで完結し、テーブルを触らない。**RLS の説明をこの5画面の章に置いても
   確かめる相手がいない。**RLS は `users` と `posts` を作る章から始まる。
2. **書き込みが集中するのは投稿作成（#4）**である。1回の投稿で `posts` / `post_media` /
   `hashtags` / `post_hashtags` と Storage に触る。ここを1章に収めるか分けるかは B1 の判断材料になる。
3. **検索（#10）の行だけ、書けるだけの材料がまだ無い**。05 §4 課題5（LIKE / pg_trgm / 全文検索）が
   決まっていないため、データアクセスの形が定まらない。検索はパートC なので、
   パートB の章を書き進めながら決めても順序は壊れない。

### 1.4 メール確認前の書き込みを何が止めるのか（03 UC3-4 の裏取りが要る）

`03_基本設計書.md` UC3 の手順4 は「確認が済むまでは、**RLS により**投稿の書き込みができない」と
断定している。**しかし本書 §2 のどのポリシーもメール確認の状態を見ていない。**
`posts_insert_own` は `to authenticated` と `author_id = auth.uid()` だけである。
つまり 03 の断定に対応する仕組みが、本書には無い。

本書 §0.2 は「03・05 に無い事項を本書で新たに決めない」と宣言しているが、
ここは逆で、**03 に書いてある事項が本書で落ちている側**の食い違いである。埋め方は2案ある。

| 案 | 何で止まるか | 本書への影響 |
|---|---|---|
| (a) Auth 側の設定で、確認が済むまでセッションを発行しない | そもそも `authenticated` にならないので、`to authenticated` の全ポリシーに当たらない | §2 は現状のままでよい。03 UC3-4 の「RLS により」という文言が誤りになる |
| (b) ポリシー側で確認状態を見る（`auth.jwt()` の確認日時が入っているかを条件に足す） | 書き込み系ポリシー全部に条件が1つ増える | §2.4 以下の insert / update ポリシーを全部書き直す |

**どちらであるかは Supabase の設定と発行される JWT を見ないと決まらない。実測が要る**（§7.2 U16）。
確定したら **03 UC3-4 の文言も直す**。U3（05 §5 の表の是正）と同じく、
**本書では直せない他文書側の修正項目**である。

---

## 2. RLS ポリシー定義（本書の中心）

### 2.1 前置き — 3つの言葉を取り違えない

**RLS は「どの行を触れるか」しか決めない。**これは 05 §5 の★節が既に書いていることで、
本書はその線の内側だけを SQL にする。

| 言葉 | 何を決めるか | 取り違えたときに起きること |
|---|---|---|
| `using` | **既にある行のうち、どれを操作の対象にできるか** | update / delete で書き忘れると、他人の行を対象にできる |
| `with check` | **書き込んだ結果の行が満たすべき条件** | insert / update で書き忘れると、他人の名義の行を作れる・自分の行を他人へ移せる |
| ロール（`to`） | そのポリシーが誰に効くか。`anon`＝未ログイン、`authenticated`＝ログイン済み | 未ログインに配ると、アプリを通さない素の呼び出しで読まれる |

- **select と delete は `using` だけ**を持つ。`with check` は書けない。
- **insert は `with check` だけ**を持つ。既にある行が無いので `using` は書けない。
- **update は両方要る。**片方だけだと、読める行と書ける行がずれる。

**RLS を有効にしたテーブルは、ポリシーが1本も無ければ全拒否になる。**
本書が「ポリシーを書かない」と書いている操作（`posts` の delete など）は、
**書かないこと自体が禁止の表現**である。消し忘れではない。

**キーの取り違えは RLS より上にある。** publishable key はアプリに入れてよく、
secret key / `service_role` は**絶対に入れない**（RLS を丸ごと迂回する。05 §5 の★節）。
教材ではキーを扱う最初の章で明示する。

### 2.2 全テーブルで RLS を有効にする

```sql
alter table public.users         enable row level security;
alter table public.posts         enable row level security;
alter table public.post_media    enable row level security;
alter table public.likes         enable row level security;
alter table public.follows       enable row level security;
alter table public.notifications enable row level security;
alter table public.hashtags      enable row level security;
alter table public.post_hashtags enable row level security;
alter table public.bookmarks     enable row level security;
```

**これが無いと何が漏れるか**: 有効にし忘れた1テーブルだけが全公開になる。
9テーブルのうち1本落としても他は守られるので、画面を見ている限り気づけない。

**教材での置き方**: この9行を1箇所にまとめて書かせない。**テーブルを作る章で、
そのテーブルの `alter` とポリシーを一緒に書かせる**（05 §5）。まとめて書く形にすると、
後から足したテーブルで必ず抜ける。

**Realtime を使うテーブルには、これとは別の `alter` がもう1本要る**（§4.1）。
`enable row level security` を書いただけでは行の変化は配信されない。同じ「テーブルを作る章で
書かせる」置き方に揃える。

### 2.3 `users`（パートB）

```sql
-- 読む: 全ログイン利用者に公開
create policy "users_select"
  on public.users for select
  to authenticated
  using (true);

-- 書く: 自分の行だけ
create policy "users_update_own"
  on public.users for update
  to authenticated
  using      (id = auth.uid())
  with check (id = auth.uid());
```

- **insert のポリシーは書かない。** 行は `auth.users` のトリガーが作る（§3.1）。
  アプリから直接 insert できると、他人の id で先回りしてプロフィール行を作られる。
- **delete のポリシーは書かない。** アカウント削除は機能要件に無い（`01_要件定義書.md` §2）。

| ポリシー | これが無いと何が漏れるか |
|---|---|
| `users_select` | 誰のプロフィールも読めなくなる（漏れではなく機能が死ぬ）。RLS 有効＋ポリシー0本＝全拒否だから |
| `users_update_own` の `using` | 他人のプロフィールを書き換えられる。表示名もアイコンも乗っ取られる |
| `users_update_own` の `with check` | 自分の行の `id` を他人の id へ書き換えて、行ごと横取りできる |
| insert を書かないこと | 他人の id のプロフィール行を先に作って占拠できる |

**章末で確かめること**: 他人の `display_name` を書き換える呼び出しを1回投げ、DB に拒否される
（更新0行になる）ところを見る。**この「0行」は既定の呼び出し方では画面にもコンソールにも
現れない。§6.3 の「影響行数を得る既定形」で投げる必要がある。**
**「エラーが出ない」ことの意味は §6.3 で扱う。**

### 2.4 `posts`（パートB）

```sql
-- 読む: 削除されていない投稿は全ログイン利用者に公開
create policy "posts_select"
  on public.posts for select
  to authenticated
  using (deleted_at is null);            -- ← この 1 行は B27 が決まるまで仮

-- 作る: 自分の名義でだけ
create policy "posts_insert_own"
  on public.posts for insert
  to authenticated
  with check (author_id = auth.uid());

-- 直す・論理削除する: 自分の投稿だけ
create policy "posts_update_own"
  on public.posts for update
  to authenticated
  using      (author_id = auth.uid())
  with check (author_id = auth.uid());

-- delete のポリシーは書かない（＝誰にも許可しない）
```

| ポリシー | これが無いと何が漏れるか |
|---|---|
| `posts_select` の `deleted_at is null` | 論理削除した投稿が他人から読める。**画面側の絞り込みだけに任せると、改造したクライアントに素通しされる**（B27 の論点そのもの） |
| `posts_insert_own` の `with check` | 他人になりすまして投稿できる。`author_id` に他人の id を入れるだけで済む |
| `posts_update_own` の `using` | 他人の投稿を書き換えられる。`deleted_at` を立てれば他人の投稿を消せる |
| `posts_update_own` の `with check` | 自分の投稿の `author_id` を他人へ付け替えて、他人の名義の投稿を作れる |
| delete を書かないこと | 改造したアプリから**物理削除**できる。リプライ元が消えてスレッド構造が壊れる（05 §3 の論理削除の理由が破れる） |

**⚠️ このポリシーは「行の持ち主」しか見ておらず、「どの列を触ってよいか」を制限していない（U19。2026-08-09 追記）。**
`author_id` さえ自分のままなら、**改造したクライアントは `created_at`・`body`・`reply_to_post_id`・
`repost_of_post_id` を後から書き換えられる。**FR3 は投稿の作成と削除しか定めておらず、
**投稿の編集は機能要件に無い**のに、この契約は編集を許してしまう。
`created_at` を書き換えられるとタイムラインの並びを後から動かせるし、
`reply_to_post_id` を書き換えられると既存のスレッド構造を作り替えられる。
下の「削除は update で行う契約」という説明と、実際に許している範囲が食い違っている。
**塞ぎ方は U4（`notifications` の列制限）と同じ2案** — 列単位の `GRANT UPDATE(deleted_at)` か、
論理削除だけを行う `security definer` 関数を1本置くか。**本書では決めない**（05 の列定義に触るため）。

**削除は update で行う契約**にする。画面が「削除」と呼ぶ操作の実体は
`update posts set deleted_at = now() where id = ...` である。
**この契約は §6.3（0行更新は静かに失敗する）と対で教える。**

**未決定に触れている箇所**: `using (deleted_at is null)` を採るかは B27。
採らない案（画面側の絞り込みに任せる）を選ぶと、上の表の1行目がそのまま実害になる。
本書は仮に「DB 側で隠す」で書いているが、**決めたのは B27 であって本書ではない**。

**章末で確かめること**: 他人の投稿に `deleted_at` を立てる update を投げて拒否されること。
続けて `delete from posts` を投げて、**自分の投稿でも拒否される**ことを見る。
後者が 05 §5 の「RLS を書いたうえでなお通ってしまう操作」を塞いだ側の実演になる。

### 2.5 `post_media`（パートB）

```sql
create policy "post_media_select"
  on public.post_media for select
  to authenticated
  using (true);

create policy "post_media_insert_own_post"
  on public.post_media for insert
  to authenticated
  with check (
    exists (
      select 1 from public.posts p
      where p.id = post_media.post_id
        and p.author_id = auth.uid()
    )
  );

create policy "post_media_update_own_post"
  on public.post_media for update
  to authenticated
  using      (exists (select 1 from public.posts p
                      where p.id = post_media.post_id and p.author_id = auth.uid()))
  with check (exists (select 1 from public.posts p
                      where p.id = post_media.post_id and p.author_id = auth.uid()));

create policy "post_media_delete_own_post"
  on public.post_media for delete
  to authenticated
  using (exists (select 1 from public.posts p
                 where p.id = post_media.post_id and p.author_id = auth.uid()));
```

| ポリシー | これが無いと何が漏れるか |
|---|---|
| `post_media_insert_own_post` | **他人の投稿に画像を差し込める。**投稿本文は他人のもののまま、画像だけ入れ替わる |
| `post_media_update_own_post` の `with check` | 自分の画像行の `post_id` を他人の投稿へ付け替えられる（上と同じ結果を update で作れる） |
| `post_media_delete_own_post` | 他人の投稿から画像を消せる |

**要実測が2つある。ここは仕様として確定していない。**

1. **親テーブルを参照するポリシー式が、`posts` 側の RLS を通るかどうか。**
   通る場合、**論理削除した自分の投稿の画像行を自分で触れなくなる**
   （`posts_select` が `deleted_at is null` で弾くため、`exists` が偽になる）。
   通らない場合は逆に、他人の削除済み投稿の存在を突けることになる。
   どちらであるかを確かめてから、`security definer` の補助関数に逃がすかを決める（§7 U2）。
2. **`order` は SQL の予約語である。**識別子として使うには引用が要る。
   05 に注記が無く、教材のコード片をそのまま写経させると落ちる（§7 U8）。

**論理削除の隠蔽が親にしか掛かっていない。**`posts_select` は `deleted_at is null` で弾くが、
`post_media_select` は `using (true)` なので、**`post_id` を指定すれば削除済み投稿の画像行が返る**。
05 の Storage 節は `post_media.url` を「その公開 URL」と定義しているので、
**URL が読めた時点で画像そのものが取れる**。同じ穴が `likes_select`（§2.6）と
`post_hashtags_select`（§2.8）にもある。B27 で「DB 側で隠す」を選んでも、
この3本を直さなければ削除済み投稿のいいね・タグ・画像は読めたままである。

塞ぎ方は2案ある。**どちらを採るかは決まっていない。**

| 案 | 書き方 | 代償 |
|---|---|---|
| (a) 子テーブルの select にも親の条件を広げる | `using (exists (select 1 from public.posts p where p.id = post_media.post_id and p.deleted_at is null))` | 一覧のたびに親を引く条件が増える。§7 U2（`exists` が親の RLS を通るか）の結論に結果が左右される |
| (b) 隠蔽は `posts` に限る | 現状のまま | 削除済み投稿の子行は読める。B27 が「DB 側で隠す」を選んだ意味が半分になる |

**B27 の現在の文面は `posts` の SELECT ポリシーだけを指している。**
「子テーブルまで同じ条件を広げるか」は B27 の論点に入っていないので、
**B27 の論点として 16 へ追記が要る**（期限は B27 と同時）。
(a) を採る場合の成立可否は U2 と同じ実測で分かるので、**両者は1回の実測でまとめて片づく**。

**05 §4 課題2（最大4枚をDB層でどう保証するか）は、この節で必ずぶつかる。**
枚数のような**行をまたぐ条件**は、`with check` に副問い合わせを書けば構文としては通る
（`(select count(*) from public.post_media m where m.post_id = post_media.post_id) < 4` は書ける）。
**書けるが、上限としては成立しない。**理由は3つある。

1. **同一の INSERT 文で複数行を入れると、各行の副問い合わせが自分より前の行を数えられない。**
   4枚を1文で入れれば4行とも「0枚」を見て通る。
2. **同時に走る別トランザクションの行が見えない。**2枚ずつ2回同時に投げれば越えられる。
3. **数える対象が `post_media_select` の RLS を通る。**見えない行は数に入らない。

CHECK 制約・トリガー・アプリ層検証のどれを採るかが決まるまで、この節は4枚制限を持たない。
**教材としてはここが「行をまたぐ制約は RLS の担当ではない」を教える良い材料になる。**
実際に4枚を1文で入れて上限を越えるところまで見せる案を、下の「章末で確かめること」に足してある。

**章末で確かめること**: 他人の投稿の `post_id` を指定して画像行を作ろうとして拒否されること。
続けて、上の副問い合わせ版 `with check` を書いた状態で **4枚を1文で入れて通ってしまう**ところを見る
（05 §4 課題2 が決まってから書く。決まる前は前半だけ）。

### 2.6 `likes` / `follows` / `bookmarks`（likes・follows はパートB、bookmarks はパートC）

3テーブルとも「複合主キー・自分の行だけ・付けたり外したりする」という同じ形をしている。
**教材では likes で型を教え、follows と bookmarks は同じ型の反復として書かせる**のが素直である。
どこまでを反復として扱うかは B1 の判断。

```sql
-- likes
create policy "likes_select"      on public.likes for select to authenticated using (true);
create policy "likes_insert_own"  on public.likes for insert to authenticated with check (user_id = auth.uid());
create policy "likes_delete_own"  on public.likes for delete to authenticated using      (user_id = auth.uid());

-- follows
create policy "follows_select"      on public.follows for select to authenticated using (true);
create policy "follows_insert_own"  on public.follows for insert to authenticated with check (follower_id = auth.uid());
create policy "follows_delete_own"  on public.follows for delete to authenticated using      (follower_id = auth.uid());

-- bookmarks（本人のみ。読み取りも公開しない）
create policy "bookmarks_select_own" on public.bookmarks for select to authenticated using      (user_id = auth.uid());
create policy "bookmarks_insert_own" on public.bookmarks for insert to authenticated with check (user_id = auth.uid());
create policy "bookmarks_delete_own" on public.bookmarks for delete to authenticated using      (user_id = auth.uid());
```

**⚠️ この insert 系は「誰として書くか」しか見ておらず、「相手の投稿が生きているか」を見ていない（U20。2026-08-09 追記）。**
論理削除される前に投稿の id を知っていた利用者は、**削除された後でも いいね と ブックマーク を作れる。**
外部キーは親の行が存在することしか確かめず、`deleted_at is null` は要求しないためである。
いいねを作れば §3.2 のトリガーが動き、**受け取った人が開けない投稿を指す通知が届く。**
**B27 を「DB 側で隠す」に決めても、この書き込み経路は閉じない** — B27（および 08 §5.6 に足した検証）は
子テーブルの **select** に親の条件を広げる話であって、**insert には触れていない**。
塞ぐなら `with check` に `exists (select 1 from public.posts p where p.id = post_id and p.deleted_at is null)` を足す。
**ただしこれは U2（親を参照する `exists` が `posts` の RLS を通るか）が未実測なので、
実測してからでないと書けない。**`follows` にはこの論点が無い（親が投稿ではないため）。

**update のポリシーは3テーブルとも書かない。**更新すべき列が無いからである
（列は主キー2列と `created_at` だけ）。付け外しは insert と delete で表す。

| ポリシー | これが無いと何が漏れるか |
|---|---|
| `likes_select` を公開にすること | いいね数が表示できない（05 §5 が公開にした理由がこれ） |
| `likes_insert_own` | **他人の名義でいいねできる。**しかも §3.2 のトリガーが動くので、他人の名義の通知まで飛ぶ |
| `likes_delete_own` | 他人のいいねを外せる |
| `follows_insert_own` | **他人を勝手に自分のフォロワーにできる。**タイムラインの中身を他人に押し込める |
| `follows_delete_own` | 他人のフォロー関係を切れる |
| `bookmarks_select_own` を本人限定にすること | **他人が何を保存したかが読める。**ブックマークは公開の機能ではない（05 §5） |

**`follows` の select を公開にした代償を1つ書いておく**: フォロー一覧・フォロワー一覧の
表示に要るので公開にしたが、これは「誰が誰をフォローしているか」が全員に読めることを意味する。
**05 §5 が「読み取りは原則全公開」と決めた範囲の中なので本書では変えない。**

**`follows_insert_own` は自分自身へのフォローを止めていない。**見ているのは
`follower_id = auth.uid()` だけなので、`follower_id = followee_id` の行が作れる。
05 の follows は主キー2列だけで CHECK 制約を持たないため、DB 側にも止める仕組みが無い。
この行ができると **§3.2 のフォロー通知トリガーが `recipient_id = actor_id` の通知を自分宛に作る**。
塞ぎ方は2案ある。**どちらを採るかは決まっていない**（§7.2 U17）。

- (a) ポリシー側: `with check (follower_id = auth.uid() and follower_id <> followee_id)`
- (b) DB の CHECK 制約側: `check (follower_id <> followee_id)` を 05 の follows に足す（**05 の修正**）

§7 U11（自己操作の通知を作るか）は「通知を作るか」だけを論点にしていて、
**自己フォローそのものを許すかは含まれていない。**同じ節で決める。
(a) を採るなら、**RLS の式に「自分かどうか」以外の条件も書けることを見せる小さな題材**になる。

**`likes_select` は `posts` の論理削除を見ていない**（§2.5 の同じ穴）。
削除済み投稿のいいねが読める。B27 の論点に含める。

**章末で確かめること**: `user_id`（`follower_id`）に他人の id を入れて insert し、拒否されること。
`bookmarks` は他人の行を select して**0件が返る**ことを見る（select の 0 件は返ってきた配列が
空であることで見える。update / delete の「0行」は既定の呼び出しでは見えない。§6.3）。

### 2.7 `notifications`（パートB）★ RLS だけでは足りないテーブル

```sql
-- 読む: 本人宛だけ
create policy "notifications_select_own"
  on public.notifications for select
  to authenticated
  using (recipient_id = auth.uid());

-- 既読にする: 行は本人のものだけ
create policy "notifications_update_own"
  on public.notifications for update
  to authenticated
  using      (recipient_id = auth.uid())
  with check (recipient_id = auth.uid());

-- insert のポリシーは書かない（行は §3.2 のトリガーが作る）
-- delete のポリシーは書かない（§7 U5 で扱う）
```

**上のポリシーだけでは「既読フラグだけ更新できる」にならない。**
行さえ自分のものなら `actor_id` も `type` も `created_at` も書き換えられる。
05 §5 の★節が名指しした「RLS では列を絞れない」がこれである。
**05 §5 の表は「UPDATE は既読フラグのみ本人可」と書いているが、その表現のまま SQL にはできない。**
表側を「**行は本人のみ。列の制限は別手段**」に直す必要がある（§7 U3）。

塞ぎ方は2案ある。**どちらを採るかは決まっていない**（§7 U4）。

**案1: 列単位の権限**

```sql
revoke update on public.notifications from authenticated;
grant  update (read_at) on public.notifications to authenticated;
```

**案2: 既読化の関数を1本だけ公開する**

```sql
create function public.mark_notification_read(p_notification_id uuid)
returns void
language sql
security definer                       -- ← invoker では動かない。理由は下記
set search_path = ''
as $$
  update public.notifications
     set read_at = now()
   where id = p_notification_id
     and recipient_id = auth.uid();
$$;
```

**この関数を `security invoker` で書くと必ず落ちる。**`security invoker` の関数の本体は
**呼び出した人の権限で走る**ので、下に書くとおり `revoke update` を掛けた `authenticated` が
呼ぶと、本体の `update public.notifications` が権限エラー（42501 `permission denied for table
notifications`）になる。**塞ぐための `revoke` が、塞いだ先の関数まで一緒に殺す。**
よって案2は `security definer`（所有者は `postgres` 等）で書く。`set search_path = ''` は
§3.1 と同じ理由で維持する。

**`security definer` にすると、この関数は RLS も列単位の権限も越える。**
だから **`where id = ... and recipient_id = auth.uid()` が本人確認の全部**になる。
この `and` を1つ落とすと、id さえ分かれば他人の通知を既読にできる。
教材ではここを「権限を越える関数を作るときは、関数の中の条件が守りの全部になる」として扱う。

**案2を採る場合も `revoke update` は要る。**関数を用意しただけでは、
クライアントが直接 update を投げる道が残るからである。
**「関数を1本用意すれば済む」と書くと嘘になる。**
加えて、`security definer` の関数は **`execute` を誰に配るか**（`authenticated` だけか）も
併せて決める必要がある。**この実装形（invoker / definer、`execute` の配り先）は
§7 U4 に含めて決める。**

| ポリシー・手当て | これが無いと何が漏れるか |
|---|---|
| `notifications_select_own` | **他人宛の通知が全部読める。**誰が誰にいいねしたかが総なめできる |
| `notifications_update_own` の `using` | 他人の通知を既読にできる |
| insert を書かないこと | 偽の通知を他人へ送れる。通知は「誰かが自分に何かした」の証拠なので、作れると偽装になる |
| `revoke update` ＋ 列単位 GRANT（または関数＋revoke） | **通知の中身を書き換えられる。**`actor_id` を差し替えれば、いいねしていない人がいいねしたことにできる |

**教材での位置づけ**: 05 §5 が「RLS を書けば安心という誤解を正す題材」と決めた場所がここである。
RLS を扱う章の最後に、**ポリシーを正しく書いた状態で `actor_id` を書き換える呼び出しを1回通し**、
そのうえで列単位の権限で塞ぐところまでを見せる。順序を逆にすると、何を塞いだのかが見えない。

### 2.8 `hashtags` / `post_hashtags`（パートC）

```sql
create policy "hashtags_select"
  on public.hashtags for select to authenticated using (true);

create policy "hashtags_insert_authenticated"
  on public.hashtags for insert to authenticated with check (true);
-- update / delete のポリシーは書かない

create policy "post_hashtags_select"
  on public.post_hashtags for select to authenticated using (true);

create policy "post_hashtags_insert_own_post"
  on public.post_hashtags for insert
  to authenticated
  with check (
    exists (select 1 from public.posts p
            where p.id = post_hashtags.post_id and p.author_id = auth.uid())
  );

create policy "post_hashtags_delete_own_post"
  on public.post_hashtags for delete
  to authenticated
  using (
    exists (select 1 from public.posts p
            where p.id = post_hashtags.post_id and p.author_id = auth.uid())
  );
```

| ポリシー | これが無いと何が漏れるか |
|---|---|
| `hashtags_insert_authenticated` | タグを新規に作れず、**初めて使われるタグを含む投稿が作れなくなる**（機能が死ぬ） |
| `hashtags` の update を書かないこと | **既存タグの文字列を書き換えられる。**`#expo` を別の語に変えると、その語に紐づく全投稿の意味が変わる |
| `hashtags` の delete を書かないこと | タグ行を消すと `post_hashtags` の参照先が失われる |
| `post_hashtags_insert_own_post` | **他人の投稿に勝手なタグを付けられる。**検索結果を汚せる |

**`post_hashtags` の update ポリシーは書かない。**中間テーブルは主キー2列だけなので、
付け替えは delete と insert で表す。

**「既に在るタグは使い回す」経路を先に決めておく。**`hashtags.tag` は UNIQUE（05）なので、
2回目以降の投稿で同じタグを素直に insert すると**一意制約違反で落ちる**。
`upsert()` を既定のまま使うと `on conflict do update` が飛び、**`hashtags` の update は
ポリシーを書かない設計なので通らない。**この2つを組み合わせると、
学習者はタグの章で「タグを1回使うと2回目から投稿が落ちる」に確実にぶつかる。

そこで取得経路を2段構えで契約にする。

1. **行を確保する**: `insert into public.hashtags (tag) values (...) on conflict (tag) do nothing`
   （supabase-js なら `upsert(..., { onConflict: 'tag', ignoreDuplicates: true })`）。
   `do nothing` なので UPDATE の権限もポリシーも要らない。
2. **id を引く**: `hashtags_select` が全ログイン利用者に公開なので、直後に
   `select id from public.hashtags where tag = ...` で引ける。
   1 が既存行に当たって何も返さない場合があるため、**id は必ず 2 で取る**。

**この2段構えは §7 U9（正規化を誰がやるか）と同じ節で扱う。**
1 の `on conflict (tag)` が効くかどうかは、書き込む前に `tag` を正規化したかで決まる。
正規化しないと `Expo` と `expo` が別行になり、UNIQUE は素通りしたまま検索結果だけが割れる。

**§2.5 と同じ2点がここにも当たる**: 親を参照する `exists` が `posts` の RLS を通るか（§7 U2）。
**`post_hashtags_select` も `posts` の論理削除を見ていない**（§2.5 の同じ穴）。
削除済み投稿のタグの結びつきが読める。B27 の論点に含める。

**章末で確かめること**: 他人の投稿の `post_id` でタグを結ぼうとして拒否されること。
続けて、**同じタグを含む投稿を2回作って2回目も通る**ことを見る（上の `do nothing` が効いている側の確認）。

### 2.9 ポリシー一覧（この節のまとめ）

| テーブル | select | insert | update | delete |
|---|---|---|---|---|
| `users` | 全ログイン利用者 | **なし**（トリガーが作る） | 自分の行 | **なし** |
| `posts` | 全ログイン利用者（`deleted_at is null`。B27） | 自分の名義 | 自分の投稿 | **なし**（論理削除で表す） |
| `post_media` | 全ログイン利用者 | 親の author が自分 | 親の author が自分 | 親の author が自分 |
| `likes` | 全ログイン利用者 | 自分 | **なし**（更新する列が無い） | 自分 |
| `follows` | 全ログイン利用者 | 自分 | **なし**（同上） | 自分 |
| `notifications` | 本人宛のみ | **なし**（トリガーが作る） | 本人の行＋**列単位の手当て** | **なし**（§7 U5） |
| `hashtags` | 全ログイン利用者 | ログイン済みなら可 | **なし** | **なし** |
| `post_hashtags` | 全ログイン利用者 | 親の author が自分 | **なし** | 親の author が自分 |
| `bookmarks` | 本人のみ | 自分 | **なし**（更新する列が無い） | 自分 |

**子テーブル（`post_media` / `likes` / `post_hashtags`）の select には `deleted_at` の条件が無い。**
親の `posts` だけが論理削除を隠している状態なので、削除済み投稿の画像・いいね・タグは読める。
広げるかどうかは B27 の論点に含める（§2.5）。

**「全ログイン利用者」を `anon`（未ログイン）まで広げるかは決まっていない**（§7 U7）。
05 §5 は「全員」と書くだけで、未ログインを含むかを書いていない。
本書は全ポリシーを `to authenticated` で書いてある。パートD（Web 出力）で
未ログイン閲覧を見せるなら、この判断が変わる。

---

## 3. DB トリガー関数の仕様

### 3.1 `auth.users` → `public.users` の行作成（パートB・認証の章）

**役割**: `auth.users` に行ができた時点で、`public.users` に対応する行を作る。
アプリ側の書き忘れで「認証はできるがプロフィールが無い」状態を作らないため（05 users 節）。

| 項目 | 仕様 |
|---|---|
| 起動 | `auth.users` への insert 後（行ごと） |
| 入れる値 | **`id` と日時だけ。**`username` と `display_name` には触らない |
| 関数の属性 | `security definer`（RLS を越えて挿入するため）＋ `set search_path = ''`（同名の別オブジェクトへのすり替えを防ぐため） |
| 失敗したときの影響 | **登録処理そのものが取り消される。**利用者には原因の読めないエラーが出る（05 users 節・16 B20） |
| 使ってはいけない入力 | `raw_user_meta_data`（利用者が後から書き換えられるため、権限や一意性の判断に使わない。16 B20） |

```sql
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.users (id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
```

**この関数が `insert into public.users (id)` だけで済むのは、`created_at` と `updated_at` に
既定値があるからである。B19（既定値を誰が入れるか）で「クライアントが全部入れる」を選ぶと、
この関数はクライアントではないので破綻する。**B19 の選択肢は「DB に持たせる」「クライアントが
入れる」の2つだが、**トリガーが入れる行はクライアントを経由しない**。
よって B19 は「クライアント」一択にはできない。§7 U10 に書いた。

**教材での置き方**: 認証の章。`username` を NOT NULL にしたまま進めると新規登録そのものが
落ちる（16 B20）ので、**この失敗を体験させるかどうか**が章の設計判断になる。
本物の詰まりとして開発ログに記録されれば `12` の要素4（エラー体験）に使える
（`decisions/D5_章の骨格.md`）。記録が無いのに創作してはいけない。

### 3.2 通知行の作成（パートB・通知の章）

**役割**: いいね・リプライ・リポスト・フォローが起きたときに `notifications` へ行を作る。
アプリ側に置かないのは、書き忘れを防ぐ置き場所が DB しかないため（03 UC2）。

**実装範囲は B28 で未決である。**本書は骨格だけを書き、確定した仕様として書かない。

| 契機 | 起動 | `type` | `recipient_id` | `actor_id` | `post_id` |
|---|---|---|---|---|---|
| いいね | `likes` への insert 後 | `like` | いいねされた投稿の `author_id` | `likes.user_id` | `likes.post_id` |
| リプライ | `posts` への insert 後（`reply_to_post_id` が非 NULL） | `reply` | 返信元投稿の `author_id` | `posts.author_id` | 作られた投稿の `id` |
| リポスト | `posts` への insert 後（`repost_of_post_id` が非 NULL） | `repost` | リポスト元投稿の `author_id` | `posts.author_id` | 作られた投稿の `id` |
| フォロー | `follows` への insert 後 | `follow` | `followee_id` | `follower_id` | NULL |

**全トリガーに共通の属性**: `security definer` ＋ `set search_path = ''`。
理由は §3.1 と同じで、`notifications` は insert のポリシーを持たない（§2.7）ため、
RLS を越えて挿入する必要がある。**この2つの属性を落とすと通知が1件も作られない。**

**決まっていないことが5つある。この5つが埋まるまで、通知の章は書けない。**

1. **どこまでをトリガーで作るか**（B28）。4契機のうち一部をアプリ側に残すか。
2. **UC1 の「新規投稿のフォロワー通知」を `type` に含めるか**（B7・05 §4 課題1）。
   含めるなら、フォロワー数だけ行が増える形になり、上の表に5行目が要る。
3. **自分に対する操作で通知を作るか**（自分の投稿への自分のいいね、自分の投稿への自分のリプライ）。
   `recipient_id = actor_id` の行を作るかどうか。**どの文書にも記述が無い**（§7 U11）。
4. **取り消したときに通知行をどうするか**（いいねを外す・フォローを外す）。
   残すか消すかが決まっていない。消すなら delete のトリガーも要る（§7 U11）。
5. **`type` の enum と FR9 の通知種別が1対1で対応しているかの照合**（05 §4 課題6）。

**章末で確かめること**: 別アカウントから自分の投稿にいいねし、`notifications` に行が増えるのを見る。
**この確認には2アカウントが要る**ので、B10（デモ／シードデータ方針）と B14（メール送信の上限）に
直接ぶつかる。

---

## 4. Realtime の購読契約

### 4.1 契約の形

購読は次の6項目を1組で決める。**1つでも欠けると、画面が黙って古いままになる。**

| 項目 | 意味 |
|---|---|
| **配信を有効にする** | **そのテーブルを `supabase_realtime` パブリケーションへ入れる。DB 側の準備** |
| 購読するもの | テーブルと、insert / update / delete のどれを受けるか |
| フィルタ | DB 側で絞る条件 |
| 画面への反映 | 受け取った行を画面のどこにどう足すか |
| 購読を始める時点 | 初回取得との前後関係を含めて書く |
| 購読を解除する時点 | 画面の離脱・アプリが背面へ回る・ログアウト |

**1項目目を落とすと、§4.2 の行がすべて1件も発火しない。**

```sql
alter publication supabase_realtime add table public.posts;
alter publication supabase_realtime add table public.notifications;
alter publication supabase_realtime add table public.likes;
```

**これが無いと何が起きるか**: 購読のコードは正しく書けていて、エラーも出ず、
`subscribe()` も成功する。**ただ何も届かない。**原因はクライアント側のコードに一切現れないので、
初学者はここで確実に止まる。しかもコードを見直しても直らない種類の詰まりである。

**教材での置き方**: §2.2 の `enable row level security` と同じく、**1箇所にまとめて書かせない。**
そのテーブルを作る章で、`alter table ... enable row level security` とポリシーと
この1行を並べて書かせる（§0.3 の方針）。後から Realtime を足す形にすると、必ず抜ける。
`likes` は投稿詳細（#5）のいいね数のために要る。`follows` / `bookmarks` などは購読しないので入れない。

### 4.2 購読の一覧（`03_基本設計書.md` UC1・UC2 由来）

**§4.1 は6項目を1組と定めているので、表も6項目ぶんの列を持つ**
（2026-08-09 に「始める時点・前面へ戻ったとき」の列を足した。
それまで4列しか無く、**§4.1 が必須と書いた「購読を始める時点」を表のどの行も書いていなかった**）。

| 画面 | 購読するもの | フィルタ | 画面への反映 | **始める時点・前面へ戻ったとき** | 解除の時点 |
|---|---|---|---|---|---|
| タイムライン（#3） | `posts` の insert | **フォロー中の集合で絞れるかは未確定**（§7 U6） | 先頭に足す。既に並んでいる id は足さない | **未確定（B22）。**初回取得との前後関係と、背面から戻ったときに購読を張り直すかつ張り直すなら取りこぼしをどう埋めるかを、B22 と同じ席で決める | 画面を離れるとき／アプリが背面へ回るとき |
| 通知（#9） | `notifications` の insert | `recipient_id` が自分 | 一覧の先頭に足し、未読の数を増やす | 同上 | 同上 |
| 投稿詳細（#5） | `likes` の insert | `post_id` がこの投稿 | いいね数を増やす | 同上 | 画面を離れるとき |
| 投稿詳細（#5） | `likes` の **delete** | **フィルタを書けない**（下記） | 届いた行の `post_id` を**アプリ側で判定**してから、いいね数を減らす | 同上 | 同上 |
| 投稿詳細（#5） | `posts` の insert（リプライ） | `reply_to_post_id` がこの投稿 | スレッドの末尾に足す | 同上 | 同上 |

**「始める時点」を空欄のままにしない理由**は2つある。
初回取得より先に購読を張ると、取得の結果で一覧を上書きした瞬間に、
購読で受け取った新着が消える（**取りこぼしではなく上書きで消える**ので、再接続では戻らない）。
逆に後に張ると、取得から購読開始までの間に来た行が落ちる。
どちらを採るかで画面のコードの並びが変わるので、**章の手順の順序が変わる。**
また §4.1 の解除の項目が「アプリが背面へ回る」を含む以上、
**前面へ戻ったときに張り直す処理が対になって要る**が、それを書いた行がどこにも無かった。

**`likes` の delete だけ形が違う理由**を、行を分けたうえで書いておく。

- **Realtime は DELETE イベントにフィルタを適用しない**（公式ドキュメントの Limitations に
  「Delete events are not filterable」と明記されている）。`post_id` の絞り込みは insert にしか効かない。
- **DELETE には RLS も適用されない**。削除された行にその人が到達できたかを Postgres が
  検証できないためである。つまり**購読している端末には、`likes` の削除が全部届く**。
- **届く中身は既定では主キー列だけ**（replica identity が既定のため）。
  `likes` の主キーは `(user_id, post_id)` なので、**`post_id` は取れる**。
  だからアプリ側で「いま見ている投稿の `post_id` か」を判定できる。判定を書かないと、
  他人の投稿のいいね解除でこの画面のいいね数が減る。

**`posts` と `notifications` を delete で購読していない現行設計は、この事実と整合している。**
どちらも delete を購読していないので、フィルタの効かない配信を受け取る経路が無い。
`posts` の削除は論理削除（`deleted_at` を立てる update）なので、そもそも DELETE イベントにならない。

### 4.3 取りこぼしを前提に書く（B22）

**Realtime は全変更の配信を保証しない。**03 UC1 の「フォロワーがタイムラインを開いていれば
即時反映」を、取りこぼしが無い前提として読んではいけない。契約に次の3つを含めるかが B22 の論点である。

1. **購読開始前の初回取得**。購読を始めるより先に一覧を取ると、その間の変更が落ちる。
   逆順にすると、購読が先で一覧が後になり、重複が出る。
2. **再接続後の再取得**。切れている間の変更は届かない。
3. **重複排除**。1と2をやると同じ行が二度届く。id で弾く。

**この3つは「入れるか」ではなく「どう書くか」の問題に見えるが、教材では分量に直結する。**
3つとも入れると、通知の章とタイムラインの章の両方が重くなる。B22 が決まるまで確定しない。

### 4.4 要実測（仕様として書けない2点）

1. **insert / update の購読が RLS を通るか。**通るなら、`notifications` は
   `recipient_id = auth.uid()` の行しか配信されないので、フィルタは二重の守りになる。
   通らないなら、**フィルタが唯一の守りになり、フィルタを書き忘れた時点で他人宛の通知が
   端末へ届く。**どちらであるかで危険度が変わる（§7 U6）。
   **DELETE はここに含めない。**§4.2 のとおり RLS も適用されずフィルタも効かないことが
   公式ドキュメントで分かっているので、測る対象は insert / update に限る。
2. **フィルタに書ける条件の範囲。**「フォロー中の利用者の投稿だけ」のような集合を使う条件を
   DB 側で書けるかが分からない。書けなければ、全投稿を受け取ってアプリ側で捨てることになり、
   **他人の投稿が端末に届いてから捨てられる**（漏れではないが、B4 のプル型／プッシュ型の
   判断材料になる）。

### 4.5 教材での置き方

`15_カリキュラム骨子案.md` は **Realtime の独立パートを廃止し、通知の章とタイムラインの章に
溶かす**と決めている。よって本節を1章にまとめない。購読解除の置き場所（画面の寿命と
アプリの前面・背面）は `04_詳細設計書.md` 目次9（セッションの寿命管理）と同じ章に来る可能性がある。
どこに置くかは B1。

---

## 5. Storage のパス設計とポリシー

### 5.1 バケットとパス

| バケット | 何を入れるか | パス |
|---|---|---|
| `avatars` | アバター画像・ヘッダー画像（#7） | `<利用者のid>/avatar.<拡張子>` / `<利用者のid>/header.<拡張子>` |
| `post-media` | 投稿に添付する画像（#4） | `<利用者のid>/<生成したファイル名>.<拡張子>` |

**先頭のフォルダを利用者の id にする**のが設計の中心である。
「自分のフォルダ配下だけ書ける」を、パスの1段目と `auth.uid()` の一致で表現する（05 §5）。

**`post-media` のパスに `post_id` を入れない理由**: 03 UC1 の順序が
「画像を上げる → `posts` に行を入れる」なので、**上げる時点で `post_id` がまだ存在しない**。
パスに入れると順序を逆にするしかなく、本文だけ先に保存された投稿が画像を待つ形になる。

### 5.2 ポリシー

```sql
-- avatars: 読むのは全員、書くのは自分のフォルダだけ
create policy "avatars_objects_read"
  on storage.objects for select
  to authenticated
  using (bucket_id = 'avatars');

create policy "avatars_objects_write_own"
  on storage.objects for insert
  to authenticated
  with check (
    bucket_id = 'avatars'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "avatars_objects_update_own"
  on storage.objects for update
  to authenticated
  using      (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "avatars_objects_delete_own"
  on storage.objects for delete
  to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
```

`post-media` も同じ形で、`bucket_id` を `'post-media'` に差し替えた4本を書く。
**名前は §1.2 の「効くポリシー」列から引けるように、ここで確定させておく。**

| ポリシー名 | 操作 | 条件 |
|---|---|---|
| `post_media_objects_read` | select | `bucket_id = 'post-media'` |
| `post_media_objects_write_own` | insert | `bucket_id = 'post-media'` かつ `(storage.foldername(name))[1] = auth.uid()::text` |
| `post_media_objects_update_own` | update | 同上（`using` と `with check` の両方） |
| `post_media_objects_delete_own` | delete | 同上 |

**名前を分けるのは必須である。**`storage.objects` はテーブルが1本しかなく、
**ポリシー名はテーブル単位で一意**なので、`avatars` 側と同じ名前は付けられない。
バケットごとに接頭辞を変える形にしてある。

| ポリシー | これが無いと何が漏れるか |
|---|---|
| `..._write_own` の `with check` | **他人のフォルダへ画像を置ける。**相手のアバターを差し替えられる |
| `..._update_own` の `with check` | 自分のフォルダのファイルを他人のフォルダへ移せる（上と同じ結果を update で作れる） |
| `..._delete_own` | 他人の画像を消せる |
| `bucket_id` の条件 | **バケットの区別が消える。**`avatars` のポリシーが `post-media` にも効いてしまう |

### 5.3 決まっていないこと

1. **バケットを公開にするか**（§7 U12）。`post_media.url` は「その公開 URL を持つ」と
   05 が書いており、公開バケットは URL を知っていれば誰でも開ける。
   **つまり `storage.objects` の select ポリシーは、公開バケットでは読み取りの守りにならない。**
   05 §5 が「閲覧は全員可」と決めているので矛盾はしないが、**教材でそう説明しないと
   「ポリシーで守られている」という誤解が残る。**
2. **MIME と容量の上限をバケット側で設定するか**（B21）。現在は画面入力の検証だけで、
   改造したクライアントは迂回できる。`01_要件定義書.md` §3 は「MIMEタイプ・拡張子・サイズを検証」と
   断定するが、**どこで検証するかは書いていない。**01 の断定だけを根拠にクライアント検証と
   決め打ちしない。
3. **孤児ファイルの扱い**（§7 U13）。画像を上げたあと `posts` の insert に失敗すると、
   Storage にファイルだけが残る。投稿を論理削除しても実体は残る。片づけるかどうかが未決である。

### 5.4 教材での置き方

パートB のプロフィール編集（アバター）と投稿作成（画像）で1回ずつ触る。
**カメラ（FR15）で撮った画像もこの経路に乗る**ので、パートC のカメラの章は
Storage のポリシーを新しく書かない。既に書いたポリシーが効いていることを確かめる側に回る。

**章末で確かめること**: 他人の id をパスの1段目にしてアップロードを投げ、拒否されること。

---

## 6. エラーハンドリングの共通方針

### 6.1 原因分類（X1〜X6）— 04 の E1〜E3 とは別の軸である

**記号を分ける。**`04_詳細設計書.md` §1.1 は **E1〜E3 を「画面での出し方」の3種**として
既に使っている（E1 入力エラー＝入力欄の直下 / E2 操作の失敗＝画面上部の帯 /
E3 取得の失敗＝一覧の代わり）。04 §1.2 の16画面の表も 08 もこの意味で E1〜E3 を使う。
**本書が分けるのは「何が原因で失敗したか」であって、出し方ではない。**
同じ記号を別の意味で使うと参照が壊れるので、本書は **X1〜X6** を使う。

| # | 原因分類 | 具体例 | どこで起きるか |
|---|---|---|---|
| X1 | 入力の誤り（DB の制約が拒否した） | `username` の UNIQUE 違反、文字数超過、CHECK 違反 | #13-2 / #7 / #4 |
| X2 | 認可の拒否（RLS が拒否した） | 他人の行への insert / update | 書き込みのある全画面 |
| X3 | 認証の状態 | 未ログイン、メール未確認、セッション切れ | 全画面 |
| X4 | 通信の失敗 | オフライン、タイムアウト、Realtime の切断 | 全画面 |
| X5 | Supabase 側の制限 | メール送信の上限、ログインのレート制限 | #2 / #13 / #14 |
| X6 | 想定外 | 上のどれでもないもの | — |

### 6.2 原因分類 → 04 の表示3種の対応表（本書が正本）

`04_詳細設計書.md` §1.1 は「Supabase が返すエラーをこの3種のどれへ落とすかの対応表は
**06 §6 が正本**になる」と本書を名指ししている。その対応表がこれである。

| 原因（本書 X） | 04 の表示（E） | 出し方 |
|---|---|---|
| X1 入力の誤り | **E1 入力エラー** | 該当する入力欄の直下 |
| X2 認可の拒否 | **表示先なし** | 利用者に出さない。開発中のログにだけ出す（下記2） |
| X3 認証の状態 | **画面遷移**（E ではない） | ログイン画面／メール確認待ち画面へ送る。帯を出して留めない |
| X4 通信の失敗（取得のとき） | **E3 取得の失敗** | 一覧の中身の代わりに置き、再試行を伴う |
| X4 通信の失敗（書き込みのとき） | **E2 操作の失敗** | 画面上部の帯。入力した値を消さない |
| X5 Supabase 側の制限 | **E2 操作の失敗** | 画面上部の帯。待てば直ることを伝える |
| X6 想定外 | **E2 操作の失敗** | 画面上部の帯。原文は出さない（下記3） |

**X4 が2行あるのが対応表の要点である。**同じ「通信の失敗」でも、取得の途中なら
一覧の代わりに出し、書き込みの途中なら帯で出す。04 の3種は**操作の種類**で分かれているので、
原因だけでは表示先が決まらない。

**文言そのものと表示位置の細部は 04 の担当である。**本書が決めるのは上の対応と、次の3つ。

1. **X1 は入力に紐づけて出す。**どの入力欄が悪いのかが分かる形にする。
   `username` の重複は **DB の UNIQUE 制約違反がそのままアプリへ返る**（05 users 節）ので、
   これを「このIDは使われています」に変換する対応表が要る。
2. **X2 は利用者の操作の誤りではない。**正しく作ったアプリでは X2 は起きない。
   X2 が画面に出た時点で、**それは実装の欠陥である**。教材では X2 を
   「利用者に見せるもの」ではなく「開発中に自分が見るもの」として扱う。だから表示先が無い。
3. **エラーの原文をそのまま画面に出さない。**DB の制約名やポリシー名が出ると、
   テーブルの構造がそのまま読める。

### 6.3 ★ 最も重要な1点 — 拒否は「エラー」として返るとは限らない

RLS は「触れる行の集合」を絞る仕組みなので、**触れる行が0件だったときの結果は
「エラー」ではなく「0件」になる**（§2 の各節で「章末で確かめること」を
「拒否される」ではなく「0行になる」と書いた箇所がこれにあたる）。

| 操作 | 拒否されたときに返るもの |
|---|---|
| select | 空の一覧。**エラーは出ない** |
| update / delete | 更新された行が0件。**エラーは出ない**（要実測。§7 U14） |
| insert | ポリシー違反のエラー。**これは出る** |

**これが教材で最も効く1点である。**「他人の投稿を消す」を試したときに、
アプリは何事もなく成功したように見える。**画面を再読み込みして初めて消えていないことが分かる。**

**しかも、その「0行」は既定の呼び出しでは見えない。**supabase-js の `update()` / `delete()` は
**既定で行を返さない**ので、返ってくるのは `data: null` と `error: null` である。
「0行だった」ことも「1行更新した」ことも、この返り値からは区別できない。
**§2 の各節に置いた「更新0行になるところを見る」は、このままでは手順として実行できない。**

よって書き込みの契約に次を入れる。**この契約の具体的な書き方は 04 の担当だが、
契約そのものは本書が決める。**

- **書き込みの既定形は「影響行数が返る呼び出し方」にする。**返り行を受け取る（`select()` を繋ぐ）か、
  件数を要求する（`count` を指定する）かのどちらかを、update / delete の全箇所で必ず付ける。
- **update と delete は、影響した行数を必ず確認する。**0件なら「成功」として扱わない。
- **確認せずに画面を先へ進めない。**

**§2 の各節の「章末で確かめること」は、この既定形で投げることを前提にしている。**
既定形を先に教えないと、「拒否されたのに成功したように見える」という一番効く実演が
**そもそも観測できない。**教材ではこの呼び出し方を、最初に update を書く章（`users`）で出す。
なお select の 0 件は返ってきた配列が空であることで見えるので、この手当ては要らない。

**「0行更新は静かに失敗する」を実測で確かめてから教材に書く**（§7 U14）。
実測前に断定して書くと、`16` A3 と同じ型の誤り（測らずに決める）になる。

### 6.4 教材での置き方

エラーの扱いは1章にまとめない。**X1 は #13-2（表示IDの重複）で、X2 は RLS の章で、
X5 はメール確認の章で、それぞれ目の前の機能が動かない文脈が生まれた瞬間に扱う**
（`11_ターゲット・ペルソナ・UX定義.md` 原則6「重いトピックは必要になった瞬間に最小限」）。
X4（通信の失敗）は `08_テスト計画書.md` 目次7（オフライン・再接続）と対になる。

---

## 7. 本書で決められなかったこと（`16_決定バックログ.md` へ起票する候補）

**本書はここに挙げた項目を「決めた」とは書いていない。**
16 が未決定の唯一の正本である（A1）ので、起票は 16 側で行う。
期限は工程上の時点で書く（A3）。

### 7.1 既に B番号がある未決定（本書が依存しているもの）

本書のどこが止まるかだけを書く。決めるのは 16 の側である。

本書のどこが止まるかを書く。決めるのは 16 の側である。
**期限欄を空にしない**（16 A3「タイミングの無い先送りは禁止」）。
B番号がある行の期限は 16 の「いつ」欄に従うので、そのまま写す。

| B番号 | 本書のどこが止まるか | 期限 |
|---|---|---|
| B4 | §1.2 タイムラインの行。プッシュ型ならテーブルが1つ増え、§2 にポリシーが1組増える | 16 の「いつ」に従う（P1） |
| B7 | §3.2 の表に5行目が要るか | 同上（P1） |
| B19 | §3.1（トリガーはクライアントではない）、§1.2 の insert 行 | 同上（P1） |
| B21 | §5.3 の2 | 同上（P1） |
| B22 | §4.3 の3項目 | 同上（P1） |
| B24 / B25 | §1.2 の #6 / #8 / #10 / #13-2 の行 | 同上（P1） |
| B27 | §2.4 の `using (deleted_at is null)`。**子テーブル（§2.5・§2.6・§2.8）まで広げるかも含める** | 同上（P1） |
| B28 | §3.2 全体 | 同上（P1） |
| 05 §4 課題2 | §2.5（枚数は1行の条件では上限にならない） | **パートB の投稿の章の実装PR前**（下記） |
| 05 §4 課題3・課題4 | §1.2 の #4 / #5 の insert 行 | 同上 |
| 05 §4 課題5 | §1.2 の検索（#10）の行。**この行だけ書けていない** | **パートC の章分割が確定する前（B1）** |
| 05 §4 課題6 | §3.2 の `type` | **パートB の通知の章の実装PR前** |

**05 §4 の課題2〜6 には B番号が無い**（16 に対応する行が無い）。
B24・B25・B27・B28 はまさに「05 に書いてあるのに台帳に無い」穴を塞ぐために起票された経緯があり、
**同じ穴が5件残っている。**本書はこの5件を「決まっているもの」として扱っていない。

**この5件の期限は 04 §10 が既に「06 の着手前」として置いていた。**本書は 2026-08-09 に
本文へ書き下ろされたので、**その期限は守られないまま過ぎた。**上の表はそれを置き直したもので、
置き直した理由は「06 は5件が未確定でも骨格を書けたが、章を書くには確定が要る」からである
（16 B14 と同じ書き方で、期限を守れなかった事実をここに残す）。
**16 へ起票するときは、04 §10 側の期限と上の期限を1つに畳む。**2つ立てたままにしない。

### 7.2 本書を書いていて新しく出た未決定

| # | 何が決まっていないか | なぜ決めないと進めないか | 期限 |
|---|---|---|---|
| U1 | 画面IDの扱い（#13-2 の飛び番を振り直すか、番号を捨てて名前で参照するか）。#8 が1画面か2画面かもここに含む | 章分割表の行と 04 の節番号が画面番号に従う。並べ替えのたびに番号が壊れる | 章分割表の凍結前（B1） |
| U2 | 親テーブルを参照するポリシー式（`post_media` / `post_hashtags` の `exists`）が `posts` の RLS を通るか。通るなら削除済み投稿の子行を本人が触れなくなる | §2.5・§2.8 の SQL がそのままでは成立しない可能性がある。`security definer` の補助関数に逃がすかを決める。**実測が要る** | パートB の RLS を扱う章の実装PR前 |
| U3 | 05 §5 の RLS 表の `notifications` 行の文言（「UPDATE は既読フラグのみ本人可」→「行は本人のみ。列の制限は別手段」） | 表のまま SQL に書き下ろすと、教材のポリシーが嘘になる。**05 の修正であって本書では直せない** | 05 の局長承認前。**04 §10 が「06 の着手前」としていた期限は過ぎた**（本書は 2026-08-09 に書き下ろされた）。05 の承認まで置き直す |
| U4 | 既読化を列単位 GRANT で塞ぐか、専用関数で塞ぐか（どちらでも `revoke update` は要る）。**案2を採る場合の実装形も含める**: `security definer` で書くこと（`security invoker` は `revoke update` と併用すると必ず落ちる）、所有者を誰にするか、`execute` を誰に配るか | §2.7 の SQL が2案のまま。教材の章に2案は載せられない。実装形が決まらないと、そのまま写経して動かないコード片が残る | パートB の通知の章の実装PR前。**04 §10 が「06 の着手前」としていた期限は過ぎた**。理由は 05 の是正（U3）が先に要るため |
| U5 | `notifications` の delete を誰かに許すか（通知の削除は機能要件に無い） | §2.7 でポリシーを書かない扱いにしたが、根拠が「要件に無い」だけである | パートB の通知の章の実装PR前 |
| U6 | **insert / update の**購読が RLS を通るか。フィルタに集合を使う条件を書けるか。**DELETE は含めない**（フィルタが効かず RLS も適用されないことは §4.2 のとおり公式ドキュメントで確定している） | §4.2 のフィルタ列が埋まらない。通らない場合、フィルタの書き忘れが即座に他人の通知の漏れになる。**実測が要る** | 本書（06）の凍結前 |
| U7 | 読み取りを `anon`（未ログイン）まで広げるか | §2 の全ポリシーの `to` 句。パートD で未ログイン閲覧を見せるかに直結する | 章分割表の凍結前（B1） |
| U8 | `post_media.order` の扱い（列名を変えるか、引用が要る旨を注記するか） | **SQL の予約語なので、教材のコード片をそのまま写経させると落ちる。**05 に注記が無い | パートB の投稿の章の実装PR前。**04 §10 が「06 の着手前」としていた期限は過ぎた**。理由は列名を変える場合に 05 の修正が要り、05 の承認と同時でないと二度手間になるため |
| U9 | ハッシュタグ本体の正規化（大文字小文字・全角半角・前後の空白）を誰がやるか | `hashtags.tag` は UNIQUE なので、正規化しないと `Expo` と `expo` が別のタグになり検索結果が割れる | パートC の章分割が確定する前（B1） |
| U10 | B19 の選択肢に「トリガーが入れる行」が入っていない | §3.1 のトリガーはクライアントを経由しない。「全 insert でクライアントが入れる契約」は成立しない | B19 を決めるとき（同時に） |
| U11 | 自己操作の通知を作るか。取り消し（いいね解除・フォロー解除）で通知行をどうするか | §3.2 のトリガー仕様が確定しない。B28 と同じ章で決まるが、B28 の文面には含まれていない | B28 を決めるとき（同時に） |
| U12 | Storage のバケットを公開にするか | 公開なら select ポリシーは読み取りの守りにならない。教材の説明がそのまま誤解になる | パートB の画像の章の実装PR前 |
| U13 | Storage の孤児ファイル（投稿の作成に失敗した画像、論理削除した投稿の画像）を片づけるか | §5.3 の3。片づけるなら削除の経路が要り、章が1つ増えうる | 章分割表の凍結前（B1）。**04 §10 が「投稿の途中失敗」として「06 の着手前」に置いていた期限は過ぎた**。理由は片づけの有無が章数に効くので、章分割表と同時に決めるのが正しいため |
| U14 | RLS で弾かれた update / delete が「エラー」ではなく「0行」で返ることの実測。**「0行が何として観測できるか」（返り値の形。`select()` を繋いだとき／`count` を要求したときに何が返るか）も含める** | §6.3 は本書で最も教材効果の高い1点だが、**測っていない。**測る前に断定して書けない。観測の仕方が分からないと §2 の「章末で確かめること」が手順にならない | 本書（06）の凍結前 |
| U15 | 各画面のコンポーネント分割と状態の置き場（**04 §1.1 の【未決・要起票】。本書の未決ではなく、本書が従属している側**） | **§1.2 の行の粒度がこれに従属する**と 04 が明記している。埋まるまで §1.2 は仮の粒度である。本書は粒度未確定のまま一覧を書いた | 章分割表の凍結前（B1）。**04 §10 は同じ 2026-08-09 の改訂で置き直され、旧期限「06 の着手前」は〔旧: 〕付きの履歴として残っているだけである**（本書が当初書いていた「04 §10 は『06 の着手前』と書いたまま」は、その改訂前を見たもので、いまは誤り）。**04 §1.1 と 04 §10 は現在どちらも B1 で一致している。**16 へ起票するときは1本にする |
| U16 | メール確認前の書き込みを何が止めるか。(a) Auth の設定でセッションを発行しない / (b) ポリシーに確認状態の条件を足す | §1.4。**03 UC3-4 は「RLS により」と断定しているが、本書 §2 のどのポリシーもメール確認を見ていない。**(a) なら 03 の文言が誤りで、03 の修正が要る。(b) なら §2 の書き込み系ポリシーを全部書き直す。**実測が要る** | パートB の認証の章の実装PR前 |
| U17 | 自己フォローを許すか。塞ぐならポリシー側（`follower_id <> followee_id`）か DB の CHECK 制約側（**05 の修正**）か | §2.6。現状の `follows_insert_own` は自分自身へのフォローを止めていない。§3.2 のトリガーが `recipient_id = actor_id` の通知を自分宛に作る。U11（自己操作の通知）は「通知を作るか」だけを論点にしていて、自己フォロー自体を許すかを含んでいない | パートB のフォローの章の実装PR前（U11 と同じ節で決める） |
| U18 | **`users` の delete で 05 と本書が食い違っている件の是正**（2026-08-09 追記） | 05 §5 の表は `users` を「INSERT / UPDATE / DELETE ＝ 自分の行のみ、INSERT だけ除外」と読める書き方をしているが、本書 §2.3 は「delete のポリシーは書かない。アカウント削除は機能要件に無い」と決めている。**本書 §0.2 は「03・05 に無い事項を本書で新たに決めない」と宣言しているので、この1点だけ宣言を破っている。**08 §5.5 の5行目と §5.11 の期待値は、U14 の実測だけでは閉じず、この食い違いが解けるまで確定しない。**是正は 05 の文言側**（機能要件に無いものを表に書かない）を採るのが素直だが、05 は局長承認前の文書なので本書では直さない | 05 の局長承認前（U3 と同じ席） |
| U19 | **`posts` の update を論理削除だけに絞るか**（列単位の `GRANT UPDATE(deleted_at)` か、論理削除専用の `security definer` 関数か） | §2.4。現状の `posts_update_own` は行の持ち主しか見ておらず、**`created_at`・`body`・`reply_to_post_id`・`repost_of_post_id` を後から書き換えられる**。FR3 に投稿の編集は無いのに編集を許しており、「削除は update で行う契約」という §2.4 自身の説明とも食い違う。`created_at` の書き換えでタイムラインの並びを動かせ、`reply_to_post_id` の書き換えで既存のスレッド構造を作り替えられる。**U4（`notifications` の列制限）と同じ2案で、同じ席で決めるのが素直** | パートB の投稿の章の実装PR前（U4 と同じ席） |
| U20 | **論理削除された投稿に いいね／ブックマーク を作れてよいか** | §2.6。`likes_insert_own` / `bookmarks_insert_own` は「誰として書くか」しか見ておらず、**親の投稿が生きているかを見ていない**。外部キーは親の存在しか確かめないので、削除前に id を知っていれば削除後でも作れる。作れると §3.2 のトリガーが動き、**受け取った人が開けない投稿を指す通知が届く**。**B27 を「DB 側で隠す」に決めてもこの経路は閉じない**（B27 と 08 §5.6 の追加は子テーブルの select の話で、insert には触れていない）。塞ぐなら `with check` に親の `deleted_at is null` を足すが、**U2（親を参照する `exists` が `posts` の RLS を通るか）の実測が先** | 章分割表の凍結前（B1）。B27 と同じ席で決める |

---

## 8. 参照元

- 画面一覧・ユースケース: `03_基本設計書.md` §2・§3
- テーブル定義・RLS 方針: `05_DB設計書.md` §2・§5
- 技術構成と消滅した決定: `02_技術選定書.md` §4・§6
- パート構成: `15_カリキュラム骨子案.md` §1
- 章の骨格と章分割表の列: `decisions/D5_章の骨格.md`
- 章ID・置き場の規約: `decisions/D1_教材の置き場と章IDの規約.md`
- 未決定の正本: `16_決定バックログ.md`
