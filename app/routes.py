from flask import Blueprint, render_template, request, redirect, url_for, session, flash
try:
    from app.models import db, User, Building, Desk, Reservation, Feedback
except Exception:
    from models import db, User, Building, Desk, Reservation, Feedback
from datetime import datetime
from sqlalchemy import and_, text
from app.auth import require_admin
from flask import jsonify


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


def get_current_organization_id():
    """Helper: haal organization_id op van huidige gebruiker"""
    user = get_current_user()
    if user and user.organization_id:
        return user.organization_id
    return 1  # Default naar Colruyt Group voor backwards compatibility


@main.route("/reserve", methods=["GET", "POST"])
def reserve():
    """
    Stap 1: Reservatiescherm
    - Toon gebouwen 
    - Kalender voor datumselectie
    - Begintijd en eindtijd input
    """
    user = get_current_user()
    org_id = get_current_organization_id()
    
    # Allow anonymous users to view the reservation form (GET). Only require
    # login for actions that create reservations (POST).
    buildings = []
    try:
        # Get unique buildings (distinct by adress) for current organization and sort alphabetically
        from sqlalchemy import distinct
        unique_addresses = db.session.query(distinct(Building.adress)).filter(
            Building.organization_id == org_id
        ).order_by(Building.adress).all()
        # For each unique address, get one building object
        buildings = [Building.query.filter_by(adress=addr[0], organization_id=org_id).first() for addr in unique_addresses]
    except Exception:
        buildings = []
    
    # Get all unique floors from buildings of current organization, sorted
    floors = []
    try:
        unique_floors = db.session.query(distinct(Building.floor)).filter(
            Building.floor.isnot(None),
            Building.organization_id == org_id
        ).order_by(Building.floor).all()
        floors = [f[0] for f in unique_floors]
    except Exception:
        floors = [0, 1, 2]  # fallback

    # Behoud ingevoerde waarden voor aanpassingen
    saved = {
        "building_id": request.args.get("building_id", ""),
        "floor": request.args.get("floor", ""),
        "date": request.args.get("date", ""),
        "start_time": request.args.get("start_time", ""),
        "end_time": request.args.get("end_time", "")
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

        # Check of datum niet in het verleden ligt
        try:
            from datetime import datetime
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            
            if selected_date < today:
                flash("Je kunt geen reservaties maken in het verleden.")
                return redirect(url_for("main.reserve"))
            
            # Check of starttijd niet in het verleden ligt voor vandaag
            if selected_date == today:
                selected_start = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
                if selected_start < datetime.now():
                    flash("Je kunt geen reservaties maken in het verleden.")
                    return redirect(url_for("main.reserve"))
        except ValueError:
            flash("Ongeldige datum of tijd formaat.")
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
                           saved=saved,
                           is_admin=user.is_admin() if user and hasattr(user, 'is_admin') else False)


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

    # Query: alle bureaus van huidige organisatie, maar filteren op ZOWEL adress ALS floor (optioneel)
    org_id = get_current_organization_id()
    q = Desk.query.filter(Desk.organization_id == org_id)
    
    # Filter op dienst: gebruiker ziet alleen bureaus van zijn eigen dienst
    # Admins zien alle bureaus (van hun organisatie)
    if user and not user.is_admin():
        # Haal dienst op van gebruiker
        user_dienst = user.dienst
        
        if user_dienst:
            # Filter alleen desks met deze dienst OF desks zonder dienst
            q = q.filter((Desk.dienst == user_dienst) | (Desk.dienst == None))
    
    # Filter op building: zoek building die matcht met ZOWEL adress ALS floor (alleen als ingevuld)
    # Check of de waarden niet leeg zijn
    has_building = building_adress and building_adress.strip()
    has_floor = floor_str and floor_str.strip()
    
    if has_building or has_floor:
        building_filters = [Building.organization_id == org_id]  # Always filter by organization
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
    # Als geen filters, toon alle bureaus (van de organisatie)

    candidate_desks = q.all()

    # Extra filters: monitor & chair (via query params on this page)
    monitor_filter = (request.args.get("monitor") or "").strip().lower()
    chair_filter = (request.args.get("chair") or "").strip().lower()

    # Haal alle unieke scherm en stoel types op uit de database (lowercase) voor deze organisatie
    try:
        all_screens_raw = db.session.query(Desk.screen).filter(
            Desk.screen.isnot(None),
            Desk.organization_id == org_id
        ).distinct().all()
        all_screens = sorted([s[0].lower() for s in all_screens_raw if s[0]])
    except Exception:
        all_screens = []
    
    try:
        all_chairs_raw = db.session.query(Desk.chair).filter(
            Desk.chair.isnot(None),
            Desk.organization_id == org_id
        ).distinct().all()
        all_chairs = sorted([c[0].lower() for c in all_chairs_raw if c[0]])
    except Exception:
        all_chairs = []

    # Filter op monitor
    if monitor_filter and monitor_filter in all_screens:
        candidate_desks = [d for d in candidate_desks if d.screen and monitor_filter in d.screen.lower()]

    # Filter op stoel
    if chair_filter and chair_filter in all_chairs:
        candidate_desks = [d for d in candidate_desks if d.chair and chair_filter in d.chair.lower()]

    # Filter: verwijder bureaus met overlappende reservaties (binnen dezelfde organisatie)
    available_desks = []
    for desk in candidate_desks:
        overlapping = Reservation.query.filter(
            Reservation.desk_id == desk.desk_id,
            Reservation.organization_id == org_id,
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
                Reservation.user_id == user.user_id,
                Reservation.organization_id == org_id
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
        "monitor": request.args.get("monitor", "") or "",
        "chair": request.args.get("chair", "") or "",
    }

    # Safe get for buildings list van deze organisatie
    try:
        all_buildings = Building.query.filter_by(organization_id=org_id).all()
    except Exception:
        all_buildings = []

    return render_template("available.html",
                           user=user,
                           desks=available_desks,
                           saved=saved,
                           all_screens=all_screens,
                           all_chairs=all_chairs,
                           buildings=all_buildings,
                           is_admin=user.is_admin() if user and hasattr(user, 'is_admin') else False)


