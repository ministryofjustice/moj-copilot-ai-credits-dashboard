const axios = require('axios');
const { checkGitHubOrganisationMembership, checkOrgsMembershipAtLeastOne } = require('./validate_github_profile');

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
test('checkGitHubOrganisationMembership rethrows errore when github responds with a non 404 status', async () => {
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