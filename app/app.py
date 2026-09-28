"""Flask-Webanwendung und REST-API für den Cloud Task Manager.

Die Datei enthält die HTTP-Schicht der Anwendung. Die eigentliche
Datenhaltung ist in storage.py ausgelagert. Dadurch kann dieselbe
Anwendung lokal mit einer JSON-Datei oder in Azure mit Blob Storage
betrieben werden.
"""

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from storage import StorageError, build_store


# Grundlegende Anwendungsinformationen.
APP_NAME = "Cloud Task Manager"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
MAX_TITLE_LENGTH = 120

app = Flask(__name__)

# Das Storage-Backend wird anhand der Umgebungsvariable
# STORAGE_BACKEND beim Start der Anwendung ausgewählt.
store = build_store()


def utc_now_iso() -> str:
    """Liefert die aktuelle UTC-Zeit im ISO-8601-Format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def error_response(message: str, status: int):
    """Erzeugt ein einheitliches JSON-Fehlerformat für die REST-API."""
    return jsonify({"error": message}), status


@app.after_request
def add_security_headers(response):
    """Ergänzt grundlegende Security-Header für jede HTTP-Antwort."""

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"

    # Die Content-Security-Policy erlaubt nur Ressourcen,
    # die von der Anwendung selbst ausgeliefert werden.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    return response


@app.get("/")
def index():
    """Liefert die browserbasierte Benutzeroberfläche aus."""
    return render_template(
        "index.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
    )


@app.get("/api/health")
def health():
    """Prüft den Zustand der Anwendung und des Storage-Backends."""

    try:
        # Der Health Check greift auch auf das konfigurierte
        # Storage-Backend zu. So wird nicht nur Flask selbst geprüft.
        store.health_check()

        return jsonify(
            {
                "status": "ok",
                "application": APP_NAME,
                "version": APP_VERSION,
                "storage": store.backend_name,
                "timestamp": utc_now_iso(),
            }
        )

    except StorageError as exc:
        # Ist das Storage-Backend nicht erreichbar, meldet die
        # Anwendung den Status "degraded" und HTTP 503.
        return (
            jsonify(
                {
                    "status": "degraded",
                    "application": APP_NAME,
                    "version": APP_VERSION,
                    "storage": store.backend_name,
                    "error": str(exc),
                    "timestamp": utc_now_iso(),
                }
            ),
            503,
        )


@app.get("/api/info")
def info():
    """Gibt Basisinformationen über die laufende Anwendung zurück."""
    return jsonify(
        {
            "application": APP_NAME,
            "version": APP_VERSION,
            "storage": store.backend_name,
        }
    )


@app.get("/api/tasks")
def get_tasks():
    """Liefert alle gespeicherten Aufgaben als JSON zurück."""

    try:
        tasks = store.list_tasks()
        return jsonify(tasks)

    except StorageError as exc:
        return error_response(str(exc), 503)


@app.post("/api/tasks")
def create_task():
    """Erstellt eine neue Aufgabe aus einem JSON-Request."""

    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()

    # Eingaben werden vor dem Schreiben in das Storage-Backend validiert.
    if not title:
        return error_response("Der Titel darf nicht leer sein.", 400)

    if len(title) > MAX_TITLE_LENGTH:
        return error_response(
            f"Der Titel darf maximal {MAX_TITLE_LENGTH} Zeichen lang sein.",
            400,
        )

    try:
        task = store.create_task(title)
        return jsonify(task), 201

    except StorageError as exc:
        return error_response(str(exc), 503)


@app.route("/api/tasks/<task_id>", methods=["PATCH", "PUT"])
def update_task(task_id: str):
    """Aktualisiert Titel und/oder Erledigt-Status einer Aufgabe."""

    payload = request.get_json(silent=True) or {}

    title = payload.get("title")
    completed = payload.get("completed")

    # Ein neuer Titel wird nur übernommen, wenn er gültig ist.
    if title is not None:
        title = str(title).strip()

        if not title:
            return error_response("Der Titel darf nicht leer sein.", 400)

        if len(title) > MAX_TITLE_LENGTH:
            return error_response(
                f"Der Titel darf maximal {MAX_TITLE_LENGTH} Zeichen lang sein.",
                400,
            )

    # Der Status muss ein echtes JSON-Boolean sein.
    if completed is not None and not isinstance(completed, bool):
        return error_response("'completed' muss true oder false sein.", 400)

    # Mindestens ein veränderbares Feld muss vorhanden sein.
    if title is None and completed is None:
        return error_response("Keine änderbaren Felder übergeben.", 400)

    try:
        task = store.update_task(
            task_id,
            title=title,
            completed=completed,
        )

        if task is None:
            return error_response("Aufgabe nicht gefunden.", 404)

        return jsonify(task)

    except StorageError as exc:
        return error_response(str(exc), 503)


@app.delete("/api/tasks/<task_id>")
def delete_task(task_id: str):
    """Löscht eine Aufgabe anhand ihrer eindeutigen ID."""

    try:
        deleted = store.delete_task(task_id)

        if not deleted:
            return error_response("Aufgabe nicht gefunden.", 404)

        # HTTP 204 bedeutet, dass die Aktion erfolgreich war,
        # aber kein Response Body zurückgegeben wird.
        return "", 204

    except StorageError as exc:
        return error_response(str(exc), 503)


@app.errorhandler(404)
def not_found(_error):
    """Behandelt unbekannte Browser- und API-Pfade unterschiedlich."""

    if request.path.startswith("/api/"):
        return error_response("API-Endpunkt nicht gefunden.", 404)

    return render_template(
        "index.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
    ), 404


if __name__ == "__main__":
    # Dieser Block wird für den lokalen Entwicklungsbetrieb verwendet.
    # Im Docker-Container wird die Anwendung durch Gunicorn gestartet.
    port = int(os.getenv("PORT", "8000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
