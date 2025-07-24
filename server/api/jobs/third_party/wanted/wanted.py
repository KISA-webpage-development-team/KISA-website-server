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


def check_wanted_api_supports_employment_type():
    """
    Test if Wanted API supports employment_type parameter directly.
    This helps us determine if we can optimize API calls.
    """
    try:
        # Test with employment_type parameter
        params = {
            "employment_type": "intern",
            "limit": 1,
            "sort": "job.latest_order"
        }
        
        data, next_url, status_code = fetch_wanted_jobs(params)
        
        if status_code == 200 and data.get("data"):
            # Check if all returned jobs are actually interns
            jobs = data.get("data", [])
            intern_jobs = [job for job in jobs if job.get("employment_type") == "intern"]
            
            # If API filtering worked, all jobs should be interns
            return len(intern_jobs) == len(jobs)
        
        return False
        
    except Exception:
        return False


def fetch_wanted_jobs_optimized(category=None, offset=0, limit=20, employment_type=None, locations=None):
    """
    Optimized function to fetch jobs with better API parameter usage.
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    
    params = {
        "offset": offset,
        "limit": limit,
        "sort": "job.latest_order"
    }
    
    # Add employment type if supported by API
    if employment_type:
        params["employment_type"] = employment_type
    
    # Add category using WANTED_CATEGORY_MAP
    if category and category in constants.WANTED_CATEGORY_MAP:
        params["category_tag"] = constants.WANTED_CATEGORY_MAP[category]
    
    # Add locations
    if locations:
        if isinstance(locations, list):
            params["locations"] = locations
        else:
            params["locations"] = [locations]
    
    return fetch_wanted_jobs(params)


def fetch_wanted_internships(
    category=None, offset=0, limit=20, additional_params=None
):
    """
    Fetch internship and entry-level jobs from Wanted.
    Updated to use optimized approach.
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


def fetch_jobs_with_location_fallback(category=None, offset=0, limit=20, employment_type=None):
    """
    Fetch jobs with location fallback: 수도권 first, then 지방.
    Implements Approach 2 as recommended.
    """
    # Step 1: Try to get jobs from 수도권 (Seoul metropolitan area)
    try:
        data, next_url, status_code = fetch_wanted_jobs_optimized(
            category=category,
            offset=offset,
            limit=limit,
            employment_type=employment_type,
            locations=["seoul", "gyeonggi"]
        )
        
        jobs = data.get("data", [])
        
        # If we got enough jobs from 수도권, return them
        if len(jobs) >= limit or next_url:
            return data, next_url, status_code
        
        # Step 2: If 수도권 doesn't have enough jobs, get from all Korea as fallback
        remaining_limit = limit - len(jobs)
        
        if remaining_limit > 0:
            # Fetch from all Korea (no location filter)
            fallback_data, fallback_next_url, fallback_status = fetch_wanted_jobs_optimized(
                category=category,
                offset=0,  # Start from beginning for fallback
                limit=remaining_limit,
                employment_type=employment_type,
                locations=None  # No location filter = all Korea
            )
            
            fallback_jobs = fallback_data.get("data", [])
            
            # Filter out jobs we already have (avoid duplicates)
            existing_job_ids = {job.get("id") for job in jobs}
            new_jobs = [job for job in fallback_jobs if job.get("id") not in existing_job_ids]
            
            # Combine results
            jobs.extend(new_jobs)
            
            # Update response data
            data["data"] = jobs
            
            # Use fallback next_url if original is exhausted
            if not next_url and fallback_next_url:
                next_url = fallback_next_url
        
        return data, next_url, status_code
        
    except Exception as e:
        # If location-specific request fails, try without location filter
        return fetch_wanted_jobs_optimized(
            category=category,
            offset=offset,
            limit=limit,
            employment_type=employment_type,
            locations=None
        )


def fetch_jobs_by_employment_type(category=None, offset=0, limit=20, employment_type="intern"):
    """
    Optimized function to fetch jobs by employment type.
    Uses direct API filtering if supported, otherwise falls back to client-side filtering.
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    
    # Check if we can use direct API filtering (cache this result in production)
    api_supports_filtering = check_wanted_api_supports_employment_type()
    
    if api_supports_filtering:
        # Optimized path: Use API filtering directly
        data, next_url, status_code = fetch_jobs_with_location_fallback(
            category=category,
            offset=offset,
            limit=limit,
            employment_type=employment_type
        )
    else:
        # Fallback path: Client-side filtering (your current approach but optimized)
        # Fetch more jobs at once to reduce API calls
        fetch_limit = min(limit * 3, 100)  # Fetch 3x requested or max 100
        
        data, next_url, status_code = fetch_jobs_with_location_fallback(
            category=category,
            offset=offset,
            limit=fetch_limit,
            employment_type=None  # No API filtering
        )
        
        # Client-side filtering
        jobs = data.get("data", [])
        filtered_jobs = [
            job for job in jobs 
            if job.get("employment_type") == employment_type
        ]
        
        # Trim to requested limit
        filtered_jobs = filtered_jobs[:limit]
        
        # Update response
        data["data"] = filtered_jobs
    
    return transform_wanted_response_to_client_format(data)


def fetch_jobs_mixed_employment_types(category=None, offset=0, limit=20):
    """
    Fetch both 신입 (regular) and 인턴 (intern) positions.
    This is for when no specific employment type is requested.
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    
    # Fetch both employment types in one call (no employment_type filter)
    data, next_url, status_code = fetch_jobs_with_location_fallback(
        category=category,
        offset=offset,
        limit=limit,
        employment_type=None
    )
    
    # Filter for 신입 (regular) and 인턴 (intern) only
    jobs = data.get("data", [])
    filtered_jobs = [
        job for job in jobs 
        if job.get("employment_type") in ["regular", "intern"]
    ]
    
    # Update response
    data["data"] = filtered_jobs
    
    return transform_wanted_response_to_client_format(data)


def fetch_all_internships_with_employment_type_check(
    category=None, offset=0, limit=20, max_pages=3
):
    """
    Legacy function - now optimized to use the new approach.
    Reduced max_pages from 10 to 3 for better performance.
    """
    return fetch_jobs_by_employment_type(
        category=category,
        offset=offset,
        limit=limit,
        employment_type="intern"
    )


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
    
    # temporary response before final transformation
    fake_wanted_response = {
        "data": all_positions,
        "links": {"next": next_url, "prev": None}
    }
    
    return transform_wanted_response_to_client_format(fake_wanted_response)


def build_flask_response(request_args):
    """
    Enhanced Flask response builder with optimized logic.
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
    tags = request_args.get("tags", "").split(",") if request_args.get("tags") else []
    tags = [tag.strip().lower() for tag in tags if tag.strip()]
    
    try:
        # Determine what type of jobs to fetch based on tags
        if not tags:
            # No tags specified: fetch 신입 + 인턴 (both regular and intern)
            return fetch_jobs_mixed_employment_types(
                category=category,
                offset=offset,
                limit=limit
            )
        elif "intern" in tags:
            # Intern positions requested
            return fetch_jobs_by_employment_type(
                category=category,
                offset=offset,
                limit=limit,
                employment_type="intern"
            )
        elif "fulltime" in tags:
            # Fulltime positions requested
            return fetch_jobs_by_employment_type(
                category=category,
                offset=offset,
                limit=limit,
                employment_type="regular"
            )
        else:
            # Default: fetch both types
            return fetch_jobs_mixed_employment_types(
                category=category,
                offset=offset,
                limit=limit
            )
            
    except Exception as e:
        return {
            "jobs": [],
            "next": None,
            "error": str(e)
        }