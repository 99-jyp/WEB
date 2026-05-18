from django.urls import path

from .views import (
    employee_create,
    employee_delete,
    employee_detail,
    employee_export_csv,
    employee_import_csv,
    employee_list,
    employee_update,
    hr_record_create,
    hr_record_delete,
    hr_record_update,
    user_accounts_export_csv,
)

app_name = 'employee'

urlpatterns = [
    path('', employee_list, name='list'),
    path('create/', employee_create, name='create'),
    path('export/', employee_export_csv, name='export_csv'),
    path('users/export/', user_accounts_export_csv, name='user_accounts_export_csv'),
    path('import/', employee_import_csv, name='import_csv'),
    path('<int:pk>/', employee_detail, name='detail'),
    path('<int:pk>/edit/', employee_update, name='update'),
    path('<int:pk>/delete/', employee_delete, name='delete'),
    # 인사기록
    path('<int:emp_pk>/hr/create/', hr_record_create, name='hr_record_create'),
    path('<int:emp_pk>/hr/<int:pk>/edit/', hr_record_update, name='hr_record_update'),
    path('<int:emp_pk>/hr/<int:pk>/delete/', hr_record_delete, name='hr_record_delete'),
]
