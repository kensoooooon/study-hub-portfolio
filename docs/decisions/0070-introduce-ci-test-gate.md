# 0070: CIによるテストゲート導入(developとmasterへのPRでテスト必須化)

Status: proposed
Date: 2026-07-12
Related Issue: #70
Related PR:
Tags: testing, deployment

---

## Context

- これまで手動実行に依存しており、実行し忘れたままdevelop/masterへマージされうる状態だった
- 今後、組織管理者と組織の関係見直しなど、認証・権限・マルチテナント境界に影響する大きな変更を予定している
- 通常運用は「develop側で機能ブランチを切って開発→developへ統合・デプロイ→修正を取り込みつつmasterへ統合」という流れ。一方でhotfixはmasterから直接ブランチを切り、最優先で本番へ戻す例外フローが存在する
- テストコマンド(`python manage.py test`)、Python 3.12、PostgreSQL 14系、`requirements.txt`からの依存関係導入は、既存の開発環境・本番環境(Cloud SQL 14.22)にほぼ自動的に合わせた技術的前提であり、本Decisionの論点ではない。実装詳細は`.github/workflows/ci.yml`を参照

---

## Decision

- develop・master向けのPull Requestに対してCIで全体テストを自動実行し、失敗時はマージ不可にする
- 現時点は個人開発であるため、Required status checkとバイパス禁止のみを設定し、「Require branches to be up to date before merging」は有効化しない

---

## Options

### A. develop・master双方のPRでテスト必須化 + 失敗時マージ禁止

結果: 採用

理由:
- 通常フロー(develop経由)とhotfixフロー(masterから直接分岐)の両方が存在し、全ての変更が必ずdevelopを経由するわけではないため、developだけにゲートを置くとhotfix側でテスト未実行のマージが起こりうる
- masterでも修正が入ることがある(developへの取り込みを待たない変更の可能性)ため、両ブランチに同じ最低限のゲートを置く

懸念:
- CI実行時間分、マージまでのリードタイムが伸びる。個人開発のため許容

### B. Required branches to be up to date before mergingも有効化する(Strict運用)

結果: 不採用

理由:
- 現時点は個人開発であり、同時並行のPRがほぼ発生しないため、up-to-date強制による手戻り(頻繁なrebase/マージ待ち)のコストが実益に見合わない

懸念:
- 複数人開発や同時進行PRが増えた場合、developが古い状態のままマージされ、直前のマージ内容との組み合わせテストがされずに問題が混入するリスクがある

### C. CD/デプロイ自動化、Lint(ruff/mypy)、カバレッジ基準、テスト高速化も同時に導入する

結果: 不採用

理由:
- 理想を言えばCDやLintも導入したいが、どこまでの先行投資が妥当か(オーバーエンジニアリングになる境界)をまだ見極められていない
- 見極めがつくまでは、最も安価な形(テスト実行の自動化とマージ制御のみ)でまず導入し、実運用の中で必要性が明確になった仕組みから追加していく方が、投資対効果を判断しやすい

懸念:
- Lint・カバレッジ等がないため、CI導入後もコードスタイルや品質のばらつきは別途残り続ける

---

## Criteria

- 個人開発というプロジェクト規模に見合った運用負荷か
- 将来複数人開発になった際に破棄・拡張しやすいか(ロールバック容易性)
- Issueのスコープを超えていないか

---

## Consequences

良い影響:
- develop・masterへのマージ前に機械的なテスト実行が担保され、テスト未実行のままのマージを防止できる
- hotfixのようにdevelopを経由しないフローでもテストゲートが働く

悪い影響:
- up-to-dateを強制しないため、developの最新コミットとPRブランチが乖離した状態でマージされる可能性が残る。個人開発下では実害が小さいと判断
- CD・Lint等は未導入のままであり、テスト以外の品質・デプロイ面の課題は引き続き残る

---

## Follow-up

- 複数人開発や同時進行PRが増えた場合、「Require branches to be up to date before merging」の有効化を再検討する
- 運用中に事故(テストが通ったはずの変更で問題が起きた、マージ制御をすり抜けたなど)が発生した場合、本Decisionの内容を見直す
- CD、Lint(ruff/mypy)、カバレッジ基準は、必要性が明確になった時点で別Issueとして検討する
- ブランチ保護ルール(Required status check・バイパス禁止)はGitHub Web UI上で人手により設定する(リポジトリ管理者権限が必要なため)
- CI導入によって発見された、外部サービス呼び出しの未モック等の既存不具合は本Issueでは修正せず、都度報告のうえ別Issue化を判断する
- ブランチ保護ルール設定時、「Block force pushes」「Restrict deletions」もあわせて有効化した。これらは通常のPRベースの運用フローにコストを発生させない一方、develop・masterへの誤ったforce push・誤削除という、テスト未実施のマージとは別の事故を防ぐための安全策であり、Issue #70の主目的(テストゲート)とは別軸の判断として記録する
- ブランチ保護ルール(Required status check・バイパス禁止)は、Rulesets・Classic branch protection rule いずれもprivateリポジトリの現プラン(GitHub Team未満)では実効されないことが判明した。管理者へプラン変更の可否を打診中で、判断が出るまでIssue #70の完了条件のうち「テスト失敗時のマージ不可化」「意図的失敗によるマージ阻止の確認」は本Issueのスコープから除外し、判断が出た後に別途対応する
