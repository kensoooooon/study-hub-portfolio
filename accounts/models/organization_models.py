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
            return self.organization.administrators.filter(id=user.id).exists()
        elif user.role == 'classroom_administrator':
            return self.administrators.filter(id=user.id).exists()
        return False

    """
    # おそらく使ってないはず(self.roleはn)
    def get_accessible_classrooms(self):
        if self.role == 'organization_administrator':
            return Classroom.objects.filter(organization__administrators=self)
        elif self.role == 'classroom_administrator':
            return self.classrooms.all()
        return Classroom.objects.none()
    """

class Organization(models.Model):
    """
    組織モデル
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="組織名")

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
            return self.administrators.filter(id=user.id).exists()
        elif user.role == 'classroom_administrator':
            return self.classrooms.filter(administrators__id=user.id).exists()
        return False

