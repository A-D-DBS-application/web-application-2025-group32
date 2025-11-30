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
        user_id_input = request.form.get("user_id", "").strip()
        
        # Valideer dat user_id niet leeg is
        if not user_id_input:
            flash("Gelieve een gebruikers-ID in te geven.")
            return redirect(url_for("login"))
        
        # Probeer te converteren naar integer
        try:
            user_id = int(user_id_input)
        except ValueError:
            flash("Ongeldig gebruikers-ID. Gelieve een nummer in te geven.")
            return redirect(url_for("login"))
        
        # Check of gebruiker bestaat in database
        try:
            from app.models import User
            user = User.query.filter_by(user_id=user_id).first()
            if not user:
                flash("Gebruiker niet gevonden. Controleer je gebruikers-ID.")
                return redirect(url_for("login"))
            
            # Gebruiker bestaat, log in
            session["user"] = user_id
            return redirect(url_for("home"))
        except Exception as e:
            flash("Fout bij aanmelden. Probeer opnieuw.")
            return redirect(url_for("login"))
    
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
    is_admin = False  # Default value
    try:
        from app.models import User, Reservation
        from datetime import datetime, timedelta
        if user_id is not None:
            user_obj = User.query.filter_by(user_id=user_id).first()
    except Exception:
        # models not available or DB not configured — fall back to session value
        user_obj = None

    # Als we geen user record vinden, val terug op de raw session waarde
    if not user_obj:
        display = session.get("user")
        is_admin = False
    else:
        display = f"{user_obj.user_name} {user_obj.user_last_name}"
        is_admin = user_obj.is_admin()

    # Haal aankomende reservaties op (komende week)
    upcoming = []
    completed = []
    try:
        from app.models import Reservation, Feedback
        from datetime import datetime, timedelta
        now = datetime.now()
        week_later = now + timedelta(days=7)
        
        # Aankomende reservaties
        upcoming = Reservation.query.filter(
            Reservation.user_id == user_id,
            Reservation.starttijd >= now,
            Reservation.starttijd <= week_later
        ).order_by(Reservation.starttijd).all()
        
        # Voltooide reservaties (laatste 30 dagen)
        month_ago = now - timedelta(days=30)
        completed = Reservation.query.filter(
            Reservation.user_id == user_id,
            Reservation.eindtijd < now,
            Reservation.eindtijd >= month_ago
        ).order_by(Reservation.eindtijd.desc()).all()
        
        # Voeg gebouw en bureau info toe aan elke reservatie
        for res in upcoming + completed:
            if res.desk and res.desk.building:
                res.building_adress = res.desk.building.adress
                res.desk_number = res.desk.desk_number
            else:
                res.building_adress = 'N/A'
                res.desk_number = 'N/A'
            # Check if feedback exists
            res.has_feedback = Feedback.query.filter_by(reservation_id=res.res_id).first() is not None
    except Exception:
        upcoming = []
        completed = []

    return render_template("home.html", user=display, user_display=display, upcoming=upcoming, completed=completed, is_admin=is_admin)

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
    app.run(debug=True, port=5001)