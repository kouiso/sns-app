# A0-1 最初の画面を、自分の端末に出す（SDK 57 candidate）

> **候補版**　Expo SDK 57 の技術確認用です。正式教材や採用決定ではありません。

> シェル手順は Linux と macOS 向けです。Windows、初心者による通し操作、QR 読取は未確認です。

## この章でできるようになること

手元の端末に「はじめての画面」と表示し、配布された14ファイルの開始ソースを Git に保存します。

これは最初の章なので、前章の成果は必要ありません。ファイルの展開、ターミナル操作、アプリのインストールができることを前提にします。

## 完成品の地図

完成する SNS のうち、この章で扱うのは開始画面です。

```text
[開始画面: 今回] → [投稿作成] → [タイムライン] → [プロフィール]
```

阿部「iPhone と Android のどちらでも試せますか」

磯貝「SDK 57 に対応する Expo Go を使えば、どちらも対象です。QR の読み方と iPhone のログイン条件は別々に確認します」

## 道具の版を確認する

Node.js、npm、Git、エディタ、SDK 57 対応の Expo Go を用意します。Apple Developer Program、iOS Simulator、Android Emulator は必要ありません。

```bash
node --version
npm --version
git --version
```

この候補で確認する Node.js の範囲は 22.16.0 以上、23.0.0 未満です。次のコマンドが `Node version OK` を出さなければ、ここで止めます。

```bash
node -e "const [a,b]=process.versions.node.split('.').map(Number); process.exit(a===22&&b>=16?0:1)" && echo "Node version OK"
```

SDK 57 の公式最低条件は Node.js 22.13.x です。この候補では、技術確認済みの範囲を狭く使います。

## 候補ソースを安全な場所へコピーする

配布フォルダ `sdk57` の絶対パスを確認します。ターミナルで `cd ` と末尾の空白まで入力してから、配布フォルダをドラッグし、Enter を押します。この方法では引用符を自分で足しません。

パスを手入力する場合は、次の引用符内を絶対パスへ置き換えます。

```bash
cd "/ここを配布フォルダ sdk57 の絶対パスに置き換える"
pwd
test -f chapter-expo-first-screen.md && test -d start-source && echo "SOURCE OK" || echo "STOP: 配布フォルダを確認してください"
```

`SOURCE OK` が表示された場合だけ、コピーへ進みます。`cd` が失敗した場合は、配布フォルダの場所と、パス末尾に余分な空白がないかを確認します。

作業先は `$HOME/sns-course-work/my-sns-sdk57` にします。次の1ブロックが配布物、親 Git、既存の作業先を確認してからコピーと依存導入を行います。

```bash
CANDIDATE_DIR="$PWD"
PROJECT_PARENT="$HOME/sns-course-work"
PROJECT_DIR="$PROJECT_PARENT/my-sns-sdk57"
mkdir -p "$PROJECT_PARENT"
if ! test -f "$CANDIDATE_DIR/candidate-manifest.json" || ! test -d "$CANDIDATE_DIR/start-source"; then
  echo "STOP: sdk57 配布フォルダを確認してください"
elif git -C "$PROJECT_PARENT" rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "STOP: sns-course-work が別の Git リポジトリ内です"
elif test -e "$PROJECT_DIR" || test -L "$PROJECT_DIR"; then
  echo "STOP: $PROJECT_DIR はすでにあります"
else
  cp -R "$CANDIDATE_DIR/start-source" "$PROJECT_DIR" &&
    cd "$PROJECT_DIR" &&
    npm ci &&
    test -x node_modules/.bin/expo &&
    printf 'SDK57 install completed\n' > node_modules/.sns-sdk57-install-ready &&
    echo "READY: $PROJECT_DIR"
fi
```

`READY` と絶対パスが表示された場合だけ次へ進みます。`STOP` が出た場合や `READY` が出ない場合は、後続コマンドを実行せず、最初のエラーを記録します。

## 中断したところから再開する

ターミナルを閉じても、作業先のファイルは残ります。コピーと依存導入が完了していれば、新しいターミナルから次のログイン手順を続けられます。コピー手順を繰り返して既存の作業先を上書きする必要はありません。

`npm ci` が途中で失敗した場合は、最初のエラーを記録します。配布ソースをコピー済みの同じ作業先に `package-lock.json` と `App.tsx` があることを確認してから、依存導入だけをやり直せます。プロジェクトのファイルは削除しません。

```bash
if cd "$HOME/sns-course-work/my-sns-sdk57" &&
  test -f package-lock.json && test -f App.tsx; then
  rm -f node_modules/.sns-sdk57-install-ready &&
    npm ci &&
    test -x node_modules/.bin/expo &&
    printf 'SDK57 install completed\n' > node_modules/.sns-sdk57-install-ready &&
    echo "READY: $PWD"
else
  echo "STOP: コピー済みの作業先を確認してください"
fi
```

`READY` が出なければ後続へ進みません。コピー自体が失敗してソースが揃っていない場合は、失敗した状態を残して担当者に確認します。

## Expo アカウントと端末を準備する

