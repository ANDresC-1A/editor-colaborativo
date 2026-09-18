#!/bin/bash
# Script de arranque para Azure App Service (Linux) con Django Channels + Daphne.
# Azure ejecuta este script como comando de inicio del contenedor.

set -e

echo "Instalando dependencias..."
pip install -r requirements.txt

echo "Aplicando migraciones..."
python manage.py migrate --noinput

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Iniciando Daphne (ASGI, soporta HTTP + WebSockets)..."
daphne -b 0.0.0.0 -p 8000 proyecto.asgi:application
