from functools import wraps

from flask import abort, redirect, url_for
from flask_login import LoginManager, current_user, login_required  # noqa: F401

import db

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
login_manager.login_message_category = "warning"


class User:
    def __init__(self, data: dict):
        self.id = data["id"]
        self.username = data["username"]
        self.role = data["role"]

    # Flask-Login interface
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    data = db.get_user_by_id(int(user_id))
    return User(data) if data else None


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


def page_access_required(f):
    """Decorator for routes that have a <page_id> param — checks user has access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        page_id = kwargs.get("page_id")
        if page_id and not db.user_has_page_access(
            current_user.id, page_id, current_user.role
        ):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)
