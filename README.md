PROJECT OVERVIEW
DAILY is a Django-based web application for staff management and daily logging system. The project structure includes user authentication, admin dashboard functionality, and uses MongoDB database for storing of user details.

Project Structure Walkthrough

Root Directory Files

manage.py: Django's command-line utility for administrative tasks

db.sqlite3: SQLite database file (development database)

nkpacks.toml & Procfile: Deployment configuration files (likely for Heroku or similar platform)

datadump.json: Database dump file for data migration/backup

migrate_to_mongo.py: Script to migrate data from SQLite to MongoDB

venv/: Python virtual environment directory

Main Django Project Configuration

DAiLY/ & daily/: Main project directories containing:

settings.py: Project configuration and settings

urls.py: URL routing configuration

wsgi.py: WSGI configuration for deployment

asgi.py: ASGI configuration for async support

__init__.py: Python package initialization

Core Application Components

logs/: Main Django app directory containing:

models.py: Database models for SQLite

mongo_models.py: Database models for MongoDB

views.py: Application logic and request handlers

forms.py: Form definitions

admin.py: Admin interface configuration

migrations/: Database migration files

Templates (Frontend)

templates/logs/: HTML templates including:

login.html: User authentication page

admin_dashboard.html: Administrative interface

daily_log.html: Daily logging interface

add_staff.html: Staff management page

Static Files
static/: Directory for Images and fonts.
