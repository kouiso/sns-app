# 06. API設計書

ステータス: **未着手（Phase 1）**

## 着手条件

`03_基本設計書.md`（画面一覧・ユースケース）と `05_DB設計書.md`（テーブル定義）の
両方が確定した時点で着手する。エンドポイント設計はDBスキーマと画面要求の両方に
依存するため、どちらか一方が未確定な状態で先に書くと手戻りが起きる。

## 着手後にこのファイルへ記載する内容（目次予定）

**本書の性質が変わった（2026-07-26）**。Supabase はクライアント SDK 経由で DB を直接叩くため、
**自前 API のエンドポイントを設計するという作業自体が消滅**した。
本書は「アプリが Supabase をどう叩くか」の契約書になる。

- **消滅した目次項目**: エンドポイント一覧 / `openapi.yaml` を正本に置く方式 /
  `@nestjs/swagger` との差分照合（＝Phase 2 の OpenAPI 照合コンパレータも不要）/
  Authorization ヘッダーとリフレッシュトークンのローテーション手順 /
  自前 WebSocket のイベント発行契約（いずれも `02_技術選定書.md` §6 参照）

新しい目次:

1. **データアクセス一覧**（画面ごとに、どのテーブルへどの操作をするか。
   users / posts / follows / notifications / bookmarks / hashtags）
   - **Round 12 追加**: 全 insert 操作で `gen_random_uuid()` / `now()` の DB default に頼むか、
     クライアント側で生成するかの契約を明記
2. **RLS ポリシー定義**（05 §5 の方針を、実際の SQL として書き下す。本書の中心）
   - **Round 12 追加**: `notifications` の `read_at` 列のみ UPDATE 可、他列は revoke する方針。
     `posts` の DELETE 全面拒否・`deleted_at` 更新のみ許可する方針。各ポリシーが Supabase クライアント SDK
     から呼ばれるときの `auth.uid()` 渡し方
3. **DB トリガー関数の仕様**（`auth.users` → `users` の行作成、通知行の作成）
   - **Round 12 追加**: `handle_new_user()` 関数で `security definer set search_path = ''` を使い、
     `raw_user_meta_data` から `username` / `display_name` / `updated_at` を明示的に挿入する契約。
     username 競合時の挙動を含む
4. **Realtime の購読契約**（どのテーブルの何を購読し、何を画面に反映するか）
   - **Round 12 追加**: 購読対象テーブルを `supabase_realtime` publication に追加する SQL、
     購読開始前の初回 fetch、再接続後の再 fetch、重複排除の実装
5. **Storage のパス設計とポリシー**（誰がどこにアップロードでき、誰が読めるか）
   - **Round 12 追加**: bucket レベルの `allowed_mime_types` / `file_size_limit` 制限、
     `storage.objects` の RLS ポリシー。クライアント側検証はサーバー側制約の補助に過ぎないことを明記
6. エラーハンドリングの共通方針（Supabase が返すエラーをどう画面に出すか）
7. **API キーの取り扱い契約**（Round 12 追加）
   - publishable key のみを `supabaseClient` 初期化に使い、secret / `service_role` キーを
     クライアントに埋め込まないための環境変数・CI・ビルドフロー設計

## 1. データアクセス一覧

本書は 03/05 のドラフト版に基づく先行案。03/05 の局長承認後に最終確定する。

| 画面 | 読み取り | 挿入 | 更新 | 削除 |
|---|---|---|---|---|
| ログイン | `auth.users`（Supabase Auth） | — | — | — |
| 新規登録 | — | `auth.users`（Supabase Auth） | — | — |
| タイムライン | `posts`, `users`, `post_media`, `likes`, `follows` | `posts`, `post_media` | `posts`（`deleted_at` のみ） | — |
| 投稿作成 | `posts`（リプライ/リポスト元） | `posts`, `post_media`, `post_hashtags`, `hashtags` | — | — |
| 投稿詳細 | `posts`, `post_media`, `likes`, `users` | `likes`, `posts`（リプライ） | — | `posts`（`deleted_at`） |
| プロフィール | `users`, `posts` | — | `users`（自分のみ） | — |
| フォロー中一覧 | `users`, `follows` | `follows`（自分が follower） | — | `follows`（自分が follower） |
| 通知 | `notifications`, `users` | — | `notifications`（`read_at` のみ） | — |
| 検索 | `posts`, `users`, `hashtags` | — | — | — |
| ブックマーク | `bookmarks`, `posts` | `bookmarks` | — | `bookmarks` |

