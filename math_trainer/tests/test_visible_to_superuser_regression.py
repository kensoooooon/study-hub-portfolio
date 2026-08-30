"""
Issue #162 回帰テスト: math_trainer/models.py の
ProblemSessionQuerySet.visible_to() と ProblemSession.can_be_accessed_by() から
is_superuser の早期 return を撤去したことを固定する。

is_superuser フラグが立っていても、可視範囲・アクセス可否は role とテナント
スコープのみで決まることを確認する。is_superuser=True の行は CheckConstraint に
より生成できないため、メモリ上のインスタンスにフラグを立てて検証する。
"""
from django.test import TestCase

from accounts.models import Organization, OrganizationAdministrator, Student
from math_trainer.models import ProblemSession, ProblemType


class MathTrainerVisibleToSuperuserRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org2 = Organization.objects.create(name="org2")

        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            email="org1_admin@example.com",
            username="org1_admin",
            password="pass12345",
            organization=cls.org1,
        )

        cls.org1_student = Student.objects.create_user(
            username="org1_student",
            email="org1_student@example.com",
            password="pass12345",
            organization=cls.org1,
            is_active=True,
        )
        cls.org2_student = Student.objects.create_user(
            username="org2_student",
            email="org2_student@example.com",
            password="pass12345",
            organization=cls.org2,
            is_active=True,
        )

        cls.ptype = ProblemType.objects.create(name="計算", grade=7)
        cls.session_org1 = ProblemSession.objects.create(
            student=cls.org1_student, problem_type=cls.ptype, mode="display"
        )
        cls.session_org2 = ProblemSession.objects.create(
            student=cls.org2_student, problem_type=cls.ptype, mode="display"
        )

    def setUp(self):  # 毎回実行されるsuperuserへの一時的変更
        self.su_admin = OrganizationAdministrator.objects.get(pk=self.org1_admin.pk)
        self.su_admin.is_superuser = True  # DB へは保存しない

    def test_visible_to_is_not_widened_by_is_superuser(self):
        """
        ProblemSessionQuerySet.visible_to: is_superuser でも他組織のセッションは見えない。
        """
        qs = ProblemSession.objects.visible_to(self.su_admin)
        self.assertIn(self.session_org1, qs)
        self.assertNotIn(self.session_org2, qs)

    def test_can_be_accessed_by_is_not_widened_by_is_superuser(self):
        """
        ProblemSession.can_be_accessed_by: is_superuser でも他組織のセッションへは False、
        自組織のセッションへは role_obj 経由で True となることを確認する。
        """
        self.assertTrue(self.session_org1.can_be_accessed_by(self.su_admin))
        self.assertFalse(self.session_org2.can_be_accessed_by(self.su_admin))
