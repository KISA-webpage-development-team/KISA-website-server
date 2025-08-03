"""
Collection of functions to fetch and process jobs data from Wanted API.
"""

import re
from datetime import datetime
import urllib.parse as urlparse

import requests

import server.api.jobs.third_party.wanted.constants as constants
import server.api.jobs.third_party.wanted.helpers as helpers


def build_flask_response(request_args):
    """
    ENTRY POINT: Builds a Flask response for job listings, handling various request parameters.
    This version correctly handles multiple 'tags' parameters.

    Args:
        request_args: Flask request arguments

    Returns:
        Flask response with jobs data
    """
    # extract and validate query parameters
    offset = int(request_args.get("offset", 0))
    limit = int(request_args.get("limit", 60))

    category = request_args.get("category")

    # Correctly handle multiple 'tags' query parameters
    tags_list = request_args.getlist("tags")
    tags = []
    for t in tags_list:
        tags.extend(t.split(","))

    tags = sorted(
        list(set([tag.strip().lower() for tag in tags if tag.strip()]))
    )

    start_date = request_args.get("startDate")
    end_date = request_args.get("endDate")

    # Validate request parameters
    is_valid, error_message, status_code = validate_request_params(
        tags, start_date, end_date
    )
    if not is_valid:
        return {
            "jobs": [],
            "next": None,
            "error": error_message,
            "status_code": status_code,
        }

    try:
        # Determine what type of jobs to fetch based on tags
        if not tags:
            # No tags specified: fetch 신입 + 인턴 (both regular and intern)
            response_data = fetch_jobs_mixed_employment_types(
                category=category, offset=offset, limit=limit
            )
        elif "fulltime" in tags:
            # Fulltime positions requested
            response_data = fetch_jobs_by_employment_type(
                category=category,
                offset=offset,
                limit=limit,
                employment_type="regular",
            )
        elif "intern" in tags:
            # Use existing function that works with /v2/jobs endpoint
            data, next_url, status_code = fetch_wanted_internships(
                category=category, offset=offset, limit=limit
            )
            # Build original params dict for pagination
            original_params = {
                "category": category,
                "tags": tags,
                "startDate": start_date,
                "endDate": end_date,
                "offset": offset,
                "limit": limit,
            }
            response_data = transform_wanted_response_to_client_format(
                data, original_params
            )
        else:
            # Default: fetch both types
            response_data = fetch_jobs_mixed_employment_types(
                category=category, offset=offset, limit=limit
            )

        # Apply tag filtering AFTER fetching data
        if tags:
            response_data["jobs"] = filter_jobs_by_tags(
                response_data["jobs"], tags
            )

        # Apply date filtering AFTER tag filtering
        if start_date or end_date:
            response_data["jobs"] = filter_jobs_by_date_range(
                response_data["jobs"], start_date, end_date
            )

        return response_data

    except Exception as e:
        return {"jobs": [], "next": None, "error": str(e)}


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


def validate_request_params(tags, start_date, end_date):
    """
    Validate request parameters according to business rules.
    Returns (is_valid, error_message, status_code)
    """

    #  intern없이 convertible 혹은 experiential이 동시에 들어올 경우 400
    if (
        "convertible" in tags or "experiential" in tags
    ) and "intern" not in tags:
        return (
            False,
            "convertible and experiential tags require intern tag",
            400,
        )

    #  startDate와 endDate가 모두 존재할 때 startDate > endDate 일 경우 400
    if start_date and end_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)

            if start_dt > end_dt:
                return False, "startDate cannot be later than endDate", 400
        except ValueError:
            return False, "Invalid date format. Use YYYY-MM-DD", 400

    return True, None, None


def filter_jobs_by_date_range(jobs, start_date=None, end_date=None):
    """
    Filter jobs based on startDate and endDate range.
    Since Wanted API doesn't provide job start dates, we'll use due_time for filtering.
    """
    if not start_date and not end_date:
        return jobs

    filtered_jobs = []

    for job in jobs:
        # Use due_time as the date to filter by
        job_date_str = job.get("due_time") or job.get("dueDate")

        if not job_date_str:
            # If no date info, include the job
            filtered_jobs.append(job)
            continue

        try:
            # Parse job date
            job_date = datetime.fromisoformat(
                job_date_str.replace("Z", "+00:00")
            )
            include_job = True

            # Check start date
            if start_date:
                filter_start = datetime.fromisoformat(start_date)
                if job_date < filter_start:
                    include_job = False

            # Check end date
            if end_date and include_job:
                filter_end = datetime.fromisoformat(end_date)
                if job_date > filter_end:
                    include_job = False

            if include_job:
                filtered_jobs.append(job)

        except (ValueError, TypeError):
            # If date parsing fails, include the job
            filtered_jobs.append(job)

    return filtered_jobs


