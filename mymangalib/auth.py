from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Flask, current_app, Response, make_response
)
from werkzeug.security import check_password_hash, generate_password_hash

from .models import db_engine, User
from .enum import Access
from .constants import ROUTE, ENDPOINT, VAR

bp = Blueprint('auth', __name__, url_prefix='')
public_access = [ENDPOINT.AUTH_LOGIN, ENDPOINT.AUTH_REGISTER, ENDPOINT.AUTH_LOGOUT]

import re, functools, click
from flask.cli import with_appcontext

from sqlalchemy import func, select

valid_password_regex = r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&\.,*-_()]).{6,20}$"
valid_password_pattern = re.compile(valid_password_regex)

def init_app(app: Flask):    
    app.cli.add_command(register_user)
    app.cli.add_command(change_user_role)
    app.cli.add_command(change_user_password)
    app.cli.add_command(approve_user)

def onboarding():
    global before_request
    if g.requires_clearance:
        if request.path.startswith('/static'):
            g.requires_clearance = False
            return
    
    # Compared by endpoint, not path, so it still matches when the app is mounted under a prefix like /classic
    if request.endpoint != ENDPOINT.AUTH_REGISTER:
        if get_owner() is None:
            return redirect(url_for(ENDPOINT.AUTH_REGISTER))
        else:
            before_request = load_logged_in_user
            return load_logged_in_user()

before_request = onboarding

def load_logged_in_user():
    if g.requires_clearance:
        if request.path.startswith('/static'):
            g.requires_clearance = False
            return
        elif request.endpoint in public_access:
            g.requires_clearance = False
            return
        
    if g.user is None:
        if session.get('logged_out') is not None:
            session.clear()
        else:
            flash("Account Needed", 'error')
        session["requested_url"] = request.base_url
        print(session["requested_url"])
        return redirect(url_for(ENDPOINT.AUTH_LOGIN))
    
API_V1_PREFIX = "/api/v1/"
# Endpoints of /api/v1 that work without logging in
API_PUBLIC_ENDPOINTS = {"api_v1.server_info", "api_v1.login", "api_v1.register"}
# <img> tags can't send headers, so these also accept the token as ?t=
API_IMAGE_ENDPOINTS = {"api_v1.cover", "api_v1.page_image"}

def api_error(status: int, code: str, message: str):
    return make_response({"error": {"code": code, "message": message}}, status)

def load_api_user():
    """/api/v1 uses tokens only, never the session cookie, so cookie-based CSRF doesn't apply to it."""
    from .server import tokens

    g.api_token = None
    g.user = None

    raw_token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[len("Bearer "):].strip()
    elif request.endpoint in API_IMAGE_ENDPOINTS:
        raw_token = request.args.get("t")

    token = tokens.find_token(raw_token)
    if token is not None:
        user = db_engine.session.get(User, token.user_id)
        if user is not None and user.approved:
            g.api_token = token
            g.user = user

    # Preflight requests never carry the token. flask-cors answers them.
    if request.method == "OPTIONS" or request.endpoint in API_PUBLIC_ENDPOINTS:
        return None
    if g.user is None:
        return api_error(401, "unauthorized", "Login required")

@bp.before_app_request
def before_app_request():
    if request.path.startswith(API_V1_PREFIX):
        return load_api_user()

    # Only the user id lives in the cookie. The user is loaded fresh each request so the
    # password hash never leaves the server and role changes apply immediately.
    session.pop('user', None) # Clears the full user record older versions stored in the cookie
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = db_engine.session.get(User, user_id)
        if g.user is None or not g.user.approved:
            # Account no longer exists or is not approved
            g.user = None
            session.clear()

    if g.get("requires_clearance") is None:
        g.requires_clearance = True

    return before_request()

@bp.route(ROUTE.CHANGE_PASSWORD, methods=('POST',))
def changePassword():
    old_password = request.form['old-password']
    new_password = request.form['new-password']
    repeat_password = request.form['repeat-password']
    error = None

    if(new_password != repeat_password):
        error = "New passwords much match"
    elif(not check_password_hash(g.user['password'], old_password)):
        error = "Incorrect password"
    elif(not valid_password_pattern.search(new_password)):
        error = "Invalid Password: Password should be 6-20 characters long, have at least 1 number, uppercase, lowercase, and symbol (#?!@$%.,^&*-_])"

    if error is None:
        user: User = User.query.filter_by(id = g.user['id']).first()
        if user:
            user.password = generate_password_hash(new_password)
            db_engine.session.commit()
        flash("Password Updated", 'success')
    else:
        flash(error, 'error')

    return redirect(url_for(request.args['redirect'] or ENDPOINT.HOME))

