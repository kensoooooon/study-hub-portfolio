# README_AI.md

> This is the AI-reading-order document used in the private development repository, reproduced here almost verbatim. See [`docs/ai_workflow/README.md`](README.md) for context.

## Purpose

This file explains how AI assistants should use the documents in this repository.

Do not read all documents by default.

Use this file to decide which documents are relevant to the current task.

The goal is to reduce search space, not to increase context size.

---

## Basic Rule

Always start from the current user request or Issue.

Then read only the documents that are directly relevant.

Documents are guides, not absolute truth.

If documents and current code differ, check the current code, tests, and Issue scope.

---

## Reading Order

Use this order:

1. Current user request or Issue
2. Relevant source files
3. Relevant tests
4. Relevant docs only when needed
5. `docs/ai_memory/INDEX.md` only when the task may match past failure patterns
6. Individual AI Memory entries only when clearly relevant

Do not load all files under `docs/`.

Do not load all files under `docs/ai_memory/entries/`.

---

## Document Types

### Design Brief

Location: `docs/design_brief/`

Use when:

* the task involves design choices
* the scope is unclear
* there are multiple possible approaches
* the user asks for design review
* implementation should not start yet

Purpose:

* clarify goal
* clarify background
* clarify constraints
* surface uncertainty
* avoid premature implementation

A Design Brief is not final truth.
Check the current Issue and code before using it as a basis for implementation.

---

### Work Item

Location: `docs/work_items/`

A Work Item contains repository-backed Issue and plan documents for changes whose context cannot be represented safely by a single GitHub Issue or PR.

Use when at least one is true:

* the user refers to a specific Issue number, plan file, or work-item directory
* continuing an existing multi-step change
* reviewing whether implementation matches an Issue or plan
* the work is divided across multiple Issues or PRs
* migration, deployment, backup, rollback, or compatibility order matters
* a later Issue depends on decisions or completion conditions from an earlier Issue

If none apply, do not create a Work Item directory. Record the change in a single GitHub Issue or PR instead.

This is a sub-order within step 4 of the global Reading Order ("Relevant docs only when needed"). It does not replace global steps 2–3 (source files, tests) — for a Work Item task, still read the relevant source files and tests; do not treat these documents as a substitute for the code (see Basic Rule).

Read order:

1. The current user request
2. The current GitHub Issue or corresponding repository Issue file
3. The Work Item `README.md`, including its Archive Log
4. Only the `current` Issue and plan files (see Document status below)
5. Archived documents (under `_archive/`) only when investigating revision history or the reason for a change — and only the specific entry referred to, not the rest of the archive file

Do not:

* load every directory under `docs/work_items/`
* load every file in the selected Work Item
* open a document under `_archive/` merely because a pointer to it exists in the document you are reading; open it only when the current task already falls under an existing "investigate history" condition (this Read order item; Decision's "the user asks why something was designed that way"; a conflict surfaced by the Risk-First Planning Rule's document-comparison step)
* treat a plan as more authoritative than the current Issue, current code, tests, or explicit user instruction
* assume an old plan is still active
* use another Work Item merely because it concerns the same app or model

---

#### Document Lifecycle Rule

A current document (Issue, Plan, Decision, Research/Report) must accurately describe its subject — either the active instruction for work not yet done, or an accurate record of a completed phase — and must not retain procedure that matches neither (see the archive trigger below).

