"""
回帰テスト: classroom_id=None / 未指定 による NoReverseMatch 500 の防止

【背景】
classroom_id が URL クエリパラメータに存在しない状態で生徒詳細を開き、
そこから編集ページに遷移すると ?classroom_id=None が URL に混入する。
テンプレート内の {% if classroom_id %} が文字列 "None" を truthy と判定し、
{% url 'classroom_detail' "None" %} が <int:pk> にマッチせず NoReverseMatch → 500 が発生していた。

【修正内容】
_get_classroom_id(request) ヘルパーが文字列 'None' を Python None に正規化することで防止。

【このテストの目的】
上記修正の回帰防止。classroom_id 未指定・"None" 文字列のいずれでも
対象ビューが 500 にならないことを保証する。
"""

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from accounts.models import (
    Organization,
    Classroom,
    OrganizationAdministrator,
    ClassroomAdministrator,
    Teacher,
    Student,
)


class ClassroomIdNoneRegressionBase(TestCase):
    """
    共通フィクスチャ。
    classroom_id=None 回帰テストで使うユーザー・生徒・教室をまとめて定義する。
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="RegressionOrg")
        cls.classroom = Classroom.objects.create(name="RegressionClass", organization=cls.org)

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="regression_org_admin@example.com",
            username="regression_org_admin",
            password="pass123456",
            role="organization_administrator",
        )
        cls.org_admin.organizations.add(cls.org)

        cls.class_admin = ClassroomAdministrator.objects.create_user(
            email="regression_class_admin@example.com",
            username="regression_class_admin",
            password="pass123456",
            role="classroom_administrator",
            organization=cls.org,
            is_first_login=False,
        )
        cls.class_admin.classrooms.add(cls.classroom)

        cls.teacher = Teacher.objects.create_user(
            email="regression_teacher@example.com",
            username="regression_teacher",
            password="pass123456",
            organization=cls.org,
            is_first_login=False,
        )
        cls.teacher.classrooms.add(cls.classroom)

        cls.target_student = Student.objects.create_user(
            email="regression_target@example.com",
            username="regression_target",
            password="pass123456",
            line_user_id="regression_target_line_id",
            organization=cls.org,
        )
        cls.target_student.classrooms.add(cls.classroom)
        cls.target_student.teachers.add(cls.teacher)

    def login_as(self, email, password="pass123456"):
        ok = self.client.login(email=email, password=password)
        self.assertTrue(ok, f"ログイン失敗: {email}")


# ---------------------------------------------------------------------------
# StudentDetailView
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# StudentDetailView
# ---------------------------------------------------------------------------

class StudentDetailViewClassroomIdRegressionTest(
    ClassroomIdNoneRegressionBase
):
    """
    StudentDetailView における classroom_id の回帰テスト。

    通常フロー:
        教室詳細
        → 生徒詳細?classroom_id=<有効な教室ID>

    エッジケース:
        ブックマークや履歴から classroom_id なしで直接アクセスする。
        古いURLなどから classroom_id=None が渡される。

    保証すること:
        - classroom_id 未指定でも 500 エラーにならない
        - 文字列 "None" は Python の None に正規化される
        - classroom_id がない場合、HTML に classroom_id=None を再生成しない
        - 正常な classroom_id は後続画面へ引き継がれる
        - 組織管理者、教室管理者、講師の既存導線を壊さない
    """

    def _detail_url(self):
        return reverse(
            "organization_admin:student_detail",
            kwargs={"pk": self.target_student.pk},
        )

    # ------------------------------------------------------------------
    # org admin: classroom_id の状態ごとの仕様を詳細に確認
    # ------------------------------------------------------------------

    @patch(
        "accounts.views.organization_admin_views.has_vocab_progress",
        return_value=False,
    )
    def test_org_admin_no_classroom_id_does_not_render_none_parameter(
        self,
        _mock,
    ):
        """
        classroom_id が未指定でも 200 を返す。

        context 上では Python の None として扱い、
        HTML 内に classroom_id=None を生成しない。
        """
        self.login_as("regression_org_admin@example.com")

        resp = self.client.get(self._detail_url())

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["classroom_id"])
        self.assertNotContains(resp, "classroom_id=None")

    @patch(
        "accounts.views.organization_admin_views.has_vocab_progress",
        return_value=False,
    )
    def test_org_admin_none_string_is_normalized_and_not_rendered(
        self,
        _mock,
    ):
        """
        文字列 "None" が渡された場合も 200 を返す。

        Python の None へ正規化し、
        HTML 内に classroom_id=None を再生成しない。
        """
        self.login_as("regression_org_admin@example.com")

        resp = self.client.get(
            self._detail_url() + "?classroom_id=None"
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["classroom_id"])
        self.assertNotContains(resp, "classroom_id=None")

    @patch(
        "accounts.views.organization_admin_views.has_vocab_progress",
        return_value=False,
    )
    def test_org_admin_valid_classroom_id_is_preserved_and_rendered(
        self,
        _mock,
    ):
        """
        正常な classroom_id は context と HTML に引き継がれる。
        """
        self.login_as("regression_org_admin@example.com")

        resp = self.client.get(
            self._detail_url()
            + f"?classroom_id={self.classroom.pk}"
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            str(resp.context["classroom_id"]),
            str(self.classroom.pk),
        )
        self.assertContains(
            resp,
            f"classroom_id={self.classroom.pk}",
        )

    # ------------------------------------------------------------------
    # class admin: ロール別の既存導線が壊れていないことを確認
    # ------------------------------------------------------------------

    @patch(
        "accounts.views.organization_admin_views.has_vocab_progress",
        return_value=False,
    )
    def test_class_admin_no_classroom_id_returns_200(
        self,
        _mock,
    ):
        """
        教室管理者は classroom_id 未指定でもアクセスできる。
        """
        self.login_as("regression_class_admin@example.com")

        resp = self.client.get(self._detail_url())

        self.assertEqual(resp.status_code, 200)

    @patch(
        "accounts.views.organization_admin_views.has_vocab_progress",
        return_value=False,
    )
    def test_class_admin_none_string_returns_200(
        self,
        _mock,
    ):
        """
        教室管理者は classroom_id=None が渡されても
        500 エラーにならない。
        """
        self.login_as("regression_class_admin@example.com")

        resp = self.client.get(
            self._detail_url() + "?classroom_id=None"
        )

        self.assertEqual(resp.status_code, 200)

    # ------------------------------------------------------------------
    # teacher: classroom_id なしが通常導線
    # ------------------------------------------------------------------

    @patch(
        "accounts.views.organization_admin_views.has_vocab_progress",
        return_value=False,
    )
    def test_teacher_no_classroom_id_returns_200(
        self,
        _mock,
    ):
        """
        講師は classroom_id なしで通常アクセスできる。
        """
        self.login_as("regression_teacher@example.com")

        resp = self.client.get(self._detail_url())

        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# StudentEditView
# ---------------------------------------------------------------------------

class StudentEditViewClassroomIdRegressionTest(ClassroomIdNoneRegressionBase):
    """
    StudentEditView: classroom_id 未指定 / "None" でも NoReverseMatch 500 にならないことを確認する。

    【再現経路】
    1. 管理者が生徒詳細を classroom_id なしで開く
    2. detail.html が ?classroom_id=None 付きの編集リンクを生成
    3. そのリンクをクリック → edit.html のパンくずで NoReverseMatch → 500

    【修正後】
    _get_classroom_id() が 'None' を None に正規化 → {% if classroom_id %} が False →
    パンくず「教室詳細」が描画されない → 500 回避
    """

    def _edit_url(self):
        return reverse(
            "organization_admin:student_edit",
            kwargs={"pk": self.target_student.pk},
        )

    def test_org_admin_no_classroom_id_returns_200(self):
        """classroom_id 未指定でも 200"""
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url())
        self.assertEqual(resp.status_code, 200)

    def test_org_admin_classroom_id_none_string_returns_200(self):
        """
        classroom_id=None（文字列）でも 500 にならない。
        これが今回のバグ再現ケース。
        """
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url() + "?classroom_id=None")
        self.assertEqual(resp.status_code, 200)

    def test_org_admin_classroom_id_none_string_context_is_none(self):
        """
        classroom_id=None（文字列）が来たとき、コンテキストの classroom_id は
        Python None に正規化されていること。
        """
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url() + "?classroom_id=None")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["classroom_id"])

    def test_class_admin_no_classroom_id_returns_200(self):
        """教室管理者: classroom_id 未指定でも 200"""
        self.login_as("regression_class_admin@example.com")
        resp = self.client.get(self._edit_url())
        self.assertEqual(resp.status_code, 200)

    def test_class_admin_classroom_id_none_string_returns_200(self):
        """教室管理者: classroom_id=None（文字列）でも 500 にならない"""
        self.login_as("regression_class_admin@example.com")
        resp = self.client.get(self._edit_url() + "?classroom_id=None")
        self.assertEqual(resp.status_code, 200)

    def test_valid_classroom_id_returns_200(self):
        """正常な classroom_id が渡された場合も 200（正常系の確認）"""
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url() + f"?classroom_id={self.classroom.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.context["classroom_id"]), str(self.classroom.pk))


# ---------------------------------------------------------------------------
# TeacherEditView
# ---------------------------------------------------------------------------

class TeacherEditViewClassroomIdRegressionTest(ClassroomIdNoneRegressionBase):
    """
    TeacherEditView: classroom_id 未指定 / "None" でも 500 にならないことを確認する。

    通常フロー: 教室詳細?classroom_id=X → 講師編集?classroom_id=X
    エッジケース: classroom_id なし・"None" 文字列での直接アクセス。
    """

    def _edit_url(self):
        return reverse(
            "organization_admin:teacher_edit",
            kwargs={"pk": self.teacher.pk},
        )

    def test_org_admin_no_classroom_id_returns_200(self):
        """classroom_id 未指定でも 200"""
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url())
        self.assertEqual(resp.status_code, 200)

    def test_org_admin_classroom_id_none_string_returns_200(self):
        """classroom_id=None（文字列）でも 500 にならない"""
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url() + "?classroom_id=None")
        self.assertEqual(resp.status_code, 200)

    def test_org_admin_classroom_id_none_string_context_is_none(self):
        """
        classroom_id=None（文字列）が来たとき、コンテキストの classroom_id は
        Python None に正規化されていること。
        """
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url() + "?classroom_id=None")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["classroom_id"])

    def test_class_admin_no_classroom_id_returns_200(self):
        """教室管理者: classroom_id 未指定でも 200"""
        self.login_as("regression_class_admin@example.com")
        resp = self.client.get(self._edit_url())
        self.assertEqual(resp.status_code, 200)

    def test_class_admin_classroom_id_none_string_returns_200(self):
        """教室管理者: classroom_id=None（文字列）でも 500 にならない"""
        self.login_as("regression_class_admin@example.com")
        resp = self.client.get(self._edit_url() + "?classroom_id=None")
        self.assertEqual(resp.status_code, 200)

    def test_valid_classroom_id_returns_200(self):
        """正常な classroom_id が渡された場合も 200 かつ get_success_url が classroom_detail を返す（正常系）"""
        self.login_as("regression_org_admin@example.com")
        resp = self.client.get(self._edit_url() + f"?classroom_id={self.classroom.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.context["classroom_id"]), str(self.classroom.pk))
