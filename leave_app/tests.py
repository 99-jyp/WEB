from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from employee.models import Employee

from .models import LeaveRequest


class LeaveDecisionCorrectionTests(TestCase):
	def setUp(self):
		self.staff_user = User.objects.create_user(
			username='manager',
			password='testpass123',
			is_staff=True,
		)
		self.employee_user = User.objects.create_user(
			username='employee1',
			password='testpass123',
		)
		self.employee = Employee.objects.create(
			user=self.employee_user,
			name='테스트직원',
			employee_number='E-0001',
			department=Employee.Department.GENERAL_AFFAIRS,
			position='사원',
			hire_date=date(2024, 1, 2),
		)

	def _create_leave(self, *, status, start_date_value, end_date_value):
		return LeaveRequest.objects.create(
			employee=self.employee,
			start_date=start_date_value,
			end_date=end_date_value,
			leave_type=LeaveRequest.LeaveType.ANNUAL,
			leave_reason='개인 사유',
			status=status,
		)

	def test_staff_can_correct_approved_to_rejected(self):
		leave = self._create_leave(
			status=LeaveRequest.LeaveStatus.APPROVED,
			start_date_value=date(2026, 5, 1),
			end_date_value=date(2026, 5, 2),
		)
		self.client.force_login(self.staff_user)

		response = self.client.post(
			reverse('leave_app:reject', args=[leave.pk]),
			{'reject_reason': '업무 일정 충돌'},
		)

		self.assertRedirects(response, reverse('leave_app:list'))
		leave.refresh_from_db()
		self.assertEqual(leave.status, LeaveRequest.LeaveStatus.REJECTED)
		self.assertEqual(leave.approver, self.staff_user)
		self.assertEqual(leave.reject_reason, '업무 일정 충돌')

	def test_staff_can_correct_rejected_to_approved(self):
		leave = self._create_leave(
			status=LeaveRequest.LeaveStatus.REJECTED,
			start_date_value=date(2026, 6, 3),
			end_date_value=date(2026, 6, 4),
		)
		leave.reject_reason = '서류 미비'
		leave.save(update_fields=['reject_reason'])
		self.client.force_login(self.staff_user)

		response = self.client.post(reverse('leave_app:approve', args=[leave.pk]))

		self.assertRedirects(response, reverse('leave_app:list'))
		leave.refresh_from_db()
		self.assertEqual(leave.status, LeaveRequest.LeaveStatus.APPROVED)
		self.assertEqual(leave.approver, self.staff_user)
		self.assertEqual(leave.reject_reason, '')

	def test_canceled_leave_cannot_be_corrected(self):
		leave = self._create_leave(
			status=LeaveRequest.LeaveStatus.CANCELED,
			start_date_value=date(2026, 7, 7),
			end_date_value=date(2026, 7, 8),
		)
		self.client.force_login(self.staff_user)

		response_approve = self.client.post(reverse('leave_app:approve', args=[leave.pk]))
		self.assertRedirects(response_approve, reverse('leave_app:list'))
		leave.refresh_from_db()
		self.assertEqual(leave.status, LeaveRequest.LeaveStatus.CANCELED)

		response_reject = self.client.post(
			reverse('leave_app:reject', args=[leave.pk]),
			{'reject_reason': '테스트'},
		)
		self.assertRedirects(response_reject, reverse('leave_app:list'))
		leave.refresh_from_db()
		self.assertEqual(leave.status, LeaveRequest.LeaveStatus.CANCELED)

	def test_staff_sees_correctable_buttons_for_processed_status(self):
		approved_leave = self._create_leave(
			status=LeaveRequest.LeaveStatus.APPROVED,
			start_date_value=date(2026, 8, 11),
			end_date_value=date(2026, 8, 12),
		)
		rejected_leave = self._create_leave(
			status=LeaveRequest.LeaveStatus.REJECTED,
			start_date_value=date(2026, 9, 15),
			end_date_value=date(2026, 9, 16),
		)
		canceled_leave = self._create_leave(
			status=LeaveRequest.LeaveStatus.CANCELED,
			start_date_value=date(2026, 10, 20),
			end_date_value=date(2026, 10, 21),
		)
		self.client.force_login(self.staff_user)

		response = self.client.get(reverse('leave_app:list'))

		self.assertContains(response, reverse('leave_app:approve', args=[approved_leave.pk]))
		self.assertContains(response, reverse('leave_app:reject', args=[approved_leave.pk]))
		self.assertContains(response, reverse('leave_app:approve', args=[rejected_leave.pk]))
		self.assertContains(response, reverse('leave_app:reject', args=[rejected_leave.pk]))
		self.assertNotContains(response, reverse('leave_app:approve', args=[canceled_leave.pk]))
		self.assertNotContains(response, reverse('leave_app:reject', args=[canceled_leave.pk]))


