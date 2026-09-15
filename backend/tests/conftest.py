import os
import sys

# Make `import models`, `import database` and `from routers import calm` resolve exactly as they do
# when the app runs with the backend folder as the working directory.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)  # database.py loads ../.env relative to the working directory
