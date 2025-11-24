import sys
from pathlib import Path

# Ensure backend/app is on the Python path so `import app` resolves
project_root = Path(__file__).parent.parent
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))
