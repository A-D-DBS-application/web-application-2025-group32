from flask import Blueprint, render_template, request, redirect, url_for, session, flash
try:
    from app.models import db, User, Building, Desk, Reservation, Feedback
except Exception:
    from models import db, User, Building, Desk, Reservation, Feedback
from datetime import datetime
from sqlalchemy import and_, text

main = Blueprint("main", __name__)


def get_current_user():
    """Helper: haal user-object op van session"""
    if "user" not in session:
        return None

    raw = session["user"]
    # Try to interpret session value as integer user_id first
    try:
        user_id = int(raw)
        user = User.query.filter_by(user_id=user_id).first()
        if user:
            return user
    except Exception:
        # not an int - continue to try other lookups
        pass

    # Try to find by username or email (some sessions store a string username)
    try:
        user = User.query.filter((User.user_name == raw) | (User.user_email == raw)).first()
        if user:
            return user
    except Exception:
        # If the DB or model isn't available, return None
        return None

    return None


@main.route("/reserve", methods=["GET", "POST"])
def reserve():
    """
    Stap 1: Reservatiescherm
    - Toon gebouwen 
    - Kalender voor datumselectie
    - Begintijd en eindtijd input
    """
    user = get_current_user()
    # Allow anonymous users to view the reservation form (GET). Only require
    # login for actions that create reservations (POST).
    buildings = []
    try:
        # Get unique buildings (distinct by adress) and sort alphabetically
        from sqlalchemy import distinct
        unique_addresses = db.session.query(distinct(Building.adress)).order_by(Building.adress).all()
        # For each unique address, get one building object
        buildings = [Building.query.filter_by(adress=addr[0]).first() for addr in unique_addresses]
    except Exception:
        buildings = []
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

        # If the user is not logged in, redirect them to login before
        # proceeding to choose/confirm a desk.
        if not user:
            flash("Gelieve eerst aan te melden om een reservatie te maken.")
            # preserve the chosen filters as query params so we can continue
            return redirect(url_for("login", next=url_for("main.available", building_id=building_id or "", floor=floor or "", date=date_str, start_time=start_time_str, end_time=end_time_str)))

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
    # Allow anonymous view of available desks; booking requires login later.

    # Haal parameters op (building_id bevat nu de building.adress, bv 'A' of 'B')
    building_adress = request.args.get("building_id")
    floor_str = request.args.get("floor")
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

    # Query: alle bureaus, maar filteren op ZOWEL adress ALS floor (optioneel)
    q = Desk.query
    
    # Filter op building: zoek building die matcht met ZOWEL adress ALS floor (alleen als ingevuld)
    # Check of de waarden niet leeg zijn
    has_building = building_adress and building_adress.strip()
    has_floor = floor_str and floor_str.strip()
    
    if has_building or has_floor:
        building_filters = []
        if has_building:
            building_filters.append(Building.adress == building_adress.strip())
        if has_floor:
            try:
                floor_int = int(floor_str.strip())
                building_filters.append(Building.floor == floor_int)
            except ValueError:
                pass  # Ongeldige floor waarde, negeer
        
        if building_filters:
            # Zoek buildings die matchen met de filters
            matching_buildings = Building.query.filter(and_(*building_filters)).all()
            if matching_buildings:
                # Filter desks op deze building IDs
                building_ids = [b.building_id for b in matching_buildings]
                q = q.filter(Desk.building_id.in_(building_ids))
            else:
                # Geen matching buildings -> geen resultaten
                q = q.filter(False)
    # Als geen filters, toon alle bureaus

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

    # Prioriteitssortering: bureaus die de gebruiker al heeft geboekt komen bovenaan
    if user:
        # Tel per bureau hoeveel keer deze gebruiker het heeft geboekt
        desk_booking_counts = {}
        for desk in available_desks:
            count = Reservation.query.filter(
                Reservation.desk_id == desk.desk_id,
                Reservation.user_id == user.user_id
            ).count()
            desk_booking_counts[desk.desk_id] = count
        
        # Sorteer: hoogste count eerst, dan op desk_id als tiebreaker
        available_desks.sort(key=lambda d: (-desk_booking_counts.get(d.desk_id, 0), d.desk_id))

    # Behoud waarden
    saved = {
        # we bewaren hier de 'adress' string zodat de form dezelfde waarde toont
        "building_id": building_adress or "",
        "floor": floor_str or "",
        "date": date_str,
        "start_time": start_str,
        "end_time": end_str,
    }

    # Safe get for buildings list
    try:
        all_buildings = Building.query.all()
    except Exception:
        all_buildings = []

    return render_template("available.html",
                           user=user,
                           desks=available_desks,
                           saved=saved,
                           buildings=all_buildings)


