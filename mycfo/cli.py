from __future__ import annotations

import click
from flask import Flask

from .bootstrap import create_schema
from .db import Base


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        create_schema(app)
        click.echo("Initialized database schema.")

    @app.cli.command("reset-db")
    @click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
    def reset_db_command(yes: bool) -> None:
        if app.config["APP_ENV"] != "development":
            raise click.ClickException("reset-db is only available when APP_ENV=development.")

        if not yes:
            click.confirm("This will delete all data in the configured database. Continue?", abort=True)

        engine = app.extensions["db_engine"]
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        click.echo("Reset database schema.")
