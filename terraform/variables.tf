variable "location" {
  description = "Azure region for the VICC Task Manager"
  type        = string
  default     = "germanywestcentral"
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
  default     = "rg-vicc-taskmanager"
}

variable "container_image" {
  description = "Docker image of the Cloud Task Manager"
  type        = string
  default     = "pakshetpanda/vicc-cloud-task-manager:1.0.1"
}