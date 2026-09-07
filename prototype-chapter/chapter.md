# 第1章 最初の TypeScript を動かす（道具の検証用ドラフト）

この章は捨て試作です。教材の完成品ではなく、G3 文体ゲートと G5 引用ゲートが
実際に動くかを確かめるための素材として書きました。

## 型を1つ作る

阿部「投稿って、プログラムから見ると何なんですか」

磯貝「箱です。中に本文と、いつ書いたかが入っている。それだけ」

[embedmd]:# (listings/node-npm-setup/index.ts ts /^type Post/ /^};/)
```ts
type Post = {
  id: string;
  body: string; // 本文（最大280文字）
  createdAt: Date;
};
```

阿部「`body` に `string` って書いてあるのは何ですか」

磯貝「そこには文字しか入らない、という約束です。数字を入れようとすると
エディタが赤い線を引いて止めてくれます」

## 1件作って動かす

[embedmd]:# (listings/node-npm-setup/index.ts ts /^function makePost/ /^}/)
```ts
function makePost(body: string): Post {
  return { id: crypto.randomUUID(), body, createdAt: new Date() };
}
```

阿部「`crypto.randomUUID()` は何をしているんですか」

磯貝「重複しない ID を1つ作っています。投稿を後から探すときの目印になります」
