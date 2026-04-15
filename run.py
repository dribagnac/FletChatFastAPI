import subprocess
import time
import sys

def start_app():
    # 1. Start the Backend
    print("Starting Backend...")
    backend = subprocess.Popen([sys.executable, "backend.py"])
    
    # 2. Wait a moment for the server to bind to the port
    time.sleep(2)
    
    # 3. Start the Frontend
    print("Starting Frontend...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        pass
    finally:
        # 4. Kill the backend when the frontend closes
        print("Closing Backend...")
        backend.terminate()

if __name__ == "__main__":
    start_app()#!/usr/bin/env python

