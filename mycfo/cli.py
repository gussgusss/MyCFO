from __future__ import annotations

import click
from flask import Flask

from .bootstrap import create_schema


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        create_schema(app)
        click.echo("Initialized database schema.")
