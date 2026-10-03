# A0-2 書き換えたら、その場で変わる

> **試作メモ**　この章は、Expo SDK 57 の blank `App.tsx` 候補と既存 lockfile を使う試作です。技術選定書02にある SDK 54 の採用履歴の更新判断とは別であり、凍結済みの章開始状態でもありません。

阿部「前の章で画面が出ました。次は何をするんですか」

磯貝「文字と色を変えて、保存した内容が実機へすぐ届くことを確かめます」

## 前の章の続きから始める

前の章で使った `my-sns` を開きます。エディタで `App.tsx` を開き、開発サーバーも起動します。

```bash
code App.tsx
npx expo start --port 8090
```

端末は前の章と同じ Wi-Fi に接続します。iPhone はカメラ、Android は Expo Go の **Scan QR code** から QR コードを読みます。

## 文字と色を足す

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

`styles` の中には、緑色の `note` を追加します。

[embedmd]:# (listings/live-reload/App.tsx tsx /^  note:/ /^  },/)
```tsx
  note: {
    fontSize: 14,
    marginTop: 24,
    color: '#0a7',
  },
```

## 保存して確かめる

`Ctrl+S` で保存します。macOS では `Command+S` です。

阿部「保存しました。端末に緑の文字が増えました」

磯貝「端末を操作せず、保存した内容が届きました。これが開発中のその場反映です」

この章どおりの初心者による両実機の通し操作は未観測です。表示されない場合も、成功したことにせず次の順で切り分けます。

| 見るところ | 確かめること |
|---|---|
| 未保存の印 | エディタのタブに丸印などが残っていないか |
| 開発サーバー | `npx expo start` を実行した画面が閉じていないか |
| 接続 | パソコンと端末が同じ Wi-Fi にいるか |
| iPhone | Expo Go のローカルネットワーク許可が有効か |
| アカウント | ログインを求められた場合、同じ Expo アカウントか |

直らない場合は、ターミナルの最初のエラーを記録します。Android の USB 接続や `--tunnel` は、同じ Wi-Fi で届かないときの補助手段です。

## Git で保存する

変更を確認し、`App.tsx` だけを保存します。

```bash
git status --short App.tsx
git diff -- App.tsx
git add App.tsx
git commit -m "文字と色の変更を確かめる"
```

## Git で元に戻す

もう一度 `App.tsx` を編集したら、保存してから状態を確認します。エディタに未保存の変更があると、`git restore` の後で古い内容を再保存してしまうことがあります。

```bash
git status --short App.tsx
git restore App.tsx
```

`git restore App.tsx` は、最後にコミットした `App.tsx` へ戻します。ほかのファイルは対象にしません。

## この章でできたこと

- 文字と色を変え、保存後の実機表示を確かめる手順を実行した
- 変わらない場合の確認箇所を切り分けた
- `App.tsx` だけを Git に保存し、元へ戻す方法を覚えた

次の章では、文字列や数値に TypeScript の型を付け、画面へ表示します。
