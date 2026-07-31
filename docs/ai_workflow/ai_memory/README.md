# AI Memory 運用 README

> これは実プロジェクトで運用しているAI Memoryの運用方針をほぼそのまま転載したものです。実際のentry(具体的なコード指摘)は機密性の観点からここには含めていません。詳細は[`docs/ai_workflow/README.md`](../README.md)を参照してください。

## 目的

このディレクトリは、通常の設計資料やIssue記録ではなく、**AIとの協調開発における推論補正メモリ**を管理するための場所です。

目的は、AIに大量の背景知識を読ませることではありません。

AIが次回以降、

* どこから確認を始めるべきか
* どの前提を疑うべきか
* このプロジェクト固有の例外は何か
* 過去に人間・AIがどこを見落としたか

を判断しやすくすることです。

つまり、このディレクトリは **AIの探索空間を補正するための記録**です。

---

## 基本方針

### 1. 人間がトリガーを握る

AIが自動で大量にメモリを生成する運用にはしません。

記録するのは、人間が次のように感じた瞬間だけです。

* これは普通の推論だと外れる
* AIが見落とした
* 自分も見落とした
* このプロジェクト固有の前提だった
* 次回も同じミスが起きそう
* マルチテナント境界・認可・queryset・migration・非同期処理などで危険な発見があった

「なんとなく学びがあった」だけでは記録しません。

---

### 2. Prediction Correction に統一する

最初から次のような複数体系を別々に管理しません。

* AI Memory
* Exception Collection
* Bias Profile
* Observation Event
* Observation Matrix

まずはすべてを **Prediction Correction** という1つの記録単位にまとめます。

Prediction Correction とは、

> AIまたは人間が自然に予測したことと、実際に起きたことのズレを記録するもの

です。

---

### 3. 一般知識は記録しない

記録対象は、このプロジェクト固有の事情に限定します。

記録しないものの例:

* 一般的なDjango知識
* 一般的なPython知識
* 公式ドキュメントを見れば分かること
* 単なる実装手順
* Issueの作業ログ
* AIが毎回読まなくてもよい反省文

記録するものの例:

* このプロジェクトでは他テナントの存在隠蔽のため 403 ではなく 404 を返す箇所がある
* `Student` 取得では `Student.objects.active()` や `visible_students_qs()` を優先する
* permission を追加しても scope 制御にはならず、selector 側の絞り込みが必要
* M2M の `exclude()` は意図と異なる結果になりやすい
* `transaction.atomic()` だけでは Lost Update を防げない

---

## ディレクトリ構成

```text
docs/
  ai_memory/
    README.md
    INDEX.md
    entries/
      2026-07-04_tenant-boundary-404-before-403.md
      2026-07-04_student-active-queryset.md
      2026-07-04_m2m-exclude-danger.md
    views/
      heuristics.md
      bias_profile.md
    archive/
```

### README.md

このファイルです。
人間向けの運用方針をまとめます。

### INDEX.md

AIが最初に読む入口です。
個別エントリの全文ではなく、1行要約だけを並べます。

### entries/

個別の Prediction Correction を保存します。

### views/

10〜20件ほど溜まった後に、AIで横断整理した派生ビューを置きます。

例:

* よく出る失敗パターン
* 次回AIに渡すべき共通注意
* AIごとの見落とし傾向
* 人間側の見落とし傾向

最初から作らなくてよいです。

### archive/

前提が変わったもの、再発可能性が低いものを退避します。
削除はしませんが、通常のAI読み込み対象からは外します。

---

## INDEX.md の形式

`INDEX.md` は短く保ちます。

```md
# AI Memory Index

| ID | Title | Pattern | Status | Summary |
|---|---|---|---|---|
| 2026-07-04-001 | tenant-boundary-404-before-403 | Tenant boundary / QuerySet | active | visible queryset が対象を消すと 403 ではなく 404 になる |
| 2026-07-04-002 | student-active-queryset | Soft delete / QuerySet | active | Student取得は active() / visible_students_qs() を優先する |
```

AIにはまず `INDEX.md` だけを読ませます。
必要な場合だけ、個別エントリを最大3件程度まで開きます。

---

## エントリのテンプレート

新規エントリ作成時に使う記入用テンプレートは `docs/markdown_templates/PREDICTION_CORRECTION.md` を正とする。ここで二重定義しない。

以下はテンプレートを用いた具体例
実際の例ではないので注意

```md
# 2026-07-04 tenant-boundary-404-before-403

## Predicted

権限外アクセスなので 403 になる。

## Reality

visible queryset から対象が除外され、get_object 段階で 404 になった。

## Why

このプロジェクトでは、他テナントの存在を露出しないために queryset 側で先に絞る箇所がある。

## Pattern

Tenant boundary / QuerySet / 403-vs-404

## Found By

Human

## Missed By

Claude / ChatGPT

## Next Check

権限チェック前に visible_*_qs で対象が消えていないか確認する。

## Related

- Issue:
- PR:
- Decision:
```

---

## 記録するタイミング

### 記録する

* AIの予測が外れた
* 人間の予測が外れた
* Claude と ChatGPT の判断が分かれた
* マルチテナント境界の見落としがあった
* 認可・認証・queryset・migration・非同期処理で危険な発見があった
* 次回同じ種類のIssueで再発しそう
* プロジェクト固有の設計判断が明らかになった

### 記録しない

* 単なる作業ログ
* 一般的なDjango/Python知識
* そのIssueでしか使わない一時的な判断
* すでに design brief / decision / README に明確にある内容
* AIが自動生成しただけの反省文
* 人間が驚いていないこと

---

## 運用フロー

### Step 1: 驚きが発生する

例:

