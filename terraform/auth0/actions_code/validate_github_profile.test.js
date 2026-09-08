const axios = require('axios');
const { checkGitHubOrganisationMembership } = require('./validate_github_profile');

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

