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

    # Query: alle bureaus, maar filteren op ZOWEL adress ALS floor (optioneel)
    q = Desk.query
    
    # Filter op dienst: gebruiker ziet alleen werkposten van zijn eigen dienst
    # Admins zien alle werkposten
    if user and not user.is_admin():
        # Haal dienst_id op van gebruiker (gebaseerd op user_afdeling)
        user_afdeling = user.user_afdeling
        
        # Mapping van user_afdeling naar dienst_id
        afdeling_to_dienst = {
            'Marketing': 1,
            'IT': 3,
            'Sales': 5
        }
        
        user_dienst_id = afdeling_to_dienst.get(user_afdeling)
        
        if user_dienst_id:
            # Filter alleen desks met deze dienst_id OF desks zonder dienst (voor backwards compatibility)
            q = q.filter((Desk.dienst_id == user_dienst_id) | (Desk.dienst_id == None))
        # Als user_afdeling niet herkend wordt, toon alle desks (backwards compatibility)
    
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
    # Allow viewing desk details without login; require login for confirmation.

    desk = Desk.query.filter_by(desk_id=desk_id).first()
    if not desk:
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


@main.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    """Admin dashboard - werkposten beheren en koppelen aan diensten"""
    user = get_current_user()
    
    # Check voor edit mode, delete confirmation, en add new parameters
    edit_desk_id = request.args.get('edit', type=int)
    confirm_delete = request.args.get('delete', type=int)
    add_new = request.args.get('add_new', type=int)
    
    try:
        # Haal alle desks op met building info
        desks = Desk.query.join(Building).order_by(Building.adress, Desk.desk_number).all()
        
        # Haal alle unieke gebouwen op (distinct op adress om duplicaten te voorkomen)
        buildings_query = db.session.query(Building.adress, Building.building_id).distinct(Building.adress).order_by(Building.adress).all()
        buildings_list = [{'id': b.building_id, 'naam': b.adress} for b in buildings_query]
        
        # Haal alle unieke scherm types op uit de database
        screens_query = db.session.query(Desk.screen).filter(Desk.screen.isnot(None)).distinct().all()
        screens_raw = [s[0] for s in screens_query if s[0]]
        # Custom volgorde: Single, Dual, Triple, dan de rest alfabetisch
        screen_order = ['single', 'dual', 'triple']
        screens_ordered = []
        for screen in screen_order:
            # Match op basis van 'bevat' in plaats van exacte match
            matching = [s for s in screens_raw if screen in s.lower()]
            if matching:
                screens_ordered.append(matching[0].capitalize())
                screens_raw = [s for s in screens_raw if screen not in s.lower()]
        # Voeg overige toe (alfabetisch, met hoofdletter)
        screens_ordered.extend(sorted([s.capitalize() for s in screens_raw]))
        screens_list = screens_ordered
        
        # Haal alle unieke stoel types op uit de database
        chairs_query = db.session.query(Desk.chair).filter(Desk.chair.isnot(None)).distinct().all()
        chairs_raw = [c[0] for c in chairs_query if c[0]]
        # Custom volgorde: Standard, Standing, Ergonomic, dan de rest alfabetisch
        chair_order = ['standard', 'standing', 'ergonomic']
        chairs_ordered = []
        for chair in chair_order:
            matching = [c for c in chairs_raw if c.lower() == chair]
            if matching:
                chairs_ordered.append(matching[0].capitalize())
                chairs_raw = [c for c in chairs_raw if c.lower() != chair]
        # Voeg overige toe (alfabetisch, met hoofdletter)
        chairs_ordered.extend(sorted([c.capitalize() for c in chairs_raw]))
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
                'dienst_id': desk.dienst_id,
                'dienst_naam': desk.get_dienst_naam(),
                'screen': desk.screen or 'Niet gespecificeerd',
                'chair': desk.chair or 'Niet gespecificeerd'
            }
            desk_list.append(desk_info)
            
            # Bewaar desk number voor edit mode banner
            if edit_desk_id and desk.desk_id == edit_desk_id:
                edit_desk_number = desk.desk_number
        
        # Lijst van beschikbare diensten
        diensten = [
            {'id': 1, 'naam': 'Marketing'},
            {'id': 3, 'naam': 'IT'},
            {'id': 5, 'naam': 'Sales'}
        ]
        
    except Exception as e:
        flash(f"Fout bij ophalen werkposten: {str(e)}", "danger")
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
                         confirm_delete=confirm_delete,
                         add_new=add_new,
                         is_admin=True)


