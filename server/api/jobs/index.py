import flask
import server
import server.api.jobs.third_party.wanted.wanted as wanted

@server.application.route("/api/v2/jobs/", methods=["GET"])
def get_jobs_info():
    source = flask.request.args.get("from", "third-party")
    
    if source == "third-party":
        try:
            # Use the optimized build_flask_response function
            response = wanted.build_flask_response(flask.request.args)
            
            # Check for errors
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