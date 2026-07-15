resource "auth0_client" "auth0_terraform_provider" {
  allowed_clients                                      = []
  allowed_logout_urls                                  = []
  allowed_origins                                      = []
  app_type                                             = "non_interactive"
  async_approval_notification_channels                 = []
  callbacks                                            = []
  client_aliases                                       = []
  client_metadata                                      = {}
  compliance_level                                     = null
  cross_origin_auth                                    = false
  cross_origin_loc                                     = null
  custom_login_page                                    = null
  custom_login_page_on                                 = true
  description                                          = null
  encryption_key                                       = null
  form_template                                        = null
  grant_types                                          = ["client_credentials"]
  initiate_login_uri                                   = null
  is_first_party                                       = true
  is_token_endpoint_ip_header_trusted                  = false
  logo_uri                                             = null
  name                                                 = "Auth0 Terraform Provider"
  oidc_conformant                                      = true
  organization_discovery_methods                       = []
  organization_require_behavior                        = null
  organization_usage                                   = null
  redirection_policy                                   = null
  require_proof_of_possession                          = false
  require_pushed_authorization_requests                = false
  resource_server_identifier                           = null
  skip_non_verifiable_callback_uri_confirmation_prompt = "null"
  sso                                                  = true
  sso_disabled                                         = false
  third_party_security_mode                            = null
  web_origins                                          = []
  default_organization {
    disable         = true
    flows           = []
    organization_id = null
  }
  jwt_configuration {
    alg                 = "RS256"
    lifetime_in_seconds = 36000
    scopes              = {}
    secret_encoded      = false
  }
  native_social_login {
    apple {
      enabled = false
    }
    facebook {
      enabled = false
    }
    google {
      enabled = false
    }
  }
  refresh_token {
    expiration_type              = "non-expiring"
    idle_token_lifetime          = 2592000
    infinite_idle_token_lifetime = true
    infinite_token_lifetime      = true
    leeway                       = 0
    rotation_type                = "non-rotating"
    token_lifetime               = 31557600
  }
}

resource "auth0_client_credentials" "auth0_terraform_provider" {
  authentication_method    = "client_secret_post"
  client_id                = auth0_client.auth0_terraform_provider.client_id
}

