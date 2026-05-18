from django.contrib import admin
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .audit import write_audit_log
from .models import AuditLog, Employee, HRRecord, SignupRequest


def _has_signup_account_link(signup):
	user = User.objects.filter(username=signup.employee_number).first()
	if user is None:
		return False
	employee = Employee.objects.filter(employee_number=signup.employee_number).select_related('user').first()
	return bool(employee and employee.user == user)


def _finalize_signup_approval(signup, actor):
	with transaction.atomic():
		if signup.employee_number.startswith('REQ-'):
			raise ValueError('임시 사번입니다. 승인 전 가입신청에서 사번을 수정해 주세요.')

		if not signup.position or signup.position == '미기재':
			raise ValueError('직급 미기재입니다. 승인 전 가입신청에서 직급을 입력해 주세요.')

		user = User.objects.filter(username=signup.employee_number).first()
		if user is None:
			user = User.objects.create_user(
				username=signup.employee_number,
				first_name=signup.name,
			)
		user.first_name = signup.name
		user.password = signup.password_hash
		user.save(update_fields=['first_name', 'password'])

		employee = Employee.objects.filter(employee_number=signup.employee_number).first()
		if employee is None:
			Employee.objects.create(
				user=user,
				name=signup.name,
				employee_number=signup.employee_number,
				department=signup.department,
				position=signup.position,
				hire_date=signup.hire_date,
				employment_status=Employee.EmploymentStatus.ACTIVE,
			)
		else:
			if employee.user is not None and employee.user != user:
				raise ValueError('해당 직원은 이미 다른 사용자와 연결되어 있습니다.')
			employee.user = user
			employee.name = signup.name
			employee.department = signup.department
			employee.position = signup.position
			employee.hire_date = signup.hire_date
			employee.employment_status = Employee.EmploymentStatus.ACTIVE
			employee.save()

		signup.status = SignupRequest.Status.APPROVED
		signup.processed_by = actor
		signup.processed_at = timezone.now()
		signup.admin_memo = ''
		signup.save(update_fields=['status', 'processed_by', 'processed_at', 'admin_memo'])
		write_audit_log(
			actor=actor,
			action='signup_approved',
			target=signup,
			detail=f'가입신청 승인: {signup.employee_number} ({signup.name})',
		)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
	list_display = ('name', 'employee_number', 'department', 'position', 'employment_status')
	list_filter = ('employment_status', 'department')
	search_fields = ('name', 'employee_number', 'department', 'position')


@admin.register(HRRecord)
class HRRecordAdmin(admin.ModelAdmin):
	list_display = ('employee', 'year', 'department_change', 'position_change', 'created_at')
	list_filter = ('year',)
	search_fields = ('employee__name', 'employee__employee_number', 'memo')


@admin.register(SignupRequest)
class SignupRequestAdmin(admin.ModelAdmin):
	list_display = ('employee_number', 'name', 'department', 'position', 'status', 'requested_at', 'processed_at', 'processed_by')
	list_filter = ('status', 'department')
	search_fields = ('employee_number', 'name', 'position')
	readonly_fields = ('requested_at', 'processed_at', 'processed_by', 'password_hash')
	actions = ('approve_requests', 'reject_requests')

	def save_model(self, request, obj, form, change):
		previous_status = None
		if change:
			previous_status = SignupRequest.objects.only('status').get(pk=obj.pk).status

		needs_account_sync = obj.status == SignupRequest.Status.APPROVED and (
			previous_status != SignupRequest.Status.APPROVED or not _has_signup_account_link(obj)
		)

		if needs_account_sync:
			# 상세 화면에서 승인 상태로 저장해도 동일한 승인 로직을 적용한다.
			obj.status = previous_status or SignupRequest.Status.PENDING
			super().save_model(request, obj, form, change)
			signup = SignupRequest.objects.get(pk=obj.pk)
			try:
				_finalize_signup_approval(signup, request.user)
				self.message_user(request, '가입신청 승인 처리되었습니다.')
			except Exception as exc:  # noqa: BLE001
				signup.admin_memo = str(exc)
				signup.save(update_fields=['admin_memo'])
				self.message_user(request, f'가입신청 승인 실패: {exc}', level='warning')
			return

		super().save_model(request, obj, form, change)

	@admin.action(description='선택한 가입신청 승인 처리')
	def approve_requests(self, request, queryset):
		approved = 0
		failed = 0
		for signup in queryset.filter(status=SignupRequest.Status.PENDING):
			try:
				_finalize_signup_approval(signup, request.user)
				approved += 1
			except Exception as exc:  # noqa: BLE001
				signup.admin_memo = str(exc)
				signup.save(update_fields=['admin_memo'])
				failed += 1

		if approved:
			self.message_user(request, f'{approved}건 승인 처리되었습니다.')
		if failed:
			self.message_user(request, f'{failed}건 승인 실패했습니다. 관리자 메모를 확인하세요.', level='warning')

	@admin.action(description='선택한 가입신청 반려 처리')
	def reject_requests(self, request, queryset):
		pending_requests = queryset.filter(status=SignupRequest.Status.PENDING)
		now = timezone.now()
		updated = 0
		for signup in pending_requests:
			signup.status = SignupRequest.Status.REJECTED
			signup.processed_by = request.user
			signup.processed_at = now
			signup.save(update_fields=['status', 'processed_by', 'processed_at'])
			write_audit_log(
				actor=request.user,
				action='signup_rejected',
				target=signup,
				detail=f'가입신청 반려: {signup.employee_number} ({signup.name})',
			)
			updated += 1
		self.message_user(request, f'{updated}건 반려 처리되었습니다.')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
	list_display = ('created_at', 'actor', 'action', 'target_model', 'target_id', 'target_repr')
	list_filter = ('action', 'target_model', 'created_at')
	search_fields = ('target_repr', 'detail', 'actor__username')
	readonly_fields = ('created_at', 'actor', 'action', 'target_model', 'target_id', 'target_repr', 'detail')

	def has_add_permission(self, request):
		return False

	def has_change_permission(self, request, obj=None):
		return False
