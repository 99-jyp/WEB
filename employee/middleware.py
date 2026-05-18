from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """직원 계정의 최초 로그인 시 비밀번호 변경을 강제한다."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.is_active:
            employee = getattr(user, 'employee_profile', None)
            if employee and employee.must_change_password:
                allowed_paths = {
                    reverse('password_change'),
                    reverse('password_change_done'),
                    reverse('logout'),
                }
                if request.path not in allowed_paths and not request.path.startswith('/static/'):
                    return redirect('password_change')

        return self.get_response(request)
