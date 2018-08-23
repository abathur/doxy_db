import logging

loggle = logging.getLogger(__name__)
loggle.addHandler(logging.NullHandler())

from pathlib import Path

DEFAULT_DB_URI = str(Path() / "doxygen_sqlite3.db")
