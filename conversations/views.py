from django.http import JsonResponse
from django.views import View
from accounts.models import Student
from processors.summary_processor import SummaryProcessor

from django.core.exceptions import PermissionDenied
from conversations.models import StudentSummary, MessageLog

# br直接表示防止用
from django.utils.html import escape


class StudentSummaryView(View):
    def get(self, request, student_id):
        # 🔐 生徒が存在するか確認
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return JsonResponse({"error": "生徒が見つかりません"}, status=404)

        # 🔐 アクセス制限チェック（StudentDetailViewと同等）
        role_object = request.user.get_role_object()

        role_object = request.user.get_role_object()
        if not role_object or not hasattr(role_object, 'can_manage_student') or not role_object.can_manage_student(student):
            raise PermissionDenied("この生徒にアクセスする権限がありません。")

        # ✅ 要約キャッシュの取得または生成
        summary_obj, created = StudentSummary.objects.get_or_create(student=student)

        if not created and not summary_obj.needs_update():
            # 🔁 キャッシュ有効時は再利用
            safe_text = escape(summary_obj.summary_text)
            formatted_summary = safe_text.replace("\n", "<br>")
        else:
            # ♻️ 再生成
            summary_processor = SummaryProcessor(student)
            summary = summary_processor.generate_summary()

            logs = MessageLog.objects.filter(
                conversation__student=student,
                is_sent_by_user=True
            )
            new_count = logs.count()
            latest_message = logs.order_by('-timestamp').first()

            summary_obj.summary_text = summary
            summary_obj.last_conversation_count = new_count
            summary_obj.last_message_timestamp = latest_message.timestamp if latest_message else None
            summary_obj.save()

            safe_text = escape(summary)
            formatted_summary = safe_text.replace("\n", "<br>")

        return JsonResponse({"student": student.username, "summary": formatted_summary}, status=200)