@bp.route(ROUTE.CHANGE_USERNAME, methods=["POST"])
def changeUsername():
    new_username = request.form["new-username"]

    existing_user = User.query.where(func.lower(User.username) == new_username.lower()).one_or_none()

    if existing_user is None:
        user: User = User.query.get({"id": g.user['id']})
        user.username = new_username
        db_engine.session.commit()
        flash("Changed Username", "success")
    else:
        flash("Username Already Exists", "error")

    return redirect(request.referrer)


@bp.route(ROUTE.REGISTER, methods=('GET', 'POST'))
def register():
    registrationOpen = None
    auto_approve = None
    if g.user is not None:
        user_role = get_user_role()
        if user_role < Access.ADMIN:
            return redirect(url_for('manga.home'))
        else:
            registrationOpen = True
            auto_approve = True
    else:
        registrationOpen = current_app.config['ALLOW_NEW_USERS']
        auto_approve = current_app.config['AUTO_APPROVE_NEW_USERS']

    username, password = '', ''
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username:
            error = 'Username is required'
        elif not password:
            error = 'Password is required'
        else:
            user, error = register_account(username, password, registrationOpen, auto_approve)
            if error is not None:
                flash(error, "error")
            elif user.role == Access.OWNER.toString():
                flash("Created Owner Account", 'success')
            elif user.approved:
                flash("Registration Successfull", 'success')
            else:
                flash('Successfully registered, please wait to be approved', 'success')

            if error is None:
                return redirect(url_for(ENDPOINT.AUTH_LOGIN, last_username=username))
            else:
                return redirect(url_for(ENDPOINT.AUTH_REGISTER, last_username=username))
        
        if error is not None:
            return render_template('auth/register.html', last_username=username, last_password=password)
    else:
        owner = get_owner()
        if owner is None:
            return render_template('auth/register.html', registrationOpen=True, registration_info="Create Owner Account")
        else:
            return render_template('auth/register.html', registrationOpen=registrationOpen, registration_info="Register New User")

def registration_rules() -> tuple[bool, bool]:
    """(registration open, auto approve) for the current request. Admins can always add approved users."""
    if g.user is not None and get_user_role() >= Access.ADMIN:
        return True, True
    return bool(current_app.config['ALLOW_NEW_USERS']), bool(current_app.config['AUTO_APPROVE_NEW_USERS'])

def register_account(username: str, password: str, registration_open: bool, auto_approve: bool) -> tuple[User | None, str | None]:
    """Creates a user. The first account becomes the owner even when registration is closed.
    Returns (user, None) or (None, error message)."""
    existing_user = db_engine.session.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if existing_user is not None:
        return None, f"User {username} is already registered"

    if get_owner() is None:
        registration_open = True
    if not registration_open:
        return None, 'Registration is closed'

    user = User.create(username=username, password_hash=generate_password_hash(password))
    db_engine.session.add(user)
    db_engine.session.flush()

    if user.id == 1:
        user.role = Access.OWNER.toString()
        user.approved = True
    elif auto_approve:
        user.approved = True
    db_engine.session.commit()
    return user, None

def check_credentials(username: str, password: str) -> tuple[User | None, str | None]:
    user: User = User.query.filter_by(username=username).first()
    if user is None:
        return None, 'Invalid username'
    elif not check_password_hash(user.password, password):
        return None, 'Incorrect password'
    elif not user.approved:
        return None, 'Account is waiting for approval'
    return user, None

@bp.route(ROUTE.LOGIN, methods=('GET', 'POST'))
def login():
    print(request.referrer)
    # if g.get("user") is not None:
    if g.user is not None:
        return redirect(url_for('manga.home'))
    
    username, password = '', ''

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user, error = check_credentials(username, password)

        if error is None:
            landing_page = session.get("requested_url", "/")
            session.clear()
            session['user_id'] = user.id
            g.user = user
            flash("Login Successful", 'success')
            return redirect(landing_page)
        
        flash(error, 'error')

    html_data = render_template('auth/login.html', last_username=username, last_password=password)
    return html_data