@main.route('/admin/desk/update/<int:desk_id>', methods=['POST'])
@require_admin
def admin_update_desk(desk_id):
    """Admin kan desk details wijzigen (bureau, gebouw, dienst, scherm, stoel)"""
    user = get_current_user()
    
    try:
        desk = Desk.query.filter_by(desk_id=desk_id).first()
        if not desk:
            flash("Werkpost niet gevonden.", "danger")
            return redirect(url_for('main.admin_dashboard'))
        
        # Haal waardes op uit form
        new_desk_number = request.form.get('desk_number')
        new_building_id = request.form.get('building_id')
        new_building_other = request.form.get('building_other', '').strip()
        new_dienst_id = request.form.get('dienst_id')
        new_screen = request.form.get('screen')
        new_screen_other = request.form.get('screen_other', '').strip()
        new_chair = request.form.get('chair')
        new_chair_other = request.form.get('chair_other', '').strip()
        
        # Update bureau nummer
        if new_desk_number:
            desk.desk_number = int(new_desk_number)
        
        # Update gebouw - check eerst of "Andere" is geselecteerd
        if new_building_id == 'other' and new_building_other:
            # Maak nieuw gebouw aan
            new_building = Building(adress=new_building_other, floor=1)
            db.session.add(new_building)
            db.session.flush()  # Om building_id te krijgen
            desk.building_id = new_building.building_id
            flash(f"Nieuw gebouw '{new_building_other}' aangemaakt.", "success")
        elif new_building_id and new_building_id != 'other':
            desk.building_id = int(new_building_id)
        
        # Update dienst
        if new_dienst_id and new_dienst_id != 'None':
            desk.dienst_id = int(new_dienst_id)
        else:
            desk.dienst_id = None
        
        # Update scherm - check eerst of "Andere" is geselecteerd
        if new_screen == 'other' and new_screen_other:
            desk.screen = new_screen_other.capitalize()
        elif new_screen and new_screen != 'other':
            desk.screen = new_screen.capitalize()
        
        # Update stoel - check eerst of "Andere" is geselecteerd  
        if new_chair == 'other' and new_chair_other:
            desk.chair = new_chair_other.capitalize()
        elif new_chair and new_chair != 'other':
            desk.chair = new_chair.capitalize()
        
        db.session.commit()
        flash(f"Werkpost {desk.desk_number} succesvol gewijzigd.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Fout bij wijzigen werkpost: {str(e)}", "danger")
    
    # Redirect terug naar edit mode zodat gebruiker op dezelfde plek blijft
    return redirect(url_for('main.admin_dashboard', edit=desk_id, _anchor=f'desk-{desk_id}'))


