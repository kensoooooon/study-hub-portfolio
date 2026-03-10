from django.core.management.base import BaseCommand
from accounts.models import Student
from vocab_trainer.models import StudentContextProgress, QuizResult

class Command(BaseCommand):
    help = "student.textbook と一致しない学習履歴を削除します"

    def handle(self, *args, **kwargs):
        deleted_progress_count = 0
        deleted_quizresult_count = 0

        for student in Student.objects.all():
            if not student.textbook:
                continue

            self.stdout.write(f"処理中: {student}")

            # StudentContextProgress
            mismatched_progress = StudentContextProgress.objects.filter(
                student=student
            ).exclude(
                context__chapter__textbook=student.textbook
            )
            deleted_progress_count += mismatched_progress.count()
            mismatched_progress.delete()

            # QuizResult
            mismatched_quizresult = QuizResult.objects.filter(
                student=student
            ).exclude(
                context__chapter__textbook=student.textbook
            )
            deleted_quizresult_count += mismatched_quizresult.count()
            mismatched_quizresult.delete()

        self.stdout.write(self.style.SUCCESS(
            f"削除完了: Progress={deleted_progress_count}, QuizResult={deleted_quizresult_count}"
        ))
