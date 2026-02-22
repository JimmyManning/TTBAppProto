"""Application factory for the TTB label verification service."""

from flask import Flask

from ttb_label_verifier.routes import api_blueprint


def create_app() -> Flask:
    """Create and configure the Flask application instance.

    Returns:
        A configured Flask application.
    """
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        static_url_path="/static",
    )
    app.register_blueprint(api_blueprint)
    return app
