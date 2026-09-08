"""Role-based access control decorators."""
from functools import wraps

from flask import abort
from flask_login import current_user

from models import ROLE_ADMIN, ROLE_FACULTY, ROLE_DIRECTOR, ROLE_HOD


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
    """Admin, faculty, director, or HOD only."""
    return roles_required(ROLE_ADMIN, ROLE_FACULTY, ROLE_DIRECTOR, ROLE_HOD)(view)


def admin_required(view):
    """Admin only."""
    return roles_required(ROLE_ADMIN)(view)


def director_required(view):
    """Director or HOD (or admin)."""
    return roles_required(ROLE_ADMIN, ROLE_DIRECTOR, ROLE_HOD)(view)



def hod_required(view):
    """HOD only (or admin/director)."""
    return roles_required(ROLE_ADMIN, ROLE_DIRECTOR, ROLE_HOD)(view)
