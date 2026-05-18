from django import forms
from django.db.models import Q

from .models import LeaveRequest


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['start_date', 'end_date', 'leave_type', 'leave_reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'leave_reason': forms.Textarea(attrs={'rows': 3, 'placeholder': '휴가 사유를 입력하세요'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        employee = getattr(self.instance, 'employee', None)

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('종료일은 시작일보다 빠를 수 없습니다.')

        leave_reason = (cleaned_data.get('leave_reason') or '').strip()
        if not leave_reason:
            self.add_error('leave_reason', '휴가 사유를 입력해 주세요.')

        # 같은 직원의 기간 중복 체크 (대기/승인 상태만)
        if start_date and end_date and employee:
            overlapping = LeaveRequest.objects.filter(
                employee=employee,
                status__in=['pending', 'approved'],
            ).filter(
                Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
            )
            if self.instance and self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise forms.ValidationError('해당 기간에 이미 휴가 신청이 있습니다.')

        return cleaned_data


class LeaveRejectForm(forms.Form):
    reject_reason = forms.CharField(
        label='반려 사유',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '반려 사유를 입력하세요'}),
    )
