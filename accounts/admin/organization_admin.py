from django.contrib import admin
from accounts.models import Organization, Classroom


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """
    Organization 管理画面
    """
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    """
    Classroom 管理画面
    """
    list_display = ('name', 'organization')
    search_fields = ('name', 'organization__name')
    list_filter = ('organization',)