[Expo のアカウント作成ページ](https://expo.dev/signup)で無料アカウントを作ります。端末には App Store または Google Play から、SDK 57 に対応する Expo Go をインストールします。

ストアで特定の版番号を選べるとは限りません。Expo Go の設定画面で実際の版を記録し、SDK 57 非対応と表示された場合は止めます。制作側で確認した iPhone の版は 57.0.9 ですが、これをストアの必須版とはしません。

固定 lockfile で導入した CLI だけを使ってログインします。

```bash
if cd "$HOME/sns-course-work/my-sns-sdk57" &&
  test -f node_modules/.sns-sdk57-install-ready &&
  test -x node_modules/.bin/expo &&
  npx --no-install expo login &&
  npx --no-install expo whoami; then
  echo "ACCOUNT OK"
else
  echo "STOP: 依存導入とログインを確認してください"
fi
```

`whoami` には自分のユーザー名が表示されます。`ACCOUNT OK` が出ない場合や未ログインと表示された場合は、先へ進みません。

iPhone では Expo Go のサインイン画面を開き、同じユーザー名でログインします。Android でも同じアカウントを使えますが、現在の公式要件で端末ログインが必須なのは iOS です。

パソコンと端末を同じ Wi-Fi に接続します。iPhone でローカルネットワークへの接続確認が出た場合は許可します。

## 画面の中身を確認する

エディタを起動し、`$HOME/sns-course-work/my-sns-sdk57/App.tsx` を開きます。VS Code の `code` コマンドを設定済みなら、次の方法も使えます。

```bash
cd "$HOME/sns-course-work/my-sns-sdk57"
code App.tsx
```

`code: command not found` と出た場合は、エディタのメニューからファイルを開きます。

```tsx
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';

// これから作る SNS の、いちばん最初の画面。
// ここに書いた文字が、そのまま手元の端末に出る。
export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>はじめての画面</Text>
      <Text style={styles.body}>ここから SNS を作っていきます</Text>
      <StatusBar style="auto" />
    </View>
  );
}
```

画面の配置と文字の見た目は、同じファイルの `styles` で指定します。

```tsx
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
  },
  body: {
    fontSize: 16,
    marginTop: 8,
    color: '#555',
  },
});
```

阿部「`View` と `Text` は何ですか」

磯貝「`View` は画面の箱、`Text` は文字です。見た目は `styles` で決めます」

`Ctrl+S` で保存します。macOS では `Command+S` です。

## 実機で動かす

1つ目のターミナルで開発サーバーを起動します。このターミナルは起動中のままにします。

```bash
if cd "$HOME/sns-course-work/my-sns-sdk57" &&
  test -f node_modules/.sns-sdk57-install-ready &&
  test -x node_modules/.bin/expo &&
  npx --no-install expo whoami; then
  npx --no-install expo start --port 8090
else
  echo "STOP: 依存導入とログインを確認してください"
fi
```

iPhone は標準カメラ、Android は Expo Go の **Scan QR code** で QR コードを読みます。画面に「はじめての画面」が出るまで成功扱いにしません。

LAN で接続できない場合は、まず同じ Wi-Fi、SDK 57 対応、iPhone の同一ユーザー名とローカルネットワーク許可を確認します。この候補は `@expo/ngrok` を同梱していないため、自己判断で tunnel を追加しません。

追加ツールのインストールを求められたら拒否して止め、表示された文を記録します。準備済み環境で tunnel を試す場合も、先に `Ctrl+C` で現在の Metro を止めます。

## Git に出発点を保存する

開発サーバーは1つ目のターミナルに残します。2つ目のターミナルを開き、絶対パスで作業先へ移動します。

```bash
cd "$HOME/sns-course-work/my-sns-sdk57"
pwd
git init
git config --local --get user.name
git config --local --get user.email
```

名前またはメールアドレスが空なら、自分の値を設定します。

```bash
git config --local user.name "あなたの名前"
git config --local user.email "あなたのメールアドレス"
```

配布した開始ソースだけを明示して追加します。

```bash
git add .gitignore App.tsx LICENSE app.json index.ts
git add package.json package-lock.json tsconfig.json
git add assets/android-icon-background.png
git add assets/android-icon-foreground.png
git add assets/android-icon-monochrome.png
git add assets/favicon.png assets/icon.png assets/splash-icon.png
git diff --cached --name-only
```

一覧が配布した14ファイルと一致しない場合はコミットしません。`node_modules`、`.expo`、`.env` が表示された場合も止めます。

```bash
git commit -m "最初の画面を作る"
git log -1 --format=%s
git ls-files
git status --short
```

コミット名が「最初の画面を作る」、追跡一覧が14ファイル、最後の状態表示が空であることを確認します。確認後、1つ目のターミナルへ戻り、`Ctrl+C` で Metro を止めてから次章へ進みます。

## 自分の言葉で確かめる

阿部「固定ソースを安全な作業先へコピーし、OS に合う方法で QR を読みました。表示後に配布された14ファイルだけを保存しました」

磯貝「作業先、実機表示、Git の追跡一覧を順番に確認できました。これが次章の出発点です」

## この章でできたこと

- SDK 57 の固定 lockfile から候補プロジェクトを再現した
- OS ごとに異なる QR 導線を確認した
- 実機表示後に14ファイルの開始ソースを Git に保存した

## 演習

Android と iPhone の QR 読取方法、iPhone に必要なログイン条件を、それぞれ1文で説明してください。演習中に解答ファイルを開く必要はありません。
