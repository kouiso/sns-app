# SDK 57 candidate 演習解答（別掲）

> **レビュー担当用**　この解答は演習後の確認に使います。学習者が演習中に参照する前提ではありません。

## A0-1

Android は Expo Go の **Scan QR code**、iPhone は標準カメラで QR コードを読みます。iPhone 実機では CLI と Expo Go に同じ Expo アカウントでログインします。

## A0-2

3つ目の `<Text>` を変更して保存し、実機表示を確認します。コミットせず、次のコマンドで `App.tsx` だけを戻します。

```bash
git status --short App.tsx
git diff -- App.tsx
```

状態が正確に ` M App.tsx` で練習用の差分だけであることを確認してから戻します。

```bash
git restore App.tsx
git diff -- App.tsx
git status --short
```

最後の `git diff` と `git status` に何も出ず、3つ目の文がコミット済みの内容に戻れば完了です。
