# A0-1 最初の画面を、自分の端末に出す

> **対照版メモ**　抜いた要素: 開発ログで高価値と分類した、ディスク不足とポート競合の詰まりを扱う会話。必要なコマンドと技術手順は残しています。

> **試作メモ**　この章は、Expo SDK 54 の blank `App.tsx` と main の固定 lockfile を使う試作です。章の開始状態はまだ正式に凍結していません。SDK 57 で得た過去の端末実測は、この版の実機確認の代用にはしません。

> このシェル手順は Linux と macOS 向けの試作であり、Windows では未実測です。

阿部「今日から SNS を作るんですよね。まず何をするんですか」

磯貝「画面を1枚出します。中身は文字だけです」

阿部「それだけですか」

磯貝「それだけです。ただし、出る先はブラウザではありません。**自分の端末**です」

## この章で起きること

最後まで進むと、手元の端末に「はじめての画面」という文字が出ます。
そこから先の章で、この画面が少しずつ SNS になっていきます。

## 始める前に必要なもの

Node.js 22.16.0 と npm、エディタ、Expo Go を用意してください。

```bash
node --version
npm --version
```

両方とも版の番号が出れば準備できています。
これらの導入時間は、初心者の実測値がまだありません。


### Expo Go と教材の版を合わせる

この試作のプロジェクトは Expo SDK 54 です。Expo Go は、同じ SDK に対応する版でなければ開けません。

Expo Go 57.0.9 を使う iPhone では、このプロジェクトを開けません。Wi-Fi を変えたり `--tunnel` を使ったりしても、版の不一致は直りません。

Android 実機は、[SDK 54 用の Expo Go](https://expo.dev/go) を選んで用意します。iPhone の起動手順は、この試作には含めません。

この版で端末を開く手順を書いているのは、対応する Expo Go を用意できた Android 実機です。iPhone 実機の追加準備と、macOS 専用の iOS Simulator の起動手順はまだ含めていません。iPhone や Simulator を使う場合は、この試作には起動手順が足りません。

対応する起動アプリを用意できていなければ、ここで実機手順を止めます。SDK の番号だけを書き換えて進めないでください。[版の確認と端末別の公式手順](https://docs.expo.dev/troubleshooting/expo-go-version-mismatch/)を参照します。

## 試作用プロジェクトを用意する

このリポジトリの `prototype-chapter` にいる状態で、検証済み lockfile を含む clean snapshot を作ります。
`create-expo-app@latest` は版が動くため、この試作の再現入口には使いません。

```bash
tools/make-snapshot.sh expo-first-screen
test ! -e my-sns
cp -R snapshots/expo-first-screen my-sns
cd my-sns
npm ci
```

`make-snapshot.sh` は `node_modules` と `.expo` を除外し、制作側の `AGENTS.md`、`CLAUDE.md`、`.claude` も持ち込みません。assets と `package-lock.json` は snapshot に残します。

依存導入が完了したら、次へ進みます。

## 画面の中身を書く

エディタで `App.tsx` を開きます。Visual Studio Code なら、次のコマンドでも開けます。

```bash
code App.tsx
```

中身をすべて消し、次の内容に書き換えます。

[embedmd]:# (listings/expo-first-screen/App.tsx tsx /^import/ /^}/)
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

阿部「`View` と `Text` って何ですか。ウェブだと `div` じゃないんですか」

磯貝「`View` は箱で、`Text` は文字です。端末の画面では React Native の部品を使います」

見た目を決める `styles` も続けて書きます。

[embedmd]:# (listings/expo-first-screen/App.tsx tsx /^const styles/ /^}\);/)
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

`Ctrl+S` で保存します。macOS では `Command+S` です。

## 実機で動かす

```bash
npx expo start --port 8090
```

前節で SDK 54 対応を確認した Expo Go を使い、パソコンと端末を同じ Wi-Fi に接続します。ログインを求められた場合はパソコン側と同じ Expo アカウントを使います。

「Project is incompatible with this version of Expo Go」と出たら、前節の版を確認します。Wi-Fi や `--tunnel` の切替では直りません。

Android 実機の Expo Go で **Scan QR code** を開き、QR コードを読みます。これは Expo 公式案内に基づく手順であり、今回この章の手順としては未実測です。

阿部「QR コードを読んでも開かないときは、どうしますか」

磯貝「まず同じ Wi-Fi かを確かめます。社内や公共の Wi-Fi が端末同士の通信を遮る場合は、`npx expo start --tunnel` も試せます」

Android は USB 接続を補助に使える場合があります。USB は機種ごとの設定が要るため、この章の成功条件にはしません。

この QR 手順は読者が実機で確かめるための手順です。現時点の試作記録にはシミュレーターと個別の実機表示証拠（SDK 57 の過去記録）がありますが、この章どおりの初心者による QR 通し操作は未観測です。

## Git に出発点を保存する

端末に「はじめての画面」が表示されたことを確認してから、出発点を保存します。最初に `my-sns` 自身を Git リポジトリにします。

```bash
git init
git rev-parse --show-toplevel
```

表示された末尾が `my-sns` であることを確認します。次に、このリポジトリ専用の名前とメールアドレスが設定済みかを調べます。

```bash
git config --local --get user.name
git config --local --get user.email
```

何も出なかった項目だけ、自分の値に置き換えて設定します。例の名前やメールアドレスをそのまま使わないでください。

```bash
git config --local user.name "あなたの名前"
git config --local user.email "あなたのメールアドレス"
```

この章で追跡するのは `App.tsx` だけです。保存と履歴確認も `my-sns` の中で行います。

```bash
git add App.tsx
git commit -m "最初の画面を作る"
git log -1 --oneline
```

## この章でできたこと

対応する実機で画面を表示できたら、次の項目がこの章の成果です。起動アプリを用意できずに止まった場合は、表示確認を完了したことにはしません。

- lockfile から試作用プロジェクトを再現した
- `View` と `Text` を使って最初の画面を書いた
- `App.tsx` だけを Git に保存した
- Android 実機の Expo Go で QR を読み、画面を表示した

次の章では、保存した文字や色が実機へすぐ届くことを確かめます。
