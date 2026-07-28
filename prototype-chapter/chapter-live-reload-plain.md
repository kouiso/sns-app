# A0-2 書き換えたら、その場で変わる

## この章で起きること

`App.tsx` に1行足すと、**保存した瞬間に**端末の画面が変わります。
アプリを入れ直す作業も、開き直す作業もありません。

## 前の章の続きから始める

前の章で作った `my-sns` をそのまま使います。開発サーバーを起動しておきます。

```bash
npx expo start
```

端末で QR を読んで、前の章の画面が出ている状態にしてください。
**この画面を出したまま**、次に進みます。

## 1行足す

`App.tsx` の `<Text>` が2つ並んでいるところに、3つ目を足します。

[embedmd]:# (listings/live-reload/App.tsx tsx /^export default function App/ /^}/)
```tsx
export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>はじめての画面</Text>
      <Text style={styles.body}>ここから SNS を作っていきます</Text>
      <Text style={styles.note}>いま書き換えたところが、すぐここに出ます</Text>
      <StatusBar style="auto" />
    </View>
  );
}
```

見た目も足します。`styles` の中に `note` を追加します。

[embedmd]:# (listings/live-reload/App.tsx tsx /^  note:/ /^  },/)
```tsx
  note: {
    fontSize: 14,
    marginTop: 24,
    color: '#0a7',
  },
```

## 保存する

端末の画面がそこまで追いついてきます」

## なぜこれが大事か

入れ直しに1分かかるなら、人は1日に数回しか試しません。
1秒で変わるなら、100回試せます。**試した回数がそのまま上達の速さになります**」

書く、保存する、端末を見る。これの繰り返しです」

## 変わらないときに見るところ

| 見るところ | 確かめること |
|---|---|
| 保存したか | 編集した画面に「未保存」の印が残っていないか |
| 開発サーバー | `npx expo start` を動かしている画面が、閉じていないか |
| 端末とパソコン | 同じ Wi-Fi のままか。前の章と同じ条件です |

それで直ります」

## この章でできたこと

- 文字を1行足して、端末の画面がその場で変わることを確かめた
- 見た目の指定を `styles` に足す形を覚えた
- 変わらないときに見る場所が3つあると分かった

次の章では、画面に置いた文字をボタンに変えて、押したときの動きを付けます。
