"""
Compatibility database module.

This file re-exports database utilities from `app.database` so imports using
`backend/database.py` continue to work consistently.
"""

from app.database import *  # noqa: F401,F403

