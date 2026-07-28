// 投稿を1件あらわす型。
// SNS の「ポスト」は、つきつめると こういうオブジェクト。
type Post = {
  id: string;
  body: string; // 本文（最大280文字）
  createdAt: Date;
};

// 最初の1件を作って画面に出してみる
function makePost(body: string): Post {
  return { id: crypto.randomUUID(), body, createdAt: new Date() };
}

const first = makePost("はじめての投稿");
console.log(first.body);
