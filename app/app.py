from flask import render_template, request, redirect, url_for, session, flash

# Use application factory from package
from app import create_app

app = create_app()

# Import db for create_all on startup
try:
    from app.models import db
except Exception:
    from models import db


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form["user_id"]
        session["user"] = user_id
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    # Haal volledige user op uit DB zodat we naam/achternaam kunnen tonen
    try:
        user_id = int(session.get("user"))
    except Exception:
        user_id = None

    # try to load the user record from the DB (models available via package)
    user_obj = None
    try:
        from app.models import User
        if user_id is not None:
            user_obj = User.query.filter_by(user_id=user_id).first()
    except Exception:
        # models not available or DB not configured — fall back to session value
        user_obj = None

    # Als we geen user record vinden, val terug op de raw session waarde
    if not user_obj:
        display = session.get("user")
    else:
        display = f"{user_obj.user_name} {user_obj.user_last_name}"

    return render_template("home.html", user=display)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route('/db_test')
def db_test():
    """Simple DB connection test: returns ok or error."""
    try:
        with app.app_context():
            # simple query
            db.session.execute('SELECT 1')
        return "DB OK"
    except Exception as e:
        return f"DB Error: {e}", 500

if __name__ == "__main__":
    with app.app_context():
        try:
            db.create_all()  # Maak alle tabellen aan als ze niet bestaan
        except Exception as e:
            print(f"Warning: could not create tables: {e}")
    app.run(debug=True)