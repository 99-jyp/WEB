from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import Employee


@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    """직원 등록 시 User 계정이 없으면 자동 생성하여 연결"""
    if not created:
        return
    if instance.user is None:
        username = instance.employee_number
        if not User.objects.filter(username=username).exists():
            user = User.objects.create_user(
                username=username,
                first_name=instance.name,
            )
            # 초기 비밀번호는 '1'로 설정
            user.set_password('1')
            user.save()
            Employee.objects.filter(pk=instance.pk).update(user=user)
