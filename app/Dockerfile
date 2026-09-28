# Schlankes offizielles Python-Image als Basis.
FROM python:3.12-slim


# Python soll keine .pyc-Dateien erstellen und Logs
# direkt an stdout/stderr weitergeben.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000


# Arbeitsverzeichnis innerhalb des Containers.
WORKDIR /app


# Dependencies werden separat kopiert, damit Docker
# den Layer bei unveränderten Requirements wiederverwenden kann.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Anwendungscode in den Container kopieren.
COPY . .


# Die Anwendung läuft aus Sicherheitsgründen nicht als root.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser


# Die Anwendung ist im Container auf Port 8000 erreichbar.
EXPOSE 8000


# Gunicorn startet die Flask-Anwendung für den Containerbetrieb.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "30", "--access-logfile", "-", "app:app"]
