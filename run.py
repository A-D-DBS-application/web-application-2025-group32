"""Run the Flask application using the `app` instance that defines routes.

We import the module `app.app` which creates the configured `app` and registers
the route handlers. Using that `app` avoids the previous mismatch where
`run.py` created a different app without the '/' route.
"""
import importlib
import sys

# Import the module that defines `app` (app/app.py)
try:
    app_module = importlib.import_module('app.app')
    app = getattr(app_module, 'app')
except Exception as e:
    print(f"Failed to import app.app: {e}")
    sys.exit(1)

if __name__ == "__main__":
    # Try to create tables (if DB is reachable) then run
    try:
        from app.models import db
        with app.app_context():
            db.create_all()
    except Exception as e:
        print(f"Warning: could not create tables: {e}")

    app.run(debug=True)