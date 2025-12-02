from functools import wraps
from flask import session, flash, redirect, url_for

def require_admin(f):
    """Decorator om routes te beschermen - alleen admins toegang"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.routes import get_current_user
        
        user = get_current_user()
        if not user:
            flash("Gelieve eerst aan te melden.")
            return redirect(url_for('login'))
        
        if not user.is_admin():
            flash("Toegang geweigerd. Admin rechten vereist.")
            return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function