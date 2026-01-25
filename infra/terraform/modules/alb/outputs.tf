output "target_group_arn" {
  value = aws_lb_target_group.main.arn
}

output "security_group_id" {
  value = aws_security_group.alb.id
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}
