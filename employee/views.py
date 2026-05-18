import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .audit import write_audit_log
from .forms import EmployeeForm, EmployeePasswordChangeForm, EmployeeSignupForm, HRRecordForm
from .models import Employee, HRRecord
from leave_app.models import LeaveRequest


def _is_staff(user):
    return user.is_staff


def _normalize_department(value):
    normalized = (value or '').strip().lower()
    for token in (' ', '\t', '\r', '\n', '(', ')', '[', ']', '/', '-', '_'):
        normalized = normalized.replace(token, '')
    return normalized


def _map_department(raw_department, dept_values):
    if raw_department in dept_values:
        return raw_department

    normalized = _normalize_department(raw_department)
    alias_map = {
        '간호부3병동': '3병동',
        '3병동간호부': '3병동',
        '3병동간호과': '3병동',
        '간호부5a병동': '5A병동',
        '5a병동간호부': '5A병동',
        '5a병동간호과': '5A병동',
        '간호부5b병동': '5B병동',
        '5b병동간호부': '5B병동',
        '5b병동간호과': '5B병동',
    }

    candidate = alias_map.get(normalized)
    if candidate:
        return candidate

    keyword_rules = [
        ('5a', '5A병동'),
        ('5b', '5B병동'),
        ('3병동', '3병동'),
        ('수술', '수술실'),
        ('치료실', '치료실'),
        ('외래', '외래'),
        ('상담', '상담실'),
        ('간호행정', '간호행정'),
        ('간호', '간호부'),
        ('원무', '원무과'),
        ('총무', '총무과'),
        ('시설', '시설과'),
        ('심사', '심사과'),
        ('검진', '검진센터'),
        ('영상', '영상의학과'),
        ('진단검사', '진단검사의학과'),
        ('검사의학', '진단검사의학과'),
        ('물리', '물리치료'),
        ('운동', '운동치료'),
        ('약국', '원내약국'),
        ('영양', '영양과'),
        ('진료', '진료부'),
    ]

    for keyword, mapped in keyword_rules:
        if keyword in normalized:
            return mapped

    return None


@login_required
def home(request):
    return render(request, 'home.html')


@login_required
def my_page(request):
    employee = getattr(request.user, 'employee_profile', None)
    return render(request, 'employee/my_page.html', {'employee': employee})


class EmployeePasswordChangeView(PasswordChangeView):
    form_class = EmployeePasswordChangeForm
    template_name = 'registration/password_change_form.html'
    success_url = reverse_lazy('password_change_done')

    def form_valid(self, form):
        response = super().form_valid(form)
        employee = getattr(self.request.user, 'employee_profile', None)
        if employee and employee.must_change_password:
            employee.must_change_password = False
            employee.save(update_fields=['must_change_password'])

        write_audit_log(
            actor=self.request.user,
            action='password_changed',
            target=self.request.user,
            detail='사용자가 비밀번호를 변경했습니다.',
        )
        return response


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = EmployeeSignupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '가입 신청이 접수되었습니다. 관리자 승인 후 로그인해 주세요.')
            return redirect('/accounts/login/')
    else:
        form = EmployeeSignupForm()

    return render(request, 'registration/signup.html', {'form': form})


@user_passes_test(_is_staff)
def employee_list(request):
    employees = Employee.objects.all().order_by('employee_number')

    # 부서 필터
    dept_filter = request.GET.get('department', '')
    if dept_filter:
        employees = employees.filter(department=dept_filter)

    # 재직상태 필터
    status_filter = request.GET.get('status', '')
    if status_filter:
        employees = employees.filter(employment_status=status_filter)

    # 검색
    search = request.GET.get('q', '')
    if search:
        employees = employees.filter(name__icontains=search)

    departments = Employee.objects.values_list('department', flat=True).distinct().order_by('department')
    paginator = Paginator(employees, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'employee/employee_list.html', {
        'employees': page_obj,
        'page_obj': page_obj,
        'departments': departments,
        'current_dept': dept_filter,
        'current_status': status_filter,
        'search_query': search,
    })


