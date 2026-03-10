from django.contrib import admin
from .models import StudyReminder

@admin.register(StudyReminder)
class StudyReminderAdmin(admin.ModelAdmin):
    list_display = ('student', 'day_of_week', 'time_of_day', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    search_fields = ('student__username',)
