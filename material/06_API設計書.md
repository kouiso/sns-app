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

### 2.4 post_media

```sql
CREATE POLICY "post_media_select_all" ON post_media FOR SELECT USING (true);
CREATE POLICY "post_media_insert_own" ON post_media FOR INSERT TO authenticated
  WITH CHECK (EXISTS (
    SELECT 1 FROM posts WHERE posts.id = post_media.post_id AND posts.author_id = auth.uid()
  ));
CREATE POLICY "post_media_update_own" ON post_media FOR UPDATE TO authenticated
  USING (EXISTS (
    SELECT 1 FROM posts WHERE posts.id = post_media.post_id AND posts.author_id = auth.uid()
  ));
CREATE POLICY "post_media_delete_own" ON post_media FOR DELETE TO authenticated
  USING (EXISTS (
    SELECT 1 FROM posts WHERE posts.id = post_media.post_id AND posts.author_id = auth.uid()
  ));
```

### 2.5 likes

```sql
CREATE POLICY "likes_select_all" ON likes FOR SELECT USING (true);
CREATE POLICY "likes_insert_own" ON likes FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());
CREATE POLICY "likes_delete_own" ON likes FOR DELETE TO authenticated
  USING (user_id = auth.uid());
```

### 2.6 follows

```sql
CREATE POLICY "follows_select_all" ON follows FOR SELECT USING (true);
CREATE POLICY "follows_insert_own" ON follows FOR INSERT TO authenticated
  WITH CHECK (follower_id = auth.uid());
CREATE POLICY "follows_delete_own" ON follows FOR DELETE TO authenticated
  USING (follower_id = auth.uid());
```

### 2.7 hashtags

```sql
CREATE POLICY "hashtags_select_all" ON hashtags FOR SELECT USING (true);
CREATE POLICY "hashtags_insert_auth" ON hashtags FOR INSERT TO authenticated
  WITH CHECK (true);
```

### 2.8 post_hashtags

```sql
CREATE POLICY "post_hashtags_select_all" ON post_hashtags FOR SELECT USING (true);
CREATE POLICY "post_hashtags_insert_own" ON post_hashtags FOR INSERT TO authenticated
  WITH CHECK (EXISTS (
    SELECT 1 FROM posts WHERE posts.id = post_hashtags.post_id AND posts.author_id = auth.uid()
  ));
CREATE POLICY "post_hashtags_delete_own" ON post_hashtags FOR DELETE TO authenticated
  USING (EXISTS (
    SELECT 1 FROM posts WHERE posts.id = post_hashtags.post_id AND posts.author_id = auth.uid()
  ));
```

### 2.9 bookmarks

```sql
CREATE POLICY "bookmarks_select_own" ON bookmarks FOR SELECT TO authenticated
  USING (user_id = auth.uid());
CREATE POLICY "bookmarks_insert_own" ON bookmarks FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());
CREATE POLICY "bookmarks_delete_own" ON bookmarks FOR DELETE TO authenticated
  USING (user_id = auth.uid());
```

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

#### likes → like 通知

```sql
CREATE OR REPLACE FUNCTION public.handle_like_notification()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  post_author uuid;
BEGIN
  SELECT author_id INTO post_author FROM public.posts WHERE id = new.post_id;
  IF post_author IS NOT NULL AND post_author <> new.user_id THEN
    INSERT INTO public.notifications (recipient_id, actor_id, type, post_id)
    VALUES (post_author, new.user_id, 'like', new.post_id);
  END IF;
  RETURN new;
END;
$$;

CREATE TRIGGER on_like_created
  AFTER INSERT ON public.likes
  FOR EACH ROW EXECUTE FUNCTION public.handle_like_notification();
```

#### posts → reply / repost 通知

