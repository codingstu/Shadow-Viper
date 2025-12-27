# backend/main.py
import uvicorn
import os
import sys

# This is the directory containing 'main.py' and the 'app/' package.
# It needs to be on the Python path for imports like 'from app.main...' to work.
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

if __name__ == "__main__":
    # The 'reload_dirs' argument tells the reloader to watch our project directory.
    # The string "app.main:app" tells uvicorn where to find the FastAPI app instance.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[os.path.join(APP_ROOT, 'app')])
