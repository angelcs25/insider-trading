output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "function_name" {
  value = aws_lambda_function.ingest.function_name
}

output "log_group" {
  value = aws_cloudwatch_log_group.ingest.name
}
