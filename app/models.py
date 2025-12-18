from flask_sqlalchemy import SQLAlchemy
from datetime import date, time as time_type

db = SQLAlchemy()

class Organization(db.Model):
    """
    Organization model - vertegenwoordigt een bedrijf/organisatie
    """
    __tablename__ = "organization"
    organization_id = db.Column(db.Integer, primary_key=True)
    bedrijf = db.Column(db.String(200), nullable=False)  # Bedrijfsnaam
    logo_filename = db.Column(db.String(100), default='Logo_colruyt_group.png')  # Logo bestandsnaam
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_active = db.Column(db.Boolean, default=True)
    
    # Relaties
    users = db.relationship("User", back_populates="organization", lazy="dynamic")
    buildings = db.relationship("Building", back_populates="organization", lazy="dynamic")
    desks = db.relationship("Desk", back_populates="organization", lazy="dynamic")
    reservations = db.relationship("Reservation", back_populates="organization", lazy="dynamic")
    feedbacks = db.relationship("Feedback", back_populates="organization", lazy="dynamic")

    def __repr__(self):
        return f"<Organization {self.organization_id}: {self.bedrijf}>"
    
    def get_logo_path(self):
        """Geef het volledige path voor het logo terug"""
        return f"images/{self.logo_filename}" if self.logo_filename else "images/Logo_colruyt_group.png"


class User(db.Model):
    """
    User model - vertegenwoordigt een werknemer
    """
    __tablename__ = "user"
    user_id = db.Column(db.Integer, primary_key=True)  # Unieke ID
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    user_name = db.Column(db.String(100))
    user_last_name = db.Column(db.String(100))
    dienst = db.Column(db.String(200))  # Afdeling/dienst van de gebruiker
    user_email = db.Column(db.String(200))
    role = db.Column(db.String(50), default='Medewerker')
    
    # Relaties
    organization = db.relationship("Organization", back_populates="users")
    reservations = db.relationship("Reservation", back_populates="user", lazy="dynamic", passive_deletes=True)

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
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    adress = db.Column(db.String(200))  # Note: typo in original table (adress not address)
    floor = db.Column(db.Integer)  # Verdieping
    
    # Relaties
    organization = db.relationship("Organization", back_populates="buildings")
    desks = db.relationship("Desk", back_populates="building", lazy="dynamic")

    def __repr__(self):
        return f"<Building {self.building_id}>"


class Desk(db.Model):
    """
    Desk model - vertegenwoordigt een bureau
    """
    __tablename__ = "desk"
    desk_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    desk_number = db.Column(db.Integer)  # Bureau nummer
    building_id = db.Column(db.Integer, db.ForeignKey("building.building_id"), nullable=False)
    dienst = db.Column(db.String(100))  # Afdeling/dienst - komt overeen met user.dienst
    screen = db.Column(db.String(100))  # Type scherm
    chair = db.Column(db.String(100))  # Type stoel
    
    # Relaties
    organization = db.relationship("Organization", back_populates="desks")
    building = db.relationship("Building", back_populates="desks")
    reservations = db.relationship("Reservation", back_populates="desk", lazy="dynamic", passive_deletes=True)

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
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete='CASCADE'), nullable=False)
    desk_id = db.Column(db.Integer, db.ForeignKey("desk.desk_id", ondelete='CASCADE'), nullable=False)
    starttijd = db.Column(db.DateTime, nullable=False)  # Begintijd met datum
    eindtijd = db.Column(db.DateTime, nullable=False)  # Eindtijd met datum
    modified_by_admin = db.Column(db.Boolean, default=False)  # Of admin de reservatie heeft gewijzigd
    
    # Relaties
    organization = db.relationship("Organization", back_populates="reservations")
    user = db.relationship("User", back_populates="reservations")
    desk = db.relationship("Desk", back_populates="reservations")
    feedback = db.relationship("Feedback", back_populates="reservation", uselist=False, passive_deletes=True)

    def __repr__(self):
        return f"<Reservation {self.user_id} - {self.desk_id}>"


