terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {

      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  #Remote state computer and github actions see the same infrastructure
  #bucket name is passed at init time: terraform init -backend-config="bucket=insider-trading-tfstate<account_id>"

  backend "s3" {
    key          = "insider-trading/infrastructure.tfstate"
    region       = "us-east-1"
    use_lockfile = true #S3-native state locking 
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}


