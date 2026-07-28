# A0-1 最初の画面を、自分の端末に出す

阿部「今日から SNS を作るんですよね。まず何をするんですか」

磯貝「画面を1枚出します。中身は文字だけです」

阿部「それだけですか」

磯貝「それだけです。ただし、出る先はブラウザではありません。**自分の端末**です」

## この章で起きること

最後まで進むと、手元の端末に「はじめての画面」という文字が出ます。
そこから先の章で、この画面が少しずつ SNS になっていきます。

## プロジェクトを作る

```bash
npx create-expo-app@latest my-sns --template blank-typescript@sdk-54
cd my-sns
npm install
```

阿部「`npm install` が長いですね」

磯貝「入れているファイルが多いからです。全部で300MB くらいあります」

## 画面の中身を書く

`App.tsx` を開きます。

```tsx
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

阿部「QR コードが出ました」

磯貝「その QR を端末で読むと、いま書いた画面が出ます」

阿部「出ました。自分のスマホに文字が出ています」

磯貝「これが出発点です」

## この章でできたこと

- 自分の端末に、自分で書いた文字が出た
- ブラウザの `div` ではなく、`View` と `Text` を使った

次の章では、この画面に文字を追加して、書き換えたその場で反映されることを確かめます。
