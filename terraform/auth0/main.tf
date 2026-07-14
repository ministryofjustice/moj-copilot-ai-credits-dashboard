terraform {
  backend "s3" {
    acl     = "private"
    bucket  = var.tf_state_s3_bucket_name
    encrypt = true
    use_lockfile = true
    key     = "terraform/auth0/copilot-credits-dev/terraform.tfstate"
    region  = "eu-west-2"
  }
  required_providers {
    auth0 = {
      source  = "auth0/auth0"
      version = "1.52.0"
    }
  }
  required_version = "~> 1.15.8"
}

provider "auth0" {
  domain        = var.auth0_domain
  client_id     = var.auth0_client_id
  client_secret = var.auth0_client_secret
}