def fetch_wanted_jobs_optimized(
    category=None, offset=0, limit=60, locations=None
):
    """
    Optimized function to fetch jobs with better API parameter usage.
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit

    params = {"offset": offset, "limit": limit, "sort": "job.latest_order"}

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
    category=None, offset=0, limit=60, additional_params=None
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


def transform_wanted_response_to_client_format(
    wanted_data, original_params=None
):
    """
    Transform Wanted API response to match client-expected format.
    Updated with proper convertible/experiential logic and null fallback.

    Args:
        wanted_data: Raw response from Wanted API
        original_params: Original request parameters to preserve in pagination
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
        job_name = str(job.get("name", ""))

        # Map employment_type to boolean flags
        is_fulltime_position = employment_type == "regular"
        is_international = "foreigner" in additional_apply_types

        # Enhanced convertible logic with null fallback
        is_fulltime_convertible = None  # Default fallback value

        if employment_type == "intern":
            # Check for explicit indicators in additional_apply_type
            if "convertible" in additional_apply_types:
                is_fulltime_convertible = True
            elif "experiential" in additional_apply_types:
                is_fulltime_convertible = False
            else:
                # Priority 2: ENHANCED keyword detection in job name
                # Convertible keywords (채용연계형)
                convertible_keywords = [
                    "채용연계",
                    "정규직전환",
                    "정규직",
                    "전환가능",
                    "전환형",
                    "연계형",
                    "정규전환",
                    "채용전환",
                    "(전환형)",
                    "(연계형)",
                    "(채용연계)",
                    "(정규직전환)",
                ]

                # Experiential keywords (체험형)
                experiential_keywords = [
                    "체험형",
                    "체험",
                    "인턴십",
                    "실습",
                    "현장실습",
                    "(체험형)",
                    "(체험)",
                    "(실습)",
                    "단기",
                    "방학",
                ]

                # Check for convertible keywords first
                if any(
                    keyword in job_name for keyword in convertible_keywords
                ):
                    is_fulltime_convertible = True
                # Then check for experiential keywords
                elif any(
                    keyword in job_name for keyword in experiential_keywords
                ):
                    is_fulltime_convertible = False
                # If no indicators found, keep as null

        # Transform to client format
        transformed_job = {
            "jobID": job.get("id", 0),
            "company": company_name,
            "position": job.get("name", ""),
            "startDate": "",  # Wanted API doesn't provide this
            "endDate": "",  # Wanted API doesn't provide this
            "dueDate": job.get("due_time", ""),
            "link": job.get("url", ""),
            "isFulltimePosition": is_fulltime_position,
            "isFulltimeConvertible": is_fulltime_convertible,  # Can be true, false, or null
            "isOnlyForInternationalUniversity": is_international,
            "source": "wanted-api",
        }
        transformed_jobs.append(transformed_job)

    # Convert pagination links
    links = wanted_data.get("links", {})
    next_link = None
    if links.get("next"):
        wanted_next = links.get("next")
        offset_match = re.search(r"offset=(\d+)", wanted_next)
        limit_match = re.search(r"limit=(\d+)", wanted_next)

        if offset_match and limit_match:
            offset = offset_match.group(1)
            limit = limit_match.group(1)

            # Build next URL with all original parameters
            if original_params:
                # Create a copy of original params and update offset/limit
                next_params = original_params.copy()
                next_params["offset"] = offset
                next_params["limit"] = limit

                # Build query string
                param_pairs = []
                for key, value in next_params.items():
                    if value is not None and value != "":
                        if key == "tags" and isinstance(value, list):
                            # Handle tags as comma-separated string
                            tags_str = ",".join(value)
                            param_pairs.append(f"{key}={tags_str}")
                        elif isinstance(value, list):
                            # Handle other list parameters as separate entries
                            for v in value:
                                param_pairs.append(f"{key}={v}")
                        else:
                            param_pairs.append(f"{key}={value}")

                next_link = f"/api/v2/jobs/?{'&'.join(param_pairs)}"
            else:
                # Fallback to just offset and limit if no original params
                next_link = f"/api/v2/jobs/?offset={offset}&limit={limit}"

    return {"jobs": transformed_jobs, "next": next_link}


