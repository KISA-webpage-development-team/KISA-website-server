import flask
import server
from ..helpers import token_required

@server.application.route("/api/v2/images/presigned_url/", methods=["POST"])
@token_required
def presigned_url_for_post():
    """
    Generate a pre-signed URL for uploading an image to S3.
    """
    # Fetch the file key and type from the request body
    body = flask.request.get_json()
    file_key = body["fileKey"]
    file_type = body["fileType"]

    # Generate a pre-signed URL for PUT request
    aws_client = server.model.AWSClient()
    presigned_url = aws_client.generate_presigned_url(
        "put_object",
        file_key,
        file_type
    )

    return flask.jsonify({"presignedURL": presigned_url})

@server.application.route("/api/v2/images/presigned_url/", methods=["GET"])
@token_required
def presigned_url_for_get():
    """
    Generate a pre-signed URL of an image uploaded to S3.
    """
    # Fetch the file key and type from the request body
    file_key = flask.request.args.get("fileKey", type=str)
    file_type = flask.request.args.get("fileType", type=str)

    # Generate a pre-signed URL for PUT request
    aws_client = server.model.AWSClient()
    presigned_url = aws_client.generate_presigned_url(
        "get_object",
        file_key,
        file_type
    )

    return flask.jsonify({"fileURL": presigned_url})