## 2. RLS ポリシー定義

05 §5 の方針を SQL として書き下す。以下は 03/05 ドラフトに基づく先行案。

### 2.1 users

```sql
-- 自分の行だけを更新・削除できる。SELECT は全員。
-- INSERT は auth.users 作成トリガー経由のため、クライアントから直接行わない。
CREATE POLICY "users_select_all" ON users FOR SELECT USING (true);
CREATE POLICY "users_update_own" ON users FOR UPDATE TO authenticated
  USING (id = auth.uid());
```

### 2.2 posts

```sql
-- 削除は誰にも許可しない。削除相当の操作は `deleted_at` を立てる UPDATE。
CREATE POLICY "posts_select_all" ON posts FOR SELECT
  USING (deleted_at IS NULL);
CREATE POLICY "posts_insert_own" ON posts FOR INSERT TO authenticated
  WITH CHECK (author_id = auth.uid());
CREATE POLICY "posts_update_own" ON posts FOR UPDATE TO authenticated
  USING (author_id = auth.uid());
-- DELETE ポリシーは作成しない。DELETE 自体を拒否する。
```

### 2.3 notifications

```sql
-- SELECT は本人のみ。UPDATE 可能な列を read_at のみにするため、
-- まず authenticated から UPDATE を revoke してから read_at 列のみ GRANT。
CREATE POLICY "notifications_select_own" ON notifications FOR SELECT TO authenticated
  USING (recipient_id = auth.uid());

REVOKE UPDATE ON notifications FROM authenticated;
GRANT UPDATE (read_at) ON notifications TO authenticated;

CREATE POLICY "notifications_update_read_at" ON notifications FOR UPDATE TO authenticated
  USING (recipient_id = auth.uid())
  WITH CHECK (recipient_id = auth.uid());
```

### 2.4 他テーブル（TODO: 03/05承認後に全部）

`post_media`, `likes`, `follows`, `hashtags`, `post_hashtags`, `bookmarks` の
RLS ポリシーは 03/05 承認後に追加する。

## 3. DB トリガー関数の仕様

### 3.1 auth.users → users の行作成

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.users (id, username, display_name, updated_at)
  VALUES (
    new.id,
    new.raw_user_meta_data ->> 'username',
    COALESCE(new.raw_user_meta_data ->> 'display_name', new.raw_user_meta_data ->> 'username'),
    now()
  );
  RETURN new;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

**注意**: `username` が `raw_user_meta_data` に含まれない場合、トリガーは失敗し
新規登録自体をブロックする。B20 で username を登録画面で必須とするか、
トリガー側で仮の値を作るかを確定するまで、この SQL は仮案とする。

### 3.2 通知行の作成

`likes`, `follows`, `posts`（リプライ/リポスト）の変更を検知して
`notifications` 行を作るトリガー。詳細は 05 §3 未解決課題 1 と連動。

## 4. Realtime の購読契約

対象テーブルを `supabase_realtime` publication に追加するマイグレーション：

```sql
BEGIN;
  DROP PUBLICATION IF EXISTS supabase_realtime;
  CREATE PUBLICATION supabase_realtime;
COMMIT;

ALTER PUBLICATION supabase_realtime ADD TABLE posts;
ALTER PUBLICATION supabase_realtime ADD TABLE likes;
ALTER PUBLICATION supabase_realtime ADD TABLE follows;
ALTER PUBLICATION supabase_realtime ADD TABLE notifications;
```

アプリ側では購読開始前に初回 `select`、再接続後に再 `select`、
受信時に重複排除（同じ `id` / `created_at` の二重配信を無視）を行う。

## 参照元

- 画面一覧: `03_基本設計書.md` セクション2
- テーブル定義: `05_DB設計書.md`
