import csv
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from employee.audit import write_audit_log
from employee.models import Employee
from .forms import LeaveRejectForm, LeaveRequestForm
from .models import LeaveRequest

ANNUAL_LEAVE_DAYS = 15  # 기본 연차 일수


def _is_staff(user):
    return user.is_staff


def _get_used_days(employee, year=None):
    """해당 연도 승인된 휴가 사용일수 합계"""
    if year is None:
        year = date.today().year
    qs = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        start_date__year=year,
    )
    total = qs.aggregate(total=Sum('days_count'))['total'] or Decimal('0')
    return total


@login_required
def leave_list(request):
    qs = LeaveRequest.objects.select_related('employee', 'approver').order_by('-requested_at')
    dept_filter = ''

    # 일반 직원 → 내 신청만
    if not request.user.is_staff:
        qs = qs.filter(employee__user=request.user)

    # 필터: 상태
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    # 필터: 부서(스태프만)
    if request.user.is_staff:
        dept_filter = request.GET.get('department', '')
        if dept_filter:
            qs = qs.filter(employee__department=dept_filter)

    departments = Employee.objects.values_list('department', flat=True).distinct().order_by('department')
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'leave_app/leave_list.html', {
        'leaves': page_obj,
        'page_obj': page_obj,
        'departments': departments,
        'current_status': status_filter,
        'current_dept': dept_filter,
    })


@login_required
def leave_request_create(request):
    employee = getattr(request.user, 'employee_profile', None)

    # 잔여일 계산
    remaining = None
    my_leave_history = LeaveRequest.objects.none()
    if employee:
        used = _get_used_days(employee)
        remaining = Decimal(str(ANNUAL_LEAVE_DAYS)) - used
        my_leave_history = (
            LeaveRequest.objects.filter(employee=employee)
            .select_related('approver')
            .order_by('-requested_at')[:8]
        )

    def render_leave_form(form_instance):
        return render(
            request,
            'leave_app/leave_form.html',
            {
                'form': form_instance,
                'remaining': remaining,
                'my_leave_history': my_leave_history,
                'employee': employee,
            },
        )

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if employee:
            form.instance.employee = employee

        if form.is_valid():
            leave_request = form.save(commit=False)
            if not employee:
                messages.error(request, '현재 계정에 연결된 직원 정보가 없습니다. 관리자에게 문의하세요.')
                form.add_error(None, '현재 계정에 연결된 직원 정보가 없습니다. 관리자에게 문의하세요.')
                return render_leave_form(form)
            leave_request.employee = employee
            leave_request.save()
            messages.success(request, '휴가 신청이 등록되었습니다.')
            return redirect('leave_app:list')
    else:
        form = LeaveRequestForm()

    return render_leave_form(form)


@user_passes_test(_is_staff)
def leave_approve(request, pk):
    leave_request = get_object_or_404(LeaveRequest, pk=pk)

    # 취소된 신청은 최종 상태로 간주해 정정 대상에서 제외한다.
    if leave_request.status == LeaveRequest.LeaveStatus.CANCELED:
        messages.warning(request, '취소된 신청은 승인/반려로 정정할 수 없습니다.')
        return redirect('leave_app:list')

    previous_status = leave_request.status
    status_labels = {str(key): label for key, label in LeaveRequest.LeaveStatus.choices}
    previous_status_label = status_labels.get(str(previous_status), previous_status)

    if request.method != 'POST':
        return render(request, 'leave_app/leave_approve_confirm.html', {'leave': leave_request})

    leave_request.status = LeaveRequest.LeaveStatus.APPROVED
    leave_request.approver = request.user
    leave_request.reject_reason = ''
    leave_request.save(update_fields=['status', 'approver', 'reject_reason'])
    write_audit_log(
        actor=request.user,
        action='leave_approved',
        target=leave_request,
        detail=(
            f'휴가 승인: {leave_request.employee.name} '
            f'({leave_request.employee.employee_number}) {leave_request.start_date}~{leave_request.end_date} '
            f'상태변경: {previous_status_label} -> 승인'
        ),
    )
    if previous_status == LeaveRequest.LeaveStatus.REJECTED:
        messages.success(request, '휴가 신청 상태를 반려에서 승인으로 정정했습니다.')
    elif previous_status == LeaveRequest.LeaveStatus.APPROVED:
        messages.success(request, '휴가 신청을 승인 상태로 다시 저장했습니다.')
    else:
        messages.success(request, '휴가 신청을 승인했습니다.')
    return redirect('leave_app:list')


