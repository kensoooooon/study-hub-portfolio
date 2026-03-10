from django.contrib import admin
from accounts.models import Student, Teacher, ClassroomAdministrator, OrganizationAdministrator 

class TeachersInline(admin.TabularInline):
    """
    生徒ごとの講師をインライン表示
    """
    model = Student.teachers.through  # ManyToManyの中間テーブルを指定
    extra = 1  # 追加可能な行数


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """
    Student 管理画面
    """
    list_display = ('username', 'email', 'is_active', 'date_joined', 'line_user_id')
    search_fields = ('username', 'email', 'line_user_id')
    list_filter = ('is_active', 'date_joined')
    readonly_fields = ('date_joined',)
    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'line_user_id', 'is_active', 'date_joined'),
        }),
    )
    inlines = [TeachersInline]
    filter_horizontal = ('teachers',)  # 講師との紐づけを水平フィルタで表示



@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    """
    Teacher 管理画面
    """
    list_display = ('username', 'email', 'is_active', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'date_joined')
    readonly_fields = ('date_joined',)
    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'is_active', 'date_joined'),
        }),
    )


@admin.register(ClassroomAdministrator)
class ClassroomAdministratorAdmin(admin.ModelAdmin):
    """
    ClassroomAdministrator 管理画面
    """
    list_display = ('username', 'email', 'is_active', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'date_joined')
    readonly_fields = ('date_joined',)
    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'is_active', 'date_joined'),
        }),
    )


@admin.register(OrganizationAdministrator)
class OrganizationAdministratorAdmin(admin.ModelAdmin):
    """
    OrganizationAdministrator 管理画面
    """
    list_display = ('username', 'email', 'is_active', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'date_joined')
    readonly_fields = ('date_joined',)
    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'is_active', 'date_joined'),
        }),
    )
    
