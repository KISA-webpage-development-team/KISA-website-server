"""
Jobs API exposed to the FE.

- GET /api/v2/jobs/
Fetch list of jobs from the third-party API 
in MVP, only Wanted API is supported.
Doc: https://linear.app/jdy-1/issue/JDY-26/apiv2jobs-api-documentation-v1-wanted-api-only
"""

import flask
import server
import server.api.jobs.third_party.wanted.wanted as wanted

@server.application.route("/api/v2/jobs/", methods=["GET"])
def get_jobs():
    """Get jobs from different sources."""
    source = flask.request.args.get("from", "third-party")
    
    if source == "third-party":
        try:
            # MVP: Only Wanted API is supported
            response = wanted.build_flask_response(flask.request.args)
            
            # Check for validation errors (400 status code)
            if "error" in response and "status_code" in response:
                return flask.Response(
                    flask.json.dumps({
                        "jobs": [],
                        "next": None,
                        "error": response["error"]
                    }, ensure_ascii=False, indent=2),
                    status=response["status_code"],  # Use the specific status code (400)
                    mimetype='application/json; charset=utf-8'
                )
            
            # Check for other errors (500 status code)
            if "error" in response:
                return flask.Response(
                    flask.json.dumps({
                        "jobs": [],
                        "next": None,
                        "error": response["error"]
                    }, ensure_ascii=False, indent=2),
                    status=500,
                    mimetype='application/json; charset=utf-8'
                )
            
            # Return successful response with Korean text support
            return flask.Response(
                flask.json.dumps(response, ensure_ascii=False, indent=2),
                mimetype='application/json; charset=utf-8'
            )
            
        except Exception as e:
            return flask.Response(
                flask.json.dumps({
                    "jobs": [],
                    "next": None,
                    "error": str(e)
                }, ensure_ascii=False, indent=2),
                status=500,
                mimetype='application/json; charset=utf-8'
            )
            
    elif source == "crawler":
        return flask.jsonify({
            "message": "Crawler job source not implemented yet."
        }), 501
    else:
        return flask.jsonify({
            "error": f"Job source '{source}' is not supported."
        }), 400