def filter_jobs_by_tags(jobs, tags):
    """
    Updated tag filtering logic to handle null values for isFulltimeConvertible.
    """
    if not tags:
        return jobs

    filtered_jobs = []

    for job in jobs:
        should_include = False

        if "fulltime" in tags:
            # 신입 정규직: isFulltimePosition === true
            if job.get("isFulltimePosition", False):
                should_include = True

        elif "intern" in tags:
            # 인턴 포지션: isFulltimePosition === false
            if not job.get(
                "isFulltimePosition", True
            ):  # This means it's an intern
                if "convertible" in tags:
                    # 채용연계형만: isFulltimeConvertible === true
                    if job.get("isFulltimeConvertible") is True:
                        should_include = True
                elif "experiential" in tags:
                    # 체험형만: isFulltimeConvertible === false
                    if job.get("isFulltimeConvertible") is False:
                        should_include = True
                else:
                    # 모든 인턴 (체험형 + 채용연계형 + 불명확한 것들)
                    # Include all intern positions regardless of convertible status
                    should_include = True

        if should_include:
            filtered_jobs.append(job)

    return filtered_jobs


def fetch_jobs_with_location_fallback(
    category=None, offset=0, limit=60, employment_type=None
):
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
            locations=["seoul", "gyeonggi"],
        )

        jobs = data.get("data", [])

        # If we got enough jobs from 수도권, return them
        if len(jobs) >= limit:
            return data, next_url, status_code

        # Step 2: If 수도권 doesn't have enough jobs, get from all Korea as fallback
        remaining_limit = limit - len(jobs)

        if remaining_limit > 0:
            # Fetch from all Korea (no location filter)
            fallback_data, fallback_next_url, fallback_status = (
                fetch_wanted_jobs_optimized(
                    category=category,
                    offset=0,  # Start from beginning for fallback
                    limit=remaining_limit,
                    locations=None,  # No location filter = all Korea
                )
            )

            fallback_jobs = fallback_data.get("data", [])

            # Filter out jobs we already have (avoid duplicates)
            existing_job_ids = {job.get("id") for job in jobs}
            new_jobs = [
                job
                for job in fallback_jobs
                if job.get("id") not in existing_job_ids
            ]

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
            category=category, offset=offset, limit=limit, locations=None
        )


def fetch_jobs_by_employment_type(
    category=None, offset=0, limit=60, employment_type="intern"
):
    """
    Optimized function to fetch jobs by employment type.
    Uses direct API filtering if supported, otherwise falls back to client-side filtering.
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit

    # No client-side filtering needed, data is already filtered by API

    data, next_url, status_code = fetch_jobs_with_location_fallback(
        category=category,
        offset=offset,
        limit=limit,
        employment_type=None,  # No API filtering
    )

    # Client-side filtering
    jobs = data.get("data", [])
    filtered_jobs = [
        job for job in jobs if job.get("employment_type") == employment_type
    ]

    # Trim to requested limit
    filtered_jobs = filtered_jobs[:limit]

    # Update response
    data["data"] = filtered_jobs

    # Build original params dict for pagination
    original_params = {"category": category, "offset": offset, "limit": limit}
    return transform_wanted_response_to_client_format(data, original_params)


def fetch_jobs_mixed_employment_types(category=None, offset=0, limit=60):
    """
    Fetch both 신입 (regular) and 인턴 (intern) positions.
    This is for when no specific employment type is requested.
    """
    # Ensure offset and limit are integers
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit

    # Fetch both employment types in one call (no employment_type filter)
    data, next_url, status_code = fetch_jobs_with_location_fallback(
        category=category, offset=offset, limit=limit, employment_type=None
    )

    # Filter for 신입 (regular) and 인턴 (intern) only
    jobs = data.get("data", [])
    filtered_jobs = [
        job
        for job in jobs
        if job.get("employment_type") in ["regular", "intern"]
    ]

    # Update response
    data["data"] = filtered_jobs

    # Build original params dict for pagination
    original_params = {"category": category, "offset": offset, "limit": limit}
    return transform_wanted_response_to_client_format(data, original_params)


def fetch_all_internships_with_employment_type_check(
    category=None, offset=0, limit=60, max_pages=3
):
    """
    Legacy function - now optimized to use the new approach.
    Reduced max_pages from 10 to 3 for better performance.
    """
    return fetch_jobs_by_employment_type(
        category=category, offset=offset, limit=limit, employment_type="intern"
    )


def fetch_wanted_internships_with_search_position(
    category=None, offset=0, limit=60, max_pages=10
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
    category=None, offset=0, limit=60, max_pages=10
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

        if params and "offset" in params:
            offset = int(params.get("offset", [str(offset + limit)])[0])
        else:
            offset = offset + limit

        page_count += 1

    # temporary response before final transformation
    tmp_wanted_response = {
        "data": all_positions,
        "links": {"next": next_url, "prev": None},
    }
    # Build original params dict for pagination
    original_params = {"category": category, "offset": offset, "limit": limit}
    # Transform the response to client format
    return transform_wanted_response_to_client_format(
        tmp_wanted_response, original_params
    )
