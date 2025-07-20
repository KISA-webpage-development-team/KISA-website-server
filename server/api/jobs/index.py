import flask
import server

import server.api.jobs.third_party.wanted.wanted as wanted


@server.application.route("/api/v2/jobs/", methods=["GET"])
def get_jobs_info():
    source = flask.request.args.get("from", "third-party")
    
    if source == "third-party":
        # Convert Flask string parameters to integers BEFORE passing to wanted functions
        try:
            offset = int(flask.request.args.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
            
        try:
            limit = int(flask.request.args.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
            
        category = flask.request.args.get("category")  # This can stay as string
        
        response = wanted.fetch_all_internships_with_employment_type_check(
            category=category,
            offset=offset,    # Now definitely an integer
            limit=limit,      # Now definitely an integer
        )
        
        return flask.Response(
            flask.json.dumps(response, ensure_ascii=False, indent=2),
            mimetype='application/json; charset=utf-8'
        )
        
    elif source == "crawler":
        return flask.jsonify(
            {"message": "Crawler job source not implemented yet."}
        ), 501
    else:
        return flask.jsonify(
            {"error": f"Job source '{source}' is not supported."}
        ), 400