@user_passes_test(_is_staff)
def leave_reject(request, pk):
    leave_request = get_object_or_404(LeaveRequest, pk=pk)

    # 취소된 신청은 최종 상태로 간주해 정정 대상에서 제외한다.
    if leave_request.status == LeaveRequest.LeaveStatus.CANCELED:
        messages.warning(request, '취소된 신청은 승인/반려로 정정할 수 없습니다.')
        return redirect('leave_app:list')

    previous_status = leave_request.status
    status_labels = {str(key): label for key, label in LeaveRequest.LeaveStatus.choices}
    previous_status_label = status_labels.get(str(previous_status), previous_status)

    if request.method == 'POST':
        form = LeaveRejectForm(request.POST)
        if form.is_valid():
            leave_request.status = LeaveRequest.LeaveStatus.REJECTED
            leave_request.approver = request.user
            leave_request.reject_reason = form.cleaned_data['reject_reason']
            leave_request.save(update_fields=['status', 'approver', 'reject_reason'])
            write_audit_log(
                actor=request.user,
                action='leave_rejected',
                target=leave_request,
                detail=(
                    f'휴가 반려: {leave_request.employee.name} '
                    f'({leave_request.employee.employee_number}) '
                    f'상태변경: {previous_status_label} -> 반려 / 사유: {leave_request.reject_reason}'
                ),
            )
            if previous_status == LeaveRequest.LeaveStatus.APPROVED:
                messages.success(request, '휴가 신청 상태를 승인에서 반려로 정정했습니다.')
            elif previous_status == LeaveRequest.LeaveStatus.REJECTED:
                messages.success(request, '휴가 신청을 반려 상태로 다시 저장했습니다.')
            else:
                messages.success(request, '휴가 신청을 반려했습니다.')
            return redirect('leave_app:list')
    else:
        form = LeaveRejectForm()
    return render(request, 'leave_app/leave_reject.html', {'form': form, 'leave': leave_request})


@login_required
def leave_cancel(request, pk):
    leave_request = get_object_or_404(LeaveRequest, pk=pk, employee__user=request.user)

    # 일반 직원은 대기 상태일 때만 취소 가능
    if leave_request.status != LeaveRequest.LeaveStatus.PENDING:
        messages.warning(request, '대기 상태인 신청만 취소할 수 있습니다.')
        return redirect('leave_app:list')

    if request.method == 'POST':
        leave_request.status = LeaveRequest.LeaveStatus.CANCELED
        leave_request.approver = None
        leave_request.reject_reason = ''
        leave_request.save(update_fields=['status', 'approver', 'reject_reason'])
        messages.success(request, '휴가 신청을 취소했습니다.')
        return redirect('leave_app:list')

    return render(request, 'leave_app/leave_cancel_confirm.html', {'leave': leave_request})


# ── 엑셀(CSV) 다운로드 ──


@user_passes_test(_is_staff)
def leave_export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="leave_requests.csv"'

    writer = csv.writer(response)
    writer.writerow(['직원', '사번', '부서', '시작일', '종료일', '종류', '휴가사유', '사용일수', '상태', '승인자', '반려사유', '신청일'])
    leave_type_labels = {str(key): label for key, label in LeaveRequest.LeaveType.choices}
    status_labels = {str(key): label for key, label in LeaveRequest.LeaveStatus.choices}

    for lr in LeaveRequest.objects.select_related('employee', 'approver').all():
        writer.writerow([
            lr.employee.name,
            lr.employee.employee_number,
            lr.employee.department,
            lr.start_date,
            lr.end_date,
            leave_type_labels.get(lr.leave_type, lr.leave_type),
            lr.leave_reason,
            lr.days_count,
            status_labels.get(lr.status, lr.status),
            lr.approver.username if lr.approver else '',
            lr.reject_reason,
            lr.requested_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response


