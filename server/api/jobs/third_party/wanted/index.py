import requests
import flask
import server.api.jobs.third_party.wanted.constants as constants
import server.api.jobs.third_party.wanted.helpers as helpers
import server

@server.application.route('/api/v2/jobs/categories/', methods=['GET'])
def get_job_categories():
    """Get list of job categories available on Wanted API."""
    endpoint = '/tags/categories'
    url = constants.WANTED_BASE_URL + endpoint
    headers = helpers.get_wanted_headers()
    try:
        resp = requests.get(url, headers=headers, timeout=constants.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return flask.jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return flask.jsonify({'error': str(e)}), 500