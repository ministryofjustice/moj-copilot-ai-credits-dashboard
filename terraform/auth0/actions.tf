resource "auth0_action_module" "config" {
  name    = "config"
  publish = true
  code    = file("${path.module}/actions_code/config.js")
}

resource "auth0_action_module" "validate_github_profile" {
  name    = "validate_github_profile"
  publish = true
  code    = file("${path.module}/actions_code/validate_github_profile.js")

  dependencies {
    name    = "axios"
    version = "1.18.1"
  }
}

resource "auth0_action" "enforce_github_identity" {
  code               = templatefile("${path.module}/actions_code/enforce_github_itdentity.js", {
    uri_namespace = "https://${var.webapp_domain}",
    environment = var.environment
  })
  deploy             = true
  name               = "Enforce GitHub Identity"
  runtime            = "node22"

  supported_triggers {
    id      = "post-login"
    version = "v3"
  }

  dependencies {
    name    = "auth0"
    version = "3.3.0"
  }

  modules {
    module_id         = auth0_action_module.config.id
    module_version_id = auth0_action_module.config.version_id
  }

  modules {
    module_id         = auth0_action_module.validate_github_profile.id
    module_version_id = auth0_action_module.validate_github_profile.version_id
  }

  secrets_wo_version = 1
  
  secrets_wo {
    name  = "AUTH0_DOMAIN"
    value = var.auth0_domain
  }

  secrets_wo {
    name  = "AUTH0_MANAGEMENT_CLIENT_ID"
    value = auth0_client.auth0_actions_management_client.client_id
  }

  secrets_wo {
    name  = "AUTH0_MANAGEMENT_CLIENT_SECRET"
    value = auth0_client_credentials.auth0_actions_management_client.client_secret
  }
}

resource "auth0_trigger_actions" "post_login" {
  trigger = "post-login"
  actions {
    display_name = "Enforce GitHub Identity"
    id           = auth0_action.enforce_github_identity.id
  }
}