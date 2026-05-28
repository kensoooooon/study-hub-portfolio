"""
組織（Organization）と教室（Classroom）と
生徒（Student）／講師（Teacher）／教室管理者（ClassroomAdministrator）の
整合性制約が正しく機能していることを総合的に検証するテスト群。

============================================================
【1】StudentOrganizationClassroomSignalTests（Student.m2m シグナルの動作確認）
------------------------------------------------------------
目的：
    Student.classrooms (ManyToMany) に教室を追加する際、
    生徒の所属組織（student.organization）と異なる組織の教室が
    誤って紐付けられないことを保証する。

検証内容：
    ・同一組織の教室 → 正常に追加される
    ・異なる組織の教室 → m2m_changed シグナルにより ValidationError が発生し、
        関係が追加されないことを確認する

============================================================
【2】StudentCleanMethodTests（Student.clean による既存データ整合性チェック）
------------------------------------------------------------
目的：
    signals をすり抜けた「既に存在する不整合データ」を
    Student.clean() が正しく検出できることを保証する。

検証内容：
    ・既存データに組織不整合がある場合、clean() が ValidationError を投げる

（補足）
    m2m シグナルは「新規追加時の防御」、clean() は「既存データの整合性チェック」の防御。

============================================================
【3】UnassignedStudentListViewTests（未割当生徒一覧ビューの表示制御）
------------------------------------------------------------
目的：
    組織管理者（OrganizationAdministrator）が、
    自分の所属組織の生徒だけを適切に閲覧できることを保証する。

検証内容：
    ・org_admin1 は組織1の未割り当て生徒のみ閲覧できる
    ・org_admin2 は組織2のみ閲覧できる
    ・teacher / classroom_admin は 403 Forbidden となる（アクセス権限なし）

============================================================
【4】AssignClassroomFormTests（教室割当フォームの動作確認）
------------------------------------------------------------
目的：
    教室割当フォーム（AssignClassroomForm）が、ビューから渡された
    current_user（組織管理者）に基づいて正しい queryset を生成し、
    不正な割り当てができない状態であることを保証する。

検証内容：
    ・フォーム生成時、student と classroom の queryset が
        current_user の管理組織に属するものだけに絞られる
    ・同一組織内の生徒と教室の組み合わせであれば正常に割り当て可能
    ・（組織間の誤った組み合わせの防御は、
        AssignClassroomForm.save() および signals により保証される）

============================================================
【5】TeacherOrganizationClassroomSignalTests / TeacherCleanMethodTests
      （Teacher と Organization/Classroom 整合性テスト）
------------------------------------------------------------
目的：
    Teacher.classrooms に対して m2m 追加を行う際、
    teacher.organization と異なる組織の教室が紐付かないこと、
    また既存データに不整合があれば Teacher.clean() で検出できることを保証する。

検証内容：
    ・講師が所属している組織の教室への紐付けは正常に成功する
    ・講師が所属していない組織の教室を紐付けようとすると、
        m2m_changed シグナルにより ValidationError が発生し追加されない
    ・既存データとして「Teacher.organization と教室の organization が矛盾している」
        状態を作った場合、Teacher.clean() が ValidationError を投げる

============================================================
【6】ClassroomAdminOrganizationClassroomSignalTests /
      ClassroomAdminCleanMethodTests
     （ClassroomAdministrator と Organization/Classroom 整合性テスト）
------------------------------------------------------------
目的：
    ClassroomAdministrator.classrooms に対する m2m 追加時に、
    classroom_admin.organization と異なる組織の教室が紐付かないこと、
    また既存データに不整合があれば ClassroomAdministrator.clean() で検出できることを保証する。

検証内容：
    ・教室管理者が所属している組織の教室への紐付けは正常に成功する
    ・教室管理者が所属していない組織の教室を紐付けようとすると、
        m2m_changed シグナルにより ValidationError が発生し追加されない
    ・既存データとして「ClassroomAdministrator.organization と教室の organization が矛盾している」
        状態を作った場合、ClassroomAdministrator.clean() が ValidationError を投げる

============================================================
本テスト全体の目的：
    「生徒／講師／教室管理者の所属組織（organization）を真とする」という仕様のもと、

    ・ビュー（未割当生徒一覧など）
    ・フォーム（AssignClassroomForm や Teacher 作成フォーム等の前提となる制約）
    ・モデル（Student.clean / Teacher.clean / ClassroomAdministrator.clean）
    ・シグナル（Student / Teacher / ClassroomAdministrator に対する m2m_changed）

    これらが一貫して、
    『Student / Teacher / ClassroomAdministrator が
        自身の所属組織と異なる組織の教室に誤って紐付かない』
    という制約を正しく維持できているかを包括的に検証する。

この整合性が確認されることで、今後のリマインダー機能や
マルチチャンネル送信機能においても、
「各ユーザーの organization を唯一の正しい所属情報として扱う」
という実装を安全に行える。
"""



