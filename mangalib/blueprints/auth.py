import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Flask, current_app, abort, make_response
)
from werkzeug.security import check_password_hash, generate_password_hash

from mangalib.blueprints.db import get_user_db as get_db

import click

from ..lib.enum import Access

bp = Blueprint('auth', __name__, url_prefix='')
public_access = ['auth.login', 'auth.register', 'auth.logout']

import re

valid_password_regex = r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&\.,*-_()]).{6,20}$"
valid_password_pattern = re.compile(valid_password_regex)

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()

    g.requires_clearance = True

    if request.path.startswith('/static'):
        g.requires_clearance = False
    elif request.path in [url_for(endpoint) for endpoint in public_access]:
        g.requires_clearance = False

    if g.requires_clearance and g.user is None:
        if session.get('logged_out', None) is not None:
            session.clear()
        else:
            flash("Account Needed", 'error')

        return redirect(url_for('auth.login'))

def init_app(app: Flask):    
    app.cli.add_command(testRegister)

@click.command('test-reg')
def testRegister():
    try:
        db = get_db()
        user_id = db.execute(
            "INSERT INTO user (username, password) VALUES (?, ?)",
            ('test', generate_password_hash('test')),
        ).lastrowid
        if user_id == 1:
            print('Registered user is owner')
            db.execute(
                "UPDATE user SET role = 'owner' WHERE id = 1"
            )
        #db.commit()
    except db.IntegrityError:
        print("Already Registered")

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
        db = get_db()
        db.execute(
            "UPDATE user SET password = ? WHERE id = ?",
            (generate_password_hash(new_password), g.user['id'])
        )
        db.commit()
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
        db = get_db()

        if not username:
            error = 'Username is required'
        elif not password:
            error = 'Password is required'
        
        if error is None:
            try:
                user_id = db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password),),
                ).lastrowid
                if user_id == 1:
                    db.execute(
                        "UPDATE user SET role = 'owner', approved = TRUE WHERE id = 1"
                    )
                    db.commit()
                    flash("Registration Successfull", 'success')
                    return redirect(url_for("auth.login"))
                elif current_app.config['ALLOW_NEW_USERS']:
                    if current_app.config['AUTO_APPROVE_NEW_USERS']:
                        db.execute(
                            "UPDATE user SET approved = TRUE WHERE id = ?",
                            (user_id,)
                        )
                        db.commit()
                        flash("Registration Successfull", 'success')
                    else:
                        flash('Successfully registered, please wait to be approved', 'success')
                        db.commit()
                    return redirect(url_for("auth.login", last_username=username))
                else:
                    error = 'Registration is closed'
                    
            except db.IntegrityError:
                error = f"User {username} is already registered"
            
        if error is not None:
            flash(error, 'error')
            return render_template('auth/register.html', last_username=username, last_password=password)
    else:
        return render_template('auth/register.html')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user is not None:
        return redirect(url_for('home'))
    
    username, password = '', ''

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        user = db.execute(
            "SELECT * FROM user WHERE username = ?", (username,)
        ).fetchone()

        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
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