A Decision may keep a concise statement of rejected alternatives and why they were rejected (see Decision's Purpose below); this is rationale, not procedure, and it stays in the body.

Do not keep operational content for a rejected or superseded approach — runbooks, checklists, step-by-step procedures, Go/No-Go conditions, rollback instructions, or a step-by-step investigative process (e.g. "we searched, found X, then re-searched and found Y instead") — in the body of a current document, whether it belonged to a formally rejected alternative or to an earlier draft of the approach that was ultimately adopted. Leave at most a short pointer explaining what changed.

Archive when a current document's body still contains procedure of this kind that is no longer the current instruction. This is the only trigger; do not archive rationale merely because it explains an earlier stage of reasoning (see above). None of the following is, by itself, a reason to archive:

* an Issue being closed on GitHub — Issue status and document status are separate axes (see Document status below)
* a completed phase's Issue or Plan, as long as its procedure still matches what was actually executed
* writing a new Decision — archive only the specific procedure it superseded, not the whole prior Decision
* a Research/Report document that is still current supporting evidence for an active decision

When archiving:

* move the superseded content into that Work Item's `_archive/<same file name>.md` (`docs/work_items/<item>/_archive/`), appending to that file if it already exists, instead of creating a new file per removal or deleting the content
* give the archived entry a short dated heading (e.g. "2026-07-24 Checkpoint D") and a one-line note that it is archived and no longer current, pointing back to the current file for the current approach
* move the content as-is; do not summarize or compress it
* record the move in the Work Item `README.md` Archive Log: one line per move, with date, file, and reason
* leave a pointer in the current document — one short sentence with the date, the reason, and the archive entry's heading — only when the removed content touched a High-Risk Area (above), a rollback, migration, or deployment procedure, or was large enough that its absence could make the current document look self-contradictory or like a broken prior commitment. Otherwise the Archive Log entry alone is sufficient; no in-body pointer is required
* the first time a Work Item's `_archive/<file>.md` is created, add a one-line header noting that it accumulates archived entries and that a reader should jump to the specific dated entry referenced rather than read the file sequentially
* before reporting archiving work as complete, re-read the bullets above and check the Archive Log and any in-body pointers against them one by one — one Archive Log line per archived entry (not per file or per session), and each required pointer carries date, reason, and the archive entry's heading, matched against what the heading actually says. Do this by re-reading the bullets themselves, not from memory of them.

`_archive/` is outside the default read order (see Read order and Do not above). Do not open a document under `_archive/` merely because a pointer to it exists; open it only when the current task already falls under an existing "investigate history" condition (Read order item 5; Decision's "the user asks why something was designed that way"; a conflict surfaced by the Risk-First Planning Rule's document-comparison step). The pointer makes that investigation precise once it is already warranted — it does not by itself create a reason to investigate.

After opening an archived entry, re-read the current document's active procedure for the same topic before taking any action. Do not carry archived content forward as current; the archive visit is not complete until the current document has been reconfirmed.

Document status is a separate axis from Work Item status:

* Work Item status (`draft` / `active` / `completed`, below) describes the whole initiative.
* Document status is `current` or `archived` only. A document is `current` while it lives outside `_archive/`, and `archived` once moved into `_archive/`. Do not introduce further document-level status values (`completed`, `superseded`, `historical`, etc.); record the specific reason for archiving as one line in the Archive Log instead.

Claude may propose that a document or section be archived, citing the specific later decision or Issue that superseded it. Do not move, delete, or rewrite the file without the human maintainer's explicit approval.

For a new Work Item, reuse the file layout of existing items (`README.md`, Issue file(s), Plan file(s), optional Research/Report, `_archive/`). Add a template under `docs/markdown_templates/` only once this layout has proven reusable across multiple Work Items.

---

#### Correction and AI Memory Trigger

A factual correction (a wrong date, a wrong Issue mapping, a wrong file count, and similar errata) is neither procedure nor rationale. Fix it in place. Do not retain "this used to say X" prose in the body of a current document — git history is the record of the correction.

Propose an AI Memory candidate (do not create the entry yourself; follow the AI Memory Rule below) only when at least one of the following holds:

* the incorrect content was actually relied on as fact by another document, decision, plan step, or scope boundary before being caught
* it touches a High-Risk Area (above), and the correction is not co-located with the error — a reader would need to reach a different file, or a later and non-adjacent passage, to learn it was wrong

If neither holds, fix the error and move on without further note.

If the human maintainer accepts the proposal, the resulting entry lives only in `docs/ai_memory/`. Do not add a correction note to the Work Item document itself.

---

Each Work Item should have a `README.md` that identifies:

* the parent Issue
* the goal
* the current phase
* the active Issue and plan
* completed phases
* the expected work order
* relevant Decisions
* an Archive Log (date, file, reason — one line per archived document or removed section)

Status meanings (Work Item level):

* `draft`: not yet approved as the current work basis
* `active`: currently used for implementation or review
* `completed`: finished and retained as a record

#### Work Item Completion Check

The purpose of a Work Item's documents is to keep ongoing work coherent. Once
work has genuinely ended, they are normally not read again. The one exception
is rework: someone later needs to reconstruct the judgment criteria, the
reasoning, and the sequence of a decision, in a case where GitHub history
alone cannot show it. This check exists only to keep that one scenario
working — it is not a general tidiness pass, and it is not a reason to
restructure or archive documents that are already correct.

Before marking a Work Item `completed`, at that phase's natural end point:

* confirm the Work Item `README.md`'s current-location pointer correctly
  names the Decision document(s) — and section, if more than one applies —
  that hold the final rationale a future rework investigation would need
* confirm no open item under "human judgment needed" (or equivalent) was
  silently dropped; if one remains unresolved, ask the human maintainer
  whether to resolve it now or record it explicitly as an accepted open
  question before completing — do not decide this alone

Do not use completion as a trigger to archive Plan or Issue files that still
match what was executed (see the Document Lifecycle Rule above), and do not
create a separate rework-only document to consolidate this information — the
Decision document is the single owner of rationale (see the Single-Owner Rule
above); keep it accurate rather than duplicating it elsewhere.

GitHub remains the source of truth for Issue status, discussion, and Close state.

Repository files within a Work Item each have one responsibility, beyond what
README.md's required contents (above) and the named rules below cover:

* **Issue**: records scope, completion criteria, and constraints when durable
  context is required.
* **Plan**: records the intended execution order and safety checkpoints. Not
  proof that the implementation followed the plan.
* **Research/Report** (optional): records the investigation findings and
  evidence available at the time of writing — the observations, code trace
  results, and data a Decision was based on. Frozen; not re-verified or kept
  in sync with later decisions. When later work supersedes a conclusion, add
  a short dated note pointing to the current source instead of rewriting the
  original findings (see `research-65-impact-analysis.md` for the pattern).
  Stays current — not archived merely for being old — as long as it is still
  cited as supporting evidence for an active Decision.
* **Archive** (`_archive/`): holds superseded procedure and historical
  revision narrative that no longer describes the current instruction, or
  content displaced by the Single-Owner Rule below. Not a place for content
  that is merely old but still accurate.

#### Single-Owner Rule for Procedures

A concrete step-by-step procedure — a Runbook, a numbered sequence of commands,
checks, or deployment steps — has exactly one owning document per Work Item.
Decide the owner by the Purposes above: Plan owns the steps; Decision owns the
rationale for why the steps are ordered or constrained that way; Issue owns the
scope and completion criteria the steps satisfy. Neither of the other two
restates the numbered steps themselves — they reference the owning document by
file name and section heading instead.

This is a separate concern from the Document Lifecycle Rule above. That rule is
about staleness (current vs. superseded); this rule is about ownership (current
vs. current). Two documents can each accurately describe the current
instruction and still violate this rule if both hold the same steps — that is
not something the archive trigger catches, so do not rely on it here.

When the same procedure appears verbatim in more than one current document,
consolidate it into the owning document and replace the copies with a pointer
(file name and section heading). This is a content edit, not an archive move —
it does not go through `_archive/` or the Archive Log, since none of the copies
were ever superseded; one was simply redundant.

---

### Decision

Location: `docs/decisions/`

Use when:

* the task touches an area with past design decisions
* the reason for an existing structure is unclear
* changing behavior may violate a previous decision
* the user asks why something was designed that way

Purpose:

* record what was decided
* record why it was decided
* record rejected alternatives, as concise rationale — not as retained runbooks, checklists, or procedures for the rejected option (see Document Lifecycle Rule above)
* preserve future review context

A Decision explains past intent.
It does not automatically override the current Issue, current code, or current security requirements.

---

### AI Memory

Location: `docs/ai_memory/`

Use when the task may involve a repeated prediction failure.

Examples:

* tenant boundary
* permission vs scope
* queryset visibility
* soft delete
* M2M or JOIN behavior
* migration and existing data
* transaction or `on_commit`
* role object assumptions
* outdated test expectations

Read order:

1. `docs/ai_memory/INDEX.md`
2. Only the individual entries that are clearly relevant

Never load all AI Memory entries by default.

---

#### AI Memory Rule

AI Memory is not a general knowledge base.

It records project-specific cases where human or AI prediction failed.

Use it to adjust where to look first.

Do not use it as implementation instructions without checking the current code.

---

#### When Creating AI Memory

Create an AI Memory entry only when the human maintainer identifies a meaningful surprise or repeated risk.

For a factual correction found while working in a Work Item document, see Correction and AI Memory Trigger (under Work Item) for when to propose a candidate.

Do not proactively create AI Memory entries after every task.

Do not automatically generate multiple entries.

The human maintainer should provide at least:

* Predicted
* Reality
* Why

Claude may draft the following fields for human confirmation:

* Pattern
* Found By
* Missed By
* Next Check
* Related

Use Prediction Correction format:

* Predicted
* Reality
* Why
* Pattern
* Found By
* Missed By
* Next Check
* Related

Do not record general Django or Python knowledge.

If the human asks whether an event should be recorded and it is not reusable, say:

`記録不要`

---

#### AI Memory Editing Scope

For AI Memory entry creation, edit the files in the main project working tree directly.

Do not create or switch to a separate git worktree unless explicitly requested.

Only the following paths may be edited:

* `docs/ai_memory/entries/`
* `docs/ai_memory/INDEX.md`

Do not edit application code, tests, migrations, settings, URLs, templates, or global AI instruction files unless explicitly requested.

Do not commit or push.


---

## High-Risk Areas

When reviewing or implementing, pay special attention to:

* organization boundary
* classroom boundary
* role boundary
* queryset filtering
* soft delete and `is_active`
* inactive user sessions
* LINE account and organization binding
* invitation and authentication flows
* open redirect
* migration effects on existing data
* tests that encode outdated expectations

---

## Risk-First Planning Rule

### Purpose

The Risk-First Summary is a decision gate, not a general summary of the plan.

Its purpose is to prevent external state changes, production risks, authorization risks, and unresolved human decisions from being buried inside long plans or reviews.

The instruction language is English, but the three required labels are Japanese so that the human maintainer can identify them immediately.

---

### Required Opening Format

For applicable tasks, begin the response with exactly these three labels:

* 【状態変更・ロールバック】
* 【運用・データ・権限リスク】
* 【人間が判断すべき事項】

The complete opening summary must be 3–5 lines.

Do not place an introduction, heading, acknowledgment, or general conclusion before these three items.

Detailed procedures, file lists, background, test plans, and commands must appear after the opening summary.

Use:

* `該当なし` only when the category has been checked and no relevant item exists
* `未確認` when the available code, data, environment, or current state is insufficient for a reliable judgment

Do not use vague text such as `注意が必要` without naming the concrete risk.

---

### 1. State Changes and Rollback

Under `【状態変更・ロールバック】`, identify:

* external state that will actually change in the current task
* external state changes planned only for a later phase
* operations that leave permanent history, identifiers, or audit records
* the method required to undo each operation
* the point after which the previous application version can no longer safely run
* whether rollback requires another migration, data restoration, redeployment, manual correction, or GitHub operation

Do not classify an operation only by its name.

Examples:

* Closing a GitHub Issue is reversible by reopening it, but the close event and comments remain in history.
* Creating a GitHub Issue leaves a permanent Issue number and history even if the Issue is later closed.
* A schema migration may be technically reversible while its deleted or transformed data is not recoverable.
* Adding a NOT NULL constraint may be reversible, but rollback to an older application version is unsafe if that version does not write the required field.
* Renaming a local document is reversible in Git, but references in GitHub Issues or other documents may require separate correction.
* Deploying a new version may be reversible only while the database schema and write behavior remain backward compatible.

Explicitly distinguish:

```text
current task operation
planned later operation
approved operation
unapproved operation
```

---

### 2. Operational, Data, and Authorization Risks

Under `【運用・データ・権限リスク】`, check at least:

* compatibility with currently deployed and older application versions
* all write paths before and after a migration
* backfill correctness
* missing, duplicated, reassigned, or partially migrated data
* organization and classroom boundaries
* role boundaries
* queryset and selector scope
* object-level authorization
* permission escalation
* inactive users and existing authenticated sessions
* rollback behavior after new data has been written
* intermediate states caused by external-service failure
* whether tests encode an outdated behavior rather than the intended behavior

For multi-tenant changes, explicitly check whether a user can access or modify data belonging to:

* another organization
* another classroom
* an unassigned or unrelated user
* a record that is hidden from the user’s normal queryset

A permission check does not replace queryset or selector scoping.

A successful form or view test does not prove tenant safety.

---

### 3. Decisions Reserved for the Human Maintainer

Under `【人間が判断すべき事項】`, surface decisions involving:

* What and Why
* responsibility and ownership
* tenant and authorization boundaries
* business meaning of deletion, transfer, reassignment, merge, or replacement
* completion criteria
* out-of-scope work
* Issue and PR boundaries
* deployment units
* observation periods
* rollback policy
* acceptable irreversible boundaries
* production rollout order
* handling of inconsistent existing data

Do not infer these decisions merely because one implementation is technically simpler.

If a decision has already been explicitly approved in the current Issue, Decision document, or current user instruction, identify it as approved rather than presenting it again as unresolved.

If documents conflict, do not silently choose one. Compare:

1. the current user instruction or Issue
2. current code and tests
3. the relevant Decision
4. older plans and work-item documents

Then state the conflict.

---

### Stop Conditions

Stop before implementation or external state changes when an unresolved decision can materially affect:

* organization, classroom, or role boundaries
* authorization behavior
* data ownership
* migration results
* production availability
* rollback viability
* Issue or PR scope

In that case:

1. describe the unresolved decision
2. present the realistic options
3. explain the consequence of each option
4. identify the safest default, if one exists
5. do not execute the affected operation

Do not stop for minor wording, naming, or formatting choices that do not affect behavior or scope.

---

### Good Example

```text
- 【状態変更・ロールバック】新規Issueは番号と履歴が残る。#12・#13は再オープン可能だが、supersededとしてのコメント履歴は残る。
- 【運用・データ・権限リスク】Expand内でNOT NULL化すると、FKを書かない旧App Engineバージョンへ安全にrollbackできなくなる。
- 【人間が判断すべき事項】Expandを1 Issueに保つ判断と、1回のdeployで実施する判断は別であり、deploy境界は未確定。
```

---

### Bad Example

```text
- 【状態変更・ロールバック】Issueを変更する。
- 【運用・データ・権限リスク】注意が必要。
- 【人間が判断すべき事項】作業順を決める。
```

The bad example names categories but does not expose the actual decision or risk.

---

### Relationship to Other Documents

The Risk-First Summary does not replace:

* a Design Brief
* a Decision document
* an Issue
* an implementation plan
* deployment verification
* backup and restore procedures
* tests

It is the compact human-facing checkpoint placed before those details.

Use the current Issue or user instruction to determine scope.

Use Decision documents for approved design rationale.

Use work-item documents for investigation and implementation detail.

Use current code, tests, and production facts to verify whether the documented assumptions are still valid.

---

## Review Priorities

For review tasks, check in this order:

1. Scope
2. Tenant boundary
3. Authentication and authorization
4. QuerySet filtering
5. Soft delete and active status
6. Existing data and migrations
7. Tests
8. Unrelated changes

Do not start by improving code style if access boundaries are unclear.

---

## Implementation Priorities

Before implementation, confirm:

* what problem is being solved
* what is out of scope
* what the completion criteria are
* which tenant boundary is involved
* which roles are allowed
* which data must not be visible
* which tests should protect the behavior

Do not decide these on behalf of the human maintainer unless explicitly asked.

---

## What Not To Do

Do not:

* read every document
* treat docs as more reliable than current code
* mix unrelated improvements into the current branch
* expand the scope beyond the Issue
* create AI Memory entries without a clear reusable surprise
* load all AI Memory entries into context
* use general best practices to override project-specific constraints without checking
* assume `@login_required` blocks inactive users with existing sessions
* assume permission checks automatically define object scope
* assume a passing form or view test proves tenant safety

---

## Git and PR Discipline

Branches should normally be created from `develop`.

PRs should normally target `develop`.

Use PRs to compare:

Issue scope
↓
Actual diff

Before PR, check:

* `git status`
* test results
* unrelated file changes
* migration impact
* security and tenant boundaries

---

## Test Expectations

For behavior changes, add or update tests.

For bug fixes, prefer regression tests.

For authorization or tenant-boundary changes, include tests for:

* same organization allowed
* other organization denied
* same classroom allowed where appropriate
* other classroom denied where appropriate
* unauthenticated user behavior
* wrong role behavior
* inactive user behavior when relevant

---

## How To Use AI Memory During Review

When reviewing an Issue or PR:

1. Identify the main risk pattern.
2. Check `docs/ai_memory/INDEX.md`.
3. If a clearly relevant entry exists, read that entry.
4. Apply its `Next Check`.
5. Do not read unrelated entries.

AI Memory should narrow the review focus.
It should not replace source-code inspection.

---

## One-Line Summary

Use docs as a map, not as bulk context.