from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError


from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

from accounts.models import (
    Organization,
    Classroom,
    Student,
    OrganizationAdministrator,
    ClassroomAdministrator,
    Teacher,
)

from accounts.forms import AssignClassroomForm


class StudentOrganizationClassroomSignalTests(TransactionTestCase):
    def setUp(self):
        # 組織を2つ作成
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        # 各組織に教室を1つずつ作成
        self.classroom_org1 = Classroom.objects.create(
            name="Classroom Org1",
            description="Org1の教室",
            organization=self.org1,
        )
        self.classroom_org2 = Classroom.objects.create(
            name="Classroom Org2",
            description="Org2の教室",
            organization=self.org2,
        )

        # Org1 に所属する生徒
        self.student_org1 = Student.objects.create(
            username="Student Org1",
            line_user_id="U-STUDENT-ORG1",
            organization=self.org1,
        )

    def test_add_classroom_same_organization_ok(self):
        """
        生徒と同じ organization の教室は正常に紐付けられる
        """
        self.student_org1.classrooms.add(self.classroom_org1)
        self.student_org1.refresh_from_db()

        self.assertIn(self.classroom_org1, self.student_org1.classrooms.all())

    def test_add_classroom_different_organization_raises_validation_error(self):
        """
        生徒と異なる organization の教室を紐付けようとすると ValidationError で止まる
        （m2m_changed シグナルによる検出）
        """
        with self.assertRaises(ValidationError):
            self.student_org1.classrooms.add(self.classroom_org2)

        # 失敗したので、実際には紐付いていないことを確認
        self.assertNotIn(self.classroom_org2, self.student_org1.classrooms.all())



class StudentCleanMethodTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.classroom_org1 = Classroom.objects.create(
            name="Classroom Org1",
            description="Org1の教室",
            organization=self.org1,
        )
        self.classroom_org2 = Classroom.objects.create(
            name="Classroom Org2",
            description="Org2の教室",
            organization=self.org2,
        )

        self.student_org1 = Student.objects.create(
            username="Student Org1",
            line_user_id="U-STUDENT-ORG1",
            organization=self.org1,
        )

    def test_clean_detects_invalid_existing_classroom(self):
        """
        もし何らかの理由で異なる organization の教室が紐付いてしまっていたら、
        clean() が ValidationError で検出する
        """
        # シグナルをすり抜けた不正データを無理やり作りたい場合、
        # 中間テーブルを直接触る or signals を一時無効化…などがありますが、
        # ここでは簡易的に「正しい教室を紐付け → org を変えて矛盾を作る」という手にします。
        self.student_org1.classrooms.add(self.classroom_org1)
        # 強引に organization を org2 に変更して矛盾を発生させる
        self.student_org1.organization = self.org2

        with self.assertRaises(ValidationError):
            self.student_org1.clean()


