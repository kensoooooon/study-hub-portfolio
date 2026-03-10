# text_scheduler/templatetags/url_extras.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag(takes_context=True)
def url_with_query(context, base_url, **extras):
    """
    base_url に、現在の request.GET（ホワイトリスト）と extras を合成。
    - None/空文字は無視
    - 同名キーは extras を優先して「上書き」
    """
    request = context.get("request")
    params = {}

    if request:
        # 必要なキーだけ拾う（重複は最後の値1つに正規化）
        allow = {"student_id", "classroom_id", "number", "kind"}
        for k in allow:
            values = request.GET.getlist(k)
            if values:
                params[k] = [values[-1]]  # 最後の値で1本化

    # 追加パラメータは上書き（重複を作らない）
    for k, v in extras.items():
        if v not in (None, ""):
            params[k] = [v]

    qs = urlencode(params, doseq=True)
    return f"{base_url}?{qs}" if qs else base_url