@bp.route('/logout')
def logout():
    session.clear()
    session['logged_out'] = True
    flash("Successfully Logged Out", 'info')
    return redirect(url_for('manga.home'))

def get_user_role() -> Access:
    return Access.fromString(g.user['role'])

def get_role_context():
    user_role = get_user_role()
    context = {
        "isOwner": user_role == Access.OWNER,
        "isAdmin": user_role >= Access.ADMIN,
        "isMod": user_role >= Access.MODERATOR
    }
    return context

def owner_access(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for(ENDPOINT.AUTH_LOGIN))
        
        user_access = Access.fromString(g.user['role'])
        if user_access < Access.OWNER:
            return make_response(render_template('not_found.html'), 404)
        
        return view(**kwargs)
    
    return wrapped_view

def admin_access(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for(ENDPOINT.AUTH_LOGIN))
        
        user_access = Access.fromString(g.user['role'])
        if user_access < Access.ADMIN:
            return make_response(render_template('not_found.html'), 404)
        
        return view(**kwargs)
    
    return wrapped_view

def moderator_access(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for(ENDPOINT.AUTH_LOGIN))
        
        user_access = Access.fromString(g.user['role'])
        if user_access < Access.MODERATOR:
            return make_response(render_template('not_found.html'), 404)

        return view(**kwargs)
    
    return wrapped_view

def api_access(minimum: Access = Access.USER):
    """JSON version of the access decorators for /api/v1: 401 when logged out, 403 when the role is too low."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.get("user") is None:
                return api_error(401, "unauthorized", "Login required")
            if Access.fromString(g.user['role']) < minimum:
                return api_error(403, "forbidden", "Your account doesn't have access to this")
            return view(**kwargs)
        return wrapped_view
    return decorator

select_owner = (
    select(User)
    .where(User.id == 1)
)
def get_owner() -> User:
    if db_engine.session is None:
        return None
    
    owner: User = db_engine.session.scalar(select_owner)
    return owner

@click.command("register-user")
@click.option("-u", "--username")
@click.option("-p", "--password")
@click.option("-r", "--role", default="user")
def register_user(username, password, role):
    if User.query.filter_by(username=username).first() is None:
        user: User = User.create(username=username, password_hash=generate_password_hash(password))
        db_engine.session.add(user)
        user = User.query.filter_by(username=username).first()
        if Access.OWNER == role:
            if user.id == 1:
                user.role = Access.OWNER.toString()
                user.approved = True
                db_engine.session.commit()
                click.echo(f"Registered user: {username}")
            else:
                click.echo("Cannot make account Owner, only the first registered user can be the owner")
        else:
            user.role = (Access.fromString(role) or Access.USER).toString()
            user.approved = True
            db_engine.session.commit()
            click.echo(f"Registered user: {username}")
    else:
        click.echo("Username is already registered")

@click.command("change-user-role")
@click.option("-u", "--username")
@click.option("-r", "--role", default="user")
def change_user_role(username, role):
    user: User | None = User.query.filter_by(username=username).first()
    if user is not None:
        old_role = Access.fromString(user.role)
        if Access.OWNER == role:
            if user.id == 1:
                user.role = Access.OWNER.toString()
                click.echo(f"Success changed {username} role from '{old_role}' to '{user.role}'")
                db_engine.session.commit()
            else:
                click.echo("Cannot make account Owner, only the first registered user can be the owner")
        else:
            user.role = (Access.fromString(role) or Access.USER).toString()
            click.echo(f"Successfully changed {username} role from '{old_role}' to '{user.role}'")
            db_engine.session.commit()
    else:
        click.echo("Username is not registered")

@click.command("change-user-password")
@click.option("-u", "--username")
@click.option("-p", "--password")
def change_user_password(username, password):
    user: User | None = User.query.filter_by(username=username).first()
    if user is not None:
        user.password = generate_password_hash(password)
        db_engine.session.commit()
        click.echo(f"Success changed {username} password")

@click.command("approve-user")
@click.option("-u", "--username")
@with_appcontext
def approve_user(username):
    user: User | None = User.query.filter_by(username=username).first()
    if user is None:
        click.echo("Username is not registered")
    elif user.approved:
        click.echo(f"{username} is already approved")
    else:
        user.approved = True
        db_engine.session.commit()
        click.echo(f"Approved {username}")
