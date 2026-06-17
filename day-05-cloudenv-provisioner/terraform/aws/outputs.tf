output "instance_id" {
  value = aws_instance.env.id
}

output "bucket_name" {
  value = aws_s3_bucket.env_bucket.bucket
}

output "role_arn" {
  value = aws_iam_role.env_role.arn
}

output "cost_alert_topic_arn" {
  value = aws_sns_topic.cost_alerts.arn
}
