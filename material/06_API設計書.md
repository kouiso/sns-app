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

## 参照元

- 画面一覧: `03_基本設計書.md` セクション2
- テーブル定義: `05_DB設計書.md`
