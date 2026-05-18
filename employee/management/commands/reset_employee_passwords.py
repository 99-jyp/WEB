from django.core.management.base import BaseCommand
from employee.models import Employee


class Command(BaseCommand):
    help = '모든 직원의 비밀번호를 "1"로 초기화합니다.'

    def handle(self, *args, **options):
        employees = Employee.objects.select_related('user').all()
        updated = 0
        skipped = 0

        for emp in employees:
            if emp.user is None:
                self.stdout.write(
                    self.style.WARNING(f'  [건너뜀] {emp.name} ({emp.employee_number}) - 연결된 계정 없음')
                )
                skipped += 1
                continue

            emp.user.set_password('1')
            emp.user.save(update_fields=['password'])
            emp.must_change_password = True
            emp.save(update_fields=['must_change_password'])
            self.stdout.write(
                self.style.SUCCESS(f'  [완료] {emp.name} ({emp.employee_number})')
            )
            updated += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'총 {updated}명 비밀번호 초기화 완료, {skipped}명 건너뜀'))
