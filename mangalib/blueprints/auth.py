from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Flask, current_app, Response, make_response
)
from werkzeug.security import check_password_hash, generate_password_hash

from mangalib.blueprints.models import db, Users
from mangalib.lib.enum import Access

bp = Blueprint('auth', __name__, url_prefix='')
public_access = ['auth.login', 'auth.register', 'auth.logout']

import re, functools, click

from sqlalchemy import select

valid_password_regex = r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&\.,*-_()]).{6,20}$"
valid_password_pattern = re.compile(valid_password_regex)

def init_app(app: Flask):    
    app.cli.add_command(register_user)
    app.cli.add_command(change_user_role)
    app.cli.add_command(change_user_password)

@bp.after_app_request
def after_request(response: Response):
    return response

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    elif session.get('user') is None:
        session["user"] = Users.query.get({"id": user_id})
        g.user = session["user"]
    else:
        g.user = session["user"]

    if g.user is not None and user_id != g.user['id']:
        print("User error")
        return redirect(url_for('auth.logout'))

    g.requires_clearance = True
    if request.path.startswith('/static'):
        g.requires_clearance = False
    elif request.path in [url_for(endpoint) for endpoint in public_access]:
        g.requires_clearance = False

    if g.requires_clearance and g.user is None:
        if session.get('logged_out') is not None:
            session.clear()
        else:
            flash("Account Needed", 'error')

        return redirect(url_for('auth.login'))

@bp.route('/auth/change-password', methods=('POST',))
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
        user: Users = Users.query.filter_by(id = g.user['id']).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()
        flash("Password Updated", 'success')
    else:
        flash(error, 'error')

    return redirect(url_for(request.args['redirect'] or 'home'))

@bp.route('/register', methods=('GET', 'POST'))
def register():
    if g.user is not None:
        return redirect(url_for('home'))
    
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
            user = Users(username=username, password=generate_password_hash(password))
            exisiting_user = Users.query.filter_by(username=username).first()
            if exisiting_user:
                error = f"User {username} is already registered"
            else:
                db.session.add(user)
                user = Users.query.filter_by(username=username).first()

                if user.id == 1:
                    user.role = Access.OWNER.toString()
                    user.approved = True
                    flash("Registration Successfull", 'success')
                elif current_app.config['ALLOW_NEW_USERS']:
                    if current_app.config['AUTO_APPROVE_NEW_USERS']:
                        user.approved = True
                        flash("Registration Successfull", 'success')
                    else:
                        flash('Successfully registered, please wait to be approved', 'success')
                else:
                    error = 'Registration is closed'
            if error is None:
                db.session.commit()
                return redirect(url_for("auth.login", last_username=username))
            else:
                db.session.rollback()
        
        if error is not None:
            flash(error, 'error')
            return render_template('auth/register.html', last_username=username, last_password=password)
    else:
        owner = Users.query.filter_by(id=1).first()
        registrationOpen = owner is None or current_app.config['ALLOW_NEW_USERS']
        return render_template('auth/register.html', registrationOpen=registrationOpen)

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user is not None:
        return redirect(url_for('home'))
    
    username, password = '', ''

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None

        user: Users = Users.query.filter_by(username=username).first()
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user.password, password):
            error = 'Incorrect password'

        if error is None:
            session.clear()
            session['user_id'] = user.id
            g.user = user
            flash("Login Successful", 'success')
            return redirect('/')
        
        flash(error, 'error')

    return render_template('auth/login.html', last_username=username, last_password=password)

@bp.route('/logout')
def logout():
    session.clear()
    session['logged_out'] = True
    flash("Successfully Logged Out", 'info')
    return redirect(url_for('home'))

def owner_access(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        user_access = Access.fromString(g.user['role'])
        if user_access < Access.OWNER:
            return make_response(render_template('not_found.html'), 404)
        
        return view(**kwargs)
    
    return wrapped_view

def admin_access(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        user_access = Access.fromString(g.user['role'])
        if user_access < Access.ADMIN:
            return make_response(render_template('not_found.html'), 404)
        
        return view(**kwargs)
    
    return wrapped_view

def moderator_access(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        user_access = Access.fromString(g.user['role'])
        if user_access < Access.MODERATOR:
            return make_response(render_template('not_found.html'), 404)

        return view(**kwargs)
    
    return wrapped_view

@click.command("register-user")
@click.option("-u", "--username")
@click.option("-p", "--password")
@click.option("-r", "--role", default="user")
def register_user(username, password, role):
    if Users.query.filter_by(username=username).first() is None:
        user: Users = Users(username=username, password=generate_password_hash(password))
        db.session.add(user)
        user = Users.query.filter_by(username=username).first()
        if Access.OWNER == role:
            if user.id == 1:
                user.role = Access.OWNER.toString()
                user.approved = True
                db.session.commit()
                click.echo(f"Registered user: {username}")
            else:
                click.echo("Cannot make account Owner, only the first registered user can be the owner")
        else:
            user.role = (Access.fromString(role) or Access.USER).toString()
            user.approved = True
            db.session.commit()
            click.echo(f"Registered user: {username}")
    else:
        click.echo("Username is already registered")

@click.command("change-user-role")
@click.option("-u", "--username")
@click.option("-r", "--role", default="user")
def change_user_role(username, role):
    user: Users | None = Users.query.filter_by(username=username).first()
    if user is not None:
        old_role = Access.fromString(user.role)
        if Access.OWNER == role:
            if user.id == 1:
                user.role = Access.OWNER.toString()
                click.echo(f"Success changed {username} role from '{old_role}' to '{user.role}'")
                db.session.commit()
            else:
                click.echo("Cannot make account Owner, only the first registered user can be the owner")
        else:
            user.role = (Access.fromString(role) or Access.USER).toString()
            click.echo(f"Successfully changed {username} role from '{old_role}' to '{user.role}'")
            db.session.commit()
    else:
        click.echo("Username is not registered")

@click.command("change-user-password")
@click.option("-u", "--username")
@click.option("-p", "--password")
def change_user_password(username, password):
    user: Users | None = Users.query.filter_by(username=username).first()
    if user is not None:
        user.password = generate_password_hash(password)
        db.session.commit()
        click.echo(f"Success changed {username} password")