@main.route('/admin/desk/create', methods=['POST'])
@require_admin
def admin_create_desk():
    """Admin kan nieuw bureau toevoegen"""
    user = get_current_user()
    
    try:
        # Haal waardes op uit form
        new_desk_number = request.form.get('desk_number')
        new_building_id = request.form.get('building_id')
        new_building_other = request.form.get('building_other', '').strip()
        new_dienst_id = request.form.get('dienst_id')
        new_screen = request.form.get('screen')
        new_screen_other = request.form.get('screen_other', '').strip()
        new_chair = request.form.get('chair')
        new_chair_other = request.form.get('chair_other', '').strip()
        
        # Valideer bureau nummer
        if not new_desk_number or int(new_desk_number) < 1:
            flash("Bureau nummer moet minimaal 1 zijn.", "danger")
            return redirect(url_for('main.admin_dashboard', add_new=1))
        
        desk_number = int(new_desk_number)
        
        # Check of bureau nummer al bestaat
        existing = Desk.query.filter_by(desk_number=desk_number).first()
        if existing:
            flash(f"Bureau {desk_number} bestaat al.", "danger")
            return redirect(url_for('main.admin_dashboard', add_new=1))
        
        # Handle gebouw
        if new_building_id == 'other' and new_building_other:
            new_building = Building(adress=new_building_other, floor=1)
            db.session.add(new_building)
            db.session.flush()
            building_id = new_building.building_id
            flash(f"Nieuw gebouw '{new_building_other}' aangemaakt.", "success")
        elif new_building_id and new_building_id != 'other':
            building_id = int(new_building_id)
        else:
            flash("Selecteer een gebouw.", "danger")
            return redirect(url_for('main.admin_dashboard', add_new=1))
        
        # Handle dienst
        if new_dienst_id and new_dienst_id != 'None':
            dienst_id = int(new_dienst_id)
        else:
            dienst_id = None
        
        # Handle scherm
        if new_screen == 'other' and new_screen_other:
            screen = new_screen_other.capitalize()
        elif new_screen and new_screen != 'other':
            screen = new_screen.capitalize()
        else:
            screen = None
        
        # Handle stoel
        if new_chair == 'other' and new_chair_other:
            chair = new_chair_other.capitalize()
        elif new_chair and new_chair != 'other':
            chair = new_chair.capitalize()
        else:
            chair = None
        
        # Maak nieuw bureau aan
        new_desk = Desk(
            desk_number=desk_number,
            building_id=building_id,
            dienst_id=dienst_id,
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
    """Admin kan desk verwijderen"""
    user = get_current_user()
    
    try:
        desk = Desk.query.filter_by(desk_id=desk_id).first()
        if not desk:
            flash("Werkpost niet gevonden.", "danger")
            return redirect(url_for('main.admin_dashboard'))
        
        desk_number = desk.desk_number
        db.session.delete(desk)
        db.session.commit()
        flash(f"Werkpost {desk_number} succesvol verwijderd.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Fout bij verwijderen werkpost: {str(e)}", "danger")
    
    return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/reservation/delete/<int:res_id>', methods=['POST'])
@require_admin
def admin_delete_reservation(res_id):
    """Admin kan elke reservatie verwijderen"""
    user = get_current_user()
    
    try:
        reservation = Reservation.query.filter_by(res_id=res_id).first()
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
    """Admin overzicht van alle toekomstige reservaties"""
    user = get_current_user()
    
    try:
        # Haal alle toekomstige reservaties op met user, desk en building info
        now = datetime.now()
        reservations = db.session.query(
            Reservation.res_id,
            Reservation.starttijd,
            Reservation.eindtijd,
            User.user_name,
            User.user_last_name,
            User.user_email,
            Desk.desk_number,
            Building.adress.label('building_adress')
        ).join(User, Reservation.user_id == User.user_id
        ).join(Desk, Reservation.desk_id == Desk.desk_id
        ).join(Building, Desk.building_id == Building.building_id
        ).filter(Reservation.starttijd >= now
        ).order_by(Reservation.starttijd).all()
        
    except Exception as e:
        flash(f"Fout bij ophalen reservaties: {str(e)}")
        reservations = []
    
    return render_template('admin_reservations_overview.html',
                         user=user,
                         reservations=reservations)


@main.route('/admin/reservation/edit/<int:res_id>', methods=['GET', 'POST'])
@require_admin
def admin_edit_reservation(res_id):
    """Admin kan reservatie wijzigen"""
    user = get_current_user()
    
    try:
        reservation = Reservation.query.filter_by(res_id=res_id).first()
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
            
            chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time_obj = datetime.strptime(start_str, "%H:%M").time()
            end_time_obj = datetime.strptime(end_str, "%H:%M").time()
            
            start_datetime = datetime.combine(chosen_date, start_time_obj)
            end_datetime = datetime.combine(chosen_date, end_time_obj)
            
            if start_time_obj >= end_time_obj:
                flash("Eindtijd moet later zijn dan starttijd.")
                return redirect(url_for('main.admin_edit_reservation', res_id=res_id))
            
            # Check overlap met andere reservaties (behalve deze zelf)
            overlapping = Reservation.query.filter(
                Reservation.desk_id == reservation.desk_id,
                Reservation.res_id != res_id,
                Reservation.starttijd < end_datetime,
                start_datetime < Reservation.eindtijd
            ).first()
            
            if overlapping:
                flash("Dit tijdslot is al geboekt voor dit bureau!")
                return redirect(url_for('main.admin_edit_reservation', res_id=res_id))
            
            # Update reservatie
            reservation.starttijd = start_datetime
            reservation.eindtijd = end_datetime
            db.session.commit()
            
            flash("Reservatie succesvol gewijzigd.")
            return redirect(url_for('main.admin_reservations_overview'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Fout bij wijzigen: {str(e)}")
            return redirect(url_for('main.admin_edit_reservation', res_id=res_id))
    
    # GET: toon formulier
    return render_template('admin_edit_reservation.html', 
                         user=user, 
                         reservation=reservation)


@main.route('/admin/reservation/create', methods=['GET', 'POST'])
@require_admin
def admin_create_reservation():
    """Admin kan reservatie aanmaken voor een gebruiker"""
    user = get_current_user()
    
    # Haal alle users en buildings op
    try:
        all_users = User.query.order_by(User.user_name).all()
        all_buildings = Building.query.all()
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
            
            # Check overlap
            overlapping = Reservation.query.filter(
                Reservation.desk_id == desk_id,
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
                         all_users=all_users,
                         buildings=all_buildings)


@main.route('/api/desks')
def api_desks():
    """API endpoint om bureaus op te halen per gebouw"""
    building_id = request.args.get('building_id')
    
    if not building_id:
        return jsonify([])
    
    try:
        desks = Desk.query.filter_by(building_id=building_id).all()
        return jsonify([{
            'desk_id': d.desk_id,
            'desk_number': d.desk_number
        } for d in desks])
    except Exception:
        return jsonify([])