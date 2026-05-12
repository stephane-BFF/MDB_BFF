"""
Point d'entrée de l'application MDB BFF.

Usage :
    flask run --debug                      (développement)
    gunicorn run:app -w 4                  (production Linux/NAS Synology)
    waitress-serve --port=5000 run:app     (production Windows Server)
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
