from flask import Flask

from .cli import register_cli
from .config import Config
from .db import close_db, init_db
from .errors import register_error_handlers
from .request_context import attach_request_context
from .routes import register_routes


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    init_db(app)
    attach_request_context(app)
    register_error_handlers(app)
    register_routes(app)
    register_cli(app)
    app.teardown_appcontext(close_db)

    return app
