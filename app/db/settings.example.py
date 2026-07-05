# Copy this file to app/db/settings.py and fill in real values.
import os
DB_HOST = os.environ.get("DB_HOST", "your-rds-endpoint-here")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "your-password-here")
