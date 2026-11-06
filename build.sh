
#!/usr/bin/env bash

set -o errexit

echo "Installing dependencies..."
python -m pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --clear --noinput

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Build completed successfully."
