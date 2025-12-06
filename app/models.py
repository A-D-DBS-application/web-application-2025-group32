from flask_sqlalchemy import SQLAlchemy
from datetime import date, time as time_type

db = SQLAlchemy()

class User(db.Model):
    """
    User model - vertegenwoordigt een werknemer
    """
    __tablename__ = "user"
    user_id = db.Column(db.Integer, primary_key=True)  # Unieke ID
    user_name = db.Column(db.String(120))
    user_last_name = db.Column(db.String(120))
    dienst = db.Column(db.String(200))  # Afdeling/dienst van de gebruiker
    user_email = db.Column(db.String(200))
    role = db.Column(db.String(50), default='user')
    
    # Relaties
    reservations = db.relationship("Reservation", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.user_id}>"

    def is_admin(self):
        """Check of gebruiker admin is - kijkt naar role veld in database"""
        # Accepteer zowel 'Beheerder', 'admin' als 'Admin' voor admin rechten
        if not self.role:
            return False
        role_lower = self.role.lower()
        return role_lower in ['beheerder', 'admin']


class Building(db.Model):
    """
    Building model - vertegenwoordigt een gebouw (A, B, C, etc.)
    """
    __tablename__ = "building"
    building_id = db.Column(db.Integer, primary_key=True)
    adress = db.Column(db.String(200))  # Note: typo in original table (adress not address)
    floor = db.Column(db.Integer)  # Verdieping
    
    # Relatie naar desks
    desks = db.relationship("Desk", back_populates="building", lazy="dynamic")

    def __repr__(self):
        return f"<Building {self.building_id}>"


class Desk(db.Model):
    """
    Desk model - vertegenwoordigt een bureau
    """
    __tablename__ = "desk"
    desk_id = db.Column(db.Integer, primary_key=True)
    desk_number = db.Column(db.Integer)  # Bureau nummer
    building_id = db.Column(db.Integer, db.ForeignKey("building.building_id"), nullable=False)
    dienst = db.Column(db.String(100))  # Afdeling/dienst - komt overeen met user.dienst
    screen = db.Column(db.Text)  # Type scherm
    chair = db.Column(db.Text)  # Type stoel
    
    # Relaties
    building = db.relationship("Building", back_populates="desks")
    reservations = db.relationship("Reservation", back_populates="desk", lazy="dynamic")

    def __repr__(self):
        return f"<Desk {self.desk_id}>"
    
    def get_dienst(self):
        """Geef de dienst terug"""
        return self.dienst if self.dienst else "Geen dienst"



class Reservation(db.Model):
    """
    Reservation model - vertegenwoordigt een bureauboeking
    """
    __tablename__ = "reservation"
    res_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete='CASCADE'), nullable=False)
    desk_id = db.Column(db.Integer, db.ForeignKey("desk.desk_id", ondelete='CASCADE'), nullable=False)
    starttijd = db.Column(db.DateTime, nullable=False)  # Begintijd met datum
    eindtijd = db.Column(db.DateTime, nullable=False)  # Eindtijd met datum
    modified_by_admin = db.Column(db.Boolean, default=False)  # Of admin de reservatie heeft gewijzigd
    
    # Relaties
    user = db.relationship("User", back_populates="reservations")
    desk = db.relationship("Desk", back_populates="reservations")
    feedback = db.relationship("Feedback", back_populates="reservation", uselist=False)

    def __repr__(self):
        return f"<Reservation {self.user_id} - {self.desk_id}>"


class Feedback(db.Model):
    """
    Feedback model - vertegenwoordigt feedback voor een reservatie
    """
    __tablename__ = "Feedback"
    feedback_id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.res_id", ondelete='CASCADE'), nullable=False)
    netheid_score = db.Column(db.SmallInteger)  # Netheid score (1-5)
    wifi_score = db.Column(db.SmallInteger)  # Wifi score (1-5)
    ruimte_score = db.Column(db.SmallInteger)  # Ruimte score (1-5)
    stilte_score = db.Column(db.SmallInteger)  # Stilte score (1-5)
    algemene_score = db.Column(db.SmallInteger)  # Algemene score (1-5)
    extra_opmerkingen = db.Column(db.Text)  # Extra opmerkingen
    is_reviewed = db.Column(db.Boolean, default=False)  # Of admin de feedback heeft bekeken
    reviewed_at = db.Column(db.DateTime, nullable=True)  # Wanneer bekeken
    
    # Relatie
    reservation = db.relationship("Reservation", back_populates="feedback")

    def __repr__(self):
        return f"<Feedback {self.feedback_id}>"


class AdminNotification(db.Model):
    """
    AdminNotification model - notificaties voor gebruikers over admin acties
    """
    __tablename__ = "admin_notification"
    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete='CASCADE'), nullable=False)
    reservation_id = db.Column(db.Integer, nullable=True)  # Null als verwijderd
    notification_type = db.Column(db.String(50), nullable=False)  # 'modified' of 'deleted'
    message = db.Column(db.Text, nullable=False)  # Bericht voor gebruiker
    
    # Voor deleted reservaties
    deleted_desk_number = db.Column(db.String(50))
    deleted_building = db.Column(db.String(200))
    deleted_date = db.Column(db.String(20))
    deleted_time = db.Column(db.String(20))
    
    # Voor modified reservaties  
    changed_field = db.Column(db.String(50))  # Wat is er gewijzigd? (datum/tijd/bureau)
    old_value = db.Column(db.String(200))  # Oude waarde
    new_value = db.Column(db.String(200))  # Nieuwe waarde
    
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    # Relatie
    user = db.relationship("User", backref="notifications")

    def __repr__(self):
        return f"<AdminNotification {self.notification_id}>"
