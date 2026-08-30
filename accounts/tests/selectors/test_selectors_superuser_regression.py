"""
Issue #162 回帰テスト: accounts/selectors.py の各セレクターが is_superuser
フラグによってバイパスされないことを固定する。

背景:
    - accounts/models/user_models.py の BaseUser で has_perm /
      has_module_perms / get_all_permissions をオーバーライドし、
      PermissionsMixin / ModelBackend が本来持つ
      「is_active かつ is_superuser なら全権限 True」という短絡を無効化した。
    - accounts/selectors.py は is_superuser を直接見ておらず、
      permission と role・テナントスコープのみで可視範囲を決める。
      したがって is_superuser=True でも可視範囲は広がらない。

テスト手法:
    is_superuser=True の行は create_user / save() のガードと
    BaseUser.Meta の CheckConstraint により生成不可能なため、
    DB へは保存せずメモリ上のインスタンスにフラグを立てて検証する。
"""

from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from accounts.models import (
    Classroom,
    Organization,
    OrganizationAdministrator,
    Student,
)
from accounts.selectors import (
    get_visible_self_student,
    visible_inactive_students_qs,
    visible_organizations_qs,
    visible_students_qs,
)


def _add_perm(user, codename: str, model) -> None:
    """model に対する指定 codename の権限を user に明示付与する。"""
    ct = ContentType.objects.get_for_model(model)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


class SelectorsSuperuserRegressionTests(TestCase):
    """accounts/selectors.py の各セレクターが is_superuser でバイパスされないことを確認する。"""

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

        cls.classroom_org1 = Classroom.objects.create(
            name="org1-classroom", organization=cls.org1
        )

        cls.org1_student = Student.objects.create_user(
            username="org1_student",
            email="org1_student@example.com",
            password="pass12345",
            organization=cls.org1,
        )
        cls.org1_student.classrooms.add(cls.classroom_org1)

        cls.org1_inactive_student = Student.objects.create_user(
            username="org1_inactive_student",
            email="org1_inactive_student@example.com",
            password="pass12345",
            organization=cls.org1,
        )
        cls.org1_inactive_student.classrooms.add(cls.classroom_org1)
        cls.org1_inactive_student.is_active = False
        cls.org1_inactive_student.save()

        cls.org2_student = Student.objects.create_user(
            username="org2_student",
            email="org2_student@example.com",
            password="pass12345",
            organization=cls.org2,
        )

    def setUp(self):
        # ロールオブジェクト／権限のキャッシュを避けるため取り直し、is_superuser を立てる
        self.su_admin = OrganizationAdministrator.objects.get(pk=self.org1_admin.pk)
        self.su_admin.is_superuser = True  # DB へは保存しない

    # ------------------------------------------------------------------
    # visible_organizations_qs
    # ------------------------------------------------------------------
    def test_visible_organizations_qs_denies_superuser_without_perm(self):
        """
        is_superuser=True でも accounts.view_organization を明示付与されていなければ、
        visible_organizations_qs は空クエリセットを返す（バイパス不可）ことを確認する回帰テスト。
        """
        qs = visible_organizations_qs(self.su_admin)
        self.assertEqual(qs.count(), 0)

    def test_visible_organizations_qs_superuser_does_not_grant_view_all(self):
        """
        is_superuser=True かつ accounts.view_organization のみ明示付与された場合、
        visible_organizations_qs は自組織のみを返し、view_all_organizations 相当の
        全件可視には広がらないことを確認する回帰テスト。
        """
        _add_perm(self.su_admin, "view_organization", Organization)

        qs = visible_organizations_qs(self.su_admin)

        self.assertEqual(list(qs), [self.org1])

    # ------------------------------------------------------------------
    # visible_students_qs
    # ------------------------------------------------------------------
    def test_visible_students_qs_is_not_widened_by_superuser(self):
        """
        is_superuser=True の組織管理者でも、visible_students_qs の可視範囲は
        role とテナントスコープのみで決まり、他組織の生徒は見えないことを確認する回帰テスト。
        """
        qs = visible_students_qs(self.su_admin)

        self.assertIn(self.org1_student, qs)
        self.assertNotIn(self.org2_student, qs)
        self.assertNotIn(self.org1_inactive_student, qs)

    def test_visible_students_qs_denies_superuser_student_role(self):
        """
        role="student" のユーザーは is_superuser=True でも
        visible_students_qs から何も取得できないことを確認する回帰テスト。
        """
        su_student = Student.objects.get(pk=self.org1_student.pk)
        su_student.is_superuser = True  # DB へは保存しない

        qs = visible_students_qs(su_student)

        self.assertEqual(qs.count(), 0)

    # ------------------------------------------------------------------
    # visible_inactive_students_qs
    # ------------------------------------------------------------------
    def test_visible_inactive_students_qs_is_not_widened_by_superuser(self):
        """
        is_superuser=True の組織管理者でも、visible_inactive_students_qs は
        自組織の非アクティブ生徒のみを返し、他組織へは広がらないことを確認する回帰テスト。
        """
        qs = visible_inactive_students_qs(self.su_admin)

        self.assertIn(self.org1_inactive_student, qs)
        self.assertNotIn(self.org1_student, qs)
        self.assertNotIn(self.org2_student, qs)

    # ------------------------------------------------------------------
    # get_visible_self_student
    # ------------------------------------------------------------------
    def test_get_visible_self_student_denies_superuser_non_student(self):
        """
        role が student でないユーザーは is_superuser=True でも
        get_visible_self_student が None を返すことを確認する回帰テスト。
        """
        self.assertIsNone(get_visible_self_student(self.su_admin))

    def test_get_visible_self_student_unauthenticated_returns_none(self):
        """
        未認証ユーザーに対しては（superuser 云々以前に）None を返すことを確認する。
        """
        self.assertIsNone(get_visible_self_student(AnonymousUser()))
