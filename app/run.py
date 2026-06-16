from app.app import create_app


# Gunicorn entry point - used in production and referenced in the`Dockerfile`
def app():
    return create_app()


# Flask entry point - used for local development and referenced in the `makefile`
def run_app():
    flask_app = create_app()
    flask_app.run(port=4567)
    return flask_app


if __name__ == "__main__":
    run_app()
