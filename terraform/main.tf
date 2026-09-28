resource "azurerm_resource_group" "taskmanager" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    project = "VICC Cloud Task Manager"
    purpose = "Praxisarbeit"
  }
}

resource "azurerm_storage_account" "taskmanager" {
  name                     = "stvicctaskmanager01"
  resource_group_name      = azurerm_resource_group.taskmanager.name
  location                 = azurerm_resource_group.taskmanager.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  https_traffic_only_enabled = true

  tags = {
    project = "VICC Cloud Task Manager"
    purpose = "Praxisarbeit"
  }
}

resource "azurerm_storage_container" "taskmanager" {
  name                  = "taskmanager"
  storage_account_id    = azurerm_storage_account.taskmanager.id
  container_access_type = "private"
}

resource "azurerm_container_group" "taskmanager" {
  name                = "aci-vicc-taskmanager"
  location            = azurerm_resource_group.taskmanager.location
  resource_group_name = azurerm_resource_group.taskmanager.name
  ip_address_type     = "Public"
  dns_name_label      = "vicc-taskmanager-2026"
  os_type             = "Linux"
  restart_policy      = "Always"

  container {
    name   = "cloud-task-manager"
    image  = var.container_image
    cpu    = "1"
    memory = "1"

    ports {
      port     = 8000
      protocol = "TCP"
    }

    environment_variables = {
      STORAGE_BACKEND         = "azure"
      AZURE_STORAGE_CONTAINER = azurerm_storage_container.taskmanager.name
      AZURE_STORAGE_BLOB      = "tasks.json"
    }

    secure_environment_variables = {
      AZURE_STORAGE_CONNECTION_STRING = azurerm_storage_account.taskmanager.primary_connection_string
    }
  }

  tags = {
    project = "VICC Cloud Task Manager"
    purpose = "Praxisarbeit"
  }
}