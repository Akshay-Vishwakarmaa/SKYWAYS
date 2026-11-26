
import os
from flask import Flask
from pathlib import Path


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get(
            "SECRET_KEY",
            "skyways-development-key"
        ),
        DATABASE=str(Path(app.instance_path) / "skyways.db")
    )

    Path(app.instance_path).mkdir(
        parents=True,
        exist_ok=True
    )

    from app.models import init_app
    init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    return app
