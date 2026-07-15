variable "auth0_domain" {
  description = "value of the Auth0 domain"
  default     = ""
  type        = string
  sensitive   = true
}

variable "auth0_client_id" {
  description = "value of the Auth0 client id"
  default     = ""
  type        = string
  sensitive   = true
}

variable "auth0_client_secret" {
  description = "value of the Auth0 client secret"
  default     = ""
  type        = string
  sensitive   = true
}

variable "github_oauth_client_id" {
  description = "value of the GitHub OAuth client id"
  default     = ""
  type        = string
  sensitive   = true
}

variable "github_oauth_client_secret" {
  description = "value of the GitHub OAuth client secret"
  default     = ""
  type        = string
  sensitive   = true
}

variable "webapp_domain" {
  description = "Domain name of web application"
  default     = ""
  type        = string
  sensitive   = false
}

variable "environment" {
  description = "Application environment"
  default     = ""
  type        = string
  sensitive   = false
}