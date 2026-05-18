from django.urls import path

from .views import (
    leave_approve,
    leave_cancel,
    leave_export_csv,
    leave_list,
    leave_reject,
    leave_request_create,
)

app_name = 'leave_app'

urlpatterns = [
    path('', leave_list, name='list'),
    path('request/', leave_request_create, name='request_create'),
    path('export/', leave_export_csv, name='export_csv'),
    path('<int:pk>/approve/', leave_approve, name='approve'),
    path('<int:pk>/reject/', leave_reject, name='reject'),
    path('<int:pk>/cancel/', leave_cancel, name='cancel'),
]