```sql
CREATE OR REPLACE FUNCTION public.handle_post_notification()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  reply_author uuid;
  repost_author uuid;
BEGIN
  IF new.reply_to_post_id IS NOT NULL THEN
    SELECT author_id INTO reply_author FROM public.posts WHERE id = new.reply_to_post_id;
    IF reply_author IS NOT NULL AND reply_author <> new.author_id THEN
      INSERT INTO public.notifications (recipient_id, actor_id, type, post_id)
      VALUES (reply_author, new.author_id, 'reply', new.id);
    END IF;
  END IF;

  IF new.repost_of_post_id IS NOT NULL THEN
    SELECT author_id INTO repost_author FROM public.posts WHERE id = new.repost_of_post_id;
    IF repost_author IS NOT NULL AND repost_author <> new.author_id THEN
      INSERT INTO public.notifications (recipient_id, actor_id, type, post_id)
      VALUES (repost_author, new.author_id, 'repost', new.id);
    END IF;
  END IF;

  RETURN new;
END;
$$;

CREATE TRIGGER on_post_created
  AFTER INSERT ON public.posts
  FOR EACH ROW EXECUTE FUNCTION public.handle_post_notification();
```

#### follows → follow 通知

```sql
CREATE OR REPLACE FUNCTION public.handle_follow_notification()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  IF new.follower_id <> new.followee_id THEN
    INSERT INTO public.notifications (recipient_id, actor_id, type)
    VALUES (new.followee_id, new.follower_id, 'follow');
  END IF;
  RETURN new;
END;
$$;

CREATE TRIGGER on_follow_created
  AFTER INSERT ON public.follows
  FOR EACH ROW EXECUTE FUNCTION public.handle_follow_notification();
```

#### UC1「新規投稿のフォロワー通知」を追加するか

01_要件定義書.md FR9 には「いいね・リプライ・リポスト・フォロー」の4種類のみ記載。
UC1「新規投稿のフォロワー通知」を `notifications.type` に追加する場合は
`new_post` 種別を追加し、上記 `handle_post_notification()` に
フォロワー一覧をループして通知を挿入する処理を追加する。B7 で確定。

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

## 5. Storage のパス設計とポリシー

### 5.1 bucket 制約

```sql
-- bucket レベルで MIME タイプとファイルサイズを制限
-- Supabase Dashboard またはマイグレーションで設定
insert into storage.buckets (id, name, public, allowed_mime_types, file_size_limit)
values ('post-images', 'post-images', true, '{"image/jpeg", "image/png"}', 5242880);
```

### 5.2 パス設計

- `{auth.uid}/{post_id}/{random-uuid}.{ext}`
- `auth.uid` によるユーザー分離は必須。
- `post_id` はまだ存在しない新規投稿の場合、クライアント側で生成した UUID を使う
  （05_DB 設計書の default `gen_random_uuid()` と合わせる）。

### 5.3 RLS ポリシー

```sql
CREATE POLICY "storage_select_all" ON storage.objects FOR SELECT
  USING (bucket_id = 'post-images');

CREATE POLICY "storage_insert_own" ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'post-images'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "storage_delete_own" ON storage.objects FOR DELETE TO authenticated
  USING (
    bucket_id = 'post-images'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );
```

## 6. エラーハンドリングの共通方針

Supabase SDK が返すエラーを画面に出す方針。仮案：

| エラーコード | 画面表示 |
|---|---|
| `23505` （unique violation）| その値はすでに使われています |
| `23503` （foreign key violation）| 参照先が見つかりません。再度お試しください |
| `42501` （RLS 拒否）| 権限がありません（内部知識で補完しない） |
| `AuthApiError: Email not confirmed` | メール確認を完了してください |

詳細は 04_詳細設計書.md 承認後に確定。

## 7. API キーの取り扱い契約

### 7.1 許可されるキー

- `publishable key`（`sb_publishable_...`）のみをアプリに埋め込む。
- `anon` キー（レガシー版 publishable）も同様に安全。

### 7.2 禁止されるキー

- `secret key`（`sb_secret_...`）
- `service_role` キー（レガシー版 secret）

これらは `BYPASSRLS` 属性を持ち、RLS を丸ごと迂回する。アプリに埋めると
改造クライアントから全データを読み書き可能になる。

### 7.3 環境変数と CI

- `.env` はリポジトリに含めず、`.env.example` には `EXPO_PUBLIC_SUPABASE_URL`
  と `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` のみを置く。
- EAS Build の secrets に publishable key を登録する。
- 公開リポジトリでは、publishable key ですら build artifact から読めることを
  学習者に正直に示す（Round 12 指摘）。

## 参照元

- 画面一覧: `03_基本設計書.md` セクション2
- テーブル定義: `05_DB設計書.md`
