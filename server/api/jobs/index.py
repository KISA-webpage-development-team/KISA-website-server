import flask
import server

import server.api.jobs.third_party.wanted.wanted as wanted


@server.application.route("/api/v2/jobs/", methods=["GET"])
def get_jobs_info():
    source = flask.request.args.get("from", "third-party")
    if source == "third-party":
        # wanted api - internships
        # data, next_url, status_code = wanted.fetch_wanted_internships(
        #     category=flask.request.args.get('category'),
        #     offset=flask.request.args.get('offset', 0),
        #     limit=flask.request.args.get('limit', 20)
        # )

        # approach 1: fetch all internships with employment_type == 'intern'
        # NOTE: this approach works, but slow because it fetches multiple pages
        response = wanted.fetch_all_internships_with_employment_type_check(
            category=flask.request.args.get("category"),
            offset=flask.request.args.get("offset", 0),
            limit=flask.request.args.get("limit", 20),
        )

        # approach 2: fetch all internships with search position
        # NOTE: this approach is not ideal because category is not used
        # response = wanted.fetch_all_internships_with_search_position(
        #     category=flask.request.args.get("category"),
        #     offset=flask.request.args.get("offset", 0),
        #     limit=flask.request.args.get("limit", 20),
        # )

        return flask.jsonify(response), 200
    elif source == "crawler":
        # Placeholder for crawler logic
        return flask.jsonify(
            {"message": "Crawler job source not implemented yet."}
        ), 501
    else:
        return flask.jsonify(
            {"error": f"Job source '{source}' is not supported."}
        ), 400
