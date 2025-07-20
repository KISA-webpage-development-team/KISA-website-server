import requests
import server.api.jobs.third_party.wanted.constants as constants
import server.api.jobs.third_party.wanted.helpers as helpers
import urllib.parse as urlparse
import re


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
    next_url = data.get("links", {}).get("next")
    return data, next_url, resp.status_code


def fetch_wanted_internships(
    category=None, offset=0, limit=20, additional_params=None
):
    """
    Fetch internship and entry-level jobs from Wanted.
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    
    params = {
        "offset": offset,
        "limit": limit,
        "years": [0, 2],  # intern, entry level
    }
    
    # Add additional params first
    if additional_params:
        params.update(additional_params)
    
    # Add category using WANTED_CATEGORY_MAP
    if category and category in constants.WANTED_CATEGORY_MAP:
        params["category_tag"] = constants.WANTED_CATEGORY_MAP[category]
    
    return fetch_wanted_jobs(params)


def transform_wanted_response_to_client_format(wanted_data):
    """
    Transform Wanted API response to match client-expected format.
    Converts from {"data": [...], "links": {...}} to {"jobs": [...], "next": "..."}
    """
    # Extract jobs from Wanted response
    jobs_raw = wanted_data.get("data", [])
    
    # Transform each job to match client format
    transformed_jobs = []
    for job in jobs_raw:
        # Extract company name safely
        company_name = ""
        if isinstance(job.get("company"), dict):
            company_name = job.get("company", {}).get("name", "")
        else:
            company_name = str(job.get("company", ""))
        
        # Determine employment type and convertible status
        employment_type = job.get("employment_type", "regular")
        additional_apply_types = job.get("additional_apply_type") or []
        
        # Map employment_type to boolean flags
        is_fulltime_position = employment_type == "regular"
        is_fulltime_convertible = False
        is_international = "foreigner" in additional_apply_types
        
        # For intern positions, determine if they are convertible
        if employment_type == "intern":
            # Check if it's convertible (채용연계형)
            is_fulltime_convertible = (
                "convertible" in additional_apply_types or 
                "채용연계" in str(job.get("name", "")) or
                "정규직" in str(job.get("name", ""))
            )
        
        # Transform to client format
        transformed_job = {
            "jobID": job.get("id", 0),
            "company": company_name,
            "position": job.get("name", ""),
            "startDate": "",  # Wanted API doesn't provide this
            "endDate": "",    # Wanted API doesn't provide this
            "dueDate": job.get("due_time", ""),
            "link": job.get("url", ""),
            "isFulltimePosition": is_fulltime_position,
            "isFulltimeConvertible": is_fulltime_convertible,
            "isOnlyForInternationalUniversity": is_international,
            "source": "wanted-api"
        }
        transformed_jobs.append(transformed_job)
    
    # Convert pagination links
    links = wanted_data.get("links", {})
    next_link = None
    if links.get("next"):
        # Convert from "/v2/jobs?offset=50&limit=5..." to "/api/v2/jobs/?offset=50&limit=5"
        wanted_next = links.get("next")
        offset_match = re.search(r'offset=(\d+)', wanted_next)
        limit_match = re.search(r'limit=(\d+)', wanted_next)
        
        if offset_match and limit_match:
            offset = offset_match.group(1)
            limit = limit_match.group(1)
            next_link = f"/api/v2/jobs/?offset={offset}&limit={limit}"
    
    # Return in client format
    response = {
        "jobs": transformed_jobs,
        "next": next_link
    }
    
    return response


def fetch_all_internships_with_employment_type_check(
    category=None, offset=0, limit=20, max_pages=10
):
    """
    Fetch all internship jobs from Wanted by paginating and filtering by employment_type == 'intern'.
    Returns transformed data in client format: {"jobs": [...], "next": "..."}
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    
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
            if params and "offset" in params:
                offset = int(params.get("offset", [str(offset + limit)])[0])
            else:
                offset = offset + limit
        except Exception:
            offset = offset + limit
            
        page_count += 1
    
    # Transform to client format
    fake_wanted_response = {
        "data": all_internships,
        "links": {"next": next_url, "prev": None}
    }
    
    return transform_wanted_response_to_client_format(fake_wanted_response)


def fetch_wanted_internships_with_search_position(
    category=None, offset=0, limit=20, max_pages=10
):
    """
    Fetch internships from Wanted using /v1/search/position with query='인턴' and years=[0,2].
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    
    endpoint = "/search/position"
    url = constants.WANTED_BASE_URL + endpoint
    headers = helpers.get_wanted_headers()
    params = {
        "query": "인턴",
        "offset": offset,
        "limit": limit,
    }
    if category and category in constants.WANTED_CATEGORY_MAP:
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
    Returns transformed data in client format: {"jobs": [...], "next": "..."}
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    
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
            if params and "offset" in params:
                offset = int(params.get("offset", [str(offset + limit)])[0])
            else:
                offset = offset + limit
        except Exception:
            offset = offset + limit
            
        page_count += 1
    
    # Transform to client format
    fake_wanted_response = {
        "data": all_positions,
        "links": {"next": next_url, "prev": None}
    }
    
    return transform_wanted_response_to_client_format(fake_wanted_response)


# Additional helper functions for enhanced functionality
def build_flask_response(request_args):
    """
    Build response for Flask endpoint from request arguments.
    Converts Flask request.args to the format expected by our functions.
    """
    # Extract and validate parameters
    try:
        offset = int(request_args.get("offset", 0))
    except (ValueError, TypeError):
        offset = 0
        
    try:
        limit = int(request_args.get("limit", 20))
    except (ValueError, TypeError):
        limit = 20
        
    category = request_args.get("category")
    
    # Use the existing function but ensure it returns client format
    return fetch_all_internships_with_employment_type_check(
        category=category,
        offset=offset,
        limit=limit,
        max_pages=5  # Limit pages for faster response
    )
