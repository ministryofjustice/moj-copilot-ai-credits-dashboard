resource "auth0_action" "enforce_github_identity" {
  code               = templatefile("${path.module}/actions_code/enforce_github_itdentity.js", {
    uri_namespace = "https://${var.webapp_domain}"
  })
  deploy             = true
  name               = "Enforce GitHub Identity"
  runtime            = "node22"

  supported_triggers {
    id      = "post-login"
    version = "v3"
  }

  dependencies {
    name    = "axios"
    version = "1.18.1"
  }

  dependencies {
    name    = "auth0"
    version = "3.3.0"
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