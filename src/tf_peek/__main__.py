"""Module entrypoint so ``python -m tf_peek`` runs the CLI."""

from .cli import app

if __name__ == "__main__":
    app()