class Feedback(db.Model):
    """
    Feedback model - vertegenwoordigt feedback voor een reservatie
    """
    __tablename__ = "Feedback"
    feedback_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.res_id", ondelete='CASCADE'), nullable=False)
    netheid_score = db.Column(db.SmallInteger)  # Netheid score (1-5)
    wifi_score = db.Column(db.SmallInteger)  # Wifi score (1-5)
    ruimte_score = db.Column(db.SmallInteger)  # Ruimte score (1-5)
    stilte_score = db.Column(db.SmallInteger)  # Stilte score (1-5)
    algemene_score = db.Column(db.SmallInteger)  # Algemene score (1-5)
    extra_opmerkingen = db.Column(db.String(1000))  # Extra opmerkingen
    is_reviewed = db.Column(db.Boolean, default=False)  # Of admin de feedback heeft bekeken
    reviewed_at = db.Column(db.DateTime, nullable=True)  # Wanneer bekeken
    
    # Relaties
    organization = db.relationship("Organization", back_populates="feedbacks")
    reservation = db.relationship("Reservation", back_populates="feedback")

    def __repr__(self):
        return f"<Feedback {self.feedback_id}>"


# Analytics Models voor Dynamic Word Lists
class AnalyticsStopword(db.Model):
    """
    Analytics Stopwords - Nederlandse stopwoorden voor feedback analyse
    """
    __tablename__ = "analytics_stopwords"
    stopword_id = db.Column(db.BigInteger, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Unique constraint per word per organization
    __table_args__ = (
        db.UniqueConstraint('word', 'organization_id', name='analytics_stopwords_unique_word_org'),
    )
    
    # Relaties
    organization = db.relationship("Organization")

    def __repr__(self):
        return f"<AnalyticsStopword {self.word}>"


class AnalyticsSentimentWord(db.Model):
    """
    Analytics Sentiment Words - Positieve en negatieve woorden voor sentiment analyse
    """
    __tablename__ = "analytics_sentiment_words"
    sentiment_word_id = db.Column(db.BigInteger, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    sentiment_type = db.Column(db.String(10), nullable=False)  # 'positief' of 'negatief'
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Check constraint for sentiment_type
    __table_args__ = (
        db.CheckConstraint("sentiment_type IN ('positief', 'negatief')", name='check_sentiment_type'),
        db.UniqueConstraint('word', 'sentiment_type', 'organization_id', name='analytics_sentiment_words_unique_word_type_org'),
    )
    
    # Relaties
    organization = db.relationship("Organization")

    def __repr__(self):
        return f"<AnalyticsSentimentWord {self.word} ({self.sentiment_type})>"


class AnalyticsTopicCategory(db.Model):
    """
    Analytics Topic Categories - Categorieën voor topic modeling (netheid, wifi, etc.)
    """
    __tablename__ = "analytics_topic_categories"
    topic_category_id = db.Column(db.BigInteger, primary_key=True)
    category_name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Unique constraint per category per organization
    __table_args__ = (
        db.UniqueConstraint('category_name', 'organization_id', name='analytics_topic_categories_unique_name_org'),
    )
    
    # Relaties
    organization = db.relationship("Organization")
    keywords = db.relationship("AnalyticsTopicKeyword", back_populates="topic_category", lazy="dynamic")

    def __repr__(self):
        return f"<AnalyticsTopicCategory {self.category_name}>"


class AnalyticsTopicKeyword(db.Model):
    """
    Analytics Topic Keywords - Keywords per topic categorie voor classificatie
    """
    __tablename__ = "analytics_topic_keywords"
    topic_keyword_id = db.Column(db.BigInteger, primary_key=True)
    topic_category_id = db.Column(db.BigInteger, db.ForeignKey("analytics_topic_categories.topic_category_id"), nullable=False)
    keyword = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.organization_id"), nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Unique constraint per keyword per category per organization
    __table_args__ = (
        db.UniqueConstraint('keyword', 'topic_category_id', 'organization_id', name='analytics_topic_keywords_unique_keyword_category_org'),
    )
    
    # Relaties
    organization = db.relationship("Organization")
    topic_category = db.relationship("AnalyticsTopicCategory", back_populates="keywords")

    def __repr__(self):
        return f"<AnalyticsTopicKeyword {self.keyword}>"
