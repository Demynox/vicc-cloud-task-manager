import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from storage import StorageError, build_store

APP_NAME = "Cloud Task Manager"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
MAX_TITLE_LENGTH = 120

app = Flask(__name__)
store = build_store()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def error_response(message: str, status: int):
    return jsonify({"error": message}), status


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
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
    return render_template("index.html", app_name=APP_NAME, app_version=APP_VERSION)


@app.get("/api/health")
def health():
    try:
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
    return jsonify(
        {
            "application": APP_NAME,
            "version": APP_VERSION,
            "storage": store.backend_name,
        }
    )


@app.get("/api/tasks")
def get_tasks():
    try:
        tasks = store.list_tasks()
        return jsonify(tasks)
    except StorageError as exc:
        return error_response(str(exc), 503)


@app.post("/api/tasks")
def create_task():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()

    if not title:
        return error_response("Der Titel darf nicht leer sein.", 400)
    if len(title) > MAX_TITLE_LENGTH:
        return error_response(
            f"Der Titel darf maximal {MAX_TITLE_LENGTH} Zeichen lang sein.", 400
        )

    try:
        task = store.create_task(title)
        return jsonify(task), 201
    except StorageError as exc:
        return error_response(str(exc), 503)


@app.route("/api/tasks/<task_id>", methods=["PATCH", "PUT"])
def update_task(task_id: str):
    payload = request.get_json(silent=True) or {}

    title = payload.get("title")
    completed = payload.get("completed")

    if title is not None:
        title = str(title).strip()
        if not title:
            return error_response("Der Titel darf nicht leer sein.", 400)
        if len(title) > MAX_TITLE_LENGTH:
            return error_response(
                f"Der Titel darf maximal {MAX_TITLE_LENGTH} Zeichen lang sein.", 400
            )

    if completed is not None and not isinstance(completed, bool):
        return error_response("'completed' muss true oder false sein.", 400)

    if title is None and completed is None:
        return error_response("Keine änderbaren Felder übergeben.", 400)

    try:
        task = store.update_task(task_id, title=title, completed=completed)
        if task is None:
            return error_response("Aufgabe nicht gefunden.", 404)
        return jsonify(task)
    except StorageError as exc:
        return error_response(str(exc), 503)


@app.delete("/api/tasks/<task_id>")
def delete_task(task_id: str):
    try:
        deleted = store.delete_task(task_id)
        if not deleted:
            return error_response("Aufgabe nicht gefunden.", 404)
        return "", 204
    except StorageError as exc:
        return error_response(str(exc), 503)


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return error_response("API-Endpunkt nicht gefunden.", 404)
    return render_template("index.html", app_name=APP_NAME, app_version=APP_VERSION), 404


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
