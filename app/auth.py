from flask import Blueprint, request, redirect, url_for, session, render_template, flash
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import check_password_hash
from functools import wraps
from users import users_data

# Flask-Login setup
# login_manager = LoginManager()


def requires_roles(*roles):
    def wrapper(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_info = users_data.get(current_user.get_id())  # Assuming current_user returns a User object with a method get_id()
            if user_info and user_info['role'] not in roles:
                # Flash a message or return an error response
                return "Access denied!", 403
            return f(*args, **kwargs)
        return wrapped
    return wrapper