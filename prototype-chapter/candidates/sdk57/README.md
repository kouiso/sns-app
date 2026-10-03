# Expo SDK 57 A0 candidate（NON_FORMAL）

このディレクトリは、A0「最初の画面」と「その場反映」を Expo SDK 57 で技術確認するための候補です。正式教材、正式な技術採用、凍結済み開始状態、G3/G6 合格を表しません。`formal_start_frozen` と `phase0_approval_changed` は manifest でも `false` です。

`start-source/` は両章が参照する共通のソース成果物です。最初の画面章では bootstrap に使い、その場反映章では前章を完了して初回コミットを作った状態から続けます。main の SDK 54 source を基礎にし、`package.json` と `package-lock.json` だけを既存の SDK 57 実測環境からそのまま移しています。

`start-source/` に `node_modules`、`.expo`、`.git`、環境ファイル、制作側の AI 指示ファイルは含めません。正式な開始状態はまだ凍結していません。

`completed-live/App.tsx` は、その場反映章のコード変更後に期待するファイルです。両章の本文と対照版は同じコマンド、端末条件、未観測範囲を保ちます。

## 対照版と内部判定

`controls/*/plain.md` は会話を除いた対照版です。`controls/expo-first-screen/intro-ablation.experimental.md` は導入会話だけを除く実験版で、G6 の正式な R2（高価値の詰まりを除く版）ではありません。

`answers.md` は演習後にレビュー担当が照合する別掲解答です。学習者が章の実行や演習中に開く必要はありません。

初心者が実際に詰まった高価値項目は、現在0件です。このため正式な R2 は作れません。開発ログで高価値項目が分類されるまでは、実験版を R2 や G6 完走の証拠に使いません。

SDK 不一致、アカウント、ローカルネットワークは制作側の技術確認または未観測項目です。本文には監査用分類を混ぜず、読者が判断できる停止条件だけを置いています。

## 観測済みと未観測

- この候補は iPhone と Android の SDK 57 対応 Expo Go を対象にします。2026-10-03 の技術試行では、同じ App コードと package/lock を物理 iPhone 12 mini、iOS 26.5.2、Expo Go 57.0.9 build 1017880 で表示・更新しました。
- 上記は制作側の技術試行です。今回組み直した14ファイル全体、章本文どおりの QR 読取、初心者による両章の通し操作は未観測です。
- Android の QR 手順と iOS の標準カメラ手順は公式資料に基づく手順です。この候補で SDK 57 対応 Expo Go を使う物理 Android の QR 通し操作は未観測です。
- Apple Developer Program、iOS Simulator、Android Emulator は、この候補の必須条件にしません。

## 公式資料

- [Expo Go 57 and required sign-in](https://expo.dev/changelog/expo-go-57-login)
- [iOS device sign-in requirement](https://docs.expo.dev/troubleshooting/expo-go-sign-in-required/)
- [Android/iOS QR instructions](https://docs.expo.dev/tutorial/create-your-first-app/)
- [LAN and tunnel development](https://docs.expo.dev/get-started/start-developing/)
- [Expo CLI tunnel dependency and command](https://docs.expo.dev/more/expo-cli/)
- [SDK 57 Node.js requirement](https://docs.expo.dev/versions/latest/)

`candidate-manifest.json` は開始ソース、章、対照版、期待ファイルの SHA-256 を記録します。manifest 自身は自己参照を避けるため、その一覧には含めません。
