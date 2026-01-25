variable "app_name" {
  type = string
}

variable "app_image" {
  type = string
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type    = number
  default = 2
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "target_group_arn" {
  type = string
}

variable "alb_security_group_id" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "container_environment" {
  type    = list(map(string))
  default = []
}

variable "container_secrets" {
  type    = list(map(string))
  default = []
}

variable "tags" {
  type = map(string)
}
