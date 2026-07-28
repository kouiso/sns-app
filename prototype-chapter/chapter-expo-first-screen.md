# A0-1 最初の画面を、自分の端末に出す

阿部「今日から SNS を作るんですよね。まず何をするんですか」

磯貝「画面を1枚出します。中身は文字だけです」

阿部「それだけですか」

磯貝「それだけです。ただし、出る先はブラウザではありません。**自分の端末**です」

## この章で起きること

最後まで進むと、手元の端末に「はじめての画面」という文字が出ます。
そこから先の章で、この画面が少しずつ SNS になっていきます。

## 始める前に必要なもの

前の章で入れた **Node.js** と **npm** を使います。まだの場合は前の章に戻ってください。
確認は次のコマンドです。両方とも版の番号が出れば大丈夫です。

```bash
node --version
npm --version
```

## プロジェクトを作る

```bash
npx create-expo-app@latest my-sns --template blank-typescript@sdk-54
cd my-sns
npm install
```

阿部「`npm install` が長いですね」

磯貝「入れているファイルが多いからです。この本を書いた時点では 300MB ほどでした。
版によって変わるので、数字は目安として見てください」

阿部「300MB。そんなに使うんですか」

磯貝「使います。ここで**ディスクの空きが足りないと途中で止まります**」

阿部「止まったら、どうすればいいんですか」

磯貝「画面に出た文字の1行目を読んでください。
`no space left on device` と書いてあったら、原因はそれです」

## 画面の中身を書く

`App.tsx` を開いて、中身をすべて消し、次の内容に書き換えます。

最初の2行は「これから使う部品を持ってくる」という意味です。
この2行が無いと、下の `View` や `Text` が見つからずに失敗します。

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

磯貝「ここではブラウザの部品を使いません。`View` が箱で、`Text` が文字です。
端末の画面はブラウザではないので、部品の名前も別になっています」

阿部「見た目はどこで決めるんですか」

磯貝「下の `styles` です」

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

阿部「`alignItems` と `justifyContent` で真ん中に来るんですね」

磯貝「そうです。横方向と縦方向を別々に指定しています」

## 動かす

```bash
npx expo start
```

阿部「あっ、赤い字が出ました。`Port 8081 is running ... in another window` って」

磯貝「8081 という番号は、もう別の何かが使っています」

阿部「その別の何かを止めればいいですか」

磯貝「**何なのか分からないうちは止めないでください。**
自分の別の作業なら、そちらが止まります。空いている番号を使うほうが安全です」

```bash
npx expo start --port 8090
```

阿部「今度は出ました。QR コードが出ています」

磯貝「その QR を端末で読むと、いま書いた画面が出ます。
条件が2つあります。**端末に Expo Go を入れておくこと**と、
**パソコンと端末を同じ Wi-Fi につないでおくこと**です」

阿部「同じ Wi-Fi じゃないと駄目なんですか」

磯貝「QR を読んだ端末が、パソコンの中で動いているものを見に行くからです。
別のネットワークだと届きません」

阿部「会社の Wi-Fi だと駄目なことがありそうですね」

磯貝「そのときは `npx expo start --tunnel` を使ってください。
外側の道を通るので、同じ Wi-Fi でなくても届きます」

阿部「さっきの2回とも、書いてある通りでしたね」

磯貝「エラーは意地悪をしているのではなく、状況を説明しているだけです。
**1行目を読む。** それだけで、次にやることは決まります」

## この章でできたこと

- 自分の端末に、自分で書いた文字が出た
- ブラウザの `div` ではなく、`View` と `Text` を使った
- エラーの1行目を読めば、次にやることは決まると分かった

次の章では、この画面に文字を追加して、書き換えたその場で反映されることを確かめます。
