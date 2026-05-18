import uuid

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from .models import Employee, HRRecord, SignupRequest


class EmployeePasswordChangeForm(PasswordChangeForm):
    def validate_password_for_user(self, user, password_field_name='password2'):
        return


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name', 'employee_number', 'department', 'position', 'hire_date', 'employment_status', 'user']
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
        }


class HRRecordForm(forms.ModelForm):
    class Meta:
        model = HRRecord
        fields = ['year', 'department_change', 'position_change', 'memo']
        widgets = {
            'memo': forms.Textarea(attrs={'rows': 3}),
        }


class EmployeeSignupForm(forms.Form):
    name = forms.CharField(label='이름', max_length=50)
    department = forms.ChoiceField(label='부서', choices=Employee.Department.choices)
    hire_date = forms.DateField(label='입사일', widget=forms.DateInput(attrs={'type': 'date'}))
    password1 = forms.CharField(label='비밀번호', widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label='비밀번호 확인', widget=forms.PasswordInput, strip=False)

    @staticmethod
    def _generate_temp_employee_number() -> str:
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f'REQ-{timestamp}-{random_suffix}'

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['name'] = (cleaned_data.get('name') or '').strip()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', '비밀번호가 일치하지 않습니다.')

        name = cleaned_data.get('name')
        department = cleaned_data.get('department')
        hire_date = cleaned_data.get('hire_date')
        employee_number = ''

        if name and department and hire_date:
            matched_employee = (
                Employee.objects.filter(
                    name=name,
                    department=department,
                    hire_date=hire_date,
                )
                .only('employee_number', 'position')
                .order_by('id')
                .first()
            )

            if matched_employee is not None:
                employee_number = matched_employee.employee_number
                position = matched_employee.position
            else:
                employee_number = self._generate_temp_employee_number()
                position = '미기재'
                if SignupRequest.objects.filter(
                    name=name,
                    department=department,
                    hire_date=hire_date,
                    status=SignupRequest.Status.PENDING,
                ).exists():
                    raise forms.ValidationError('이미 대기 중인 가입 신청이 있습니다. 관리자 승인 후 로그인해 주세요.')

            cleaned_data['employee_number'] = employee_number
            cleaned_data['position'] = position

        if employee_number and User.objects.filter(username=employee_number).exists():
            raise forms.ValidationError('동일 사번의 계정이 이미 존재합니다. 로그인 후 사용하세요.')

        if employee_number and SignupRequest.objects.filter(
            employee_number=employee_number,
            status=SignupRequest.Status.PENDING,
        ).exists():
            raise forms.ValidationError('이미 대기 중인 가입 신청이 있습니다. 관리자 승인 후 로그인해 주세요.')

        return cleaned_data

    def save(self):
        signup_request = SignupRequest.objects.create(
            employee_number=self.cleaned_data['employee_number'],
            name=self.cleaned_data['name'],
            department=self.cleaned_data['department'],
            position=self.cleaned_data['position'],
            hire_date=self.cleaned_data['hire_date'],
            password_hash=make_password(self.cleaned_data['password1']),
        )
        return signup_request
