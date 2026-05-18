from django.db import models
from django.contrib.auth.models import User


class Employee(models.Model):
	class Department(models.TextChoices):
		MEDICAL = '진료부', '진료부'
		WARD_3 = '3병동', '3병동'
		WARD_5A = '5A병동', '5A병동'
		WARD_5B = '5B병동', '5B병동'
		OPERATING_ROOM = '수술실', '수술실'
		TREATMENT_ROOM = '치료실', '치료실'
		OUTPATIENT = '외래', '외래'
		COUNSELING_ROOM = '상담실', '상담실'
		NURSING = '간호부', '간호부'
		NURSING_ADMIN = '간호행정', '간호행정'
		ADMINISTRATION = '원무과', '원무과'
		GENERAL_AFFAIRS = '총무과', '총무과'
		FACILITIES = '시설과', '시설과'
		REVIEW = '심사과', '심사과'
		HEALTH_CHECK = '검진센터', '검진센터'
		RADIOLOGY = '영상의학과', '영상의학과'
		LAB_MEDICINE = '진단검사의학과', '진단검사의학과'
		PHYSICAL_THERAPY = '물리치료', '물리치료'
		EXERCISE_THERAPY = '운동치료', '운동치료'
		IN_HOUSE_PHARMACY = '원내약국', '원내약국'
		NUTRITION = '영양과', '영양과'

	class EmploymentStatus(models.TextChoices):
		ACTIVE = 'active', '재직'
		LEAVE = 'leave', '휴직'
		RESIGNED = 'resigned', '퇴사'

	user = models.OneToOneField(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='employee_profile',
	)
	name = models.CharField('이름', max_length=50)
	employee_number = models.CharField('사번', max_length=30, unique=True)
	department = models.CharField('부서', max_length=100, choices=Department.choices)
	position = models.CharField('직급', max_length=50)
	hire_date = models.DateField('입사일')
	employment_status = models.CharField(
		'재직상태',
		max_length=20,
		choices=EmploymentStatus.choices,
		default=EmploymentStatus.ACTIVE,
	)
	must_change_password = models.BooleanField(
		'최초 로그인 비밀번호 변경 필요',
		default=True,
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['name']

	def __str__(self):
		return f'{self.name} ({self.employee_number})'


class HRRecord(models.Model):
	employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='hr_records')
	year = models.PositiveIntegerField('연도')
	department_change = models.CharField('부서변경', max_length=100, blank=True)
	position_change = models.CharField('직급변경', max_length=50, blank=True)
	memo = models.TextField('메모', blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-year', '-created_at']

	def __str__(self):
		return f'{self.employee.name} - {self.year}'


class SignupRequest(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', '대기'
		APPROVED = 'approved', '승인'
		REJECTED = 'rejected', '반려'

	employee_number = models.CharField('사번', max_length=30)
	name = models.CharField('이름', max_length=50)
	department = models.CharField('부서', max_length=100, choices=Employee.Department.choices)
	position = models.CharField('직급', max_length=50)
	hire_date = models.DateField('입사일')
	password_hash = models.CharField('비밀번호 해시', max_length=128)
	status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PENDING)
	admin_memo = models.TextField('관리자 메모', blank=True)
	requested_at = models.DateTimeField('신청일', auto_now_add=True)
	processed_at = models.DateTimeField('처리일', null=True, blank=True)
	processed_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='processed_signup_requests',
		verbose_name='처리자',
	)

	class Meta:
		ordering = ['-requested_at']

	def get_status_label(self):
		try:
			return self.Status(self.status).label
		except ValueError:
			return self.status

	def __str__(self):
		return f'{self.name} ({self.employee_number}) - {self.get_status_label()}'


class AuditLog(models.Model):
	actor = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='audit_logs',
		verbose_name='행위자',
	)
	action = models.CharField('액션', max_length=50)
	target_model = models.CharField('대상 모델', max_length=100, blank=True)
	target_id = models.PositiveIntegerField('대상 ID', null=True, blank=True)
	target_repr = models.CharField('대상 표시명', max_length=255, blank=True)
	detail = models.TextField('상세', blank=True)
	created_at = models.DateTimeField('기록시각', auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'[{self.created_at:%Y-%m-%d %H:%M}] {self.action} - {self.target_repr}'
