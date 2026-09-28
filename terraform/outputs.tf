output "task_manager_url" {
  description = "Public URL of the Cloud Task Manager"
  value       = "http://${azurerm_container_group.taskmanager.fqdn}:8000"
}

output "api_health_url" {
  description = "Health endpoint"
  value       = "http://${azurerm_container_group.taskmanager.fqdn}:8000/api/health"
}

output "resource_group_name" {
  value = azurerm_resource_group.taskmanager.name
}