@main.route("/reserve/desk/<int:desk_id>", methods=["GET", "POST"])
def desk_detail(desk_id):
    """
    Stap 3: Bureau detail & bevestiging
    - Toon alle info van bureau
    - Toon datum/tijd die je geselecteerd hebt
    - Bevestig reservatie of annuleer
    """
    user = get_current_user()
    org_id = get_current_organization_id()
    # Allow viewing desk details without login; require login for confirmation.

    desk = Desk.query.filter_by(desk_id=desk_id).first()
    if not desk:
        flash("Bureau niet gevonden.")
        return redirect(url_for("main.reserve"))
    
    # Check if desk belongs to current user's organization
    if org_id and desk.building.organization_id != org_id:
        flash("Bureau niet gevonden.")
        return redirect(url_for("main.reserve"))

    # Haal context op
    date_str = request.args.get("date")
    start_str = request.args.get("start_time")
    end_str = request.args.get("end_time")
    building_id_str = request.args.get("building_id", "")
    floor_str = request.args.get("floor", "")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "confirm":
            # Require logged in user for creating a reservation
            if not user:
                flash("Gelieve eerst aan te melden om een reservatie te maken.")
                return redirect(url_for("login"))

            # Controleer of de gebruiker toegang heeft tot dit bureau
            # (dienst validatie voor medewerkers)
            if not user.is_admin():
                user_dienst = user.dienst
                if user_dienst and desk.dienst and desk.dienst != user_dienst:
                    flash("Je kunt alleen bureaus van je eigen dienst reserveren.")
                    return redirect(url_for("main.available",
                                            date=date_str,
                                            start_time=start_str,
                                            end_time=end_str))

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
                    Reservation.organization_id == org_id,
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
                    organization_id=org_id,
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
            # Ga terug naar reserve pagina met alle oorspronkelijk ingevulde waarden
            return redirect(url_for("main.reserve",
                                   building_id=building_id_str,
                                   floor=floor_str,
                                   date=date_str,
                                   start_time=start_str,
                                   end_time=end_str))

    return render_template("desk_detail.html",
                           user=user,
                           desk=desk,
                           date=date_str,
                           start_time=start_str,
                           end_time=end_str,
                           is_admin=user.is_admin() if user and hasattr(user, 'is_admin') else False)


@main.route('/mijn_reservaties')
def mijn_reservaties():
    """
    Toon alleen toekomstige reservaties van de ingelogde gebruiker.
    """
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden om je reservaties te zien.")
        return redirect(url_for('login', next=url_for('main.mijn_reservaties')))
    
    org_id = get_current_organization_id()

    try:
        from datetime import datetime
        now = datetime.now()
        # Alleen toekomstige reservaties van deze organisatie
        reservations = Reservation.query.filter(
            Reservation.user_id == user.user_id,
            Reservation.organization_id == org_id,
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
            'floor': getattr(building, 'floor', None),
            'starttijd': r.starttijd,
            'eindtijd': r.eindtijd,
            'modified_by_admin': r.modified_by_admin if hasattr(r, 'modified_by_admin') else False,
        })

    return render_template('mijn_reservaties.html', 
                           user=user, 
                           reservations=rows,
                           is_admin=user.is_admin() if user and hasattr(user, 'is_admin') else False)


@main.route('/mijn_reservaties/cancel/<int:res_id>', methods=['POST'])
def cancel_reservation(res_id):
    """Allow the current user to cancel their reservation."""
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden om reservaties te beheren.")
        return redirect(url_for('login', next=url_for('main.mijn_reservaties')))
    
    org_id = get_current_organization_id()

    try:
        reservation = Reservation.query.filter_by(
            res_id=res_id,
            organization_id=org_id
        ).first()
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


