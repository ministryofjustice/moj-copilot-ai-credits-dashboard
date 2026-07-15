resource "auth0_tenant" "tenant" {
  acr_values_supported                                 = []
  allow_organization_name_in_authentication_api        = false
  allowed_logout_urls                                  = []
  client_id_metadata_document_supported                = false
  customize_mfa_in_postlogin_action                    = false
  default_audience                                     = null
  default_directory                                    = null
  default_redirection_uri                              = null
  disable_acr_values_supported                         = true
  dynamic_client_registration_security_mode            = null
  enabled_locales                                      = ["en"]
  ephemeral_session_lifetime                           = 72
  friendly_name                                        = null
  idle_ephemeral_session_lifetime                      = 24
  idle_session_lifetime                                = 72
  phone_consolidated_experience                        = false
  picture_url                                          = null
  pushed_authorization_requests_supported              = false
  resource_parameter_profile                           = "compatibility"
  sandbox_version                                      = "22"
  session_lifetime                                     = 168
  skip_non_verifiable_callback_uri_confirmation_prompt = "null"
  support_email                                        = null
  support_url                                          = null
  flags {
    allow_legacy_delegation_grant_types    = true
    allow_legacy_ro_grant_types            = true
    allow_legacy_tokeninfo_endpoint        = false
    dashboard_insights_view                = false
    dashboard_log_streams_next             = false
    disable_clickjack_protection_headers   = false
    disable_fields_map_fix                 = false
    disable_management_api_sms_obfuscation = true
    enable_adfs_waad_email_verification    = false
    enable_apis_section                    = false
    enable_client_connections              = true
    enable_custom_domain_in_emails         = false
    enable_dynamic_client_registration     = false
    enable_idtoken_api2                    = false
    enable_legacy_logs_search_v2           = false
    enable_legacy_profile                  = false
    enable_pipeline2                       = true
    enable_public_signup_user_exists_error = false
    enable_sso                             = true
    mfa_show_factor_list_on_enrollment     = false
    no_disclose_enterprise_connections     = false
    remove_alg_from_jwks                   = false
    revoke_refresh_token_grant             = false
    use_scope_descriptions_for_consent     = false
  }
  mtls {
    disable                 = true
    enable_endpoint_aliases = false
  }
  oidc_logout {
    rp_logout_end_session_endpoint_discovery = true
  }
  session_cookie {
    mode = null
  }
  sessions {
    oidc_logout_prompt_enabled = true
  }
}

resource "auth0_resource_server" "auth0_management_api" {
  allow_offline_access                            = false
  allow_online_access                             = false
  allow_online_access_with_ephemeral_sessions     = false
  consent_policy                                  = "null"
  enforce_policies                                = null
  identifier                                      = "https://${var.auth0_domain}/api/v2/"
  name                                            = "Auth0 Management API"
  signing_alg                                     = "RS256"
  signing_secret                                  = null
  skip_consent_for_verifiable_first_party_clients = false
  token_dialect                                   = null
  token_lifetime                                  = 86400
  token_lifetime_for_web                          = 7200
  verification_location                           = null
  authorization_details {
    disable = true
    type    = null
  }
  proof_of_possession {
    disable      = true
    mechanism    = null
    required     = false
    required_for = null
  }
  subject_type_authorization {
    client {
      policy = "require_client_grant"
    }
    user {
      policy = "allow_all"
    }
  }
  token_encryption {
    disable = true
    format  = null
  }
}

resource "auth0_attack_protection" "attack_protection" {
  bot_detection {
    allowlist                       = []
    bot_detection_level             = "medium"
    challenge_password_policy       = "never"
    challenge_password_reset_policy = "never"
    challenge_passwordless_policy   = "never"
    monitoring_mode_enabled         = false
  }
  breached_password_detection {
    admin_notification_frequency = []
    enabled                      = false
    method                       = "standard"
    shields                      = []
    pre_change_password {
      shields = []
    }
    pre_user_registration {
      shields = []
    }
  }
  brute_force_protection {
    allowlist    = []
    enabled      = true
    max_attempts = 10
    mode         = "count_per_identifier_and_ip"
    shields      = ["block", "user_notification"]
  }
  captcha {
    active_provider_id = "auth_challenge"
    arkose {
      client_subdomain = "client-api"
      fail_open        = false
      secret           = null # sensitive
      site_key         = ""
      verify_subdomain = "verify-api"
    }
    auth_challenge {
      fail_open = false
    }
    friendly_captcha {
      secret   = null # sensitive
      site_key = ""
    }
    hcaptcha {
      secret   = null # sensitive
      site_key = ""
    }
    recaptcha_enterprise {
      api_key    = null # sensitive
      project_id = ""
      site_key   = ""
    }
    recaptcha_v2 {
      secret   = null # sensitive
      site_key = ""
    }
  }
  suspicious_ip_throttling {
    allowlist = []
    enabled   = true
    shields   = ["admin_notification", "block"]
    pre_login {
      max_attempts = 100
      rate         = 864000
    }
    pre_user_registration {
      max_attempts = 50
      rate         = 1200
    }
  }
}

resource "auth0_guardian" "guardian" {
  email         = false
  otp           = false
  policy        = "never"
  recovery_code = false
  duo {
    enabled         = false
    hostname        = null
    integration_key = null
    secret_key      = null # sensitive
  }
  phone {
    enabled       = false
    message_types = []
  }
  push {
    enabled  = false
    provider = null
  }
  webauthn_platform {
    enabled                  = false
    override_relying_party   = false
    relying_party_identifier = null
  }
  webauthn_roaming {
    enabled                  = false
    override_relying_party   = false
    relying_party_identifier = null
    user_verification        = null
  }
}