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
    user_afdeling = db.Column(db.String(200))
    user_email = db.Column(db.String(200))
    dienst_id = db.Column(db.Integer)
    role = db.Column(db.String(50))
    
    # Relaties
    reservations = db.relationship("Reservation", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.user_id}>"


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
    dienst_id = db.Column(db.Integer)  # Afdeling
    
    # Relaties
    building = db.relationship("Building", back_populates="desks")
    reservations = db.relationship("Reservation", back_populates="desk", lazy="dynamic")

    def __repr__(self):
        return f"<Desk {self.desk_id}>"


class Reservation(db.Model):
    """
    Reservation model - vertegenwoordigt een bureauboeking
    """
    __tablename__ = "reservation"
    res_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    desk_id = db.Column(db.Integer, db.ForeignKey("desk.desk_id"), nullable=False)
    starttijd = db.Column(db.DateTime, nullable=False)  # Begintijd met datum
    eindtijd = db.Column(db.DateTime, nullable=False)  # Eindtijd met datum
    
    # Relaties
    user = db.relationship("User", back_populates="reservations")
    desk = db.relationship("Desk", back_populates="reservations")

    def __repr__(self):
        return f"<Reservation {self.user_id} - {self.desk_id}>"
