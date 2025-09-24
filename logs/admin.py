# from django.contrib import admin
# from .models import EmployeeProfile, DailyLog

# # Register your models here.
# @admin.register(EmployeeProfile)
# class EmployeeProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'id_card_number')
#     search_fields = ('user__username', 'user__first_name', 'user__last_name', 'id_card_number')

# @admin.register(DailyLog)
# class DailyLogAdmin(admin.ModelAdmin):
#     list_display = ('employee', 'date', 'time_interval', 'status')
#     list_filter = ('date', 'status')
#     search_fields = ('employee__username', 'description')
