"""
Global rate limiter instance using slowapi.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# We instantiate the Limiter here to avoid circular imports between main.py and the API routers.
limiter = Limiter(key_func=get_remote_address)
