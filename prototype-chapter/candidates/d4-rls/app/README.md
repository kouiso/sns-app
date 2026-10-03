# SNS Auth SDK 57 trial

Expo SDK 57 と Supabase Auth を実際に接続する、認証だけの候補実装です。新規登録、メール確認、再送、ログイン、パスワード再設定、ログアウトを確認できます。確認後のプロフィール画面はセッション成立を示すプレースホルダーで、SNS 本体は含みません。

## 環境変数

Expo を起動する前に次を設定します。

```dotenv
EXPO_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=...
EXPO_PUBLIC_AUTH_RETURN_BASE=sns-auth-trial://auth/return
```

端末から controlled local trial の LAN プロキシへ接続する場合だけ、その単一ホストを明示します。任意の LAN アドレスを自動許可しません。

```dotenv
EXPO_PUBLIC_SUPABASE_URL=http://192.168.11.11:8094
EXPO_PUBLIC_AUTH_RETURN_BASE=exp://192.168.11.11:8093/--/auth/return
EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST=192.168.11.11
```

通常は `sb_publishable_...` の publishable key を使います。legacy `anon` JWT は localhost、Android emulator の `10.0.2.2`、または上記で明示した controlled trial host に限って受け付けます。`service_role` と `sb_secret_...` は拒否します。

## メールテンプレート

この候補は URL の query に `token_hash` と `type` だけがある戻り先を受け付けます。Supabase の既定メールテンプレートが作る implicit bearer callback や PKCE `code` callback は処理しません。Supabase Dashboard の対象テンプレートを、概ね次の形のリンクを作る内容へ変更する必要があります。

```html
<!-- Confirm signup -->
<a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=signup">メールアドレスを確認する</a>

<!-- Reset password -->
<a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery">パスワードを再設定する</a>
```

Supabase 側の Redirect URLs に `EXPO_PUBLIC_AUTH_RETURN_BASE` と同じ戻り先を許可してください。scheme、host、port、path のいずれかが異なるリンクは、Auth API を呼ぶ前に拒否されます。

Expo の通常起動で渡される開発サーバー URL は認証リンクとして扱いません。設定した scheme、host、port、path がすべて一致する URL だけを認証 parser へ渡し、その後に query と fragment を厳密に検証します。

本番メールのカスタムテンプレートと SMTP の運用責任者は未決です。この候補は controlled local trial 用であり、外部メール配送、development build、FR14 の完了、教材の正式ゲート通過を主張しません。

## 戻りリンクの境界

`lib/auth-return.mjs` は次を行います。

- `token_hash` と `type=signup|recovery` だけを構文として受理する
- 重複 query、余分な query、fragment、制御文字、不正な percent encoding を Auth API の前で拒否する
- `verifyOtp({ token_hash, type })` を実サーバーへ渡し、続けて `getUser()` で同一ユーザーとメール確認済み状態を検証する
- 同じ URL の同時配送を一つへまとめ、異なるリンクによる同時 Auth mutation を拒否する
- アプリ側でも認証リンクとボタン操作が同じ同期 single-flight を共有し、処理中の別操作を Supabase Auth へ送らない
- 認証リンク処理中の Auth event は直接画面へ反映せず dirty 状態として記録し、処理の最後に1回だけ現在の session と user を再検証する
- 成功済み URL をメモリ内の有界 cache に保持し、ログアウト後に同じリンクで画面を再承認しない
- `verifyOtp` 後に authoritative user を確認できなかった場合は `reconciliation_needed` と `sessionMutated` を返し、確認済みという途中結果を cache せず、パスワード再設定画面を開かない。同じ hash は再利用せず、新しいメールを送信する

raw URL、token hash、Supabase のエラー payload は結果や画面へ出しません。成功済み URL の cache は永続化しません。

Node の単体試験は次で実行できます。

```sh
node --test test-auth-return.mjs
```

主な実機操作用 `testID` は `email-input`、`password-input`、`login-button`、`show-signup-button`、`signup-button`、`confirmation-wait`、`resend-button`、`show-reset-request-button`、`reset-request-button`、`password-reset-screen`、`new-password-input`、`save-password-button`、`profile-screen`、`signout-button` です。
