from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User, Building, Desk, Reservation
from datetime import datetime
from sqlalchemy import and_

main = Blueprint("main", __name__)


def get_current_user():
    """Helper: haal user-object op van session"""
    if "user" not in session:
        return None
    user_id = int(session["user"])
    user = User.query.filter_by(user_id=user_id).first()
    return user


@main.route("/reserve", methods=["GET", "POST"])
def reserve():
    """
    Stap 1: Reservatiescherm
    - Toon gebouwen 
    - Kalender voor datumselectie
    - Begintijd en eindtijd input
    """
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden.")
        return redirect(url_for("login"))

    buildings = Building.query.all()
    floors = [0, 1, 2]

    # Behoud ingevoerde waarden voor aanpassingen
    saved = {
        "building_id": request.args.get("building_id", ""),
        "floor": request.args.get("floor", ""),
        "date": request.args.get("date", ""),
        "start_time": request.args.get("start_time", ""),
        "end_time": request.args.get("end_time", ""),
    }

    if request.method == "POST":
        building_id = request.form.get("building_id")
        floor = request.form.get("floor")
        date_str = request.form.get("date")
        start_time_str = request.form.get("start_time")
        end_time_str = request.form.get("end_time")

        # Validatie
        if not date_str or not start_time_str or not end_time_str:
            flash("Vul alstublieft datum en tijden in.")
            return redirect(url_for("main.reserve"))

        # Ga naar beschikbare bureaus
        return redirect(url_for("main.available",
                                building_id=building_id or "",
                                floor=floor or "",
                                date=date_str,
                                start_time=start_time_str,
                                end_time=end_time_str))

    return render_template("reserve.html",
                           user=user,
                           buildings=buildings,
                           floors=floors,
                           saved=saved)


@main.route("/reserve/available", methods=["GET", "POST"])
def available():
    """
    Stap 2: Beschikbare bureaus tonen
    - Filter op building, floor, datum, tijd
    - Toon alleen bureaus zonder overlappende reservatie
    """
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden.")
        return redirect(url_for("login"))

    # Haal parameters op (building_id bevat nu de building.adress, bv 'A' of 'B')
    building_adress = request.args.get("building_id")
    floor = request.args.get("floor")
    date_str = request.args.get("date")
    start_str = request.args.get("start_time")
    end_str = request.args.get("end_time")

    if not date_str or not start_str or not end_str:
        flash("Datum en tijden ontbreken.")
        return redirect(url_for("main.reserve"))

    # Parse datum en tijd
    try:
        chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time_obj = datetime.strptime(start_str, "%H:%M").time()
        end_time_obj = datetime.strptime(end_str, "%H:%M").time()
        
        # Maak volledige datetime objecten voor starttijd en eindtijd
        start_datetime = datetime.combine(chosen_date, start_time_obj)
        end_datetime = datetime.combine(chosen_date, end_time_obj)
    except:
        flash("Ongeldig datumformaat. Gebruik YYYY-MM-DD en HH:MM.")
        return redirect(url_for("main.reserve"))

    if start_time_obj >= end_time_obj:
        flash("Eindtijd moet later zijn dan starttijd.")
        return redirect(url_for("main.reserve"))

    # Query: alle bureaus
    q = Desk.query

    if building_adress:
        # zoek building record op basis van adress (A, B, ...)
        b = Building.query.filter_by(adress=building_adress).first()
        if b:
            q = q.filter(Desk.building_id == b.building_id)
        else:
            # geen gebouw met die naam -> geen resultaten
            q = q.filter(False)

    candidate_desks = q.all()

    # Filter: verwijder bureaus met overlappende reservaties
    available_desks = []
    for desk in candidate_desks:
        overlapping = Reservation.query.filter(
            Reservation.desk_id == desk.desk_id,
            Reservation.starttijd < end_datetime,
            start_datetime < Reservation.eindtijd
        ).first()
        if not overlapping:
            available_desks.append(desk)

    # Behoud waarden
    saved = {
        # we bewaren hier de 'adress' string zodat de form dezelfde waarde toont
        "building_id": building_adress or "",
        "floor": floor or "",
        "date": date_str,
        "start_time": start_str,
        "end_time": end_str,
    }

    return render_template("available.html",
                           user=user,
                           desks=available_desks,
                           saved=saved,
                           buildings=Building.query.all())


@main.route("/reserve/desk/<int:desk_id>", methods=["GET", "POST"])
def desk_detail(desk_id):
    """
    Stap 3: Bureau detail & bevestiging
    - Toon alle info van bureau
    - Toon datum/tijd die je geselecteerd hebt
    - Bevestig reservatie of annuleer
    """
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden.")
        return redirect(url_for("login"))

    desk = Desk.query.filter_by(desk_id=desk_id).first()
    if not desk:
        flash("Bureau niet gevonden.")
        return redirect(url_for("main.reserve"))

    # Haal context op
    date_str = request.args.get("date")
    start_str = request.args.get("start_time")
    end_str = request.args.get("end_time")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "confirm":
            # Maak reservatie aan
            try:
                chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                start_time_obj = datetime.strptime(start_str, "%H:%M").time()
                end_time_obj = datetime.strptime(end_str, "%H:%M").time()
                
                start_datetime = datetime.combine(chosen_date, start_time_obj)
                end_datetime = datetime.combine(chosen_date, end_time_obj)

                # Double-check: is bureau niet ondertussen al geboekt?
                overlapping = Reservation.query.filter(
                    Reservation.desk_id == desk.desk_id,
                    Reservation.starttijd < end_datetime,
                    start_datetime < Reservation.eindtijd
                ).first()
                if overlapping:
                    flash("Dit bureau is ondertussen al geboekt!")
                    return redirect(url_for("main.available",
                                            date=date_str,
                                            start_time=start_str,
                                            end_time=end_str))

                # Voeg reservatie toe
                reservation = Reservation(
                    user_id=user.user_id,
                    desk_id=desk.desk_id,
                    starttijd=start_datetime,
                    eindtijd=end_datetime
                )
                db.session.add(reservation)
                db.session.commit()

                flash("Je reservatie is succesvol toegevoegd!")
                return redirect(url_for("home"))

            except Exception as e:
                flash(f"Fout bij reservatie: {str(e)}")
                return redirect(url_for("main.available",
                                        date=date_str,
                                        start_time=start_str,
                                        end_time=end_str))

        elif action == "cancel":
            return redirect(url_for("home"))

    return render_template("desk_detail.html",
                           user=user,
                           desk=desk,
                           date=date_str,
                           start_time=start_str,
                           end_time=end_str)
