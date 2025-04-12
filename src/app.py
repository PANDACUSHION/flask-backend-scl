from flask import Flask
from flask_cors import CORS
from .config import Config
from .db import db
from .blueprints.session.rotues import bp as bp_session
from .blueprints.student.routes import bp as bp_student
from .blueprints.teacher.routes import bp as bp_teacher
from .blueprints.dashboard.routes import bp as bp_dashboard

def create_app(config: Config=Config):
    app = Flask(__name__)
    CORS(app)
    app.config.from_object(config)
    app.register_blueprint(bp_session)
    app.register_blueprint(bp_student)
    app.register_blueprint(bp_teacher)
    app.register_blueprint(bp_dashboard)
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app
