# 2026-6-28: 分割必須化について

Status: rejected
Date: 2026-6-28
Related Issue: #35
Related PR:
Tags: tenant | authorization | security | database | testing

---

## Context

- claudeに調査してもらったところ、studentのように広くテストが散らばっていなかった
- テスト構成としても、どちらか片方ではなく、両方が揃っているものが多かった

---

## Decision

- いったん全ファイルを触ってもらいチェックし、テストを実行してから考える

---

## Options

### A. 講師の必須かと教室管理者の必須化を分割して行う

結果: 不採用

理由:
- issue 34から想定したほどblast radiusが大きくならないと予想されたため

懸念:
- 実際のところはテストを追加してみないと語れない


---

## Criteria

- 既存の運用を壊さないか
- 私もAIも確認できていないが、テストで発覚する漏れがどれくらいあるか
- 分割することによるメリットとデメリットはどうか


---

## Consequences

良い影響:
- 一回のissueで処理が済む

悪い影響:
- 確認すべき範囲が増える

---

## Follow-up

-