@main.route("/reserve/desk/<int:desk_id>", methods=["GET", "POST"])
def desk_detail(desk_id):
    """
    Stap 3: Bureau detail & bevestiging
    - Toon alle info van bureau
    - Toon datum/tijd die je geselecteerd hebt
    - Bevestig reservatie of annuleer
    """
    user = get_current_user()
    # Allow viewing desk details without login; require login for confirmation.

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
            # Require logged in user for creating a reservation
            if not user:
                flash("Gelieve eerst aan te melden om een reservatie te maken.")
                return redirect(url_for("login"))

            # Maak reservatie aan
            try:
                chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                start_time_obj = datetime.strptime(start_str, "%H:%M").time()
                end_time_obj = datetime.strptime(end_str, "%H:%M").time()
                
                start_datetime = datetime.combine(chosen_date, start_time_obj)
                end_datetime = datetime.combine(chosen_date, end_time_obj)

                # Double-check: is bureau niet ondertussen al geboekt?
                # Acquire a row-level lock on the desk to reduce race conditions
                try:
                    db.session.execute(text("SELECT 1 FROM desk WHERE desk_id = :id FOR UPDATE"), {"id": desk.desk_id})
                except Exception:
                    # If locking fails (DB that doesn't support FOR UPDATE, or other issue), continue to check normally
                    pass

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


@main.route('/mijn_reservaties')
def mijn_reservaties():
    """
    Toon alleen toekomstige reservaties van de ingelogde gebruiker.
    """
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden om je reservaties te zien.")
        return redirect(url_for('login', next=url_for('main.mijn_reservaties')))

    try:
        from datetime import datetime
        now = datetime.now()
        # Alleen toekomstige reservaties
        reservations = Reservation.query.filter(
            Reservation.user_id == user.user_id,
            Reservation.starttijd >= now
        ).order_by(Reservation.starttijd).all()
    except Exception:
        reservations = []

    # Build a lightweight view model to pass to the template
    rows = []
    for r in reservations:
        desk = None
        building = None
        try:
            desk = r.desk
            building = desk.building if desk else None
        except Exception:
            desk = None
            building = None

        rows.append({
            'res_id': r.res_id,
            'desk_number': getattr(desk, 'desk_number', None),
            'building_adress': getattr(building, 'adress', None),
            'starttijd': r.starttijd,
            'eindtijd': r.eindtijd,
        })

    return render_template('mijn_reservaties.html', user=user, reservations=rows)


@main.route('/mijn_reservaties/cancel/<int:res_id>', methods=['POST'])
def cancel_reservation(res_id):
    """Allow the current user to cancel their reservation."""
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden om reservaties te beheren.")
        return redirect(url_for('login', next=url_for('main.mijn_reservaties')))

    try:
        reservation = Reservation.query.filter_by(res_id=res_id).first()
    except Exception:
        reservation = None

    if not reservation:
        flash("Reservatie niet gevonden.")
        return redirect(url_for('main.mijn_reservaties'))

    # Only allow the owner to cancel
    if reservation.user_id != user.user_id:
        flash("Je kunt alleen je eigen reservaties annuleren.")
        return redirect(url_for('main.mijn_reservaties'))

    try:
        db.session.delete(reservation)
        db.session.commit()
        flash("Reservatie geannuleerd.")
    except Exception as e:
        db.session.rollback()
        flash(f"Kon reservatie niet annuleren: {str(e)}")

    return redirect(url_for('main.mijn_reservaties'))


