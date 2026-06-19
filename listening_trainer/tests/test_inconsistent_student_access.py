"""
不整合生徒データに対する listening_trainer の現状アクセス挙動を固定する観察テスト。

対象の不整合状態:
    student.organization = None
    student.classrooms = [組織管理者の管理組織に属する教室]

    以上の状態になった際に、組織管理者の権限が教室管理者の権限を下回ることになる

このテストは現状挙動の観察テストであり、恒久仕様ではない。
テストが RED になった場合は挙動が変わったことを示す。

本番データ確認結果 (2026-06-18 時点):
    organization=None かつ classrooms あり: 0件
    不整合生徒の ListeningPassage 数: 0件
    → 現時点では該当不整合データによる実害は確認されていない。

採用方針: 方針A（厳格化）
    - visible_to() は organization=None を弾く現状挙動を維持
    - accounts 側フォールバックとの不整合は後続 Issue で整理する
    - Student.organization 必須化・フォールバック廃止は後続 Issue とする
"""

from django.test import TestCase
from django.core.exceptions import PermissionDenied
from django.http import Http404
from unittest.mock import patch


from accounts.models import (
    Organization,
    Classroom,
    OrganizationAdministrator,
    ClassroomAdministrator,
    Student,
)
from listening_trainer.models import ListeningPassage
from listening_trainer.access_check.student_access_check import ensure_can_access_student
from listening_trainer.access_check.passage_access_check import passage_access_check


class InconsistentStudentVisibleToObservationTest(TestCase):
    """
    student.organization=None かつ classrooms あり の不整合生徒に対して、
    教室管理者と組織管理者の visible_to() 挙動が非対称になることを確認する。
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="テスト組織")
        cls.classroom = Classroom.objects.create(name="教室A", organization=cls.org)

        # 不整合生徒: organization=None, classrooms=[教室A]
        cls.inconsistent_student = Student.objects.create_user(
            username="inconsistent_student_lt",
            line_user_id="inconsistent_student_lt_line_id",
            organization=None,
            is_active=True,
        )
        cls.inconsistent_student.classrooms.add(cls.classroom)

        # 教室管理者（教室A を管理）
        cls.classroom_admin = ClassroomAdministrator.objects.create_user(
            username="classroom_admin_lt",
            email="classroom_admin_lt@example.com",
            password="pass123456",
            organization=cls.org,
        )
        cls.classroom_admin.classrooms.add(cls.classroom)

        # 組織管理者（テスト組織 を管理）
        cls.org_admin = OrganizationAdministrator.objects.create_user(
            username="org_admin_lt",
            email="org_admin_lt@example.com",
            password="pass123456",
        )
        cls.org_admin.organizations.add(cls.org)

        # 不整合生徒が作成者の passage
        cls.passage = ListeningPassage.objects.create(
            title="不整合生徒の passage",
            content="content",
            created_by=cls.inconsistent_student,
            source_type="textbook",
        )

    # --- (1) 教室管理者は visible_to() で passage を取得できる ---

    def test_classroom_admin_can_see_passage_of_inconsistent_student(self):
        """教室管理者は不整合生徒の passage を visible_to() で取得できる（現状挙動）"""
        qs = ListeningPassage.objects.visible_to(self.classroom_admin)
        self.assertIn(self.passage, qs)

    # --- (2) 組織管理者は visible_to() で passage を取得できない ---

    def test_org_admin_cannot_see_passage_of_inconsistent_student(self):
        """
        組織管理者は不整合生徒の passage を visible_to() で取得できない（現状挙動）。
        organization=None は get_accessible_organizations() に含まれないため QuerySet で弾かれる。
        """
        qs = ListeningPassage.objects.visible_to(self.org_admin)
        self.assertNotIn(self.passage, qs)

    # --- (3) 組織管理者の can_manage_student() はフォールバックで True ---

    def test_org_admin_can_manage_inconsistent_student_via_classroom_fallback(self):
        """
        OrganizationAdministrator.can_manage_student() は organization=None のとき
        教室経由フォールバックで True を返す（accounts 側の現状挙動）。
        visible_to() との不整合の根拠となる箇所。
        """
        role_obj = self.org_admin.get_role_object()
        result = role_obj.can_manage_student(self.inconsistent_student)
        self.assertTrue(result)

    # --- (4) ensure_can_access_student() は組織管理者で例外を出さない ---

    def test_ensure_can_access_student_does_not_raise_for_org_admin(self):
        """
        ensure_can_access_student() は can_manage_student() フォールバック経由で
        組織管理者に対しても例外を出さない（現状挙動）。
        visible_to() とは別経路で通過できることを示す。
        """
        try:
            ensure_can_access_student(self.org_admin, self.inconsistent_student)
        except (PermissionDenied, Http404) as e:
            self.fail(
                f"ensure_can_access_student() が予期せず例外を送出しました: {e}"
            )

    # --- (5) passage_access_check() は組織管理者で Http404 になる ---

    def test_passage_access_check_raises_404_for_org_admin(self):
        """
        passage_access_check() は内部で visible_to() を呼ぶため、
        組織管理者が不整合生徒の passage にアクセスしようとすると Http404 になる（現状挙動）。
        ensure_can_access_student() に到達する前に弾かれることを示す。
        """
        with self.assertRaises(Http404):
            passage_access_check(self.org_admin, self.passage.id)
    

    def test_passage_access_check_raises_404_for_org_admin(self):
        """
        passage_access_check() は内部で visible_to() を呼ぶため、
        組織管理者が不整合生徒の passage にアクセスしようとすると Http404 になる（現状挙動）。
        ensure_can_access_student() に到達する前に弾かれることを示す。
        """
        with self.assertRaises(Http404):
            passage_access_check(self.org_admin, self.passage.id)


    # --- (6) passage_access_check() は教室管理者で成功する ---

    def test_passage_access_check_succeeds_for_classroom_admin(self):
        """教室管理者が不整合生徒の passage に access_check 経由でアクセスすると成功する（現状挙動）"""
        result = passage_access_check(self.classroom_admin, self.passage.id)
        self.assertEqual(result.id, self.passage.id)

    # --- 非対称の明示的な確認 ---

    def test_asymmetry_classroom_admin_vs_org_admin_in_visible_to(self):
        """
        visible_to() で教室管理者 > 組織管理者 の可視範囲逆転を明示的に確認する。
        このテストが GREEN である間は逆転が解消されていない。
        方針A に基づき後続 Issue で解消予定。
        """
        classroom_qs = ListeningPassage.objects.visible_to(self.classroom_admin)
        org_qs = ListeningPassage.objects.visible_to(self.org_admin)
        self.assertIn(self.passage, classroom_qs)
        self.assertNotIn(self.passage, org_qs)
