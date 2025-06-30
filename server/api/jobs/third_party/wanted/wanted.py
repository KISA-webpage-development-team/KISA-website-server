import requests
import server.api.jobs.third_party.wanted.constants as constants
import server.api.jobs.third_party.wanted.helpers as helpers
import urllib.parse as urlparse


def fetch_wanted_jobs(params=None):
    """
    General function to call the Wanted jobs API with arbitrary params.
    """
    endpoint = "/jobs"
    url = constants.WANTED_BASE_URL_V2 + endpoint
    headers = helpers.get_wanted_headers()
    if params is None:
        params = {}
    resp = requests.get(
        url, headers=headers, params=params, timeout=constants.REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    next_url = data["links"]["next"]
    return data, next_url, resp.status_code


def fetch_wanted_internships(
    category=None, offset=0, limit=20, additional_params=None
):
    """
    Fetch internship and entry-level jobs from Wanted.
    """
    params = {
        "offset": offset,
        "limit": limit,
        "years": [0, 2],  # intern, entry level
        **additional_params,
    }
    if category:
        params["category_tag"] = constants.WANTED_CATEGORY_MAP[category]
    return fetch_wanted_jobs(params)


def fetch_all_internships_with_employment_type_check(
    category=None, offset=0, limit=20, max_pages=10
):
    """
    Fetch all internship jobs from Wanted by paginating and filtering by employment_type == 'intern'.
    Returns a dict with 'data' (list of jobs) and 'links' (pagination info).
    Limits the number of pages fetched to max_pages to avoid long runtimes.
    """
    all_internships = []
    next_url = None
    page_count = 0
    while True:
        if page_count >= max_pages:
            break
        data, next_url, status_code = fetch_wanted_internships(
            category=category,
            offset=offset,
            limit=limit,
            additional_params={"locations": ["seoul", "gyeonggi"]},
        )
        jobs = (
            data.get("data", data.get("results", []))
            if isinstance(data, dict)
            else []
        )
        # Filter only internships
        internships = [
            job for job in jobs if job.get("employment_type") == "intern"
        ]
        all_internships.extend(internships)
        # Pagination: break if no more data
        if not next_url or not jobs:
            break
        # Extract next offset from next_url if available
        parsed = urlparse.urlparse(next_url)
        params = urlparse.parse_qs(parsed.query)
        try:
            offset = int(params.get("offset", [offset + limit])[0])
        except Exception:
            offset += limit
        page_count += 1
    # Compose response in the new format
    response = {
        "data": all_internships,
        "links": {
            "next": next_url,
            "prev": None,  # prev can be implemented if needed
        },
    }
    return response


def fetch_wanted_internships_with_search_position(
    category=None, offset=0, limit=20, max_pages=10
):
    """
    Fetch internships from Wanted using /v1/search/position with query='인턴' and years=[0,2].
    """
    endpoint = "/search/position"
    url = constants.WANTED_BASE_URL + endpoint
    headers = helpers.get_wanted_headers()
    params = {
        "query": "인턴",
        "offset": offset,
        "limit": limit,
    }
    if category:
        params["category_tag"] = constants.WANTED_CATEGORY_MAP[category]
    resp = requests.get(
        url, headers=headers, params=params, timeout=constants.REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    next_url = data.get("links", {}).get("next")
    # Return positions as the main data
    return data.get("positions", []), next_url, resp.status_code


def fetch_all_internships_with_search_position(
    category=None, offset=0, limit=20, max_pages=10
):
    """
    Fetch all internship jobs from Wanted using /v1/search/position by paginating.
    Returns a dict with 'data' (list of positions) and 'links' (pagination info).
    Limits the number of pages fetched to max_pages to avoid long runtimes.
    """
    all_positions = []
    next_url = None
    page_count = 0
    while True:
        if page_count >= max_pages:
            break
        positions, next_url, status_code = (
            fetch_wanted_internships_with_search_position(
                category=category,
                offset=offset,
                limit=limit,
            )
        )
        # positions is already a list of jobs
        all_positions.extend(positions)
        if not next_url or not positions:
            break
        # Extract next offset from next_url if available
        parsed = urlparse.urlparse(next_url)
        params = urlparse.parse_qs(parsed.query)
        try:
            offset = int(params.get("offset", [offset + limit])[0])
        except Exception:
            offset += limit
        page_count += 1
    response = {
        "data": all_positions,
        "links": {
            "next": next_url,
            "prev": None,
        },
    }
    return response
