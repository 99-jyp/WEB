from employee.models import AuditLog


def write_audit_log(*, actor, action, target=None, detail=''):
    """공통 감사로그 기록 헬퍼"""
    target_model = ''
    target_id = None
    target_repr = ''

    if target is not None:
        target_model = target.__class__.__name__
        target_id = target.pk
        target_repr = str(target)

    AuditLog.objects.create(
        actor=actor,
        action=action,
        target_model=target_model,
        target_id=target_id,
        target_repr=target_repr,
        detail=detail,
    )
