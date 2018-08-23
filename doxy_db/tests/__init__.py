import sys
from pathlib import Path

sys.path.append("..")

OUTPUT_DIR = Path(__file__).parent
TEST_DB = str(OUTPUT_DIR / "doxygen_sqlite3.db")
EMPTY_DB = str(OUTPUT_DIR / "empty.db")
PREVIOUS_DB = str(OUTPUT_DIR / "previous.db")
TEST_XML = str(OUTPUT_DIR / "xml/all.xml")
