"""
URL configuration for hr_portal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from employee.views import EmployeePasswordChangeView, home, my_page, signup

urlpatterns = [
    path('', home, name='home'),
    path('accounts', RedirectView.as_view(url='/accounts/', permanent=False)),
    path('accounts/signup/', signup, name='signup'),
    path('accounts/my-page/', my_page, name='my_page'),
    path('accounts/password_change/', EmployeePasswordChangeView.as_view(), name='password_change'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('employees/', include('employee.urls')),
    path('leave/', include('leave_app.urls')),
]
