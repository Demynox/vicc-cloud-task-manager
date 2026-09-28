# VICC Cloud Task Manager

Der **VICC Cloud Task Manager** ist eine kleine cloudbasierte Demoanwendung für die VICC-Praxisarbeit.

Die Anwendung ermöglicht das Erstellen, Anzeigen, Aktualisieren und Löschen von Aufgaben über eine Weboberfläche und eine REST-API. Der Schwerpunkt des Projekts liegt auf Containerisierung, Public Cloud, persistenter Datenhaltung, Automatisierung und Infrastructure as Code.

## Architektur

```text
Benutzer
   |
   v
Azure Container Instance
   |
   v
Azure Blob Storage
   |
   +-- tasks.json

GitHub -> GitHub Actions -> Docker Hub -> Azure Container Instance

Terraform -> Microsoft Azure
```

Verwendete Technologien:

- Python / Flask
- Gunicorn
- Docker
- Docker Hub
- GitHub Actions
- Microsoft Azure
- Azure Container Instances
- Azure Blob Storage
- Terraform

Die Anwendung wird in der **Microsoft Azure Public Cloud** betrieben und aus Benutzersicht als **Software as a Service (SaaS)** bereitgestellt.

## Funktionen

- Aufgaben erstellen
- Aufgaben anzeigen
- Aufgaben als erledigt oder offen markieren
- Aufgaben löschen
- Aufgaben nach Status filtern
- REST-API
- Health Check
- lokales JSON-Backend für Entwicklung und Tests
- Azure Blob Storage für den Cloud-Betrieb

## Projektstruktur

```text
vicc-cloud-task-manager/
├── .github/
│   └── workflows/
│       └── docker-publish.yml
├── app/
│   ├── data/
│   ├── static/
│   ├── templates/
│   ├── app.py
│   ├── storage.py
│   ├── Dockerfile
│   └── requirements.txt
├── terraform/
│   ├── main.tf
│   ├── outputs.tf
│   ├── variables.tf
│   ├── versions.tf
│   └── .terraform.lock.hcl
├── .gitignore
└── README.md
```

## Lokal starten

Voraussetzungen:

- Python 3
- pip

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

Die Anwendung ist danach unter folgendem Endpunkt erreichbar:

```text
http://localhost:8000
```

Standardmässig wird lokal `data/tasks.json` verwendet.

## REST-API

| Methode | Endpoint | Beschreibung |
|---|---|---|
| `GET` | `/api/health` | Status von Anwendung und Storage |
| `GET` | `/api/info` | Anwendungsinformationen |
| `GET` | `/api/tasks` | Aufgaben abrufen |
| `POST` | `/api/tasks` | Aufgabe erstellen |
| `PATCH/PUT` | `/api/tasks/{id}` | Aufgabe aktualisieren |
| `DELETE` | `/api/tasks/{id}` | Aufgabe löschen |

Beispiel:

```bash
curl http://localhost:8000/api/health
```

## Docker

Öffentliches Docker-Hub-Repository:

```text
pakshetpanda/vicc-cloud-task-manager
```

Image lokal bauen:

```bash
cd app
docker build -t vicc-cloud-task-manager:local .
```

Container lokal starten:

```bash
docker run --rm   -p 8000:8000   -e STORAGE_BACKEND=local   vicc-cloud-task-manager:local
```

## GitHub Actions

Der Workflow unter

```text
.github/workflows/docker-publish.yml
```

baut und testet das Docker Image automatisch und veröffentlicht es anschliessend auf Docker Hub.

Dabei werden unter anderem folgende Schritte ausgeführt:

1. Docker Image bauen
2. Container starten
3. `/api/health` prüfen
4. REST-API mit einem Test-Task testen
5. Image als `latest` und `1.0.<Run-Nummer>` zu Docker Hub übertragen

Für Docker Hub werden die GitHub Secrets `DOCKERHUB_USERNAME` und `DOCKERHUB_TOKEN` verwendet.

## Azure Storage

Im Azure-Betrieb verwendet die Anwendung Azure Blob Storage.

Relevante Umgebungsvariablen:

```text
STORAGE_BACKEND=azure
AZURE_STORAGE_CONNECTION_STRING=<secret>
AZURE_STORAGE_CONTAINER=taskmanager
AZURE_STORAGE_BLOB=tasks.json
```

Der Storage Connection String wird nicht im Repository gespeichert.

## Azure Deployment mit Terraform

Die Infrastruktur wird mit Terraform bereitgestellt.

Erstellt werden:

- Resource Group `rg-vicc-taskmanager`
- Azure Container Instance `aci-vicc-taskmanager`
- Storage Account `stvicctaskmanager01`
- Blob Container `taskmanager`

Deployment:

```bash
cd terraform
terraform init
terraform validate
terraform plan
terraform apply
```

Nach erfolgreichem Deployment können die Endpunkte mit Terraform ausgegeben werden:

```bash
terraform output -raw task_manager_url
terraform output -raw api_health_url
```

## Datenhaltung

Die Anwendung unterstützt zwei Storage-Backends:

- `LocalJsonTaskStore` für lokale Entwicklung
- `AzureBlobTaskStore` für den Cloud-Betrieb

In Azure werden die Aufgaben im Blob `tasks.json` gespeichert.

Die Persistenz wurde getestet, indem die Azure Container Instance gestoppt und erneut gestartet wurde. Die zuvor gespeicherten Aufgaben waren danach weiterhin verfügbar.

## Hinweise zur Architektur

Der aktuelle IST-Zustand verwendet eine einzelne Azure Container Instance.

Dadurch besteht auf Applikationsebene keine Redundanz. Für eine horizontale Skalierung wären mehrere Instanzen und eine dafür geeignete Datenhaltung erforderlich, da das aktuelle einzelne JSON-Dokument nicht für parallele Schreibzugriffe mehrerer Instanzen ausgelegt ist.

Durch die Containerisierung ist die Anwendung grundsätzlich auf andere Container-Laufzeitumgebungen portierbar. Die Terraform-Konfiguration ist jedoch Azure-spezifisch.
