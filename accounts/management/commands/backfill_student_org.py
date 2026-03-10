"""
2025/11/9
いったんnull, blank=Trueでorganizationを処理した後に走らせて、所属教室からの逆算でorgを埋めるコマンド
"""
from django.core.management.base import BaseCommand
from accounts.models import Student

class Command(BaseCommand):
    help = "Student.organization を Classroom から自動推定して埋める"

    def handle(self, *args, **opts):
        qs = Student.objects.filter(organization__isnull=True)
        for s in qs.iterator():
            org_ids = list(s.classrooms.values_list('organization_id', flat=True).distinct())
            if len(org_ids) == 1:
                s.organization_id = org_ids[0]
                s.save(update_fields=['organization'])
            else:
                # 0件 or 複数件はスキップ（後で手動補完）
                self.stdout.write(f"SKIP {s.id} org_candidates={org_ids}")