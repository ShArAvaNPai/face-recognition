"""Role-based access control decorators."""
from functools import wraps

from flask import abort
from flask_login import current_user

from models import ROLE_ADMIN, ROLE_FACULTY


def roles_required(*roles):
    """Allow access only to users whose role is in `roles`."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def staff_required(view):
    """Admin or faculty only (the people who manage students/attendance)."""
    return roles_required(ROLE_ADMIN, ROLE_FACULTY)(view)
