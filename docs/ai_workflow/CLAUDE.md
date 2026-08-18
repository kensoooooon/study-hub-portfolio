# CLAUDE.md

> This is the AI instruction file (`CLAUDE.md`) used in the private development repository, reproduced here almost verbatim. Content specific to the maintainer's local development environment (OS, virtual environment name, local database proxy settings) has been omitted as out of scope for this narrative. See [`README.md`](README.md) for context.

## Project

Django Study Hub is a Django-based multi-tenant learning platform.

The tenant hierarchy is:

Organization -> Classroom

Teacher, Student, ClassroomAdministrator, and OrganizationAdministrator are roles scoped to this hierarchy, not additional tenant levels. Teacher and Student each belong to exactly one Organization (direct FK) and are assigned to Classrooms independently (both via ManyToMany). A Teacher is not a tenant parent of Student — do not gate Student access through Teacher; check Organization/Classroom directly.

Always preserve tenant boundaries. Never allow users to access students, passages, answers, progress records, reminders, or sessions outside their organization/classroom/assignment scope.

When implementing or reviewing access control, find the actual authorization logic in this order — do not derive it from the tenant hierarchy alone, since role-scoping details (e.g. OrganizationAdministrator's organization scope) are under active migration and the hierarchy above is a map, not a substitute for the code:

1. a dedicated access-control module for the app (e.g. `access_policies.py`, `*_access_check.py`)
2. model methods such as `can_be_accessed_by`, `can_manage_*`, `get_accessible_*`, or a `visible_*_qs` selector
3. only if neither exists, do not rely on the tenant hierarchy above as authorization logic. Ask the human maintainer before proceeding — an unresolved tenant, classroom, or role boundary is a Stop Condition (see Risk-First Planning Rule in `README_AI.md`), not something to infer from the hierarchy diagram alone

## Communication Language

Respond to the human maintainer in Japanese by default.

This rule applies to:

- explanations
- progress updates
- summaries
- questions
- review findings
- risk-first summaries

Keep code, identifiers, file paths, commands, log output, and quoted repository text in their original language.

When creating or editing repository documents, follow the existing language of the document unless the user explicitly requests a specific language.

Use a language other than Japanese for human-facing communication only when the user explicitly requests it.

## Work Delivery Workflow

- Claude works in the assigned worktree.
- After finishing, reflect the result into the project side (the main, non-worktree checkout) by copying the changed files, or applying the diff — do not use `git merge` for this: a fast-forward merge commits the changes immediately and skips the review step below.
- After reflecting, stop before add/commit/push. Leave the diff uncommitted so it can be reviewed in VS Code.
- The human performs add, commit, and push.
- Exception: for changes that are clearly minor, Claude may go all the way through commit and push, but only when the human explicitly instructs it to do so for that specific change.

## Migrations

- Changing model structure (fields, `Meta.permissions`, etc.) requires a migration. Deploying new code does not apply it — run `manage.py migrate` against the target database as a separate step, including production.

## Important security rule
- Student soft delete uses is_active=False.
- Do not assume @login_required blocks inactive users with existing sessions.
- Student-facing views must explicitly reject inactive students.
- Admin-facing queries should use active students unless the feature is explicitly for restore/audit.
- Prefer Student.objects.active() or project selectors over Student.objects.all().
- URL direct access must be checked by tenant boundary and active status.

## M2M write-surface rule

When an M2M relation enforces a tenant, role, or data-integrity boundary (an `m2m_changed` receiver, a permission check, or a queryset filter depends on it), do not reason from the declared side alone. Check:
- writes from the forward related manager (`a.b.add(...)`)
- writes from the reverse related manager (`b.a_set.add(...)`) — `m2m_changed`'s `instance`/`pk_set` swap depending on which side called `.add()`/`.set()` (see the `reverse` kwarg)
- whether the through model can be written directly (e.g. an admin inline), bypassing the related manager and `m2m_changed` entirely

Does not apply to M2M relations with no tenant/role/integrity role (plain UI tagging, display-only groupings).

## Mechanical Edit Rule

When performing a bulk or mechanical edit (e.g. `replace_all`, find-and-replace across matches), the set of locations that match the search string is not guaranteed to equal the set of locations that are semantically in scope for the intended change — especially for short, generic, or frequently-repeated expressions.

- Before relying on such a match, consider whether the same string could also appear in an unrelated context with a different meaning (this matters most for authorization, tenant-boundary, or other code where similar syntax can govern different roles or entities).
- This does not require an exhaustive search up front — a brief check of whether the match is likely to be ambiguous is enough.
- Always review the resulting diff afterward to confirm no unintended location was changed; the diff review is the final backstop.

## Exhaustive Search Note

A task whose completion condition is "zero unclassified matches across the repository" (e.g. "find every place X happens", "list all callers of Y") is different work from ordinary exploration or the Mechanical Edit Rule's bulk-edit review above — check `ai_memory/INDEX.md` for the `Search completeness` pattern before starting. When an authoritative execution channel exists (e.g. the test suite), use a full run as additional completeness evidence — not as a substitute for repository-wide enumeration when static coverage itself is the completion condition.

## Test Documentation Rule

When adding or modifying tests, add a concise Japanese docstring to each test method.

The docstring must explain:

* the condition or input being tested
* the expected behavior or result
* when relevant, whether the test is a regression test or a characterization test

A class docstring may explain the common purpose or background of the test group, but it does not replace the docstring for each individual test method.

Do not create a separate documentation file only to explain newly added tests unless the task explicitly requires one.

Example:

```python
@patch("accounts.models.BaseUser.get_role_object")
def test_get_role_object_or_403_with_none_causes_403(self, mock_role_object):
    """
    get_role_object()がNoneを返した場合に、
    アクセスを許可せずPermissionDeniedになることを確認する。
    """
    mock_role_object.return_value = None

    with self.assertRaises(PermissionDenied):
        get_role_object_or_403(self.org1_admin)
```

Characterization test example:

```python
def test_admin_assigned_to_another_organization_is_currently_shown_as_candidate(self):
    """
    別組織に所属済みの組織管理者が、現状では割当候補に表示されることを確認する。

    単一所属化前の現在の挙動を記録するcharacterization testであり、
    この挙動が正しい業務仕様であることを保証するものではない。
    """
```

## Documentation Reading Rule

Read `README_AI.md` when any of the following is true:

* the task involves docs, design review, decisions, Issue review, plan review, PR review, or AI memory
* the user refers to an Issue number, plan file, work item, or an ongoing multi-step change
* the task involves splitting work, ordering migrations or deployments, defining rollback points, or coordinating multiple Issues or PRs
* the task touches or may touch tenant/classroom/role boundaries, permissions, authentication, sessions, querysets, selectors, soft delete, `is_active`, M2M/JOIN behavior, migrations, transactions, or external integration boundaries

Do not load all docs or all work items by default.

Use `README_AI.md` as a guide to decide which document is relevant.

If the task is a trivial text, typo, formatting, Git-operation question, or isolated UI-only change, do not read additional docs unless the user asks.

## Risk-First Summary Rule

When creating, reviewing, or materially revising any of the following, read the `Risk-First Planning Rule` section in `README_AI.md`:

* an Issue or work item
* an implementation plan
* a design review
* a migration or data-migration plan
* a deployment or rollback plan
* a GitHub Issue or PR restructuring plan
* a multi-step plan involving permissions, tenant boundaries, production data, or external state changes

The response must begin with exactly these three Japanese labels:

* 【状態変更・ロールバック】
* 【運用・データ・権限リスク】
* 【人間が判断すべき事項】

Keep this opening summary to 3–5 lines in total. Put detailed procedures, file lists, background, and verification steps after the summary.

Do not omit a label. Write `該当なし` when there is genuinely no relevant item, and write `未確認` when the available information is insufficient to determine the risk.

Clearly distinguish:

* operations that will actually be performed in the current task
* operations that are only planned for a later phase
* decisions that have already been approved
* decisions that still require human judgment

If an unresolved decision can affect tenant boundaries, authorization, production data, rollback viability, deployment order, or Issue scope, do not infer the decision and continue. Present the available options and their consequences, then stop before implementation or external state changes.

Do not apply this format to trivial wording changes, typo fixes, simple information lookups, isolated formatting tasks, or routine Git command explanations.

During implementation of an already approved plan, do not repeat the full summary in every progress update. Surface it again only when a new risk, rollback boundary, or human decision is discovered.

## AI Memory Editing Rule

For AI Memory entry creation, follow `README_AI.md`'s AI Memory section in full,
including when creation is appropriate ("When Creating AI Memory") — not just the edit-scope rules.

Do not edit application code, tests, migrations, settings, URLs, or templates unless the user explicitly asks.
Do not commit or push.
