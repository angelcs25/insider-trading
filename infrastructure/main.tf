data "aws_caller_identity" "current" {}

locals {
  function_name = "${var.project}-ingest"
}

resource "aws_s3_bucket" "raw" {
  #Account ID suffix to keep name globally unique without random Strings
  bucket = "${var.project}-raw-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

#Lambda package

data "archive_file" "ingest" {
  type        = "zip"
  source_dir  = "${path.module}/../src/ingest"
  output_path = "${path.module}/build/ingest.zip"
  excludes    = ["__pycache__"]
}

#IAM Least Privilage

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ingest" {
  name               = "${local.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "ingest" {
  #Can only write under raw/source=sec-form4 
  statement {
    sid       = "WriteRawForm4"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.raw.arn}/raw/source=sec_form4/*"]
  }
  #Can only write logs to its own log group
  statement {
    sid       = "OwnLogs"
    actions   = ["logs:CreateStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.ingest.arn}:*"]
  }
}

resource "aws_iam_role_policy" "ingest" {
  name   = "ingest"
  role   = aws_iam_role.ingest.id
  policy = data.aws_iam_policy_document.ingest.json
}

#LOGS (created by us so we control retention)

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "ingest" {
  function_name    = local.function_name
  role             = aws_iam_role.ingest.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.ingest.output_path
  source_code_hash = data.archive_file.ingest.output_base64sha256
  timeout          = 300 #16 tickers at 5rq/s finishes in under a minute
  memory_size      = 256

  environment {
    variables = {
      BUCKET_NAME    = aws_s3_bucket.raw.bucket
      WATCHLIST      = join(",", var.watchlist)
      SEC_USER_AGENT = var.sec_user_agent
    }
  }

  depends_on = [aws_cloudwatch_log_group.ingest, aws_iam_role_policy.ingest]
}

#Daily schedule (EventBridge)

resource "aws_cloudwatch_event_rule" "daily" {
  name                = "${var.project}-daily"
  schedule_expression = var.schedule
}

resource "aws_cloudwatch_event_target" "daily" {
  rule = aws_cloudwatch_event_rule.daily.name
  arn  = aws_lambda_function.ingest.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily.arn
}