@main.route('/feedback/<int:res_id>', methods=['GET', 'POST'])
def feedback(res_id):
    """
    Feedback formulier voor een voltooide reservatie.
    """
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden om feedback te geven.")
        return redirect(url_for('login', next=url_for('main.feedback', res_id=res_id)))

    # Haal reservatie op
    try:
        reservation = Reservation.query.filter_by(res_id=res_id).first()
    except Exception:
        reservation = None

    if not reservation:
        flash("Reservatie niet gevonden.")
        return redirect(url_for('home'))

    # Controleer of de gebruiker de eigenaar is
    if reservation.user_id != user.user_id:
        flash("Je kunt alleen feedback geven voor je eigen reservaties.")
        return redirect(url_for('home'))

    # Controleer of de reservatie is voltooid
    if reservation.eindtijd > datetime.now():
        flash("Je kunt alleen feedback geven na voltooiing van de reservatie.")
        return redirect(url_for('home'))

    # Controleer of er al feedback is gegeven
    existing_feedback = Feedback.query.filter_by(reservation_id=res_id).first()

    if request.method == 'POST':
        try:
            netheid = int(request.form.get('netheid_score', 0))
            wifi = int(request.form.get('wifi_score', 0))
            ruimte = int(request.form.get('ruimte_score', 0))
            stilte = int(request.form.get('stilte_score', 0))
            algemeen = int(request.form.get('algemene_score', 0))
            opmerkingen = request.form.get('extra_opmerkingen', '').strip()

            # Validatie (1-5 sterren)
            if not all(1 <= score <= 5 for score in [netheid, wifi, ruimte, stilte, algemeen]):
                flash("Alle scores moeten tussen 1 en 5 liggen.")
                return redirect(url_for('main.feedback', res_id=res_id))

            # Converteer naar omgekeerde schaal: (6 - sterren)
            netheid = 6 - netheid
            wifi = 6 - wifi
            ruimte = 6 - ruimte
            stilte = 6 - stilte
            algemeen = 6 - algemeen

            if existing_feedback:
                # Update bestaande feedback
                existing_feedback.netheid_score = netheid
                existing_feedback.wifi_score = wifi
                existing_feedback.ruimte_score = ruimte
                existing_feedback.stilte_score = stilte
                existing_feedback.algemene_score = algemeen
                existing_feedback.extra_opmerkingen = opmerkingen
            else:
                # Nieuwe feedback
                feedback_obj = Feedback(
                    reservation_id=res_id,
                    netheid_score=netheid,
                    wifi_score=wifi,
                    ruimte_score=ruimte,
                    stilte_score=stilte,
                    algemene_score=algemeen,
                    extra_opmerkingen=opmerkingen
                )
                db.session.add(feedback_obj)

            db.session.commit()
            flash("Bedankt voor je feedback!")
            return redirect(url_for('home'))

        except Exception as e:
            db.session.rollback()
            flash(f"Fout bij opslaan feedback: {str(e)}")
            return redirect(url_for('main.feedback', res_id=res_id))

    return render_template('feedback.html', 
                         user=user, 
                         reservation=reservation,
                         existing_feedback=existing_feedback)


@main.route("/admin/feedback-analysis")
def feedback_analysis():
    """
    Admin dashboard voor complexe feedback analyse.
    
    Toont prioriteit-gesorteerde feedback met gelezen/ongelezen status.
    """
    # Haal ingelogde gebruiker op
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden.")
        return redirect(url_for('login'))
    
    try:
        from app.analytics import analyze_feedback_from_db
        from datetime import datetime
        
        # Voer de complexe analyse uit
        analysis = analyze_feedback_from_db(db.session)
        
        # Haal ongelezen count op
        unread_count = db.session.query(Feedback).filter_by(is_reviewed=False).count()
        
        # Voeg feedback records toe aan analysis voor gelezen/ongelezen status
        for item in analysis.get('detailed_items', []):
            feedback_record = db.session.query(Feedback).filter_by(feedback_id=item['feedback_id']).first()
            if feedback_record:
                item['is_reviewed'] = feedback_record.is_reviewed
                item['reviewed_at'] = feedback_record.reviewed_at
        
        for item in analysis.get('urgent_feedback', []):
            feedback_record = db.session.query(Feedback).filter_by(feedback_id=item['feedback_id']).first()
            if feedback_record:
                item['is_reviewed'] = feedback_record.is_reviewed
                item['reviewed_at'] = feedback_record.reviewed_at
        
        # Render mooie admin template met user info
        return render_template('admin_feedback.html', analysis=analysis, unread_count=unread_count, user=user)
        
    except Exception as e:
        flash(f"Fout bij uitvoeren van feedback analyse: {str(e)}", "danger")
        return redirect(url_for('main.reserve'))


@main.route("/admin/feedback/<int:feedback_id>/mark-reviewed", methods=["POST"])
def mark_feedback_reviewed(feedback_id):
    """Markeer feedback als gelezen door admin."""
    try:
        from datetime import datetime
        
        feedback = db.session.query(Feedback).filter_by(feedback_id=feedback_id).first()
        if feedback:
            feedback.is_reviewed = True
            feedback.reviewed_at = datetime.now()
            db.session.commit()
        
        # Redirect terug naar de specifieke feedback item met anchor
        return redirect(url_for('main.feedback_analysis') + f'#feedback-{feedback_id}')
    except Exception as e:
        flash(f"Fout bij markeren van feedback: {str(e)}", "danger")
        return redirect(url_for('main.feedback_analysis'))