class UnassignedStudentListViewTests(TestCase):
    def setUp(self):
        # 組織
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        # 組織管理者（BaseUser と OrganizationAdministrator は同一PKのはず）
        # カスタムユーザーモデル
        User = get_user_model()

        self.org_admin1 = OrganizationAdministrator.objects.create(
            email="admin1@example.com",
            username="OrgAdmin1",
            role="organization_administrator",
        )
        self.org_admin1.organizations.add(self.org1)

        self.org_admin2 = OrganizationAdministrator.objects.create(
            email="admin2@example.com",
            username="OrgAdmin2",
            role="organization_administrator",
        )
        self.org_admin2.organizations.add(self.org2)

        # 未割り当て生徒（教室なし）を各組織に1人ずつ
        self.student_org1 = Student.objects.create(
            username="StudentOrg1",
            line_user_id="U-STUDENT-ORG1",
            organization=self.org1,
        )
        self.student_org2 = Student.objects.create(
            username="StudentOrg2",
            line_user_id="U-STUDENT-ORG2",
            organization=self.org2,
        )

        # URL名は organization_admin:unassigned_students を想定
        self.url = reverse("organization_admin:unassigned_students")

    def test_org_admin_sees_only_own_unassigned_students(self):
        """
        組織管理者は、自身の organizations に属する未割り当て生徒のみ閲覧できる
        """
        # OrgAdmin1 でログイン
        self.client.force_login(self.org_admin1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        students = list(response.context["students"])
        self.assertIn(self.student_org1, students)
        self.assertNotIn(self.student_org2, students)

        # OrgAdmin2 でログイン
        self.client.force_login(self.org_admin2)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        students = list(response.context["students"])
        self.assertIn(self.student_org2, students)
        self.assertNotIn(self.student_org1, students)

    def test_non_org_admin_cannot_access_unassigned_students(self):
        teacher = Teacher.objects.create(
            email="teacher@example.com",
            username="Teacher",
            role="teacher",
        )
        classroom_admin = ClassroomAdministrator.objects.create(
            email="classroom_admin@example.com",
            username="ClassroomAdmin",
            role="classroom_administrator",
        )
        # teacherチェック
        self.client.force_login(teacher)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        # classroom adminチェック
        self.client.force_login(classroom_admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


class AssignClassroomFormTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.classroom_org1 = Classroom.objects.create(
            name="Classroom Org1", description="", organization=self.org1
        )
        self.classroom_org2 = Classroom.objects.create(
            name="Classroom Org2", description="", organization=self.org2
        )

        self.student_org1 = Student.objects.create(
            username="StudentOrg1",
            line_user_id="U-STUDENT-ORG1",
            organization=self.org1,
        )
        self.student_org2 = Student.objects.create(
            username="StudentOrg2",
            line_user_id="U-STUDENT-ORG2",
            organization=self.org2,
        )

        self.org_admin1 = OrganizationAdministrator.objects.create(
            email="admin1@example.com",
            username="OrgAdmin1",
            role="organization_administrator",
        )
        self.org_admin1.organizations.add(self.org1)

    def test_form_limits_queryset_by_organization(self):
        """
        AssignClassroomForm は current_user の管理組織に属する
        生徒・教室だけを選択肢にする
        """
        form = AssignClassroomForm(current_user=self.org_admin1)

        students_qs = form.fields["student"].queryset
        classrooms_qs = form.fields["classroom"].queryset

        self.assertIn(self.student_org1, students_qs)
        self.assertNotIn(self.student_org2, students_qs)

        self.assertIn(self.classroom_org1, classrooms_qs)
        self.assertNotIn(self.classroom_org2, classrooms_qs)

    def test_form_save_success_on_same_organization(self):
        """
        同じ organization の student/classroom を選んだ場合は正常に割り当てられる
        """
        data = {
            "student": self.student_org1.pk,
            "classroom": self.classroom_org1.pk,
        }
        form = AssignClassroomForm(data=data, current_user=self.org_admin1)
        self.assertTrue(form.is_valid())

        student = form.save()
        self.assertIn(self.classroom_org1, student.classrooms.all())


# ============================================================
# 【5】Teacher と Organization/Classroom 整合性テスト
# ============================================================

class TeacherOrganizationClassroomSignalTests(TransactionTestCase):
    """
    Teacher.classrooms に対して m2m 追加を行う際、
    teacher.organization と異なる組織の教室が紐付かないことを
    m2m_changed シグナルで保証できているかを検証する。
    """

    def setUp(self):
        # 組織を2つ作成
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        # 各組織に教室を1つずつ作成
        self.classroom_org1 = Classroom.objects.create(
            name="Teacher Classroom Org1",
            description="Org1の教室（Teacher用）",
            organization=self.org1,
        )
        self.classroom_org2 = Classroom.objects.create(
            name="Teacher Classroom Org2",
            description="Org2の教室（Teacher用）",
            organization=self.org2,
        )

        # Org1 に所属する講師
        self.teacher_org1 = Teacher.objects.create(
            username="Teacher Org1",
            email="teacher_org1@example.com",
            role="teacher",
            organization=self.org1,
        )

    def test_add_classroom_same_organization_ok(self):
        """
        講師と同じ organization の教室は正常に紐付けられる
        """
        self.teacher_org1.classrooms.add(self.classroom_org1)
        self.teacher_org1.refresh_from_db()

        self.assertIn(self.classroom_org1, self.teacher_org1.classrooms.all())

    def test_add_classroom_different_organization_raises_validation_error(self):
        """
        講師と異なる organization の教室を紐付けようとすると ValidationError で止まる
        （m2m_changed シグナルによる検出）
        """
        with self.assertRaises(ValidationError):
            self.teacher_org1.classrooms.add(self.classroom_org2)

        # 失敗したので、実際には紐付いていないことを確認
        self.assertNotIn(self.classroom_org2, self.teacher_org1.classrooms.all())


class TeacherCleanMethodTests(TestCase):
    """
    signals をすり抜けた「既に存在する不整合データ」を
    Teacher.clean() が検出できることを確認する。
    """

    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.classroom_org1 = Classroom.objects.create(
            name="Teacher Classroom Org1",
            description="Org1の教室",
            organization=self.org1,
        )
        self.classroom_org2 = Classroom.objects.create(
            name="Teacher Classroom Org2",
            description="Org2の教室",
            organization=self.org2,
        )

        self.teacher_org1 = Teacher.objects.create(
            username="Teacher Org1",
            email="teacher_org1@example.com",
            role="teacher",
            organization=self.org1,
        )

    def test_clean_detects_invalid_existing_classroom(self):
        """
        何らかの理由で Teacher に異なる organization の教室が
        紐付いてしまっている場合、clean() が ValidationError を投げる
        """
        # まずは正しい教室を紐付ける
        self.teacher_org1.classrooms.add(self.classroom_org1)

        # その後、強引に organization を org2 に変更して矛盾を発生させる
        self.teacher_org1.organization = self.org2

        with self.assertRaises(ValidationError):
            self.teacher_org1.clean()


# ============================================================
# 【6】ClassroomAdministrator と Organization/Classroom 整合性テスト
# ============================================================

class ClassroomAdminOrganizationClassroomSignalTests(TransactionTestCase):
    """
    ClassroomAdministrator.classrooms に対して m2m 追加を行う際、
    classroom_admin.organization と異なる組織の教室が紐付かないことを
    m2m_changed シグナルで保証できているかを検証する。
    """

    def setUp(self):
        # 組織を2つ作成
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        # 各組織に教室を1つずつ作成
        self.classroom_org1 = Classroom.objects.create(
            name="CA Classroom Org1",
            description="Org1の教室（CA用）",
            organization=self.org1,
        )
        self.classroom_org2 = Classroom.objects.create(
            name="CA Classroom Org2",
            description="Org2の教室（CA用）",
            organization=self.org2,
        )

        # Org1 に所属する教室管理者
        self.classroom_admin_org1 = ClassroomAdministrator.objects.create(
            username="CA Org1",
            email="ca_org1@example.com",
            role="classroom_administrator",
            organization=self.org1,
        )

    def test_add_classroom_same_organization_ok(self):
        """
        教室管理者と同じ organization の教室は正常に紐付けられる
        """
        self.classroom_admin_org1.classrooms.add(self.classroom_org1)
        self.classroom_admin_org1.refresh_from_db()

        self.assertIn(self.classroom_org1, self.classroom_admin_org1.classrooms.all())

    def test_add_classroom_different_organization_raises_validation_error(self):
        """
        教室管理者と異なる organization の教室を紐付けようとすると ValidationError で止まる
        （m2m_changed シグナルによる検出）
        """
        with self.assertRaises(ValidationError):
            self.classroom_admin_org1.classrooms.add(self.classroom_org2)

        # 失敗したので、実際には紐付いていないことを確認
        self.assertNotIn(self.classroom_org2, self.classroom_admin_org1.classrooms.all())


class ClassroomAdminCleanMethodTests(TestCase):
    """
    signals をすり抜けた「既に存在する不整合データ」を
    ClassroomAdministrator.clean() が検出できることを確認する。
    """

    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.classroom_org1 = Classroom.objects.create(
            name="CA Classroom Org1",
            description="Org1の教室",
            organization=self.org1,
        )
        self.classroom_org2 = Classroom.objects.create(
            name="CA Classroom Org2",
            description="Org2の教室",
            organization=self.org2,
        )

        self.classroom_admin_org1 = ClassroomAdministrator.objects.create(
            username="CA Org1",
            email="ca_org1@example.com",
            role="classroom_administrator",
            organization=self.org1,
        )

    def test_clean_detects_invalid_existing_classroom(self):
        """
        何らかの理由で ClassroomAdministrator に異なる organization の教室が
        紐付いてしまっている場合、clean() が ValidationError を投げる
        """
        # まずは正しい教室を紐付ける
        self.classroom_admin_org1.classrooms.add(self.classroom_org1)

        # その後、強引に organization を org2 に変更して矛盾を発生させる
        self.classroom_admin_org1.organization = self.org2

        with self.assertRaises(ValidationError):
            self.classroom_admin_org1.clean()