@user_passes_test(_is_staff)
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    hr_records = HRRecord.objects.filter(employee=employee)
    leave_requests = LeaveRequest.objects.filter(employee=employee)[:10]
    return render(
        request,
        'employee/employee_detail.html',
        {
            'employee': employee,
            'hr_records': hr_records,
            'leave_requests': leave_requests,
        },
    )


# ── 직원 등록 / 수정 / 삭제 (관리자 전용) ──


@user_passes_test(_is_staff)
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '직원 정보가 등록되었습니다.')
            return redirect('employee:list')
        messages.error(request, '직원 등록에 실패했습니다. 입력값을 확인해 주세요.')
    else:
        form = EmployeeForm()
    return render(request, 'employee/employee_form.html', {'form': form, 'title': '직원 등록'})


@user_passes_test(_is_staff)
def employee_update(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            changed_fields = ', '.join(form.changed_data) if form.changed_data else '없음'
            updated_employee = form.save()
            write_audit_log(
                actor=request.user,
                action='employee_updated',
                target=updated_employee,
                detail=f'직원정보 수정. 변경 필드: {changed_fields}',
            )
            messages.success(request, '직원 정보가 수정되었습니다.')
            return redirect('employee:detail', pk=pk)
        messages.error(request, '직원 수정에 실패했습니다. 입력값을 확인해 주세요.')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'employee/employee_form.html', {'form': form, 'title': '직원 수정'})


@user_passes_test(_is_staff)
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        employee_name = employee.name
        employee.delete()
        messages.success(request, f'{employee_name} 직원 정보가 삭제되었습니다.')
        return redirect('employee:list')
    return render(request, 'employee/employee_confirm_delete.html', {'employee': employee})


# ── 인사기록 등록 / 수정 / 삭제 (관리자 전용) ──


@user_passes_test(_is_staff)
def hr_record_create(request, emp_pk):
    employee = get_object_or_404(Employee, pk=emp_pk)
    if request.method == 'POST':
        form = HRRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.employee = employee
            record.save()
            messages.success(request, '인사기록이 추가되었습니다.')
            return redirect('employee:detail', pk=emp_pk)
        messages.error(request, '인사기록 추가에 실패했습니다. 입력값을 확인해 주세요.')
    else:
        form = HRRecordForm()
    return render(request, 'employee/hr_record_form.html', {'form': form, 'employee': employee, 'title': '인사기록 추가'})


@user_passes_test(_is_staff)
def hr_record_update(request, emp_pk, pk):
    record = get_object_or_404(HRRecord, pk=pk, employee_id=emp_pk)
    if request.method == 'POST':
        form = HRRecordForm(request.POST, instance=record)
        if form.is_valid():
            changed_fields = ', '.join(form.changed_data) if form.changed_data else '없음'
            updated_record = form.save()
            write_audit_log(
                actor=request.user,
                action='hr_record_updated',
                target=updated_record,
                detail=f'인사기록 수정. 변경 필드: {changed_fields}',
            )
            messages.success(request, '인사기록이 수정되었습니다.')
            return redirect('employee:detail', pk=emp_pk)
        messages.error(request, '인사기록 수정에 실패했습니다. 입력값을 확인해 주세요.')
    else:
        form = HRRecordForm(instance=record)
    return render(request, 'employee/hr_record_form.html', {'form': form, 'employee': record.employee, 'title': '인사기록 수정'})


@user_passes_test(_is_staff)
def hr_record_delete(request, emp_pk, pk):
    record = get_object_or_404(HRRecord, pk=pk, employee_id=emp_pk)
    if request.method == 'POST':
        record.delete()
        messages.success(request, '인사기록이 삭제되었습니다.')
        return redirect('employee:detail', pk=emp_pk)
    return render(request, 'employee/hr_record_confirm_delete.html', {'record': record})


@user_passes_test(_is_staff)
def employee_export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'

    writer = csv.writer(response)
    writer.writerow(['name', 'employee_number', 'department', 'position', 'hire_date', 'employment_status'])

    for employee in Employee.objects.all().order_by('employee_number'):
        writer.writerow(
            [
                employee.name,
                employee.employee_number,
                employee.department,
                employee.position,
                employee.hire_date,
                employee.employment_status,
            ]
        )

    return response