resource "auth0_client_grant" "auth0_terraform_provider_client_grant" {
  allow_all_scopes            = false
  allow_any_organization      = false
  audience                    = "https://${var.auth0_domain}/api/v2/"
  authorization_details_types = []
  client_id                   = auth0_client.auth0_terraform_provider.client_id
  default_for                 = null
  organization_usage          = null
  scopes                      = ["read:client_grants", "create:client_grants", "delete:client_grants", "update:client_grants", "read:users", "update:users", "delete:users", "create:users", "read:users_app_metadata", "update:users_app_metadata", "delete:users_app_metadata", "create:users_app_metadata", "read:user_custom_blocks", "create:user_custom_blocks", "delete:user_custom_blocks", "create:user_tickets", "read:clients", "update:clients", "delete:clients", "create:clients", "read:client_keys", "update:client_keys", "delete:client_keys", "create:client_keys", "read:client_credentials", "update:client_credentials", "delete:client_credentials", "create:client_credentials", "read:connections", "update:connections", "delete:connections", "create:connections", "read:resource_servers", "update:resource_servers", "delete:resource_servers", "create:resource_servers", "read:device_credentials", "update:device_credentials", "delete:device_credentials", "create:device_credentials", "read:rules", "update:rules", "delete:rules", "create:rules", "read:rules_configs", "update:rules_configs", "delete:rules_configs", "read:hooks", "update:hooks", "delete:hooks", "create:hooks", "read:actions", "update:actions", "delete:actions", "create:actions", "read:email_provider", "update:email_provider", "delete:email_provider", "create:email_provider", "blacklist:tokens", "read:stats", "read:insights", "read:tenant_settings", "update:tenant_settings", "read:logs", "read:logs_users", "read:shields", "create:shields", "update:shields", "delete:shields", "read:anomaly_blocks", "delete:anomaly_blocks", "update:triggers", "read:triggers", "read:grants", "delete:grants", "read:guardian_factors", "update:guardian_factors", "read:guardian_enrollments", "delete:guardian_enrollments", "create:guardian_enrollment_tickets", "read:user_idp_tokens", "create:passwords_checking_job", "delete:passwords_checking_job", "read:custom_domains", "delete:custom_domains", "create:custom_domains", "update:custom_domains", "read:email_templates", "create:email_templates", "update:email_templates", "read:mfa_policies", "update:mfa_policies", "read:roles", "create:roles", "delete:roles", "update:roles", "read:prompts", "update:prompts", "read:branding", "update:branding", "delete:branding", "read:log_streams", "create:log_streams", "delete:log_streams", "update:log_streams", "create:signing_keys", "read:signing_keys", "update:signing_keys", "read:limits", "update:limits", "create:role_members", "read:role_members", "delete:role_members", "read:entitlements", "read:attack_protection", "update:attack_protection", "read:organizations_summary", "create:authentication_methods", "read:authentication_methods", "update:authentication_methods", "delete:authentication_methods", "read:organizations", "update:organizations", "create:organizations", "delete:organizations", "read:organization_discovery_domains", "update:organization_discovery_domains", "create:organization_discovery_domains", "delete:organization_discovery_domains", "create:organization_members", "read:organization_members", "delete:organization_members", "create:organization_connections", "read:organization_connections", "update:organization_connections", "delete:organization_connections", "create:organization_member_roles", "read:organization_member_roles", "delete:organization_member_roles", "create:organization_invitations", "read:organization_invitations", "delete:organization_invitations", "read:scim_config", "create:scim_config", "update:scim_config", "delete:scim_config", "create:scim_token", "read:scim_token", "delete:scim_token", "read:directory_provisionings", "create:directory_provisionings", "update:directory_provisionings", "delete:directory_provisionings", "delete:phone_providers", "create:phone_providers", "read:phone_providers", "update:phone_providers", "delete:phone_templates", "create:phone_templates", "read:phone_templates", "update:phone_templates", "create:encryption_keys", "read:encryption_keys", "update:encryption_keys", "delete:encryption_keys", "read:sessions", "update:sessions", "delete:sessions", "read:refresh_tokens", "update:refresh_tokens", "delete:refresh_tokens", "create:self_service_profiles", "read:self_service_profiles", "update:self_service_profiles", "delete:self_service_profiles", "create:sso_access_tickets", "delete:sso_access_tickets", "read:forms", "update:forms", "delete:forms", "create:forms", "read:flows", "update:flows", "delete:flows", "create:flows", "read:flows_vault", "read:flows_vault_connections", "update:flows_vault_connections", "delete:flows_vault_connections", "create:flows_vault_connections", "read:flows_executions", "delete:flows_executions", "read:connections_options", "update:connections_options", "read:self_service_profile_custom_texts", "update:self_service_profile_custom_texts", "create:network_acls", "update:network_acls", "read:network_acls", "delete:network_acls", "delete:vdcs_templates", "read:vdcs_templates", "create:vdcs_templates", "update:vdcs_templates", "create:custom_signing_keys", "read:custom_signing_keys", "update:custom_signing_keys", "delete:custom_signing_keys", "read:federated_connections_tokens", "delete:federated_connections_tokens", "create:user_attribute_profiles", "read:user_attribute_profiles", "update:user_attribute_profiles", "delete:user_attribute_profiles", "read:event_streams", "create:event_streams", "delete:event_streams", "update:event_streams", "read:event_deliveries", "update:event_deliveries", "create:connection_profiles", "read:connection_profiles", "update:connection_profiles", "delete:connection_profiles", "create:group_roles", "delete:group_roles", "read:user_effective_permissions", "read:user_effective_roles", "read:organization_member_effective_roles", "read:user_role_source_groups", "read:organization_member_role_source_groups", "read:user_permission_source_roles", "read:group_roles", "read:organization_groups", "create:organization_groups", "delete:organization_groups", "read:organization_group_roles", "create:organization_group_roles", "delete:organization_group_roles", "create:token_exchange_profiles", "read:token_exchange_profiles", "update:token_exchange_profiles", "delete:token_exchange_profiles", "read:organization_client_grants", "create:organization_client_grants", "delete:organization_client_grants", "read:organization_clients", "create:organization_clients", "update:organization_clients", "delete:organization_clients", "read:events", "create:rate_limit_policies", "read:rate_limit_policies", "update:rate_limit_policies", "delete:rate_limit_policies", "read:connections_keys", "update:connections_keys", "create:connections_keys", "create:groups", "read:groups", "update:groups", "delete:groups", "read:group_members"]
  subject_type                = "client"
}

