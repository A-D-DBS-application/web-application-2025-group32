"""App package initializer: application factory."""
from flask import Flask

def create_app():
    """Create and configure the Flask app, initialize extensions and blueprints."""
    app = Flask(__name__)

    # Load configuration from app.config module
    try:
        from .config import config as Config
        app.config.from_object(Config)
    except Exception:
        # fallback: no config module
        pass

    # Initialize extensions and blueprints after creating app
    # Ensure engine options include SSL for Supabase and enable pool_pre_ping
    app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {
        'connect_args': {'sslmode': 'require'},
        'pool_pre_ping': True,
    })

    from .models import db
    db.init_app(app)

    # Register blueprints
    try:
        from .routes import main
        app.register_blueprint(main)
    except Exception as e:
        print(f"[ERROR] Failed to register Blueprint 'main': {e}")
        import traceback
        traceback.print_exc()
        # if routes cannot be imported here, caller can register later
        pass

    @app.context_processor
    def inject_user():
        """Maak user_obj beschikbaar in alle templates"""
        from flask import session
        if "user" not in session:
            return dict(user_obj=None)
        
        try:
            from .models import User
            user_id = int(session.get("user"))
            user_obj = User.query.filter_by(user_id=user_id).first()
            return dict(user_obj=user_obj)
        except:
            return dict(user_obj=None)

    return app
