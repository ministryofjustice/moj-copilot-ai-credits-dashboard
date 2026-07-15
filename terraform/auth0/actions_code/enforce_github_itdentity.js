const axios = require('axios');
const ManagementClient = require('auth0').ManagementClient;

exports.onExecutePostLogin = async (event, api) => {
  if (event.connection.strategy !== 'github') return;

  try {
    // 1. Initialize using your M2M secrets
    const management = new ManagementClient({
      domain: event.secrets.AUTH0_DOMAIN,
      clientId: event.secrets.AUTH0_MANAGEMENT_CLIENT_ID,
      clientSecret: event.secrets.AUTH0_MANAGEMENT_CLIENT_SECRET,
    });

    // 2. Grab the raw user profile containing the upstream access token
    const userProfile = await management.users.get({ id: event.user.user_id });
    const githubIdentity = userProfile.identities.find(id => id.provider === 'github');

    if (!githubIdentity || !githubIdentity.access_token) {
      return api.access.deny('Could not verify your GitHub identity permissions.');
    }

    const targetOrg = "ministryofjustice";
    let githubRole = null;

    // 3. Query GitHub's API specifically for the user's membership status in this org
    try {
      const response = await axios.get(`https://api.github.com/user/memberships/orgs/${targetOrg}`, {
        headers: {
          Authorization: `token ${githubIdentity.access_token}`,
          'User-Agent': 'Auth0-Action-Org-Enforcer',
          'Accept': 'application/vnd.github.v3+json'
        }
      });
      
      // GitHub returns 'admin' for Owners and 'member' for ordinary members
      githubRole = response.data.role; 

      console.log(`User github role: ${githubRole}`);
    } catch (githubError) {
      // If GitHub returns a 404, they are not a member of the organization
      if (githubError.response && githubError.response.status === 404) {
        return api.access.deny('Access Denied: You must be a member of the Ministry of Justice GitHub organization.');
      }
      throw githubError;
    }

    // 4. Update the user metadata in Auth0 with their explicit role
    await management.users.update(
      { id: event.user.user_id },
      { user_metadata: { github_org_role: githubRole } }
    );

    // 5. Enhance the Session Payload (Tokens) with the new custom key
    // Note: Auth0 requires a URI namespace for custom claims to prevent colliding with OIDC standards
    const namespace = "${uri_namespace}";
    
    api.idToken.setCustomClaim(`${namespace}/org_role`, githubRole);

  } catch (error) {
    console.error("M2M Verification Loop Failed:", error.message);
    return api.access.deny('Authentication failed during organization authorization verification.');
  }
};