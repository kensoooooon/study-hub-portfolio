from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.db.models.deletion import ProtectedError
from django.test import TestCase

from vocab_trainer.models import Chapter, Textbook
from accounts.models import Student
from accounts.forms import StudentEditForm, StudentEditForTeachersForm


class TextbookQuerySetTest(TestCase):
    """
    カスタムマネジャーの挙動をテスト
    """
    def setUp(self):
        self.active_tb = Textbook.objects.create(name="Active", publisher="P", grade=1, is_active=True)
        self.inactive_tb = Textbook.objects.create(name="Inactive", publisher="P", grade=1, is_active=False)

    def test_active_returns_only_active(self):
        """
        activeで呼び出した場合は、activeしか返さない
        """
        qs = Textbook.objects.active()
        self.assertIn(self.active_tb, qs)
        self.assertNotIn(self.inactive_tb, qs)

    def test_inactive_returns_only_inactive(self):
        """
        inactiveで呼び出した場合は、inactiveなものしか返さない
        """
        qs = Textbook.objects.inactive()
        self.assertIn(self.inactive_tb, qs)
        self.assertNotIn(self.active_tb, qs)

    def test_all_returns_both(self):
        """
        allで呼び出した場合は、両方を返す
        """
        qs = Textbook.objects.all()
        self.assertIn(self.active_tb, qs)
        self.assertIn(self.inactive_tb, qs)


class TextbookDeactivateTest(TestCase):
    """
    教科書モデルに追加した無効化と削除のメソッド確認用
    """
    def setUp(self):
        self.textbook = Textbook.objects.create(name="TB", publisher="P", grade=1)

    def test_deactivate_sets_is_active_false(self):
        """
        deactivateを呼び出した場合、無効化されるがDBから消えたりはしない
        """
        pk = self.textbook.pk
        self.textbook.deactivate()
        self.textbook.refresh_from_db()
        self.assertFalse(self.textbook.is_active)
        self.assertTrue(Textbook.objects.filter(pk=pk).exists())

    def test_delete_override_soft_deletes(self):
        """
        deleteを呼び出した場合、無効化されるがDBから消えはしない
        """
        pk = self.textbook.pk
        self.textbook.delete()
        self.textbook.refresh_from_db()
        self.assertFalse(self.textbook.is_active)
        self.assertTrue(Textbook.objects.filter(pk=pk).exists())

    def test_inactive_textbook_str_has_inactive_prefix(self):
        """
        無効化された教科書は、無効という表現が入る
        """
        textbook = Textbook.objects.create(
            name="Inactive Book",
            publisher="P",
            grade=1,
            publication_year=2025,
            is_active=False,
        )

        self.assertTrue(str(textbook).startswith("【無効】"))

    def test_delete_override_removes_from_active_queryset(self):
        """
        削除された後はアクティブなクエリセットには含まれず、非アクティブなクエリセットには含まれる
        """
        self.textbook.delete()

        self.assertNotIn(self.textbook, Textbook.objects.active())
        self.assertIn(self.textbook, Textbook.objects.inactive())

class TextbookProtectTest(TestCase):
    """
    教科書モデルに設定した、on_delete=models.PROTECTのテスト
    """
    def setUp(self):
        self.textbook = Textbook.objects.create(name="TB", publisher="P", grade=2)
        self.chapter = Chapter.objects.create(textbook=self.textbook, title="Ch1", order=1)

    def test_queryset_delete_raises_protected_error(self):
        """チャプターが紐づいている教科書を消そうとしてもエラーが発生して削除できない"""
        with self.assertRaises(ProtectedError):
            Textbook.objects.filter(pk=self.textbook.pk).delete()

    def test_textbook_without_chapters_can_be_deleted_via_queryset(self):
        """
        チャプターが紐づいていないものであれば、削除可能
        """
        tb_no_chapter = Textbook.objects.create(name="Empty", publisher="P", grade=2)
        Textbook.objects.filter(pk=tb_no_chapter.pk).delete()
        self.assertFalse(Textbook.objects.filter(pk=tb_no_chapter.pk).exists())


