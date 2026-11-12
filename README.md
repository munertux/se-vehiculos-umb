# Sistema experto de diagnóstico de fallas en vehículos

Proyecto de la asignatura Sistemas Expertos, Universidad Manuela Beltrán (Ingeniería de Software).
Autores: Sebastián Felipe Araque Pérez, Luilly Steven Perea Vivas y Thomas Leonardo Castillo Castro.

Aplicación web en Flask con PostgreSQL. Tiene tres capas: presentación (`main.py`, `app/templates`, `app/static`),
lógica (`app/logica`: motor de inferencia, memoria de trabajo y servicio de diagnóstico) y datos (`app/datos`).

## Base de datos

```bash
createdb sistema_experto_vehiculos
psql -d sistema_experto_vehiculos -f sql/01_esquema.sql
psql -d sistema_experto_vehiculos -f sql/02_conocimiento.sql
```

## Ejecución local

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://usuario:clave@localhost:5432/sistema_experto_vehiculos?sslmode=disable"
export SE_CLAVE_HASH="<hash generado con werkzeug.security.generate_password_hash>"
export COOKIE_SEGURA=0
python main.py   # http://127.0.0.1:8000
```

En Azure App Service se arranca con `gunicorn --bind=0.0.0.0 --timeout 600 --workers 1 main:app`.
