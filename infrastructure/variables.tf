variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "insider-trading"
}

variable "sec_user_agent" {
  description = "SEC requires User-agent with email"
  type        = string

  validation {
    condition     = can(regex("@", var.sec_user_agent))
    error_message = "sec_user_agent must include a contact email address."
  }
}

variable "watchlist" {
  description = "Tickers whose insider trades to collect"
  type        = list(string)
  default = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
    "JPM", "V", "NFLX", "AMD", "PLTR", "COIN", "CRM", "ORCL",
  ]
}

variable "schedule" {
  description = "When to run (UTC). Default: 10:00 UTC daily, after EDGAR's overnight processing."
  type        = string
  default     = "cron(0 10 * * ? *)"
}

