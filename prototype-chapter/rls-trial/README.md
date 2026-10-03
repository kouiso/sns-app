# ローカルAuth/RLSの捨て試作

通常ユーザーのJWTでPostgRESTを操作し、管理接続で別途DB状態を照合する。
本番マイグレーション、正式API、D4の執筆工数、G6実走の証明ではない。

## 実行条件

- Linuxの専用Supabase CLIスタック `sns-trio-local` が `/tmp/sns-trio-local` にある。
- API/DB/メール箱は127.0.0.1の54321/54322/54324だけへ公開する。CLIのnetwork設定だけでは
  この条件を満たさなかったため、実Docker PortBindingsを確認する。`measure.py`も実設定を検査する。
- メール確認を有効にし、外部SMTPを使わず付属Mailpitへ送る。
- 共有環境・ホスト型プロジェクトへこのSQLを適用しない。

専用スタックへ初回だけ適用する。

```sh
docker exec -i supabase_db_sns-trio-local psql -U postgres -d postgres -v ON_ERROR_STOP=1 < prototype-chapter/rls-trial/001_posts.sql
docker exec -i supabase_db_sns-trio-local psql -U postgres -d postgres -v ON_ERROR_STOP=1 < prototype-chapter/rls-trial/002_soft_delete.sql
```

```sh
python3 prototype-chapter/rls-trial/measure.py --cli /tmp/sns-trio-supabase-cli/supabase --output /tmp/local-auth-rls-new-run.json
```

出力は未使用のパスを指定する。過去の証拠は上書きしない。合成ユーザー3人を各実行で作り、
キー・JWT・メールアドレス・確認/再設定リンクはメモリ内だけで扱う。
結果はHTTP状態、エラーコード、件数、真偽値、ソース/導入関数本体のハッシュで記録する。
期待と違う判定が1つでもあれば、レポートを残してexit 2とする。

## 実測で分かったこと

`SELECT deleted_at IS NULL` と本人UPDATEの組合せでは、直接の論理削除は返却形式を変えても
403/42501になった。限定RPC候補では本人1行、他人0行、匿名拒否となり、削除済み行を
全員から隠しつつ物理行を残せた。

実験のDELETE権限は、ポリシーが無いことによる拒否を測るため意図的に付与している。
INSERT/UPDATEの列制限など未検証の境界を含むため、このSQLをアプリへ採用しない。
外部メール到達、ホスト型上限、端末リンク復帰、アプリのセッション復元も未検証。
正式採用は設計文書と全認可試験の一致後に判断する。
