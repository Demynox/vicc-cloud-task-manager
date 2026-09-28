import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class StorageError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BaseTaskStore:
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
        self.list_tasks()


class JsonTaskStore(BaseTaskStore):
    """Gemeinsame CRUD-Logik für JSON-basierte Backends."""

    def __init__(self):
        self._lock = threading.RLock()

    def _read(self):
        raise NotImplementedError

    def _write(self, tasks):
        raise NotImplementedError

    def list_tasks(self):
        with self._lock:
            tasks = self._read()
            return sorted(tasks, key=lambda item: item.get("created_at", ""), reverse=True)

    def create_task(self, title: str):
        with self._lock:
            tasks = self._read()
            now = utc_now_iso()
            task = {
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
        with self._lock:
            tasks = self._read()
            target = None

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
        with self._lock:
            tasks = self._read()
            remaining = [task for task in tasks if task.get("id") != task_id]

            if len(remaining) == len(tasks):
                return False

            self._write(remaining)
            return True


class LocalJsonTaskStore(JsonTaskStore):
    backend_name = "local-json"

    def __init__(self, data_file: str):
        super().__init__()
        self.path = Path(data_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self):
        try:
            if not self.path.exists():
                return []
            content = self.path.read_text(encoding="utf-8").strip()
            if not content:
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                raise StorageError("Lokale Datendatei enthält kein gültiges Aufgaben-Array.")
            return data
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Lokaler Datenspeicher konnte nicht gelesen werden: {exc}") from exc

    def _write(self, tasks):
        try:
            tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp_path.write_text(
                json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp_path.replace(self.path)
        except OSError as exc:
            raise StorageError(f"Lokaler Datenspeicher konnte nicht geschrieben werden: {exc}") from exc


class AzureBlobTaskStore(JsonTaskStore):
    backend_name = "azure-blob"

    def __init__(self, connection_string: str, container_name: str, blob_name: str):
        super().__init__()
        try:
            from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
            from azure.storage.blob import BlobServiceClient, ContentSettings
        except ImportError as exc:
            raise StorageError(
                "Azure Storage SDK fehlt. Bitte requirements.txt installieren."
            ) from exc

        self._resource_not_found = ResourceNotFoundError
        self._content_settings = ContentSettings(content_type="application/json")
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self._container = self._service.get_container_client(container_name)
        self._blob = self._container.get_blob_client(blob_name)

        try:
            self._container.create_container()
        except ResourceExistsError:
            pass
        except Exception as exc:
            raise StorageError(f"Azure Blob Container konnte nicht initialisiert werden: {exc}") from exc

    def _read(self):
        try:
            raw = self._blob.download_blob().readall()
            if not raw:
                return []
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, list):
                raise StorageError("Azure Blob enthält kein gültiges Aufgaben-Array.")
            return data
        except self._resource_not_found:
            return []
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Azure Blob konnte nicht gelesen werden: {exc}") from exc

    def _write(self, tasks):
        try:
            payload = json.dumps(tasks, ensure_ascii=False, indent=2).encode("utf-8")
            self._blob.upload_blob(payload, overwrite=True, content_settings=self._content_settings)
        except Exception as exc:
            raise StorageError(f"Azure Blob konnte nicht geschrieben werden: {exc}") from exc


def build_store() -> BaseTaskStore:
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()

    if backend == "local":
        data_file = os.getenv("DATA_FILE", "data/tasks.json")
        return LocalJsonTaskStore(data_file)

    if backend == "azure":
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
        if not connection_string:
            raise StorageError(
                "STORAGE_BACKEND=azure gesetzt, aber AZURE_STORAGE_CONNECTION_STRING fehlt."
            )

        container_name = os.getenv("AZURE_STORAGE_CONTAINER", "taskmanager")
        blob_name = os.getenv("AZURE_STORAGE_BLOB", "tasks.json")
        return AzureBlobTaskStore(connection_string, container_name, blob_name)

    raise StorageError(f"Unbekanntes STORAGE_BACKEND: {backend}")