@user_passes_test(_is_staff)
def user_accounts_export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="user_accounts.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            'user_id',
            'username',
            'first_name',
            'is_staff',
            'is_superuser',
            'is_active',
            'last_login',
            'date_joined',
            'employee_number',
            'employee_name',
            'department',
            'position',
            'employment_status',
        ]
    )

    employees_by_user_id = {
        emp.user.pk: emp
        for emp in Employee.objects.filter(user__isnull=False)
        if emp.user is not None
    }

    users = User.objects.all().order_by('id')
    for user in users:
        employee = employees_by_user_id.get(user.pk)
        writer.writerow(
            [
            user.pk,
                user.username,
                user.first_name,
                user.is_staff,
                user.is_superuser,
                user.is_active,
                user.last_login.isoformat() if user.last_login else '',
                user.date_joined.isoformat() if user.date_joined else '',
                employee.employee_number if employee else '',
                employee.name if employee else '',
                employee.department if employee else '',
                employee.position if employee else '',
                employee.employment_status if employee else '',
            ]
        )

    return response


@user_passes_test(_is_staff)
def employee_import_csv(request):
    result = None
    errors = []

    if request.method == 'POST' and request.FILES.get('file'):
        upload = request.FILES['file']
        raw = upload.read()
        decoded_text = None
        for encoding in ('utf-8-sig', 'cp949', 'euc-kr'):
            try:
                decoded_text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if decoded_text is None:
            errors.append('CSV 인코딩을 확인해 주세요. UTF-8(권장) 또는 CP949/EUC-KR 형식을 사용해 주세요.')
            messages.error(request, 'CSV 파일 인코딩을 읽을 수 없습니다. UTF-8 또는 CP949/EUC-KR로 저장해 주세요.')
            return render(request, 'employee/employee_import.html', {'result': result, 'errors': errors})

        reader = csv.DictReader(decoded_text.splitlines())

        required_headers = {'name', 'employee_number', 'department', 'position', 'hire_date', 'employment_status'}
        if not reader.fieldnames or not required_headers.issubset(set(reader.fieldnames)):
            errors.append('CSV 헤더가 올바르지 않습니다. 필수: name, employee_number, department, position, hire_date, employment_status')
            messages.error(request, 'CSV 헤더가 올바르지 않습니다.')
        else:
            dept_values = {choice[0] for choice in Employee.Department.choices}
            status_values = {choice[0] for choice in Employee.EmploymentStatus.choices}
            created_count = 0
            updated_count = 0

            for line_no, row in enumerate(reader, start=2):
                try:
                    name = (row.get('name') or '').strip()
                    employee_number = (row.get('employee_number') or '').strip()
                    department = (row.get('department') or '').strip()
                    position = (row.get('position') or '').strip() or '미입력'
                    hire_date_raw = (row.get('hire_date') or '').strip()
                    employment_status = (row.get('employment_status') or '').strip()

                    if not (name and employee_number and department and hire_date_raw and employment_status):
                        raise ValueError('필수값 누락')

                    mapped_department = _map_department(department, dept_values)
                    if mapped_department is None:
                        raise ValueError(f'유효하지 않은 부서: {department}')

                    if employment_status not in status_values:
                        raise ValueError(f'유효하지 않은 재직상태: {employment_status}')

                    hire_date = date.fromisoformat(hire_date_raw)

                    employee, created = Employee.objects.update_or_create(
                        employee_number=employee_number,
                        defaults={
                            'name': name,
                            'department': mapped_department,
                            'position': position,
                            'hire_date': hire_date,
                            'employment_status': employment_status,
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                except Exception as exc:  # noqa: BLE001
                    errors.append(f'{line_no}행 오류: {exc}')

            result = {
                'created': created_count,
                'updated': updated_count,
                'failed': len(errors),
            }
            messages.success(
                request,
                f'CSV 처리 완료 - 신규 {created_count}건, 수정 {updated_count}건, 실패 {len(errors)}건',
            )
            if errors:
                messages.warning(request, '일부 행 처리에 실패했습니다. 아래 오류 목록을 확인해 주세요.')
    elif request.method == 'POST':
        messages.error(request, '업로드할 CSV 파일을 선택해 주세요.')

    return render(request, 'employee/employee_import.html', {'result': result, 'errors': errors})
