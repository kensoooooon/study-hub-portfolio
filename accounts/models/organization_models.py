from django.db import models



class Classroom(models.Model):
    """
    教室モデル
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="教室名")
    description = models.TextField(blank=True, null=True, verbose_name="説明")
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='classrooms', verbose_name="所属組織"
    )

    def __str__(self):
        return self.name

    def can_be_accessed_by(self, user):
        """
        ユーザーがその教室にアクセスできるかを判定
        """
        if user.role == 'organization_administrator':
            admin = user.get_role_object()
            return admin is not None and admin.organization_id == self.organization_id
        elif user.role == 'classroom_administrator':
            return self.administrators.filter(id=user.id).exists()
        return False

class Organization(models.Model):
    """
    組織モデル
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="組織名")
    
    class Meta:
        permissions = [  # 独自権限の設定
            ('view_all_organizations', "Can view all organizations"),  # 全ての組織を閲覧可能
            ('invite_organization_administrator', "Invite new organization administrator"),  # 組織管理者として新規ユーザーを招待可能
        ]

    def get_managed_classrooms(self):
        """
        組織に関連付けられたすべての教室を取得する
        """
        return self.classrooms.all()

    def __str__(self):
        return self.name

    def can_be_accessed_by(self, user):
        """
        ユーザーがこの組織にアクセスできるかを判定
        """
        if user.role == 'organization_administrator':
            admin = user.get_role_object()
            return admin is not None and admin.organization_id == self.pk
        elif user.role == 'classroom_administrator':
            return self.classrooms.filter(administrators__id=user.id).exists()
        return False

