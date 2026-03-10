from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone

from math_trainer.models import ProblemSession, ProblemInstance, StudentAnswer

from uuid import UUID
from django.http import HttpResponseBadRequest, HttpResponseForbidden

from django.db.models import Min, Max, Count

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from math_trainer.utils.student_access_check import student_access_check
from math_trainer.utils.session_access_check import session_access_check


import logging

logger = logging.getLogger(__name__)


class ScoringView(LoginRequiredMixin, View):
    def _build_keep_query(self, *, exclude=("page",)):
        """採点したいセッションのペジネーション用メソッド"""
        q = self.request.GET.copy()
        for k in exclude:
            q.pop(k, None)
        return ("&" + q.urlencode()) if q else ""

    def get(self, request):
        """
        セッションIDが指定されていない場合は「一覧モード」
        指定されている場合は「採点フォームモード」
        """
        # session_ids = request.GET.getlist("session_id")
        session_id = request.GET.get("session_id")
        if session_id:
            # 採点フォームモード
            raw_session_id = session_id
            user = request.user
            session = session_access_check(user, raw_session_id, mode="print")
            instances = (ProblemInstance.objects
                        .filter(session=session)
                        .select_related("session")
                        .order_by("session__created_at", "order", "id"))
            return render(request, "math_trainer/common/scoring.html", {
                "mode": "grade",
                "session": session,  # ← 単数
                "instances": instances,
                "classroom_id": request.GET.get("classroom_id"),
                "student_id": session.student.id,
            })

        # 一覧モード（未採点のみ・可視範囲のみ・直近200件）
        qs = (ProblemSession.objects
            .select_related("student", "problem_type")
            .filter(mode="print", score__isnull=True)
            .visible_to(request.user))  # 既存の可視範囲制御を踏襲

        raw_student_id = request.GET.get("student_id")
        user = request.user
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        
        if student_id:
            qs = qs.filter(student_id=student_id)

        qs = (qs
            .annotate(
                min_inst_id=Min("problems__id"),
                max_inst_id=Max("problems__id"),
                inst_count=Count("problems__id"),
            )
            .order_by("-created_at")[:200])
        
        # ペジネーション設定
        page = request.GET.get('page', 1)
        per_page = 20
        orphans = 0  # 端数は次ページへ
        paginator = Paginator(qs, per_page, orphans=orphans)
        
        try:
            page_obj = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        
        # 省メモリのための施策
        qs_keep = self._build_keep_query()
        
        # 省略記法のページ範囲(Django >= 3.2)
        elided = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

        return render(request, "math_trainer/common/scoring.html", {
            "mode": "index",
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": paginator.num_pages > 1,
            "elided_page_range": elided,
            "qs_keep": qs_keep,
            "classroom_id": request.GET.get("classroom_id"),
            "student_id": student_id,
        })

    @transaction.atomic
    def post(self, request):
        """
        入力された情報を元に記録を実行。同時に結果表示画面に必要な情報を渡す
        
        Notes:
            採点方式は、inst.id = ProblemInstanceのIDで紐づけを行い、
            1 = 正解、0 = 不正解で判定
            
            採点の際には「平均点」をセッションのスコアとする
        """
        session_id = request.POST.get("session_id")
        try:
            UUID(str(session_id))
        except Exception:
            return HttpResponseBadRequest("invalid session_id")

        raw_session_id = session_id
        user = request.user
        session = session_access_check(user, raw_session_id, mode="print")
        instances = ProblemInstance.objects.filter(session=session)

        total = 0
        correct = 0
        for inst in instances:
            raw = request.POST.get(f"q_{inst.id}")  # "1" or "0"
            if raw not in ("0", "1"):
                continue
            is_ok = (raw == "1")
            StudentAnswer.objects.update_or_create(
                student=inst.session.student,
                problem_instance=inst,
                defaults={
                    "selected_choice": "",
                    "is_correct": is_ok,
                    "answered_at": timezone.now(),
                }
            )
            total += 1
            correct += int(is_ok)

        # セッションのスコアを保存（平均）
        denom = total or 1
        session.score = correct / denom
        session.save(update_fields=["score"])

        # 結果画面用サマリ（従来の形に合わせて dict で）
        per_session = {str(session.id): {"correct": correct, "total": total}}

        classroom_id = request.POST.get("classroom_id") or request.GET.get("classroom_id")
        raw_student_id   = request.POST.get("student_id")   or request.GET.get("student_id")
        user = request.user
        student = student_access_check(user, raw_student_id)        
        student_id = student.id
        request.session["classroom_id"] = classroom_id
        request.session["student_id"]   = str(student_id) if student_id else None
        
        request.session["grade_result"] = per_session
        return redirect("math_trainer:common:result")


class GradeResultView(LoginRequiredMixin, View):
    def get(self, request):
        """
        採点の要約を踏まえて、結果表示に必要なものの取り出し、および値の加工
        """
        raw_student_id = request.session.get("student_id")
        user = request.user
        student = student_access_check(user, raw_student_id)
        student_id = student.id

        classroom_id = request.session.get("classroom_id")
        summary = request.session.pop("grade_result", {}) or {}

        rows = []
        for sid, v in summary.items():  # sid は str（先の修正済み前提）
            correct = int(v.get("correct", 0))
            total   = int(v.get("total", 0))
            score   = (correct / total) if total else None
            rows.append({
                "sid": sid,
                "correct": correct,
                "total": total,
                "score": score,                      # 小数（テンプレで floatformat 可）
            })

        return render(
            request,
            "math_trainer/common/result.html",
            {
                "rows": rows,
                'student_id': student_id,
                'classroom_id': classroom_id}
        )
