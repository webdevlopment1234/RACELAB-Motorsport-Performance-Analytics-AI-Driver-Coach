"""Development entrypoint: python backend/run.py"""

from __future__ import annotations

from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)
