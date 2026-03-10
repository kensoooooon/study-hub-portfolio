from urllib.parse import urlencode

from typing import Optional


def build_url(base_url: str, student_id: Optional[str], classroom_id: Optional[str]) -> str:
    """パラメータの有無も加味したURLを作成

    Args:
        base_url (str): 基礎となるリンク先
        student_id (Optional[str]): 対象の生徒ID
        classroom_id (Optional[str]): 対象の教室ID

    Returns:
        str: パラメータの有無が考慮されたURL
    """
    params = {}
    if student_id:
        params["student_id"] = str(student_id)
    if classroom_id:
        params["classroom_id"] = str(classroom_id)
    
    if params:
        url = f"{base_url}?{urlencode(params)}"
    else:
        url = base_url
    
    return url
