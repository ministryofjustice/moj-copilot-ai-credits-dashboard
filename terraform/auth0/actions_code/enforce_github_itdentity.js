const axios = require('axios');
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

    if (!githubIdentity || !githubIdentity.access_token) {
      return api.access.deny('Could not verify your GitHub identity permissions.');
    }

    // Verify GitHub Organisation membership
    // const allowedOrgs = ["ministryofjustice", "jac-uk"];
    const allowedOrgs = ["ministryofjustice"];
    let isOrgMember = false;
    let githubRole = null;

    for (const org of allowedOrgs) {
      try {
        const response = await axios.get(`https://api.github.com/user/memberships/orgs/$${org}`, {
          headers: {
            Authorization: `token $${githubIdentity.access_token}`,
            'User-Agent': 'Auth0-Action-Org-Enforcer',
            'Accept': 'application/vnd.github.v3+json'
          }
        });
        
        isOrgMember = true;

        // Extract role of user in organisation
        if (org == "ministryofjustice") {
          githubRole = response.data.role;
        } else {
          githubRole = "member"
        };

        console.log(`User github role: $${githubRole}`);
      } catch (githubError) {
        if (githubError.response && githubError.response.status === 404) {
          console.log(`User is not a member of the organisation: $${org}`);
          console.log(`error message: $${githubError}`)
          continue
        }
        throw githubError;
      }
    }

    if (!isOrgMember) {
      return api.access.deny(`Access Denied: You are not a member of an authorised organisation:$${allowedOrgs.join(', ')}`);
    };

    // Dev: Verify user memership of approved teams
    if ("${environment}" == "development") {
       const allowedTeamSlugs = [
        "cloud-optimisation-and-accountability",
        "octo-developer-experience"
      ];
      
      const githubUsername = githubIdentity.profileData ? githubIdentity.profileData.nickname : event.user.nickname;
      
      if (!githubUsername) {
        return api.access.deny('Authentication failed: Could not determine your GitHub username.');
      }

      let isTeamMember = false;

      for (const teamSlug of allowedTeamSlugs) {
        try {
          await axios.get(
            `https://api.github.com/orgs/ministryofjustice/teams/$${teamSlug}/memberships/$${githubUsername}`,
            {
              headers: {
                Authorization: `token $${githubIdentity.access_token}`,
                'User-Agent': 'Auth0-Action-Org-Enforcer',
                'Accept': 'application/vnd.github.v3+json'
              }
            }
          );
          
          isTeamMember = true;
          console.log(`User is a member of the team: $${teamSlug}`);
          break;
        } catch (teamError) {
          if (teamError.response && teamError.response.status === 404) {
            console.log(`User is not a member of the team: $${teamSlug}`);
            continue;
          }
          throw teamError;
        }
      }

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