@main.route('/mijn_reservaties/edit/<int:res_id>', methods=['GET', 'POST'])
def edit_reservation(res_id):
    """Sta gebruiker toe om hun eigen reservatie te wijzigen."""
    user = get_current_user()
    if not user:
        flash("Gelieve eerst aan te melden om reservaties te beheren.")
        return redirect(url_for('login', next=url_for('main.mijn_reservaties')))
    
    org_id = get_current_organization_id()

    try:
        reservation = Reservation.query.filter_by(
            res_id=res_id,
            organization_id=org_id
        ).first()
    except Exception:
        reservation = None

    if not reservation:
        flash("Reservatie niet gevonden.")
        return redirect(url_for('main.mijn_reservaties'))

    # Only allow the owner to edit
    if reservation.user_id != user.user_id:
        flash("Je kunt alleen je eigen reservaties wijzigen.")
        return redirect(url_for('main.mijn_reservaties'))

    if request.method == 'POST':
        from datetime import datetime, timedelta
        
        # Haal nieuwe waarden op
        new_date = request.form.get('date')
        new_start_time = request.form.get('start_time')
        new_end_time = request.form.get('end_time')
        new_desk_id = request.form.get('desk_id')

        try:
            # Parse nieuwe datum en tijden
            date_obj = datetime.strptime(new_date, '%Y-%m-%d').date()
            start_time_obj = datetime.strptime(new_start_time, '%H:%M').time()
            end_time_obj = datetime.strptime(new_end_time, '%H:%M').time()
            
            new_starttijd = datetime.combine(date_obj, start_time_obj)
            new_eindtijd = datetime.combine(date_obj, end_time_obj)
            
            # Validaties
            now = datetime.now()
            if new_starttijd < now:
                flash("Je kunt geen reservatie in het verleden maken.")
                return redirect(url_for('main.edit_reservation', res_id=res_id))
            
            if new_eindtijd <= new_starttijd:
                flash("Eindtijd moet na begintijd liggen.")
                return redirect(url_for('main.edit_reservation', res_id=res_id))
            
            # Controleer of de gebruiker toegang heeft tot het geselecteerde bureau
            # (dienst validatie voor medewerkers)
            if not user.is_admin():
                selected_desk = Desk.query.filter_by(
                    desk_id=int(new_desk_id),
                    organization_id=org_id
                ).first()
                
                if not selected_desk:
                    flash("Geselecteerd bureau niet gevonden.")
                    return redirect(url_for('main.edit_reservation', res_id=res_id))
                
                user_dienst = user.dienst
                if user_dienst and selected_desk.dienst and selected_desk.dienst != user_dienst:
                    flash("Je kunt alleen bureaus van je eigen dienst reserveren.")
                    return redirect(url_for('main.edit_reservation', res_id=res_id))
            
            # Check beschikbaarheid van het bureau op het nieuwe tijdstip
            # Zoek overlappende reservaties (exclusief huidige reservatie)
            overlapping = Reservation.query.filter(
                Reservation.desk_id == int(new_desk_id),
                Reservation.organization_id == org_id,
                Reservation.res_id != res_id,  # Exclusief huidige reservatie
                Reservation.starttijd < new_eindtijd,
                Reservation.eindtijd > new_starttijd
            ).first()
            
            if overlapping:
                flash("Dit bureau is al gereserveerd op het gekozen tijdstip.")
                return redirect(url_for('main.edit_reservation', res_id=res_id))
            
            # Update reservatie
            reservation.desk_id = int(new_desk_id)
            reservation.starttijd = new_starttijd
            reservation.eindtijd = new_eindtijd
            
            db.session.commit()
            flash("Reservatie succesvol gewijzigd.")
            return redirect(url_for('main.mijn_reservaties'))
            
        except ValueError as e:
            flash(f"Ongeldige datum of tijd: {str(e)}")
            return redirect(url_for('main.edit_reservation', res_id=res_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Kon reservatie niet wijzigen: {str(e)}")
            return redirect(url_for('main.edit_reservation', res_id=res_id))
    
    # GET request - toon formulier
    try:
        # Haal gebouwen en bureaus op voor deze organisatie
        buildings = Building.query.filter_by(organization_id=org_id).order_by(Building.adress, Building.floor).all()
        
        # Filter bureaus op dienst: medewerkers zien alleen bureaus van hun eigen dienst
        # Admins zien alle bureaus (van hun organisatie)
        desk_query = Desk.query.filter_by(organization_id=org_id)
        
        if user and not user.is_admin():
            # Haal dienst op van gebruiker
            user_dienst = user.dienst
            
            if user_dienst:
                # Filter alleen desks met deze dienst OF desks zonder dienst
                desk_query = desk_query.filter((Desk.dienst == user_dienst) | (Desk.dienst == None))
        
        desks = desk_query.order_by(Desk.desk_number).all()
        
        return render_template('edit_reservation.html',
                             user=user,
                             reservation=reservation,
                             buildings=buildings,
                             desks=desks,
                             is_admin=user.is_admin() if hasattr(user, 'is_admin') else False)
    except Exception as e:
        flash(f"Fout bij laden van formulier: {str(e)}")
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
    
    org_id = get_current_organization_id()

    # Haal reservatie op
    try:
        reservation = Reservation.query.filter_by(
            res_id=res_id,
            organization_id=org_id
        ).first()
    except Exception:
        reservation = None

    if not reservation:
        flash("Reservatie niet gevonden.")
        return redirect(url_for('home'))

    # Controleer of de gebruiker de eigenaar is
    if reservation.user_id != user.user_id:
        flash("Je kunt alleen feedback geven voor je eigen reservaties.")
        return redirect(url_for('home'))

    # Controleer als reservatie voltooid
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
                    organization_id=org_id,
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
                         existing_feedback=existing_feedback,
                         is_admin=user.is_admin() if user and hasattr(user, 'is_admin') else False)


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
    
    org_id = get_current_organization_id()
    
    try:
        from app.analytics import analyze_feedback_from_db
        from datetime import datetime
        
        # Voer de complexe analyse uit voor deze organisatie
        analysis = analyze_feedback_from_db(db.session, organization_id=org_id)
        
        # Haal ongelezen count op voor deze organisatie
        unread_count = db.session.query(Feedback).filter_by(
            is_reviewed=False,
            organization_id=org_id
        ).count()
        
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
        
        # Check if user is admin
        is_admin = user.is_admin() if user and hasattr(user, 'is_admin') else False
        
        # Render mooie admin template met user info
        return render_template('admin_feedback.html', analysis=analysis, unread_count=unread_count, user=user, is_admin=is_admin)
        
    except Exception as e:
        flash(f"Fout bij uitvoeren van feedback analyse: {str(e)}", "danger")
        return redirect(url_for('main.reserve'))


@main.route("/admin/feedback/<int:feedback_id>/mark-reviewed", methods=["POST"])
def mark_feedback_reviewed(feedback_id):
    """Markeer feedback als gelezen door admin."""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        from datetime import datetime
        
        feedback = db.session.query(Feedback).filter_by(
            feedback_id=feedback_id,
            organization_id=org_id
        ).first()
        if feedback:
            feedback.is_reviewed = True
            feedback.reviewed_at = datetime.now()
            db.session.commit()
        
        # Redirect terug naar de specifieke feedback item met anchor
        return redirect(url_for('main.feedback_analysis') + f'#feedback-{feedback_id}')
    except Exception as e:
        flash(f"Fout bij markeren van feedback: {str(e)}", "danger")
        return redirect(url_for('main.feedback_analysis'))


@main.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    """Admin dashboard - bureaus beheren en koppelen aan diensten"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    # Check voor edit mode en add new parameters
    edit_desk_id = request.args.get('edit', type=int)
    add_new = request.args.get('add_new', type=int)
    
    try:
        # Haal alle desks op met building info voor deze organisatie, gesorteerd op bureau nummer
        desks = Desk.query.join(Building).filter(
            Building.organization_id == org_id
        ).order_by(Desk.desk_number).all()
        
        # Haal alle unieke gebouwen op voor deze organisatie
        buildings_query = db.session.query(Building.adress, Building.building_id).filter(
            Building.organization_id == org_id
        ).distinct(Building.adress).order_by(Building.adress).all()
        buildings_list = [{'id': b.building_id, 'naam': b.adress} for b in buildings_query]
        
        # Haal alle unieke scherm types op uit de database voor deze organisatie
        screens_query = db.session.query(Desk.screen).join(Building).filter(
            Building.organization_id == org_id,
            Desk.screen.isnot(None)
        ).distinct().all()
        screens_raw = [s[0] for s in screens_query if s[0]]
        # Custom volgorde: single, dual, triple, dan de rest alfabetisch
        screen_order = ['single', 'dual', 'triple']
        screens_ordered = []
        for screen in screen_order:
            # Match op basis van 'bevat' in plaats van exacte match
            matching = [s for s in screens_raw if screen in s.lower()]
            if matching:
                screens_ordered.append(matching[0])
                screens_raw = [s for s in screens_raw if screen not in s.lower()]
        # Voeg overige toe (alfabetisch, lowercase)
        screens_ordered.extend(sorted(screens_raw))
        screens_list = screens_ordered
        
        # Haal alle unieke stoel types op uit de database voor deze organisatie
        chairs_query = db.session.query(Desk.chair).join(Building).filter(
            Building.organization_id == org_id,
            Desk.chair.isnot(None)
        ).distinct().all()
        chairs_raw = [c[0] for c in chairs_query if c[0]]
        # Custom volgorde: standard, standing, ergonomic, dan de rest alfabetisch
        chair_order = ['standard', 'standing', 'ergonomic']
        chairs_ordered = []
        for chair in chair_order:
            matching = [c for c in chairs_raw if c.lower() == chair]
            if matching:
                chairs_ordered.append(matching[0])
                chairs_raw = [c for c in chairs_raw if c.lower() != chair]
        # Voeg overige toe (alfabetisch, lowercase)
        chairs_ordered.extend(sorted(chairs_raw))
        chairs_list = chairs_ordered
        
        # Voeg extra info toe
        desk_list = []
        edit_desk_number = None
        
        for desk in desks:
            desk_info = {
                'desk_id': desk.desk_id,
                'desk_number': desk.desk_number,
                'building_adress': desk.building.adress if desk.building else 'N/A',
                'building_id': desk.building_id,
                'building_floor': desk.building.floor if desk.building else None,
                'dienst': desk.dienst,
                'dienst_naam': desk.get_dienst(),
                'screen': desk.screen or 'Niet gespecificeerd',
                'chair': desk.chair or 'Niet gespecificeerd'
            }
            desk_list.append(desk_info)
            
            # Bewaar desk number voor edit mode banner
            if edit_desk_id and desk.desk_id == edit_desk_id:
                edit_desk_number = desk.desk_number
        
        # Haal alle unieke diensten op uit de user tabel van deze organisatie
        diensten_query = db.session.query(User.dienst).filter(
            User.organization_id == org_id,
            User.dienst.isnot(None)
        ).distinct().all()
        diensten_set = set([d[0] for d in diensten_query if d[0]])
        
        # Voeg ook diensten toe die al gekoppeld zijn aan bureaus van deze organisatie
        bestaande_diensten = db.session.query(Desk.dienst).join(Building).filter(
            Building.organization_id == org_id,
            Desk.dienst.isnot(None)
        ).distinct().all()
        for dienst in bestaande_diensten:
            if dienst[0]:
                diensten_set.add(dienst[0])
        
        # Sorteer alfabetisch
        diensten = [{'id': None, 'naam': d} for d in sorted(diensten_set)]
        
    except Exception as e:
        flash(f"Fout bij ophalen bureaus: {str(e)}", "danger")
        desk_list = []
        diensten = []
        buildings_list = []
        screens_list = []
        chairs_list = []
        edit_desk_number = None
    
    return render_template('admin_bureaubeheer.html', 
                         user=user, 
                         desks=desk_list,
                         diensten=diensten,
                         buildings=buildings_list,
                         screens=screens_list,
                         chairs=chairs_list,
                         edit_mode=edit_desk_id is not None,
                         edit_desk_id=edit_desk_id,
                         edit_desk_number=edit_desk_number,
                         add_new=add_new,
                         is_admin=True)


@main.route('/admin/desk/update/<int:desk_id>', methods=['POST'])
@require_admin
def admin_update_desk(desk_id):
    """Admin kan desk details van hun organisatie wijzigen (bureau, gebouw, dienst, scherm, stoel)"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        # Check dat desk behoort tot de huidige organisatie
        desk = Desk.query.join(Building).filter(
            Desk.desk_id == desk_id,
            Building.organization_id == org_id
        ).first()
        if not desk:
            flash("Bureau niet gevonden.", "danger")
            return redirect(url_for('main.admin_dashboard'))
        
        # Haal waardes op uit form
        new_desk_number = request.form.get('desk_number')
        new_building_id = request.form.get('building_id')
        new_building_other = request.form.get('building_other', '').strip()
        new_dienst_id = request.form.get('dienst_id')
        new_dienst_other = request.form.get('dienst_other', '').strip()
        new_screen = request.form.get('screen')
        new_screen_other = request.form.get('screen_other', '').strip()
        new_chair = request.form.get('chair')
        new_chair_other = request.form.get('chair_other', '').strip()
        
        # Update bureau nummer
        if new_desk_number:
            desk.desk_number = int(new_desk_number)
        
        # Update gebouw - check eerst of "Andere" is geselecteerd
        if new_building_id == 'other' and new_building_other:
            # Haal floor waarde op uit form
            floor_value = int(request.form.get('floor', 1))
            # Maak nieuw gebouw aan voor deze organisatie met opgegeven floor
            new_building = Building(
                adress=new_building_other, 
                floor=floor_value,
                organization_id=org_id
            )
            db.session.add(new_building)
            db.session.flush()  # Om building_id te krijgen
            desk.building_id = new_building.building_id
            flash(f"Nieuw gebouw '{new_building_other}' (verdieping {floor_value}) aangemaakt.", "success")
        elif new_building_id and new_building_id != 'other':
            # Check of verdieping is gewijzigd
            floor_value = request.form.get('floor')
            selected_building = Building.query.filter_by(
                building_id=int(new_building_id),
                organization_id=org_id
            ).first()
            
            if floor_value and selected_building and int(floor_value) != selected_building.floor:
                # Verdieping is gewijzigd! Zoek of maak een building met deze gebouw+verdieping combinatie
                target_building = Building.query.filter_by(
                    adress=selected_building.adress,
                    floor=int(floor_value),
                    organization_id=org_id
                ).first()
                
                if not target_building:
                    # Maak nieuw building record aan voor deze gebouw+verdieping combinatie
                    target_building = Building(
                        adress=selected_building.adress, 
                        floor=int(floor_value),
                        organization_id=org_id
                    )
                    db.session.add(target_building)
                    db.session.flush()
                    flash(f"Nieuwe locatie '{selected_building.adress}' verdieping {floor_value} aangemaakt.", "success")
                
                desk.building_id = target_building.building_id
            else:
                # Geen verdieping wijziging, gewoon building_id updaten
                desk.building_id = int(new_building_id)
        
        # Update dienst - sla direct de dienst naam op
        if new_dienst_id == 'other' and new_dienst_other:
            # Sla nieuwe dienst naam op
            desk.dienst = new_dienst_other
            flash(f"Dienst '{new_dienst_other}' gekoppeld.", "success")
        elif new_dienst_id and new_dienst_id != 'None' and new_dienst_id != 'other':
            # Dit is een bestaande dienst naam
            desk.dienst = new_dienst_id
        else:
            desk.dienst = None
        
        # Update scherm - check eerst of "Andere" is geselecteerd
        if new_screen == 'other' and new_screen_other:
            desk.screen = new_screen_other.lower()
        elif new_screen and new_screen != 'other':
            desk.screen = new_screen
        
        # Update stoel - check eerst of "Andere" is geselecteerd  
        if new_chair == 'other' and new_chair_other:
            desk.chair = new_chair_other.lower()
        elif new_chair and new_chair != 'other':
            desk.chair = new_chair
        
        db.session.commit()
        flash("Wijzigingen zijn succesvol opgeslagen", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Fout bij wijzigen bureau: {str(e)}", "danger")
    
    # Redirect terug naar normale view (zonder edit mode)
    return redirect(url_for('main.admin_dashboard', _anchor=f'desk-{desk_id}'))


@main.route('/admin/desk/create', methods=['POST'])
@require_admin
def admin_create_desk():
    """Admin kan nieuw bureau toevoegen voor hun organisatie"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        # Haal waardes op uit form
        new_desk_number = request.form.get('desk_number')
        new_building_id = request.form.get('building_id')
        new_building_other = request.form.get('building_other', '').strip()
        new_dienst_id = request.form.get('dienst_id')
        new_dienst_other = request.form.get('dienst_other', '').strip()
        new_screen = request.form.get('screen')
        new_screen_other = request.form.get('screen_other', '').strip()
        new_chair = request.form.get('chair')
        new_chair_other = request.form.get('chair_other', '').strip()
        
        # Valideer bureau nummer
        if not new_desk_number or int(new_desk_number) < 1:
            flash("Bureau nummer moet minimaal 1 zijn.", "danger")
            return redirect(url_for('main.admin_dashboard', add_new=1))
        
        desk_number = int(new_desk_number)
        
        # Check of bureau nummer al bestaat in deze organisatie
        existing = Desk.query.join(Building).filter(
            Desk.desk_number == desk_number,
            Building.organization_id == org_id
        ).first()
        if existing:
            flash(f"Bureau {desk_number} bestaat al in uw organisatie.", "danger")
            return redirect(url_for('main.admin_dashboard', add_new=1))
        
        # Handle gebouw
        if new_building_id == 'other' and new_building_other:
            # Haal floor waarde op uit form
            floor_value = int(request.form.get('floor', 1))
            # Maak nieuw gebouw aan voor deze organisatie met opgegeven floor
            new_building = Building(
                adress=new_building_other, 
                floor=floor_value,
                organization_id=org_id
            )
            db.session.add(new_building)
            db.session.flush()
            building_id = new_building.building_id
            flash(f"Nieuw gebouw '{new_building_other}' (verdieping {floor_value}) aangemaakt.", "success")
        elif new_building_id and new_building_id != 'other':
            # Validate dat building behoort tot organisatie
            building = Building.query.filter_by(
                building_id=int(new_building_id),
                organization_id=org_id
            ).first()
            if not building:
                flash("Ongeldig gebouw geselecteerd.", "danger")
                return redirect(url_for('main.admin_dashboard', add_new=1))
            building_id = int(new_building_id)
        else:
            flash("Selecteer een gebouw.", "danger")
            return redirect(url_for('main.admin_dashboard', add_new=1))
        
        # Handle dienst - sla direct de dienst naam op
        if new_dienst_id == 'other' and new_dienst_other:
            # Sla nieuwe dienst naam op
            dienst = new_dienst_other
            flash(f"Dienst '{new_dienst_other}' gekoppeld.", "success")
        elif new_dienst_id and new_dienst_id != 'None' and new_dienst_id != 'other':
            # Dit is een bestaande dienst naam
            dienst = new_dienst_id
        else:
            dienst = None
        
        # Handle scherm
        if new_screen == 'other' and new_screen_other:
            screen = new_screen_other.lower()
        elif new_screen and new_screen != 'other':
            screen = new_screen
        else:
            screen = None
        
        # Handle stoel
        if new_chair == 'other' and new_chair_other:
            chair = new_chair_other.lower()
        elif new_chair and new_chair != 'other':
            chair = new_chair
        else:
            chair = None
        
        # Maak nieuw bureau aan
        new_desk = Desk(
            desk_number=desk_number,
            building_id=building_id,
            organization_id=org_id,
            dienst=dienst,
            screen=screen,
            chair=chair
        )
        
        db.session.add(new_desk)
        db.session.commit()
        flash(f"Bureau {desk_number} succesvol toegevoegd.", "success")
        
    except ValueError:
        flash("Ongeldig bureau nummer ingevoerd.", "danger")
        return redirect(url_for('main.admin_dashboard', add_new=1))
    except Exception as e:
        db.session.rollback()
        flash(f"Fout bij toevoegen bureau: {str(e)}", "danger")
        return redirect(url_for('main.admin_dashboard', add_new=1))
    
    return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/desk/delete/<int:desk_id>', methods=['POST'])
@require_admin
def admin_delete_desk(desk_id):
    """Admin kan desk van hun organisatie verwijderen"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        # Check dat desk behoort tot de huidige organisatie
        desk = Desk.query.join(Building).filter(
            Desk.desk_id == desk_id,
            Building.organization_id == org_id
        ).first()
        if not desk:
            flash("Bureau niet gevonden.", "danger")
            return redirect(url_for('main.admin_dashboard'))
        
        desk_number = desk.desk_number
        
        # Vind het volgende bureau (hogere desk_number) binnen deze organisatie om naartoe te scrollen
        next_desk = Desk.query.join(Building).filter(
            Desk.desk_number > desk_number,
            Building.organization_id == org_id
        ).order_by(Desk.desk_number).first()
        
        # Als er geen volgend bureau is, probeer het vorige binnen organisatie
        if not next_desk:
            next_desk = Desk.query.join(Building).filter(
                Desk.desk_number < desk_number,
                Building.organization_id == org_id
            ).order_by(Desk.desk_number.desc()).first()
        
        db.session.delete(desk)
        db.session.commit()
        flash(f"Bureau {desk_number} succesvol verwijderd.", "success")
        
        # Redirect naar het volgende/vorige bureau als die bestaat
        if next_desk:
            return redirect(url_for('main.admin_dashboard', _anchor=f'desk-{next_desk.desk_id}'))
        else:
            return redirect(url_for('main.admin_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Fout bij verwijderen bureau: {str(e)}", "danger")
        return redirect(url_for('main.admin_dashboard', _anchor=f'desk-{desk_id}'))


@main.route('/admin/reservation/delete/<int:res_id>', methods=['POST'])
@require_admin
def admin_delete_reservation(res_id):
    """Admin kan elke reservatie van hun organisatie verwijderen"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        reservation = Reservation.query.filter_by(
            res_id=res_id,
            organization_id=org_id
        ).first()
        if not reservation:
            flash("Reservatie niet gevonden.")
            return redirect(url_for('main.admin_reservations_overview'))
        
        # Haal user info op voor melding
        res_user = reservation.user
        user_name = f"{res_user.user_name} {res_user.user_last_name}"
        
        db.session.delete(reservation)
        db.session.commit()
        flash(f"Reservatie van {user_name} succesvol verwijderd.")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Fout bij verwijderen: {str(e)}")
    
    return redirect(url_for('main.admin_reservations_overview'))


@main.route('/admin/reservations')
@require_admin
def admin_reservations_overview():
    """Admin overzicht van alle toekomstige reservaties met verdachte reservaties gemarkeerd"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        # Haal alle toekomstige reservaties op van deze organisatie met user, desk en building info
        now = datetime.now()
        reservations_raw = db.session.query(
            Reservation.res_id,
            Reservation.user_id,
            Reservation.starttijd,
            Reservation.eindtijd,
            User.user_name,
            User.user_last_name,
            User.user_email,
            Desk.desk_number,
            Building.adress.label('building_adress'),
            Building.floor.label('building_floor')
        ).join(User, Reservation.user_id == User.user_id
        ).join(Desk, Reservation.desk_id == Desk.desk_id
        ).join(Building, Desk.building_id == Building.building_id
        ).filter(
            Reservation.starttijd >= now,
            Reservation.organization_id == org_id
        ).order_by(Reservation.starttijd).all()
        
        # Identificeer verdachte reservaties
        reservations = []
        suspicious_count = 0
        
        for res in reservations_raw:
            is_suspicious = False
            suspicious_reasons = []
            
            # Check 1: Start voor 6:00
            if res.starttijd.time().hour < 6:
                is_suspicious = True
                suspicious_reasons.append("Start voor 6:00 uur")
            
            # Check 2: Eind na 22:00
            if res.eindtijd.time().hour >= 22 or (res.eindtijd.time().hour == 21 and res.eindtijd.time().minute > 0):
                is_suspicious = True
                suspicious_reasons.append("Loopt tot na 22:00 uur")
            
            # Check 3: Meerdere reservaties op hetzelfde moment binnen organisatie
            overlapping = db.session.query(Reservation).filter(
                Reservation.user_id == res.user_id,
                Reservation.res_id != res.res_id,
                Reservation.organization_id == org_id,
                Reservation.starttijd < res.eindtijd,
                res.starttijd < Reservation.eindtijd
            ).first()
            
            if overlapping:
                is_suspicious = True
                suspicious_reasons.append("Meerdere reservaties tegelijk")
            
            if is_suspicious:
                suspicious_count += 1
            
            # Maak een dictionary van de reservatie data
            reservations.append({
                'res_id': res.res_id,
                'user_id': res.user_id,
                'starttijd': res.starttijd,
                'eindtijd': res.eindtijd,
                'user_name': res.user_name,
                'user_last_name': res.user_last_name,
                'user_email': res.user_email,
                'desk_number': res.desk_number,
                'building_adress': res.building_adress,
                'building_floor': res.building_floor,
                'is_suspicious': is_suspicious,
                'suspicious_reasons': suspicious_reasons
            })
        
    except Exception as e:
        flash(f"Fout bij ophalen reservaties: {str(e)}")
        reservations = []
        suspicious_count = 0
    
    return render_template('admin_reservations_overview.html',
                         user=user,
                         is_admin=True,
                         reservations=reservations,
                         suspicious_count=suspicious_count)


@main.route('/admin/reservation/edit/<int:res_id>', methods=['GET', 'POST'])
@require_admin
def admin_edit_reservation(res_id):
    """Admin kan reservatie van hun organisatie wijzigen"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        reservation = Reservation.query.filter_by(
            res_id=res_id,
            organization_id=org_id
        ).first()
    except Exception:
        reservation = None
    
    if not reservation:
        flash("Reservatie niet gevonden.")
        return redirect(url_for('main.admin_reservations_overview'))
    
    if request.method == 'POST':
        try:
            # Haal nieuwe waarden op
            date_str = request.form.get('date')
            start_str = request.form.get('start_time')
            end_str = request.form.get('end_time')
            desk_id = int(request.form.get('desk_id'))
            
            chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time_obj = datetime.strptime(start_str, "%H:%M").time()
            end_time_obj = datetime.strptime(end_str, "%H:%M").time()
            
            start_datetime = datetime.combine(chosen_date, start_time_obj)
            end_datetime = datetime.combine(chosen_date, end_time_obj)
            
            if start_time_obj >= end_time_obj:
                flash("Eindtijd moet later zijn dan starttijd.")
                return redirect(url_for('main.admin_edit_reservation', res_id=res_id))
            
            # Check overlap met andere reservaties binnen organisatie (behalve deze zelf)
            overlapping = Reservation.query.filter(
                Reservation.desk_id == desk_id,
                Reservation.res_id != res_id,
                Reservation.organization_id == org_id,
                Reservation.starttijd < end_datetime,
                start_datetime < Reservation.eindtijd
            ).first()
            
            if overlapping:
                flash("Dit tijdslot is al geboekt voor dit bureau!")
                return redirect(url_for('main.admin_edit_reservation', res_id=res_id))
            
            # Update reservatie
            reservation.desk_id = desk_id
            reservation.starttijd = start_datetime
            reservation.eindtijd = end_datetime
            reservation.modified_by_admin = True  # Markeer als gewijzigd door admin
            
            db.session.commit()
            
            flash("Reservatie succesvol gewijzigd.")
            return redirect(url_for('main.admin_reservations_overview'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Fout bij wijzigen: {str(e)}")
            return redirect(url_for('main.admin_edit_reservation', res_id=res_id))
    
    # GET: toon formulier
    buildings = Building.query.filter_by(organization_id=org_id).all()
    
    return render_template('admin_edit_reservation.html', 
                         user=user,
                         is_admin=True,
                         reservation=reservation,
                         buildings=buildings)


@main.route('/admin/reservation/create', methods=['GET', 'POST'])
@require_admin
def admin_create_reservation():
    """Admin kan reservatie aanmaken voor een gebruiker van hun organisatie"""
    user = get_current_user()
    org_id = get_current_organization_id()
    
    # Haal alle users en buildings van deze organisatie op
    try:
        all_users = User.query.filter_by(organization_id=org_id).order_by(User.user_name).all()
        all_buildings = Building.query.filter_by(organization_id=org_id).all()
    except Exception:
        all_users = []
        all_buildings = []
    
    if request.method == 'POST':
        try:
            selected_user_id = request.form.get('user_id')
            building_id = request.form.get('building_id')
            desk_id = request.form.get('desk_id')
            date_str = request.form.get('date')
            start_str = request.form.get('start_time')
            end_str = request.form.get('end_time')
            
            # Validatie
            if not all([selected_user_id, desk_id, date_str, start_str, end_str]):
                flash("Vul alle velden in.")
                return redirect(url_for('main.admin_create_reservation'))
            
            chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time_obj = datetime.strptime(start_str, "%H:%M").time()
            end_time_obj = datetime.strptime(end_str, "%H:%M").time()
            
            start_datetime = datetime.combine(chosen_date, start_time_obj)
            end_datetime = datetime.combine(chosen_date, end_time_obj)
            
            if start_time_obj >= end_time_obj:
                flash("Eindtijd moet later zijn dan starttijd.")
                return redirect(url_for('main.admin_create_reservation'))
            
            # Check overlap binnen organisatie
            overlapping = Reservation.query.filter(
                Reservation.desk_id == desk_id,
                Reservation.organization_id == org_id,
                Reservation.starttijd < end_datetime,
                start_datetime < Reservation.eindtijd
            ).first()
            
            if overlapping:
                flash("Dit bureau is al geboekt in dit tijdslot!")
                return redirect(url_for('main.admin_create_reservation'))
            
            # Maak reservatie
            new_reservation = Reservation(
                user_id=selected_user_id,
                desk_id=desk_id,
                organization_id=org_id,
                starttijd=start_datetime,
                eindtijd=end_datetime
            )
            db.session.add(new_reservation)
            db.session.commit()
            
            flash("Reservatie succesvol aangemaakt!")
            return redirect(url_for('main.admin_reservations_overview'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Fout bij aanmaken: {str(e)}")
            return redirect(url_for('main.admin_create_reservation'))
    
    # GET: toon formulier
    return render_template('admin_create_reservation.html', 
                         user=user,
                         is_admin=True,
                         all_users=all_users,
                         buildings=all_buildings)


@main.route('/api/desks')
def api_desks():
    """API endpoint om bureaus op te halen per gebouw"""
    building_id = request.args.get('building_id')
    user = get_current_user()
    org_id = get_current_organization_id()
    
    if not building_id or not user:
        return jsonify([])
    
    try:
        # Start met basis query: desk moet in het gevraagde gebouw zijn
        desk_query = Desk.query.filter_by(building_id=building_id)
        
        # Organisatie filtering: controleer of het building tot de juiste organisatie behoort
        # We doen dit via een subquery voor betere performance
        valid_building = Building.query.filter_by(
            building_id=building_id, 
            organization_id=org_id
        ).first()
        
        if not valid_building:
            # Building bestaat niet of behoort niet tot de organisatie
            return jsonify([])
        
        # Filter op dienst: medewerkers zien alleen bureaus van hun eigen dienst
        # Admins zien alle bureaus
        if not user.is_admin():
            user_dienst = user.dienst
            if user_dienst:
                # Filter alleen desks met deze dienst OF desks zonder dienst
                desk_query = desk_query.filter((Desk.dienst == user_dienst) | (Desk.dienst == None))
        
        desks = desk_query.all()
        
        return jsonify([{
            'desk_id': d.desk_id,
            'desk_number': d.desk_number
        } for d in desks])
    except Exception as e:
        # Log the error for debugging but don't expose it to the client
        print(f"API error in /api/desks: {e}")
        return jsonify([])

# Personeelsbeheer: overzicht, toevoegen, wijzigen, verwijderen
@main.route('/admin/personeelsbeheer')
@require_admin
def admin_personeelsbeheer():
    user = get_current_user()
    org_id = get_current_organization_id()
    
    # Haal alle medewerkers op van deze organisatie, gesorteerd op achternaam
    medewerkers = User.query.filter_by(organization_id=org_id).order_by(User.user_last_name.asc()).all()
    
    # Haal alle unieke diensten op van deze organisatie
    diensten_query = db.session.query(User.dienst).filter(
        User.organization_id == org_id,
        User.dienst.isnot(None)
    ).distinct().all()
    diensten = sorted([d[0] for d in diensten_query if d[0]])
    
    return render_template('admin_personeelsbeheer.html', user=user, medewerkers=medewerkers, diensten=diensten, is_admin=True)

# Wijzig dienst van medewerker
@main.route('/admin/medewerker/update/<int:user_id>', methods=['POST'])
@require_admin
def admin_update_medewerker(user_id):
    current_user = get_current_user()
    org_id = get_current_organization_id()
    
    user = User.query.filter_by(
        user_id=user_id,
        organization_id=org_id
    ).first()
    if not user:
        flash('Medewerker niet gevonden.', 'danger')
        return redirect(url_for('main.admin_personeelsbeheer'))
    nieuwe_dienst = request.form.get('dienst')
    nieuwe_dienst_other = request.form.get('dienst_other', '').strip()
    if nieuwe_dienst == 'other' and nieuwe_dienst_other:
        user.dienst = nieuwe_dienst_other
    elif nieuwe_dienst:
        user.dienst = nieuwe_dienst
    db.session.commit()
    flash('Dienst succesvol gewijzigd.', 'success')
    return redirect(url_for('main.admin_personeelsbeheer', _anchor=f'user-{user_id}'))

# Verwijder medewerker
@main.route('/admin/medewerker/delete/<int:user_id>', methods=['POST'])
@require_admin
def admin_delete_medewerker(user_id):
    current_user = get_current_user()
    org_id = get_current_organization_id()
    
    user = User.query.filter_by(
        user_id=user_id,
        organization_id=org_id
    ).first()
    if not user:
        flash('Medewerker niet gevonden.', 'danger')
        return redirect(url_for('main.admin_personeelsbeheer'))
    
    db.session.delete(user)
    db.session.commit()
    flash('Medewerker succesvol verwijderd.', 'success')
    return redirect(url_for('main.admin_personeelsbeheer'))

# Nieuwe medewerker toevoegen
@main.route('/admin/medewerker/create', methods=['POST'])
@require_admin
def admin_create_medewerker():
    current_user = get_current_user()
    org_id = get_current_organization_id()
    
    try:
        naam = request.form.get('user_name', '').strip()
        achternaam = request.form.get('user_last_name', '').strip()
        email = request.form.get('user_email', '').strip()
        dienst = request.form.get('dienst')
        dienst_other = request.form.get('dienst_other', '').strip()
        
        if dienst == 'other' and dienst_other:
            dienst_final = dienst_other
        else:
            dienst_final = dienst
            
        if not naam or not achternaam or not email or not dienst_final:
            flash('Vul alle velden in.', 'danger')
            return redirect(url_for('main.admin_personeelsbeheer'))
        
        # Check if email already exists in this organization
        existing_user = User.query.filter_by(
            user_email=email,
            organization_id=org_id
        ).first()
        if existing_user:
            flash(f'Een medewerker met email {email} bestaat al in uw organisatie.', 'danger')
            return redirect(url_for('main.admin_personeelsbeheer'))
        
        nieuwe_user = User(
            user_name=naam, 
            user_last_name=achternaam, 
            user_email=email, 
            organization_id=org_id,
            dienst=dienst_final
        )
        db.session.add(nieuwe_user)
        db.session.commit()
        flash('Nieuwe medewerker succesvol toegevoegd.', 'success')
        return redirect(url_for('main.admin_personeelsbeheer'))
    except Exception as e:
        db.session.rollback()
        flash(f'Fout bij het toevoegen van de medewerker: {str(e)}', 'danger')
        return redirect(url_for('main.admin_personeelsbeheer'))
