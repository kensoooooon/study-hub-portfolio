# Work Item 例: OrganizationAdministratorの単一組織FK化

> これは実プロジェクトで実際に運用しているWork Itemドキュメントの構成をそのまま使い、内容を一般化した例です。実際のIssue番号・PR番号・本番デプロイ日時は含めていません(架空の番号・日付で置き換えています)。テーマ自体([Organizationを後から必須化した際の技術的負債](../../../README.en.md#what-id-do-differently))はREADMEの「What I'd Do Differently」で触れている実際の課題です。

## 目的

`OrganizationAdministrator`と`Organization`の関係を、ManyToMany(複数組織を管理できる設計)から単一組織FK(1人の組織管理者は1組織のみを管理する、という実際の業務ルールに合わせた設計)へ移行する。

## 背景

初期実装では`OrganizationAdministrator.organizations`をM2Mとして定義していたが、招待フローや管理画面は実質「1組織管理者につき1組織」を前提にしたコードになっており、モデル定義と実際の業務ルールが食い違っていた。この種の「モデルはN:Nだが運用は1:Nを前提にしている」というギャップは、後から気づくとスキーマ変更・データ移行・後方互換性の三つを同時に扱う必要があり、段階を踏まずに一気に直すのはリスクが高い。

## 採択済みDecision

- `docs/decisions/example-organization-administrator-single-organization.md`(ドメイン決定: なぜ単一組織にすべきか)
- `docs/decisions/example-organization-administrator-migration-strategy.md`(実装・移行戦略の決定: どの順番で・どう安全に移行するか)

## 作業順

Characterize(完了) → Expand → Switch → Contract

この4フェーズは、稼働中のスキーマを壊さずに設計変更するための型です。

1. **Characterize**: 現状のコードとデータの矛盾を調査し、影響範囲を確定する。まだ何も変更しない。
2. **Expand**: 新しい列・新しい経路を追加するが、旧経路も併存させる(後方互換を保ったまま拡張)。
3. **Switch**: 読み書きの主経路を新しい構造に切り替える。
4. **Contract**: 旧経路・旧カラムを削除し、構造を単純化する。

各フェーズを独立したIssue・独立したデプロイ単位にすることで、途中で問題が見つかった場合に「どこまで戻せばよいか」を常に明確にしておく。

## 現在

Characterize完了。Expand(新しいFK列の追加・招待停止ゲートの導入)は一部完了、残りのフェーズは未着手。

## 人間が判断すべき事項(未決)

なし。既存の招待フロー停止ゲートの要否は、代替案A(ゲートのみ導入し追加の権限剥奪は行わない)で確定済み。詳細は`docs/decisions/example-organization-administrator-migration-strategy.md`を参照。

## ファイル対応

| ファイル | 対応フェーズ |
|---|---|
| `issue-characterize.md` / `plan-characterize.md` | Characterize(完了) |
| `issue-expand.md` / `plan-expand.md` | Expand |
| `issue-switch.md` / `plan-switch.md` | Switch |
| `issue-contract.md` / `plan-contract.md` | Contract |
| `research-impact-analysis.md` | 影響範囲の一次調査記録 |

## Archive Log

Work Itemの各文書は「現在の指示として正しいか」を常に保つ。フェーズ構成の見直しなどで古い手順が現行文書に残ってしまった場合、その部分だけを`_archive/`へ日付付きで退避し、ここに1行で記録する(退避した理由も添える)。

例:

```text
2026-XX-XX plan-expand.mdの権限再剥奪に関するA/B比較検討 → _archive/plan-expand.md「Checkpoint 権限再剥奪 案A/B比較(決定前の検討時点)」(決定確定に伴い、決定前の検討過程が現行文書に残っていたため)
```

## この構成が示すもの

- **段階を踏むことでロールバック地点を常に確保する**: 一気に切り替えず、Expand/Switch/Contractを分離することで、途中で問題が出ても直前のフェーズまで戻せる
- **「決まったこと」と「まだ決まっていないこと」を分離する**: `人間が判断すべき事項`の節を常に更新し、未決事項を放置しない
- **文書の陳腐化を放置しない**: 古い手順は削除せず`_archive/`に退避し、いつ・なぜ退避したかをArchive Logに残す(検証可能性を保つ)