class TextbookFormQuerysetTest(TestCase):
    """
    教科書編集に関わるフォームのテスト
    """
    def setUp(self):
        self.active_tb = Textbook.objects.create(name="Active", publisher="P", grade=1, is_active=True)
        self.inactive_tb = Textbook.objects.create(name="Inactive", publisher="P", grade=1, is_active=False)
        self.other_inactive_tb = Textbook.objects.create(
            name="Other Inactive", publisher="P", grade=1, is_active=False
        )
        self.student = Student.objects.create_user(
            username="s1", password="pw", email="s1@test.com"
        )
        self.student.textbook = self.inactive_tb
        self.student.save()

    def test_student_edit_form_includes_current_inactive(self):
        """
        無効化された教科書も既に利用中であれば選択肢にでてくる
        """
        form = StudentEditForm(instance=self.student)
        qs = form.fields["textbook"].queryset
        self.assertIn(self.active_tb, qs)
        self.assertIn(self.inactive_tb, qs)

    def test_student_edit_form_excludes_unrelated_inactive(self):
        """
        無効化された教科書でも、利用していないものは選択肢にでてこない
        """
        form = StudentEditForm(instance=self.student)
        qs = form.fields["textbook"].queryset
        self.assertNotIn(self.other_inactive_tb, qs)

    def test_student_edit_form_excludes_inactive_for_new_student(self):
        """
        教科書が設定されていない生徒にはアクティブな教科書のみ表示される
        """
        new_student = Student.objects.create_user(
            username="s2", password="pw", email="s2@test.com"
        )
        form = StudentEditForm(instance=new_student)
        qs = form.fields["textbook"].queryset
        self.assertIn(self.active_tb, qs)
        self.assertNotIn(self.inactive_tb, qs)
        self.assertNotIn(self.other_inactive_tb, qs)

    def test_teacher_form_excludes_inactive_for_student_without_textbook(self):
        """
        講師専用のフォームにおいても、新しい生徒ではアクティブな教科書だけが表示される
        """
        new_student = Student.objects.create_user(
            username="s3",
            password="pw",
            email="s3@test.com",
        )

        form = StudentEditForTeachersForm(instance=new_student)
        qs = form.fields["textbook"].queryset

        self.assertIn(self.active_tb, qs)
        self.assertNotIn(self.inactive_tb, qs)
        self.assertNotIn(self.other_inactive_tb, qs)

    def test_teacher_form_includes_current_inactive_only(self):
        """
        講師専用フォームにおいても、アクティブな教科書と既に設定されている教科書の両方が表示される
        """
        form = StudentEditForTeachersForm(instance=self.student)
        qs = form.fields["textbook"].queryset
        self.assertIn(self.active_tb, qs)
        self.assertIn(self.inactive_tb, qs)
        self.assertNotIn(self.other_inactive_tb, qs)


class ImportVocabDataInactiveTest(TestCase):
    """
    語彙データのインポートに関するテスト
    """
    def setUp(self):
        self.inactive_tb = Textbook.objects.create(
            name="Test Book",
            publisher="P",
            grade=1,
            publication_year=2023,
            is_active=False,
        )

    @patch("vocab_trainer.management.commands.import_vocab_data.get_file_information")
    def test_import_skips_inactive_textbook(self, mock_get_info):
        """
        対象が無効化された教科書であった場合、処理がスキップされる
        """
        mock_get_info.return_value = ("Test Book", "2023年度", "1年", "名詞")
        from vocab_trainer.management.commands.import_vocab_data import Command
        cmd = Command(stdout=StringIO(), stderr=StringIO())
        cmd.chapter_orders = {}
        cmd.process_tsv(Path("dummy/dummy/dummy/dummy.tsv"))
        self.inactive_tb.refresh_from_db()
        self.assertFalse(self.inactive_tb.is_active)
        self.assertFalse(Textbook.objects.active().filter(name="Test Book", grade=1).exists())
        self.assertEqual(
            Textbook.objects.filter(name="Test Book", grade=1, publication_year=2023).count(),
            1,
        )


class UpdateVocabDataInactiveTest(TestCase):
    """
    語彙のアップデートに関するテスト
    """
    def setUp(self):
        self.inactive_tb = Textbook.objects.create(
            name="Test Book",
            publisher="P",
            grade=1,
            publication_year=2023,
            is_active=False,
        )

    @patch("vocab_trainer.management.commands.update_vocab_data.get_file_information")
    def test_update_skips_inactive_textbook(self, mock_get_info):
        """
        無効化された教科書は処理をスキップされる
        """
        mock_get_info.return_value = ("Test Book", "2023年度", "1年", "名詞")
        from vocab_trainer.management.commands.update_vocab_data import Command
        cmd = Command(stdout=StringIO(), stderr=StringIO())
        cmd.process_update(Path("dummy/dummy/dummy/dummy.tsv"))
        self.inactive_tb.refresh_from_db()
        self.assertFalse(self.inactive_tb.is_active)
