const axios = require('axios');
const { 
    checkGitHubOrganisationMembership, 
    checkOrgsMembershipAtLeastOne, 
    checkGitHubTeamMembership, 
    checkTeamMembershipAtLeastOne, 
    assignUserRole } = require('./validate_github_profile');

jest.mock('axios');

// Returns true when github responds with a successful membership check
test('checkGitHubOrganisationMembership returns true when github responds with a successful membership check', async () => {
    axios.get.mockResolvedValueOnce({ status: 200, data: {} });
    const result = await checkGitHubOrganisationMembership('fake-token', 'ministryofjustice');

    expect(result).toBe(true)
});

// Returns false when github responds 404 (user is not a member of the org)
test('checkGitHubOrganisationMembership returns false when github responds with a 404 membership check', async () => {
    axios.get.mockRejectedValueOnce({ response: { status: 404 } });
    const result = await checkGitHubOrganisationMembership('fake-token', 'fake-org');

    expect(result).toBe(false)
});

// Rethrows the error when github responds with a non 404 error (e.g. 500)
test('checkGitHubOrganisationMembership rethrows error when github responds with a non 404 status', async () => {
    axios.get.mockRejectedValueOnce({ response: { status: 500 } });
    
    await expect(checkGitHubOrganisationMembership('fake-token', 'ministryofjustice')).rejects.toEqual({ response: { status: 500 } });
});

// Returns true if the user is a member of the org checked
test('checkOrgsMembershipAtLeastOne returns true if the user is a member of the org', async () => {
    axios.get.mockResolvedValueOnce({ status: 200, data: {} });
    const result = await checkOrgsMembershipAtLeastOne('fake-token', ["ministryofjustice"]);

    expect(result).toBe(true)
});

// Returns true if the user matches a later org after an earlier one fails
test('checkOrgsMembershipAtLeastOne returns true if the user matches a later org after an earlier one fails', async () => {
    axios.get
        .mockRejectedValueOnce({ response: { status: 404 } })
        .mockResolvedValueOnce({ status: 200, data: {} });
    const result = await checkOrgsMembershipAtLeastOne('fake-token', ["fake-org", "jac-uk"]);

    expect(result).toBe(true)
});

// returns false if the user is not a member of any org in the list
test('checkOrgsMembershipAtLeastOne returns false if the user is not a member of any org in the list', async () => {
    axios.get
        .mockRejectedValue({ response: { status: 404 } });
    const result = await checkOrgsMembershipAtLeastOne('fake-token', ["fake-org-1", "fake-org-2-uk"]);

    expect(result).toBe(false)
});

// Returns false when given an empty list/array of orgs
// Note: no axios mock needed here. the loop never runs when orgs is empty
test('checkOrgsMembershipAtLeastOne returns false when given an empty list/array of orgs', async () => {
    const result = await checkOrgsMembershipAtLeastOne('fake-token', []);

    expect(result).toBe(false)
});

// Returns true when Github confirms team membership
test('checkGitHubTeamMembership returns true when github confirms team membership', async () => {
    axios.get.mockResolvedValueOnce({ status: 200, data: {} });
    const result = await checkGitHubTeamMembership(
        'fake-token', 'dummy-user', 'ministryofjustice', 
        "cloud-optimisation-and-accountability");

    expect(result).toBe(true)
});

// returns false when GitHub responds 404 (not a member of the team)
test('checkGitHubTeamMembership returns false when GitHub responds user is not a member of a team', async () => {
    axios.get.mockRejectedValueOnce({ response: { status: 404 } });
    const result = await checkGitHubTeamMembership(
        'fake-token', 'dummy-user', 'ministryofjustice', "fake-team");

    expect(result).toBe(false)
});

// Rethrows the error when github responds with a non 404 error
test('checkGitHubTeamMembership rethrows error when github responds with a non 404 status', async () => {
    axios.get.mockRejectedValueOnce({ response: { status: 500 } });
    
    await expect(checkGitHubTeamMembership(
        'fake-token', 'dummy-user', 'ministryofjustice', 'fake-team'))
        .rejects.toEqual({ response: { status: 500 } 
    });
});

// Returns true if user is a member of the first team checked
test('checkTeamMembershipAtLeastOne returns true if the user is a member of the first team checked', async () => {
    axios.get.mockResolvedValueOnce({ status: 200, data: {} });
    const result = await checkTeamMembershipAtLeastOne('fake-token', 'dummy-user', 
        'ministryofjustice', ["cloud-optimisation-and-accountability", "octo-developer-experience"]);

    expect(result).toBe(true)
});

// Returns true if user is a member of a later team, after an earlier on fails
test('checkTeamMembershipAtLeastOne returns true if the user matches a later team after an earlier one fails', async () => {
    axios.get
        .mockRejectedValueOnce({ response: { status: 404 } })
        .mockResolvedValueOnce({ status: 200, data: {} });
    const result = await checkTeamMembershipAtLeastOne('fake-token', 'dummy-user', 
        'ministryofjustice', ["fake-cloud-optimisation-and-accountability", "octo-developer-experience"]);
    expect(result).toBe(true)
});

// returns false if the user is not a member of any team in the list
test('checkTeamMembershipAtLeastOne returns false if the user is not a member of any team in the list', async () => {
    axios.get
        .mockRejectedValue({ response: { status: 404 } });
    const result = await checkTeamMembershipAtLeastOne(
        'fake-token', 'dummy-user', 'ministryofjustice',
        ["fake-cloud-optimisation-and-accountability", "fake-octo-developer-experience"]);

    expect(result).toBe(false)
});

// Returns false when given an empty list/array of teams 
// Note: no axios mock needed here. the loop never runs when team is empty
test('checkTeamMembershipAtLeastOne returns false when given an empty list/array of teams', async () => {
    const result = await checkTeamMembershipAtLeastOne(
        'fake-token', 'dummy-user', 'ministryofjustice', []);

    expect(result).toBe(false)
});

// Returns "admin" when the user is a member of the admin team
test('assignUserRole returns "admin" when the user is a member of the admin team' , async () => {
    axios.get.mockResolvedValueOnce({ status: 200, data: {} });

    const result = await assignUserRole(
        'fake-token', 'ministryofjustice',
        'moj-copilot-credits-dashboard-admin', 'dummy-user');

    expect(result).toBe("admin")
});

// Returns "member" when the user is not a member of the admin team
test('assignUserRole returns "member" when the user is not a member of the admin team' , async () => {
    axios.get.mockRejectedValueOnce({ response: { status: 404 } });

    const result = await assignUserRole(
        'fake-token', 'ministryofjustice',
        'not-in-admin-team', 'dummy-user');

    expect(result).toBe("member")
});