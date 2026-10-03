# A0-2 書き換えたら、その場で変わる（SDK 57 candidate）

> **候補版**　Expo SDK 57 の技術確認用です。正式教材や採用決定ではありません。

## この章でできるようになること

前章で実機に出した開始画面を引き継ぎ、保存した文字と色がその場で変わることを確認します。

前提は、前章の依存導入と実機表示を終え、配布された14ファイルを最初のコミットへ保存していることです。

## 完成品の地図

完成する SNS の開始画面に、保存直後の更新を確認できる文字を足します。

```text
[開始画面: 今回もここ] → [投稿作成] → [タイムライン] → [プロフィール]
        └─ 保存した文字と色の反映を確認
```

阿部「保存した変更は iPhone と Android のどちらにも届きますか」

磯貝「同じ SDK 57 プロジェクトで確かめます。実際に表示を見た端末だけを確認済みにします」

## 前章の続きから始める

前章の Metro が動いていれば、起動したターミナルで `Ctrl+C` を押して止めます。新しいターミナルで、決めた絶対パスへ移動します。

```bash
cd "$HOME/sns-course-work/my-sns-sdk57"
pwd
git log -1 --format=%s
git ls-files
git status --short
```

コミット名が「最初の画面を作る」、追跡一覧が配布された14ファイル、最後の状態表示が空でなければ止めます。この確認を通した作業先だけを使います。

エディタを起動し、`$HOME/sns-course-work/my-sns-sdk57/App.tsx` を開きます。VS Code のコマンドを設定済みなら `code App.tsx` でも開けます。

1つ目のターミナルで Metro を起動し、そのまま残します。

```bash
cd "$HOME/sns-course-work/my-sns-sdk57" &&
test -x node_modules/.bin/expo &&
npx --no-install expo start --port 8090
```

iPhone は CLI と Expo Go に同じユーザー名でログインし、標準カメラで QR コードを読みます。Android は Expo Go の **Scan QR code** を使います。

どちらも SDK 57 対応の Expo Go と同じ Wi-Fi を使います。追加ツールのインストールを求められたら拒否して止め、表示された文を記録します。

## 文字と色を足す

`App.tsx` の内容を、次の2つのコードブロックを続けた内容へ置き換えます。これで完成後のファイル全体になります。

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
      <Text style={styles.note}>いま書き換えたところが、すぐここに出ます</Text>
      <StatusBar style="auto" />
    </View>
  );
}
```

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
  note: {
    fontSize: 14,
    marginTop: 24,
    color: '#0a7',
  },
});
```

`Ctrl+S` で保存します。macOS では `Command+S` です。実機に緑の文字が増えることを確認します。

表示されない場合は、未保存の印、Metro のターミナル、SDK 57 対応、同じ Wi-Fi、iPhone のユーザー名を順に確認します。LAN で届かなくても、この候補では tunnel 用の追加ツールを自己判断で導入しません。

## Git で保存する

Metro を残したまま2つ目のターミナルを開き、絶対パスで移動します。変更を確認し、`App.tsx` だけを保存します。

```bash
cd "$HOME/sns-course-work/my-sns-sdk57"
git status --short App.tsx
git diff -- App.tsx
```

状態が正確に ` M App.tsx` で、差分が3つ目の `<Text>` と `note` の見た目を足す変更だけになっていることを読みます。文の打ち間違いや別の変更があれば、ここで直して保存し、確認し直します。確認後、同じ2つ目のターミナルでコミットします。

```bash
git add App.tsx
git commit -m "文字と色の変更を確かめる"
git log -1 --format=%s
git status --short
```

コミット名が「文字と色の変更を確かめる」、最後の状態表示が空であることを確認します。違う場合は、復元練習へ進みません。

## Git で元に戻す

3つ目の `<Text>` の文を「元に戻す練習」に変え、保存します。実機にも「元に戻す練習」と出たことを確認します。

この変更はコミットせず、保存済みの作業ツリーだけに置きます。次の状態表示が正確に ` M App.tsx` でなければ、`git restore` を実行しません。

```bash
git status --short App.tsx
git diff -- App.tsx
```

` M App.tsx` と練習用の差分を確認したら、未コミットの変更だけを戻します。直前のコミットは消えません。

```bash
git restore App.tsx
git diff -- App.tsx
git status --short
```

最後の2コマンドが何も表示しないことを確認します。エディタと実機の3つ目の文も「いま書き換えたところが、すぐここに出ます」へ戻ることを確認します。

エディタにディスク上の内容を読み直す確認が出た場合は、ディスク上の内容を選びます。復元前の古いバッファを再保存しません。

## 自分の言葉で確かめる

阿部「保存後の実機表示を確認してから、`App.tsx` だけをコミットしました。練習用の未コミット変更だけを元へ戻しました」

磯貝「コミット済みの変更と、まだコミットしていない変更を分けて扱えました」

## この章でできたこと

- 保存後に文字と色が実機へ届くことを確認した
- `App.tsx` だけをコミットし、コミット名と clean 状態を確認した
- 保存済みで未コミットの練習変更だけを元へ戻した

## 演習

3つ目の文を別の文へ変え、実機で確認した後、コミットせずに元へ戻してください。演習中に解答ファイルを開く必要はありません。

演習を終えて元の文に戻したら、1つ目のターミナルへ戻り、`Ctrl+C` で Metro を止めます。