resource "auth0_client" "auth0_actions_management_client" {
  allowed_clients                                      = []
  allowed_logout_urls                                  = []
  allowed_origins                                      = []
  app_type                                             = "non_interactive"
  async_approval_notification_channels                 = []
  callbacks                                            = []
  client_aliases                                       = []
  client_metadata                                      = {}
  compliance_level                                     = null
  cross_origin_auth                                    = false
  cross_origin_loc                                     = null
  custom_login_page                                    = null
  custom_login_page_on                                 = true
  description                                          = null
  encryption_key                                       = null
  form_template                                        = null
  grant_types                                          = ["client_credentials"]
  initiate_login_uri                                   = null
  is_first_party                                       = true
  is_token_endpoint_ip_header_trusted                  = false
  logo_uri                                             = null
  name                                                 = "Auth0-Actions-Management-Client"
  oidc_conformant                                      = true
  organization_discovery_methods                       = []
  organization_require_behavior                        = null
  organization_usage                                   = null
  redirection_policy                                   = null
  require_proof_of_possession                          = false
  require_pushed_authorization_requests                = false
  resource_server_identifier                           = null
  skip_non_verifiable_callback_uri_confirmation_prompt = "null"
  sso                                                  = false
  sso_disabled                                         = false
  third_party_security_mode                            = null
  web_origins                                          = []
  default_organization {
    disable         = true
    flows           = []
    organization_id = null
  }
  jwt_configuration {
    alg                 = "RS256"
    lifetime_in_seconds = 36000
    scopes              = {}
    secret_encoded      = false
  }
  refresh_token {
    expiration_type              = "non-expiring"
    idle_token_lifetime          = 2592000
    infinite_idle_token_lifetime = true
    infinite_token_lifetime      = true
    leeway                       = 0
    rotation_type                = "non-rotating"
    token_lifetime               = 31557600
  }
}

resource "auth0_client_credentials" "auth0_actions_management_client" {
  authentication_method    = "client_secret_post"
  client_id                = auth0_client.auth0_actions_management_client.client_id
}

resource "auth0_client_grant" "auth0_actions_management_client_grant" {
  allow_all_scopes            = false
  allow_any_organization      = false
  audience                    = "https://${var.auth0_domain}/api/v2/"
  authorization_details_types = []
  client_id                   = auth0_client.auth0_actions_management_client.client_id
  default_for                 = null
  organization_usage          = null
  scopes                      = ["read:users", "update:users", "read:user_idp_tokens"]
  subject_type                = "client"
}

resource "auth0_client" "copilot_credits" {
  allowed_clients                                      = []
  allowed_logout_urls                                  = var.environment == "development" ? 
    ["https://${var.webapp_domain}/", "https://localhost:4567/"] : ["https://${var.webapp_domain}/"]
  allowed_origins                                      = []
  app_type                                             = "regular_web"
  async_approval_notification_channels                 = []
  callbacks                                            = var.environment == "development" ? 
    ["https://localhost:4567/auth/callback", "https://${var.webapp_domain}/auth/callback"] : 
    ["https://${var.webapp_domain}/auth/callback"]
  client_aliases                                       = []
  client_metadata                                      = {}
  compliance_level                                     = null
  cross_origin_auth                                    = false
  cross_origin_loc                                     = null
  custom_login_page                                    = null
  custom_login_page_on                                 = true
  description                                          = null
  encryption_key                                       = null
  form_template                                        = null
  grant_types                                          = ["authorization_code", "implicit", "refresh_token", "client_credentials"]
  initiate_login_uri                                   = null
  is_first_party                                       = true
  is_token_endpoint_ip_header_trusted                  = false
  logo_uri                                             = null
  name                                                 = "CoPilot Credits"
  oidc_conformant                                      = true
  organization_discovery_methods                       = []
  organization_require_behavior                        = null
  organization_usage                                   = null
  redirection_policy                                   = null
  require_proof_of_possession                          = false
  require_pushed_authorization_requests                = false
  resource_server_identifier                           = null
  skip_non_verifiable_callback_uri_confirmation_prompt = "null"
  sso                                                  = true
  sso_disabled                                         = false
  third_party_security_mode                            = null
  web_origins                                          = var.environment == "development" ? 
    ["https://${var.webapp_domain}", "https://localhost:4567"] : ["https://${var.webapp_domain}"]
  default_organization {
    disable         = true
    flows           = []
    organization_id = null
  }
  jwt_configuration {
    alg                 = "RS256"
    lifetime_in_seconds = 36000
    scopes              = {}
    secret_encoded      = false
  }
  native_social_login {
    apple {
      enabled = false
    }
    facebook {
      enabled = false
    }
    google {
      enabled = false
    }
  }
  refresh_token {
    expiration_type              = "non-expiring"
    idle_token_lifetime          = 2592000
    infinite_idle_token_lifetime = true
    infinite_token_lifetime      = true
    leeway                       = 0
    rotation_type                = "non-rotating"
    token_lifetime               = 31557600
  }
}

resource "auth0_client_credentials" "copilot_credits" {
  authentication_method    = "client_secret_post"
  client_id                = auth0_client.copilot_credits.client_id
}