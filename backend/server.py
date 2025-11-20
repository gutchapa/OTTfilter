import uvicorn
import sys
import site
import os

# Add user site packages to ensure dependencies are found
sys.path.append(site.getusersitepackages())

# Add current directory to path to find 'app' package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8081, reload=True)
