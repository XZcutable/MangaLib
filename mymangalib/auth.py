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

from sqlalchemy import func, select

valid_password_regex = r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&\.,*-_()]).{6,20}$"
valid_password_pattern = re.compile(valid_password_regex)

def init_app(app: Flask):    
    app.cli.add_command(register_user)
    app.cli.add_command(change_user_role)
    app.cli.add_command(change_user_password)

def onboarding():
    global before_request
    if g.requires_clearance:
        if request.path.startswith('/static'):
            g.requires_clearance = False
            return
    
    if request.path != url_for(ENDPOINT.AUTH_REGISTER):
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
        elif request.path in [url_for(endpoint) for endpoint in public_access]:
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
    
@bp.before_app_request
def before_app_request():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    elif session.get('user') is None:
        session["user"] = User.query.get({"id": user_id}) # replace
        g.user = session["user"]
    else:
        g.user = session["user"]

    if g.user is not None and user_id != g.user['id']:
        print("User error")
        return redirect(url_for(ENDPOINT.AUTH_LOGOUT))

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
            print("Creating user")

            find_user = (
                select(User)
                .where(User.username == username)
            )
            exisiting_user = db_engine.session.scalar(find_user)
            if exisiting_user is not None:
                error = f"User {username} is already registered"
                flash(error, "error")
            else:
                
                owner = get_owner()
                if owner is None:
                    registrationOpen = True
                
                if registrationOpen:
                    db_engine.session.begin_nested()
                    user = User.create(username=username, password_hash=generate_password_hash(password))
                    db_engine.session.add(user)
                    db_engine.session.commit()

                    db_engine.session.begin_nested()
                    user = db_engine.session.scalar(find_user)

                    if user.id == 1:
                        user.role = Access.OWNER.toString()
                        user.approved = True
                        flash("Created Owner Account", 'success')
                    elif auto_approve:
                        user.approved = True
                        flash("Registration Successfull", 'success')
                    else:
                        flash('Successfully registered, please wait to be approved', 'success')
                    db_engine.session.commit()
                else:
                    error = 'Registration is closed'
                    flash(error, "error")

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
        error = None

        user: User = User.query.filter_by(username=username).first()
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user.password, password):
            error = 'Incorrect password'

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
        user: User = User(username=username, password=generate_password_hash(password))
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