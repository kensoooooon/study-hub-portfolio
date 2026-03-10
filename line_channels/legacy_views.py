"""
2025/11/1
adapters.pyに分離したので、これを直接使うことは無いのでは？
→ない
"""
import json, base64, hmac, hashlib
from json import JSONDecodeError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden

from line_channels.models import LineChannel, KeyKind
from line_channels.services import get_secret

@csrf_exempt
@require_POST
def webhook(request):
    ctype = request.headers.get("Content-Type", "")
    if "application/json" not in ctype:
        return HttpResponseBadRequest("invalid content-type")

    body = request.body
    try:
        payload = json.loads(body)
        dest = payload.get("destination")
        ch = LineChannel.objects.get(bot_user_id=dest, is_active=True)
    except (JSONDecodeError, KeyError, TypeError):
        return HttpResponseBadRequest("invalid body")
    except LineChannel.DoesNotExist:
        return HttpResponseBadRequest("unknown destination")

    secret = get_secret(ch, KeyKind.CHANNEL_SECRET)
    signature = request.headers.get("X-Line-Signature") or request.META.get("HTTP_X_LINE_SIGNATURE", "")
    expected = base64.b64encode(hmac.new(secret, body, hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(signature, expected):
        return HttpResponseForbidden("invalid signature")

    # TODO: Pub/Sub publish or immediate handling
    return HttpResponse("ok")
