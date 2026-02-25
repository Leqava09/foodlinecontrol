import os
import django
import psycopg2
from psycopg2 import sql

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')

# Get DB credentials from settings
from django.conf import settings

db_config = settings.DATABASES['default']
db_name = db_config['NAME']
db_user = db_config['USER']
db_password = db_config['PASSWORD']
db_host = db_config['HOST']
db_port = db_config['PORT']

print(f"Database: {db_name}")
print(f"User: {db_user}")
print(f"Host: {db_host}")

# Connect to PostgreSQL server (using 'postgres' database)
try:
    conn = psycopg2.connect(
        database='postgres',
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Drop existing database
    print(f"\nDropping database {db_name}...")
    try:
        cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} ;").format(
            sql.Identifier(db_name)
        ))
        print("✓ Database dropped")
    except Exception as e:
        print(f"Error dropping: {e}")
    
    # Create fresh database
    print(f"Creating fresh database {db_name}...")
    cursor.execute(sql.SQL("CREATE DATABASE {} ;").format(
        sql.Identifier(db_name)
    ))
    print("✓ Database created")
    
    cursor.close()
    conn.close()
    
    print("\n✓ Fresh database ready!")
    
except Exception as e:
    print(f"Error: {e}")
