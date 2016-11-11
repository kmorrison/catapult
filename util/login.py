from functools import wraps

import flask
from google.appengine.api import users

def login_required(method):
    @wraps(method)
    def new_func(*args, **kwargs):
        user = users.get_current_user()
        if user is None:
            return flask.redirect(users.create_login_url())
        return method(*args, **kwargs)
    return new_func


def company_login_required(method):
    @wraps(method)
    def new_func(*args, **kwargs):
        user = users.get_current_user()
        if user is None:
            return flask.redirect(users.create_login_url())
        email_domain = user.email().split('@')[-1]
        if email_domain != 'yelp.com':
            flask.abort(403)

        return method(*args, **kwargs)
    return new_func


def admin_required(method):
    @wraps(method)
    def new_func(*args, **kwargs):
        if not users.is_current_user_admin():
            return flask.redirect(users.create_login_url())
        return method(*args, **kwargs)
    return new_func
