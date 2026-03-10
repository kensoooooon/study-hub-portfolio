import datetime as dt
import pytest
from django.urls import reverse
from django.utils import timezone
from accounts.models import Student, Teacher, Classroom, OrganizationAdministrator, Organization
from text_scheduler.models import LearningMaterial

import json

@pytest.mark.django_db
def test_create_update_delete_flow(client, django_user_model):
    # 下準備：組織・教室・講師・生徒
    org = Organization.objects.create(name="OrgA")
    cls = Classroom.objects.create(name="A-1", organization=org)

    teacher = Teacher.objects.create_user(email="t@example.com", password="pass", role="teacher")
    teacher.classrooms.add(cls)

    student = Student.objects.create_user(email=None, password="pass", role="student", username="stu")
    student.classrooms.add(cls)
    # 担当講師として追加
    student.teachers.add(teacher)

    # ログイン
    client.login(email="t@example.com", password="pass")

    # Create
    url = reverse("text_scheduler:material_create", kwargs={"student_id": student.pk})
    resp = client.get(url)
    assert resp.status_code == 200


    payload = {
        "title": "Unit 1",
        "unit_label": "page",
        "start_number": 1,
        "end_number": 3,
        "required_reviews": 2,
        "estimated_minutes_per_unit": 10,
        "start_date": (timezone.now().date()).isoformat(),
        "goal_date": (timezone.now().date() + dt.timedelta(days=7)).isoformat(),
        "buffer_weekdays": json.dumps([0, 2, 4]),  # ← ここをJSON文字列で
        "is_archived": False,
    }
    resp = client.post(url, data=payload)
    assert resp.status_code == 302  # 成功時は編集画面へリダイレクト
    obj = LearningMaterial.objects.get(title="Unit 1")
    assert obj.created_by_id == teacher.pk
    assert obj.target_student_id == student.pk

    # Update
    edit = reverse("text_scheduler:material_edit", kwargs={"pk": obj.pk})
    resp = client.get(edit)
    assert resp.status_code == 200
    payload["title"] = "Unit 1 (rev)"
    resp = client.post(edit, data=payload, follow=True)
    assert resp.status_code == 200
    obj.refresh_from_db()
    assert obj.title == "Unit 1 (rev)"

    # Delete
    delete = reverse("text_scheduler:material_delete", kwargs={"pk": obj.pk})
    resp = client.post(delete, follow=True)
    assert resp.status_code == 200
    assert not LearningMaterial.objects.filter(pk=obj.pk).exists()

@pytest.mark.django_db
def test_access_control_denies_other_teacher(client):
    org = Organization.objects.create(name="OrgB")
    cls = Classroom.objects.create(name="B-1", organization=org)

    t1 = Teacher.objects.create_user(email="t1@example.com", password="pass", role="teacher")
    t1.classrooms.add(cls)

    t2 = Teacher.objects.create_user(email="t2@example.com", password="pass", role="teacher")
    # t2 はクラス未所属

    stu = Student.objects.create_user(email=None, password="pass", role="student", username="s")
    stu.classrooms.add(cls)

    # t1 が作成
    lm = LearningMaterial.objects.create(
        title="x",
        unit_label="page",
        start_number=1,
        end_number=1,
        required_reviews=1,
        estimated_minutes_per_unit=5,
        start_date=timezone.now().date(),
        goal_date=timezone.now().date() + dt.timedelta(days=1),
        buffer_weekdays=[1],
        is_archived=False,
        target_student=stu,
        created_by=t1,
    )

    # t2 では閲覧/編集/削除できない（404）
    client.login(email="t2@example.com", password="pass")
    resp = client.get(reverse("text_scheduler:material_edit", kwargs={"pk": lm.pk}))
    assert resp.status_code == 404
    resp = client.post(reverse("text_scheduler:material_delete", kwargs={"pk": lm.pk}))
    assert resp.status_code == 404
