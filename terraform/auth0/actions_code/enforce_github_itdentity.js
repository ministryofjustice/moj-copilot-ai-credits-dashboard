const ManagementClient = require('auth0').ManagementClient;

exports.onExecutePostLogin = async (event, api) => {
  if (event.connection.strategy !== 'github') return;

  try {
    const management = new ManagementClient({
      domain: event.secrets.AUTH0_DOMAIN,
      clientId: event.secrets.AUTH0_MANAGEMENT_CLIENT_ID,
      clientSecret: event.secrets.AUTH0_MANAGEMENT_CLIENT_SECRET,
    });

    const userProfile = await management.users.get({ id: event.user.user_id });
    const githubIdentity = userProfile.identities.find(id => id.provider === 'github');
    const access_token = githubIdentity.access_token
    const githubUsername = githubIdentity.profileData ? githubIdentity.profileData.nickname : event.user.nickname;

    if (!githubIdentity || !githubIdentity.access_token) {
      return api.access.deny('Could not verify your GitHub identity permissions.');
    }

    if (!githubUsername) {
      return api.access.deny('Authentication failed: Could not determine your GitHub username.');
    }

    // Verify GitHub Organisation membership
    let isOrgMember = checkOrgsMembershipAtLeastOne(access_token, allowedOrgs);

    if (!isOrgMember) {
      return api.access.deny(`Access Denied: You are not a member of an authorised organisation:$${allowedOrgs.join(', ')}`);
    };

    // Set user application role
    const githubRole = assignUserRole(access_token, githubUsername);

    // Dev: Verify user membership of approved teams
    if ("${environment}" == "development") {
      const isTeamMember = checkTeamMembershipAtLeastOne(access_token, username, coreGitHubOrg, devTeamSlugs);

      if (!isTeamMember) {
        return api.access.deny('Access Denied: You are not authorized under the required GitHub teams.');
      }
    }

    // Add user role to user session token
    await management.users.update(
      { id: event.user.user_id },
      { user_metadata: { github_org_role: githubRole } }
    );

    const namespace = "${uri_namespace}";
    
    api.idToken.setCustomClaim(`$${namespace}/org_role`, githubRole);
  } catch (error) {
    console.error("M2M Verification Loop Failed:", error.message);
    return api.access.deny('Authentication failed during github identity verification.');
  }
};