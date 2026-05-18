from django.contrib import admin

from .models import LeaveRequest


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
	list_display = ('employee', 'start_date', 'end_date', 'leave_type', 'leave_reason', 'days_count', 'status', 'approver', 'requested_at')
	list_filter = ('status', 'leave_type', 'employee__department')
	search_fields = ('employee__name', 'employee__employee_number')
