from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User, Building, Desk, Reservation
from routes import main

app = Flask(__name__)
app.secret_key = "mysecretkey"

# Database configuratie
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:groep32mvp1@db.knxcqgoealvgfqcuffep.supabase.co:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Register blueprint
app.register_blueprint(main)

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

    user_obj = None
    if user_id is not None:
        user_obj = User.query.filter_by(user_id=user_id).first()

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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Maak alle tabellen aan als ze niet bestaan
    app.run(debug=True)