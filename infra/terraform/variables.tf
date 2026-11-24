variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name. Only \"production\" turns on Multi-AZ and deletion protection for the database"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be dev, staging or production."
  }
}

variable "vpc_id" {
  description = "VPC ID (optional, will create if not provided)"
  type        = string
  default     = ""
}

variable "app_image" {
  description = "Docker image for the application"
  type        = string
  default     = "renewal-desk:latest"
}

variable "app_cpu" {
  description = "CPU units for ECS task"
  type        = number
  default     = 512
}

variable "app_memory" {
  description = "Memory for ECS task"
  type        = number
  default     = 1024
}

variable "app_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "RDS max allocated storage in GB"
  type        = number
  default     = 200
}