* 「403 だと思ったら 404 だった」
* 「AIがpermissionだけ見てselectorを見落とした」
* 「M2Mのexcludeが直感と違った」
* 「soft deleteしたのに別導線にinactiveが残った」

---

### Step 2: 人間が最小メモを書く

人間はまず3行だけ書きます。

```md
Predicted:
Reality:
Why:
```

余裕があれば次も書きます。

```md
Found By:
Missed By:
Related:
```

---

### Step 3: AIに整形させる

AIに Prediction Correction 形式へ整形させます。

このとき、AIに複数エントリを自動生成させません。
候補は原則1件だけです。

---

### Step 4: 人間が残すか判断する

Issue完了時またはPR前に、次の基準で判断します。

> このエントリは、3か月後のAIに読ませても探索開始点を変えるか？

Yes なら保存します。
No なら保存しません。

---

### Step 5: INDEX.md に1行追加する

個別エントリを保存したら、`INDEX.md` に1行だけ追加します。

---

### Step 6: 10〜20件溜まったら横断整理する

10〜20件溜まるまでは、集計やBias Profileを作りません。

十分に件数が溜まったら、AIに横断整理させます。

見るもの:

* よく出る Pattern
* 再発している見落とし
* 人間が弱い観測領域
* Claude が弱い観測領域
* ChatGPT が弱い観測領域
* 毎回AIに渡すべき短い注意文
* archive してよい古いエントリ

---

## 圧縮・濾過のタイミング

### 1. 入力時

最も重要です。

「驚きがないものは書かない」
「一般知識は書かない」
「AIに勝手に増やさせない」

---

### 2. Issue完了時

保存前に1回だけ濾過します。

判断基準:

```text
3か月後のAIに読ませても役に立つか？
```

---

### 3. 10〜20件蓄積時

個別エントリを横断して、上位要約を作ります。

この段階で初めて、以下を作ります。

* `views/heuristics.md`
* `views/bias_profile.md`
* `views/pattern_summary.md`

---

### 4. 前提変更時

リファクタや仕様変更で前提が変わったエントリは `archive/` に移します。

削除はしません。
ただし、通常参照対象からは外します。

---

## AIに渡すプロンプト

### エントリ作成用

```md
以下の出来事について、AI Memory の Prediction Correction エントリ候補を1件だけ作ってください。

制約:
- 一般的なDjango知識は書かない
- このプロジェクト固有の前提、例外、見落としだけ書く
- 長文にしない
- Next Check は1行だけ
- 不要だと思う場合は「記録不要」と判断する
- 複数エントリを勝手に生成しない

入力:
- Predicted:
- Reality:
- Why:
- Found By:
- Missed By:
- Related Issue:
```

---

### AIレビュー時の参照用

```md
まず docs/ai_memory/INDEX.md だけを読んでください。

今回のIssueに関係しそうなエントリがある場合のみ、最大3件まで候補を挙げてください。
候補がなければ「関連メモなし」としてください。

個別エントリ本文は、必要と判断したものだけ読んでください。
一般論としてのDjango/Python知識ではなく、このプロジェクト固有の補正情報だけを使ってください。
```

---

### 横断整理用

```md
docs/ai_memory/entries/ 配下のエントリを横断し、以下を整理してください。

目的:
- 次回以降のAIレビュー品質を上げること
- 人間・Claude・ChatGPTの見落とし傾向を把握すること
- 毎回読むべき短いHeuristicsを抽出すること

出力:
1. よく出る Pattern
2. 再発している見落とし
3. AIに毎回渡すべき注意
4. archive 候補
5. まだ結論を出すには件数不足のもの

制約:
- 件数が少ないものを傾向として断定しない
- Bias Profile は仮説として書く
- 個別Issueの詳細説明に寄せすぎない
```

---

## 代表的な Pattern

初期候補として、以下を使います。

```text
Tenant boundary
Permission / Scope
QuerySet visibility
Soft delete
M2M / JOIN
Migration
Transaction / on_commit
Lost Update
Role object
Open Redirect
Form validation
Async / external service
Test expectation outdated
Scope creep
Naming mismatch
```

Pattern は厳密な分類ではありません。
検索と横断整理のためのタグです。

---

## 運用上の注意

### AIに全部読ませない

毎回 `entries/` 全文を読ませないこと。
まず `INDEX.md` だけを読ませます。

---

### メモリを増やすこと自体を目的にしない

記録数が多いほど良いわけではありません。
むしろ、低品質な記録はAIの推論を汚します。

---

### 人間用ドキュメントと混同しない

これは、通常の設計資料ではありません。

* Issue: 何をなぜやるか
* Design Brief: 設計判断前の整理
* Decision: 決めたことの記録
* AI Memory: AIの次回推論を補正する記録

役割を混ぜないこと。

---

### AI Bias Profile を早く作らない

数件の印象で、

* Claude はこう
* ChatGPT はこう
* 自分はこう

と決めないこと。

Bias Profile は最低でも10〜20件溜まってから、仮説として作ります。

---

## 完了条件

この運用が成立している状態は、次の条件を満たすことです。

* 人間が記録トリガーを握っている
* AIが勝手にメモリを量産していない
* `INDEX.md` だけで全体像が分かる
* 個別エントリは短く、Prediction Correction に統一されている
* 10〜20件溜まるまで過剰な集計をしていない
* 一般的なDjango/Python知識が混入していない
* 次回AIレビューで「まず見る場所」が少しでも改善されている

---

## この運用の一言要約

AI Memory は、作業ログではない。
AIに知識を詰め込む場所でもない。

**人間やAIの予測が外れた瞬間を記録し、次回の探索開始点を補正するためのプロジェクト固有メモリである。**
