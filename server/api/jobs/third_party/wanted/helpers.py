import server.api.jobs.third_party.wanted.constants as constants


def get_wanted_headers():
    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'wanted-client-id': constants.WANTED_CLIENT_ID,
        'wanted-client-secret': constants.WANTED_CLIENT_SECRET
    }
