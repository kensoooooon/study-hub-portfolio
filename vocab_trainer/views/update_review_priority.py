from django.http import JsonResponse
from vocab_trainer.models import StudentContextProgress
from django.views.decorators.csrf import csrf_exempt
import logging

# OIDC認証
from auth.oidc_verify import require_oidc_token

logger = logging.getLogger(__name__)


@csrf_exempt
@require_oidc_token(audience="https://django-study-hub.an.r.appspot.com")
def update_review_priority(request):
    """
    Google Cloud Scheduler で毎週 review_priority を再計算する
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # Cloud Scheduler からの呼び出しか確認
    if request.headers.get("X-Appengine-Cron") != "true":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    # ✅ すべての進捗情報の復習優先度を再計算
    progress_list = StudentContextProgress.objects.all()

    updated_count = 0
    for progress in progress_list:
        # ✅ 時間経過のみで review_priority を更新
        progress.update_review_priority_by_time()
        updated_count += 1

    logger.info(f"Updated review_priority for {updated_count} entries based on time.")
    return JsonResponse({"status": "success", "updated_entries": updated_count})
