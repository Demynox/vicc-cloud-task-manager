"""Storage-Abstraktion für den Cloud Task Manager.

Die Anwendung unterstützt zwei Speicher-Backends:

1. Lokale JSON-Datei für Entwicklung und Tests.
2. Azure Blob Storage für den Betrieb in Microsoft Azure.

Die CRUD-Logik ist für beide Backends identisch und wird in
JsonTaskStore zentral implementiert.
"""

import json
import os
import threading
import uuid

from datetime import datetime, timezone
from pathlib import Path

class StorageError(RuntimeError):
    """Einheitlicher Fehler für Probleme mit dem Datenspeicher."""
    pass


def utc_now_iso() -> str:
    """Liefert die aktuelle UTC-Zeit im ISO-8601-Format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BaseTaskStore:
    """Definiert die Schnittstelle, die jedes Storage-Backend bereitstellt."""

    backend_name = "unknown"

    def list_tasks(self):
        raise NotImplementedError

    def create_task(self, title: str):
        raise NotImplementedError

    def update_task(self, task_id: str, title=None, completed=None):
        raise NotImplementedError

    def delete_task(self, task_id: str):
        raise NotImplementedError

    def health_check(self):
        """Prüft das Backend durch einen einfachen Lesezugriff."""
        self.list_tasks()


class JsonTaskStore(BaseTaskStore):
    """Gemeinsame CRUD-Logik für JSON-basierte Storage-Backends."""

    def __init__(self):
        # Der Lock verhindert parallele Schreibzugriffe innerhalb
        # derselben laufenden Applikationsinstanz.
        self._lock = threading.RLock()

    def _read(self):
        """Wird vom jeweiligen Storage-Backend implementiert."""
        raise NotImplementedError

    def _write(self, tasks):
        """Wird vom jeweiligen Storage-Backend implementiert."""
        raise NotImplementedError

    def list_tasks(self):
        """Liest alle Tasks und sortiert die neusten zuerst."""

        with self._lock:
            tasks = self._read()

            return sorted(
                tasks,
                key=lambda item: item.get("created_at", ""),
                reverse=True,
            )

    def create_task(self, title: str):
        """Erstellt einen neuen Task mit UUID und Zeitstempeln."""

        with self._lock:
            tasks = self._read()
            now = utc_now_iso()

            task = {
                # UUID verhindert Abhängigkeiten von fortlaufenden IDs.
                "id": str(uuid.uuid4()),
                "title": title,
                "completed": False,
                "created_at": now,
                "updated_at": now,
            }

            tasks.append(task)
            self._write(tasks)

            return task

    def update_task(self, task_id: str, title=None, completed=None):
        """Aktualisiert einen bereits vorhandenen Task."""

        with self._lock:
            tasks = self._read()
            target = None

            # Der Task wird anhand seiner eindeutigen UUID gesucht.
            for task in tasks:
                if task.get("id") == task_id:
                    target = task
                    break

            if target is None:
                return None

            if title is not None:
                target["title"] = title

            if completed is not None:
                target["completed"] = completed

            target["updated_at"] = utc_now_iso()

            self._write(tasks)

            return target

    def delete_task(self, task_id: str):
        """Entfernt einen Task anhand seiner ID."""

        with self._lock:
            tasks = self._read()

            remaining = [
                task
                for task in tasks
                if task.get("id") != task_id
            ]

            # Wenn gleich viele Elemente vorhanden sind,
            # wurde keine passende ID gefunden.
            if len(remaining) == len(tasks):
                return False

            self._write(remaining)

            return True


class LocalJsonTaskStore(JsonTaskStore):
    """Speichert die Tasks lokal in einer JSON-Datei."""

    backend_name = "local-json"

    def __init__(self, data_file: str):
        super().__init__()

        self.path = Path(data_file)

        # Das Datenverzeichnis wird automatisch angelegt,
        # falls es noch nicht existiert.
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _read(self):
        """Liest die lokale JSON-Datei."""

        try:
            # Eine noch nicht vorhandene Datei entspricht
            # einer leeren Aufgabenliste.
            if not self.path.exists():
                return []

            content = self.path.read_text(
                encoding="utf-8",
            ).strip()

            if not content:
                return []

            data = json.loads(content)

            if not isinstance(data, list):
                raise StorageError(
                    "Lokale Datendatei enthält kein gültiges Aufgaben-Array."
                )

            return data

        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(
                f"Lokaler Datenspeicher konnte nicht gelesen werden: {exc}"
            ) from exc

    def _write(self, tasks):
        """Schreibt alle Tasks atomar in die lokale JSON-Datei."""

        try:
            # Zuerst wird in eine temporäre Datei geschrieben.
            # Anschliessend ersetzt diese die bestehende Datei.
            tmp_path = self.path.with_suffix(
                self.path.suffix + ".tmp"
            )

            tmp_path.write_text(
                json.dumps(
                    tasks,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            tmp_path.replace(self.path)

        except OSError as exc:
            raise StorageError(
                f"Lokaler Datenspeicher konnte nicht geschrieben werden: {exc}"
            ) from exc


class AzureBlobTaskStore(JsonTaskStore):
    """Speichert die Aufgaben als JSON-Dokument in Azure Blob Storage."""

    backend_name = "azure-blob"

    def __init__(
        self,
        connection_string: str,
        container_name: str,
        blob_name: str,
    ):
        super().__init__()

        # Azure-Abhängigkeiten werden erst geladen, wenn das
        # Azure-Backend tatsächlich verwendet wird.
        try:
            from azure.core.exceptions import (
                ResourceExistsError,
                ResourceNotFoundError,
            )
            from azure.storage.blob import (
                BlobServiceClient,
                ContentSettings,
            )

        except ImportError as exc:
            raise StorageError(
                "Azure Storage SDK fehlt. Bitte requirements.txt installieren."
            ) from exc

        self._resource_not_found = ResourceNotFoundError

        # Der Blob wird ausdrücklich als JSON-Dokument gekennzeichnet.
        self._content_settings = ContentSettings(
            content_type="application/json"
        )

        self._service = BlobServiceClient.from_connection_string(
            connection_string
        )

        self._container = self._service.get_container_client(
            container_name
        )

        self._blob = self._container.get_blob_client(
            blob_name
        )

        # Der Container wird bei Bedarf angelegt.
        # In der Azure-Umgebung wird er normalerweise bereits
        # durch Terraform bereitgestellt.
        try:
            self._container.create_container()

        except ResourceExistsError:
            pass

        except Exception as exc:
            raise StorageError(
                f"Azure Blob Container konnte nicht initialisiert werden: {exc}"
            ) from exc

    def _read(self):
        """Liest das JSON-Dokument aus Azure Blob Storage."""

        try:
            raw = self._blob.download_blob().readall()

            if not raw:
                return []

            data = json.loads(
                raw.decode("utf-8")
            )

            if not isinstance(data, list):
                raise StorageError(
                    "Azure Blob enthält kein gültiges Aufgaben-Array."
                )

            return data

        # Existiert tasks.json noch nicht, wird mit
        # einer leeren Aufgabenliste gestartet.
        except self._resource_not_found:
            return []

        except StorageError:
            raise

        except Exception as exc:
            raise StorageError(
                f"Azure Blob konnte nicht gelesen werden: {exc}"
            ) from exc

    def _write(self, tasks):
        """Schreibt die vollständige Aufgabenliste in Azure Blob Storage."""

        try:
            payload = json.dumps(
                tasks,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")

            # overwrite=True ersetzt den bestehenden Blob.
            self._blob.upload_blob(
                payload,
                overwrite=True,
                content_settings=self._content_settings,
            )

        except Exception as exc:
            raise StorageError(
                f"Azure Blob konnte nicht geschrieben werden: {exc}"
            ) from exc


def build_store() -> BaseTaskStore:
    """Erstellt das Storage-Backend anhand der Umgebungsvariablen."""

    backend = os.getenv(
        "STORAGE_BACKEND",
        "local",
    ).strip().lower()

    # Standardmässig wird der lokale JSON-Speicher verwendet.
    # Dies eignet sich für Entwicklung und automatisierte Tests.
    if backend == "local":
        data_file = os.getenv(
            "DATA_FILE",
            "data/tasks.json",
        )

        return LocalJsonTaskStore(
            data_file
        )

    # In Azure wird Blob Storage als persistenter
    # Datenspeicher verwendet.
    if backend == "azure":
        connection_string = os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING",
            "",
        ).strip()

        if not connection_string:
            raise StorageError(
                "STORAGE_BACKEND=azure gesetzt, "
                "aber AZURE_STORAGE_CONNECTION_STRING fehlt."
            )

        container_name = os.getenv(
            "AZURE_STORAGE_CONTAINER",
            "taskmanager",
        )

        blob_name = os.getenv(
            "AZURE_STORAGE_BLOB",
            "tasks.json",
        )

        return AzureBlobTaskStore(
            connection_string,
            container_name,
            blob_name,
        )

    raise StorageError(
        f"Unbekanntes STORAGE_BACKEND: {backend}"
    )
