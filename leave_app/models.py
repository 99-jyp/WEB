from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

from employee.models import Employee


class LeaveRequest(models.Model):
    class LeaveType(models.TextChoices):
        ANNUAL = 'annual', '연차'
        HALF_DAY = 'half_day', '반차'
        PAID = 'paid', '유급'
        UNPAID = 'unpaid', '무급'
        BEREAVEMENT = 'bereavement', '경조'
        REWARD = 'reward', '포상'
        TRAINING = 'training', '훈련'
        OTHER = 'other', '기타'

    class LeaveStatus(models.TextChoices):
        PENDING = 'pending', '대기'
        APPROVED = 'approved', '승인'
        REJECTED = 'rejected', '반려'
        CANCELED = 'canceled', '취소'

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    start_date = models.DateField('시작일')
    end_date = models.DateField('종료일')
    leave_type = models.CharField('휴가종류', max_length=20, choices=LeaveType.choices)
    leave_reason = models.TextField('휴가 사유', blank=True)
    days_count = models.DecimalField('사용일수', max_digits=4, decimal_places=1, default=Decimal('0'))
    status = models.CharField(
        '상태',
        max_length=20,
        choices=LeaveStatus.choices,
        default=LeaveStatus.PENDING,
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leave_requests',
        verbose_name='승인자',
    )
    reject_reason = models.TextField('반려 사유', blank=True)
    requested_at = models.DateTimeField('신청일', auto_now_add=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f'{self.employee.name} / {self.start_date}~{self.end_date}'

    def calc_days(self):
        """사용일수 계산 (반차=0.5일, 나머지=영업일 기준)"""
        if self.leave_type == self.LeaveType.HALF_DAY:
            return 0.5
        # 주말 제외 영업일 계산
        from datetime import timedelta
        count = 0
        current = self.start_date
        while current <= self.end_date:
            if current.weekday() < 5:  # 월~금
                count += 1
            current += timedelta(days=1)
        return count

    def save(self, *args, **kwargs):
        if self.days_count in (None, Decimal('0')):
            self.days_count = self.calc_days()
        super().save(*args, **kwargs)