class EmployeeSelfServiceLeaveTests(TestCase):
	def setUp(self):
		self.employee_user = User.objects.create_user(
			username='employee_user',
			password='testpass123',
		)
		self.other_user = User.objects.create_user(
			username='other_user',
			password='testpass123',
		)
		self.staff_user = User.objects.create_user(
			username='staff_user',
			password='testpass123',
			is_staff=True,
		)

		self.employee = Employee.objects.create(
			user=self.employee_user,
			name='일반직원',
			employee_number='E-1001',
			department=Employee.Department.GENERAL_AFFAIRS,
			position='사원',
			hire_date=date(2024, 2, 1),
			must_change_password=False,
		)
		self.other_employee = Employee.objects.create(
			user=self.other_user,
			name='다른직원',
			employee_number='E-1002',
			department=Employee.Department.GENERAL_AFFAIRS,
			position='사원',
			hire_date=date(2024, 2, 2),
			must_change_password=False,
		)

	def _create_leave(self, *, employee, status, start_date_value, end_date_value):
		return LeaveRequest.objects.create(
			employee=employee,
			start_date=start_date_value,
			end_date=end_date_value,
			leave_type=LeaveRequest.LeaveType.ANNUAL,
			leave_reason='개인 일정',
			status=status,
		)

	def test_employee_can_create_own_leave_request(self):
		self.client.force_login(self.employee_user)

		response = self.client.post(
			reverse('leave_app:request_create'),
			{
				'start_date': '2026-11-03',
				'end_date': '2026-11-03',
				'leave_type': LeaveRequest.LeaveType.ANNUAL,
				'leave_reason': '개인 일정',
			},
		)

		self.assertRedirects(response, reverse('leave_app:list'))
		leave = LeaveRequest.objects.get(employee=self.employee, start_date=date(2026, 11, 3))
		self.assertEqual(leave.status, LeaveRequest.LeaveStatus.PENDING)

	def test_employee_can_cancel_own_pending_leave(self):
		leave = self._create_leave(
			employee=self.employee,
			status=LeaveRequest.LeaveStatus.PENDING,
			start_date_value=date(2026, 12, 10),
			end_date_value=date(2026, 12, 10),
		)
		self.client.force_login(self.employee_user)

		response = self.client.post(reverse('leave_app:cancel', args=[leave.pk]))

		self.assertRedirects(response, reverse('leave_app:list'))
		leave.refresh_from_db()
		self.assertEqual(leave.status, LeaveRequest.LeaveStatus.CANCELED)
		self.assertIsNone(leave.approver)

	def test_employee_cannot_cancel_other_users_leave(self):
		other_leave = self._create_leave(
			employee=self.other_employee,
			status=LeaveRequest.LeaveStatus.PENDING,
			start_date_value=date(2026, 12, 11),
			end_date_value=date(2026, 12, 11),
		)
		self.client.force_login(self.employee_user)

		response = self.client.post(reverse('leave_app:cancel', args=[other_leave.pk]))

		self.assertEqual(response.status_code, 404)
		other_leave.refresh_from_db()
		self.assertEqual(other_leave.status, LeaveRequest.LeaveStatus.PENDING)

	def test_employee_cannot_cancel_non_pending_leave(self):
		leave = self._create_leave(
			employee=self.employee,
			status=LeaveRequest.LeaveStatus.APPROVED,
			start_date_value=date(2026, 12, 12),
			end_date_value=date(2026, 12, 12),
		)
		leave.approver = self.staff_user
		leave.save(update_fields=['approver'])
		self.client.force_login(self.employee_user)

		response = self.client.post(reverse('leave_app:cancel', args=[leave.pk]))

		self.assertRedirects(response, reverse('leave_app:list'))
		leave.refresh_from_db()
		self.assertEqual(leave.status, LeaveRequest.LeaveStatus.APPROVED)

	def test_employee_list_shows_only_own_requests_and_cancel_link(self):
		my_leave = self._create_leave(
			employee=self.employee,
			status=LeaveRequest.LeaveStatus.PENDING,
			start_date_value=date(2026, 12, 13),
			end_date_value=date(2026, 12, 13),
		)
		other_leave = self._create_leave(
			employee=self.other_employee,
			status=LeaveRequest.LeaveStatus.PENDING,
			start_date_value=date(2026, 12, 14),
			end_date_value=date(2026, 12, 14),
		)
		self.client.force_login(self.employee_user)

		response = self.client.get(reverse('leave_app:list'))

		self.assertContains(response, '일반직원')
		self.assertNotContains(response, '다른직원')
		self.assertContains(response, reverse('leave_app:cancel', args=[my_leave.pk]))
		self.assertNotContains(response, reverse('leave_app:cancel', args=[other_leave.pk]))
		self.assertContains(response, reverse('leave_app:request_create'))
