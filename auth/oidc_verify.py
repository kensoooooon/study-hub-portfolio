from functools import wraps

from django.conf import settings
from django.http import JsonResponse

from google.oauth2 import id_token
from google.auth.transport import requests


def require_oidc_token(audience: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # 🔹 local のときは認証をスキップしてそのまま通す
            if getattr(settings, "ENV", "local") == "local":
                return view_func(request, *args, **kwargs)

            # 🔹 本番など local 以外の環境では OIDC トークンを検証
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JsonResponse({"error": "Unauthorized"}, status=403)

            token = auth_header.split(" ")[1]
            try:
                id_token.verify_oauth2_token(token, requests.Request(), audience)
            except Exception:
                return JsonResponse({"error": "Invalid token"}, status=403)

            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator
