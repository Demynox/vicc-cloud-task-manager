# VICC Cloud Task Manager

Kleine SaaS-Demoanwendung für die VICC-Praxisarbeit. Die Anwendung stellt eine Weboberfläche und eine REST-API zur Aufgabenverwaltung bereit.

## Funktionen

- Aufgaben erstellen
- Aufgaben anzeigen
- Aufgaben als erledigt/offen markieren
- Aufgaben löschen
- Filter für alle/offene/erledigte Aufgaben
- REST-API
- Health-Endpunkt
- Lokaler JSON-Speicher für Entwicklung
- Azure Blob Storage für den Cloud-Betrieb

## API

| Methode | Endpoint | Zweck |
|---|---|---|
| GET | `/api/health` | Zustand der Anwendung und des Speichers |
| GET | `/api/info` | Anwendungsversion und Storage-Backend |
| GET | `/api/tasks` | Aufgaben abrufen |
| POST | `/api/tasks` | Aufgabe erstellen |
| PATCH/PUT | `/api/tasks/{id}` | Aufgabe ändern |
| DELETE | `/api/tasks/{id}` | Aufgabe löschen |

## Lokal starten

```bash
cd app
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Danach: `http://localhost:8000`

Standardmässig wird `data/tasks.json` verwendet.

## Docker

```bash
cd app
docker build -t vicc-cloud-task-manager:1.0 .
docker run --rm -p 8000:8000 -e STORAGE_BACKEND=local vicc-cloud-task-manager:1.0
```

## Azure Storage

Für Azure wird die Anwendung mit folgenden Umgebungsvariablen gestartet:

```text
STORAGE_BACKEND=azure
AZURE_STORAGE_CONNECTION_STRING=<secret>
AZURE_STORAGE_CONTAINER=taskmanager
AZURE_STORAGE_BLOB=tasks.json
```

Der Storage Connection String darf nicht im Git-Repository gespeichert werden.

## Architekturbezug zur Praxisarbeit

Die Anwendung ist absichtlich klein gehalten, damit der Schwerpunkt auf der Cloud-Infrastruktur liegt. Der Container ist zustandslos; persistente Aufgabendaten werden im Azure Blob Storage abgelegt. Dadurch lassen sich Themen wie SaaS, Public Cloud, Containerisierung, Datenmanagement, Infrastructure as Code, Skalierbarkeit, Hochverfügbarkeit und Portierung direkt an der umgesetzten Lösung diskutieren.

## Docker Image über GitHub Actions bauen und veröffentlichen

Docker Desktop ist für den Build nicht erforderlich. Bei jedem Push auf `main`, der Dateien unter `app/` verändert, baut GitHub Actions das Docker Image auf einem GitHub Runner, startet es kurz, prüft die API und veröffentlicht das erfolgreiche Image anschliessend auf Docker Hub.

Workflow: `.github/workflows/docker-publish.yml`

### Voraussetzungen

1. Auf Docker Hub ein **öffentliches** Repository mit dem Namen `vicc-cloud-task-manager` erstellen.
2. Auf Docker Hub einen Personal Access Token mit Schreibberechtigung für das Repository erstellen.
3. In GitHub unter `Settings -> Secrets and variables -> Actions` zwei Repository-Secrets anlegen:
   - `DOCKERHUB_USERNAME` = Docker-Hub-Benutzername
   - `DOCKERHUB_TOKEN` = Docker-Hub-Personal-Access-Token

Der Token wird nicht im Repository gespeichert.

### Ablauf des Workflows

1. Source Code auschecken.
2. Docker Image aus `app/Dockerfile` bauen.
3. Container mit lokalem JSON-Backend starten.
4. `/api/health` prüfen.
5. Über die API einen Test-Task erstellen und wieder abrufen.
6. Bei erfolgreichem Test bei Docker Hub anmelden.
7. Images als `latest` und `1.0.<Run-Nummer>` veröffentlichen.

Der Workflow kann zusätzlich in GitHub unter `Actions -> Build, test and publish Docker image -> Run workflow` manuell gestartet werden.
