"""
API routes package
"""

# Import all route modules to make them available when importing this package
try:
    from . import auth_routes
    from . import hitl_routes
except ImportError:
    # During development, some modules might not exist yet
    pass 