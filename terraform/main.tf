# Gemeinsame Resource Group für sämtliche Ressourcen
# des Cloud Task Managers.
resource "azurerm_resource_group" "taskmanager" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    project = "VICC Cloud Task Manager"
    purpose = "Praxisarbeit"
  }
}


# Persistenter Azure Storage Account für die Task-Daten.
# Standard/LRS wurde gewählt, um die Kosten der Demo gering zu halten.
resource "azurerm_storage_account" "taskmanager" {
  name                     = "stvicctaskmanager01"
  resource_group_name      = azurerm_resource_group.taskmanager.name
  location                 = azurerm_resource_group.taskmanager.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # Der direkte Zugriff auf den Storage Account ist nur über HTTPS erlaubt.
  https_traffic_only_enabled = true

  tags = {
    project = "VICC Cloud Task Manager"
    purpose = "Praxisarbeit"
  }
}


# Private Blob-Storage-Ablage für die JSON-Datei der Tasks.
resource "azurerm_storage_container" "taskmanager" {
  name                  = "taskmanager"
  storage_account_id    = azurerm_storage_account.taskmanager.id
  container_access_type = "private"
}


# Azure Container Instance für die eigentliche Webanwendung.
resource "azurerm_container_group" "taskmanager" {
  name                = "aci-vicc-taskmanager"
  location            = azurerm_resource_group.taskmanager.location
  resource_group_name = azurerm_resource_group.taskmanager.name

  # Die Anwendung erhält für die Praxisarbeit einen öffentlichen Endpunkt.
  ip_address_type = "Public"
  dns_name_label  = "vicc-taskmanager-2026"

  os_type        = "Linux"
  restart_policy = "Always"

  container {
    name  = "cloud-task-manager"
    image = var.container_image

    # Kleine Ressourcenkonfiguration zur Minimierung der Betriebskosten.
    cpu    = "1"
    memory = "1"

    # Gunicorn stellt die Anwendung auf Port 8000 bereit.
    ports {
      port     = 8000
      protocol = "TCP"
    }

    # Nicht sensitive Konfiguration des Azure-Storage-Backends.
    environment_variables = {
      STORAGE_BACKEND         = "azure"
      AZURE_STORAGE_CONTAINER = azurerm_storage_container.taskmanager.name
      AZURE_STORAGE_BLOB      = "tasks.json"
    }

    # Der Connection String wird als sensitive Environment Variable
    # an den Container übergeben und nicht als normale Variable angezeigt.
    secure_environment_variables = {
      AZURE_STORAGE_CONNECTION_STRING = azurerm_storage_account.taskmanager.primary_connection_string
    }
  }

  tags = {
    project = "VICC Cloud Task Manager"
    purpose = "Praxisarbeit"
  }
}
