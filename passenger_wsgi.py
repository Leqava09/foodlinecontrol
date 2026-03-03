#!/usr/bin/env python
"""
WSGI entry point for cPanel Passenger application server.
This file is used by cPanel's Passenger to run the Django application.
"""
import sys
import os

# Add the application directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application

# Create the WSGI application
application = get_wsgi_application()
