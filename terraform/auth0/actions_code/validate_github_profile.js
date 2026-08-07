const axios = require('axios');

async function checkGitHubOrganisationMembership(access_token, org) {
  try {
    const response = await axios.get(`https://api.github.com/user/memberships/orgs/${org}`, {
      headers: {
        Authorization: `token ${access_token}`,
        'User-Agent': 'Auth0-Action-Org-Enforcer',
        'Accept': 'application/vnd.github.v3+json'
      }
    });

    return true
  } catch (githubError) {
    if (githubError.response && githubError.response.status === 404) {
      console.log(`User is not a member of the organisation: ${org}`);
      return false
    }
    throw githubError;
  }

  console.log("Unable to check org membership");

  return false;
};

async function checkOrgsMembershipAtLeastOne(access_token, orgs) {
  for (const org of orgs) {
    const isMember = await checkGitHubOrganisationMembership(access_token, org);

    if (isMember) {
      return true;
    }

    console.log(`User is not a member of the organisation: ${org}`);
  }

  return false;
}

async function checkGitHubTeamMembership(access_token, username, org, team) {
  try {
    await axios.get(
      `https://api.github.com/orgs/${org}/teams/${team}/memberships/${username}`,
      {
        headers: {
          Authorization: `token ${access_token}`,
          'User-Agent': 'Auth0-Action-Org-Enforcer',
          'Accept': 'application/vnd.github.v3+json'
        }
      }
    );
          
    return true;
  } catch (teamError) {
    if (teamError.response && teamError.response.status === 404) {
      return false;
    } else {
      throw teamError;
    }
  }

  console.log("Unable to check team membership");

  return false;
};

async function checkTeamMembershipAtLeastOne(access_token, username, org, teams) {
  for (const team of teams) {
    const isMember = await checkGitHubTeamMembership(access_token, username, org, team);

    if (isMember) {
      return true;
    }

    console.log(`User is not a member of the team: ${team}`);
  }

  return false;
};

async function assignUserRole(access_token, org, adminTeam, username) {
  const githubRole = await checkGitHubTeamMembership(access_token, username, org, adminTeam) ? "admin" : "member";

  console.log(`User github role: ${githubRole}`);

  return githubRole;
};

module.exports = {
  checkGitHubOrganisationMembership,
  checkOrgsMembershipAtLeastOne,
  checkGitHubTeamMembership,
  checkTeamMembershipAtLeastOne,
  assignUserRole
};