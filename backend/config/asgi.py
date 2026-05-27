import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

application = get_asgi_application()
