"""Home page featured carousel.

An item's stored status is 'live' or 'archive'. Its effective status, which
every read uses, is 'archive' when it is stored as archive or its end date has
passed (end of that day in America/Detroit); nothing is written when an end
date passes. Live items are shown in stored position order.
"""
import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import flask
import server
from ..helpers import admin_required, authenticated_email
from . import images

TIMEZONE = "America/Detroit"

EFFECTIVE_STATUS = f"""
    CASE WHEN status = 'archive'
           OR (enddate IS NOT NULL AND enddate < (now() AT TIME ZONE '{TIMEZONE}')::date)
         THEN 'archive' ELSE 'live' END
"""

COLUMNS = f"""
    carouselitemid, title, description, link, imagepublicid, imageversion, enddate,
    position, archivedat, createdby, updatedby, created, updated,
    {EFFECTIVE_STATUS} AS effectivestatus
"""

IS_LIVE = f"({EFFECTIVE_STATUS}) = 'live'"


def _error(message, status):
    return flask.jsonify({"error": message}), status


def _isoformat(value):
    return value.isoformat() if value is not None else None


def _public_item(row):
    return {
        "carouselItemID": row["carouselItemID"],
        "title": row["title"],
        "description": row["description"],
        "link": row["link"],
        "imageUrl": images.image_url(row["imagePublicID"], row["imageVersion"]),
    }


def _admin_item(row):
    return {
        **_public_item(row),
        "endDate": _isoformat(row["endDate"]),
        "status": row["effectiveStatus"],
        "position": row["position"],
        "archivedAt": _isoformat(row["archivedAt"]),
        "createdBy": row["createdBy"],
        "updatedBy": row["updatedBy"],
        "created": _isoformat(row["created"]),
        "updated": _isoformat(row["updated"]),
    }


def _fetch_item(cursor, item_id):
    cursor.execute(
        f"SELECT {COLUMNS} FROM carouselitems WHERE carouselitemid = %(id)s",
        {"id": item_id},
    )
    return cursor.fetchone()


def _fetch_live(cursor):
    cursor.execute(
        f"SELECT {COLUMNS} FROM carouselitems WHERE {IS_LIVE} ORDER BY position",
        {},
    )
    return cursor.fetchall()


def _today():
    return datetime.datetime.now(ZoneInfo(TIMEZONE)).date()


def _parse_end_date(value, allow_past):
    """Returns (date or None, error message or None)."""
    if value in (None, ""):
        return None, None
    try:
        end_date = datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None, "endDate must be a YYYY-MM-DD date"
    if not allow_past and end_date < _today():
        return None, "endDate is in the past"
    return end_date, None


def _parse_fields(data, allow_past_end_date):
    """Validates the editable fields. Returns (fields, error message or None)."""
    title = data.get("title")
    description = data.get("description")
    link = data.get("link") or None

    if not isinstance(title, str) or not title.strip():
        return None, "title is required"
    if not isinstance(description, str) or not description.strip():
        return None, "description is required"
    if link is not None:
        parsed = urlparse(link) if isinstance(link, str) else None
        if not parsed or parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None, "link must be an http(s) URL"

    end_date, error = _parse_end_date(data.get("endDate"), allow_past_end_date)
    if error:
        return None, error

    return {
        "title": title.strip(),
        "description": description,
        "link": link,
        "endDate": end_date,
    }, None


def _is_temp_public_id(value):
    return isinstance(value, str) and value.startswith(images.TEMP_PREFIX)


def _rule_key(row):
    """End-date rule: soonest end date first, undated after, newest first."""
    end_date = row["endDate"]
    return (end_date is None, end_date or datetime.date.max, -row["created"].timestamp())


def _write_positions(cursor, item_ids):
    for position, item_id in enumerate(item_ids):
        cursor.execute(
            "UPDATE carouselitems SET position = %(position)s WHERE carouselitemid = %(id)s",
            {"position": position, "id": item_id},
        )


def _place_by_end_date_rule(cursor, item_id):
    """Put a live item before the first live item, in the current order, that
    it precedes under the end-date rule; other items keep their order."""
    item = _fetch_item(cursor, item_id)
    others = [row for row in _fetch_live(cursor) if row["carouselItemID"] != item_id]
    index = next(
        (i for i, other in enumerate(others) if _rule_key(item) < _rule_key(other)),
        len(others),
    )
    ordered = [row["carouselItemID"] for row in others]
    ordered.insert(index, item_id)
    _write_positions(cursor, ordered)


# ---- public -------------------------------------------------------------------

@server.application.route("/api/v2/carousel/", methods=["GET"])
def get_carousel():
    cursor = server.model.Cursor()
    return flask.jsonify([_public_item(row) for row in _fetch_live(cursor)]), 200


# ---- admin --------------------------------------------------------------------

@server.application.route("/api/v2/carousel/admin/", methods=["GET"])
@admin_required
def get_carousel_admin():
    cursor = server.model.Cursor()
    live = _fetch_live(cursor)
    cursor.execute(
        f"""
        SELECT {COLUMNS} FROM carouselitems
        WHERE NOT {IS_LIVE}
        ORDER BY CASE WHEN status = 'archive' THEN archivedat
                      ELSE (enddate + 1)::timestamp END DESC NULLS LAST,
                 carouselitemid DESC
        """,
        {},
    )
    archive = cursor.fetchall()
    return flask.jsonify({
        "live": [_admin_item(row) for row in live],
        "archive": [_admin_item(row) for row in archive],
    }), 200


@server.application.route("/api/v2/carousel/<int:item_id>/", methods=["GET"])
@admin_required
def get_carousel_item(item_id):
    item = _fetch_item(server.model.Cursor(), item_id)
    if not item:
        return _error("carousel item not found", 404)
    return flask.jsonify(_admin_item(item)), 200


@server.application.route("/api/v2/carousel/", methods=["POST"])
@admin_required
def create_carousel_item():
    data = flask.request.get_json(silent=True) or {}
    fields, error = _parse_fields(data, allow_past_end_date=False)
    if error:
        return _error(error, 400)

    temp_public_id = data.get("imageTempPublicID")
    copy_from = data.get("copyImageFrom")
    if bool(temp_public_id) == (copy_from is not None):
        return _error("provide exactly one of imageTempPublicID or copyImageFrom", 400)
    if temp_public_id and not _is_temp_public_id(temp_public_id):
        return _error("imageTempPublicID must be a temp/ upload", 400)

    cursor = server.model.Cursor()
    source = None
    if copy_from is not None:
        if not isinstance(copy_from, int) or isinstance(copy_from, bool):
            return _error("copyImageFrom must be a carousel item id", 400)
        source = _fetch_item(cursor, copy_from)
        if not source:
            return _error("copyImageFrom item not found", 400)

    # The image is named after the item, so reserve the id before claiming it.
    cursor.execute(
        "SELECT nextval(pg_get_serial_sequence('carouselitems', 'carouselitemid')) AS id",
        {},
    )
    item_id = cursor.fetchone()["id"]

    try:
        if source:
            version = images.copy_image(source["imagePublicID"], source["imageVersion"], item_id)
        else:
            version = images.claim_temp_image(temp_public_id, item_id)
    except Exception as error:
        print(f"Carousel image claim failed: {error}")
        return _error("image storage failed", 502)

    email = authenticated_email()
    cursor.execute(
        """
        INSERT INTO carouselitems
            (carouselitemid, title, description, link, imagepublicid, imageversion,
             enddate, status, createdby, updatedby)
        VALUES (%(id)s, %(title)s, %(description)s, %(link)s, %(publicID)s, %(version)s,
                %(endDate)s, 'live', %(email)s, %(email)s)
        """,
        {
            **fields,
            "id": item_id,
            "publicID": images.item_public_id(item_id),
            "version": version,
            "email": email,
        },
    )
    _place_by_end_date_rule(cursor, item_id)
    return flask.jsonify(_admin_item(_fetch_item(cursor, item_id))), 201


@server.application.route("/api/v2/carousel/<int:item_id>/", methods=["PUT"])
@admin_required
def update_carousel_item(item_id):
    cursor = server.model.Cursor()
    item = _fetch_item(cursor, item_id)
    if not item:
        return _error("carousel item not found", 404)

    data = flask.request.get_json(silent=True) or {}
    fields, error = _parse_fields(data, allow_past_end_date=True)
    if error:
        return _error(error, 400)

    version = item["imageVersion"]
    temp_public_id = data.get("imageTempPublicID")
    if temp_public_id:
        if not _is_temp_public_id(temp_public_id):
            return _error("imageTempPublicID must be a temp/ upload", 400)
        try:
            version = images.claim_temp_image(temp_public_id, item_id)
        except Exception as error:
            print(f"Carousel image replace failed: {error}")
            return _error("image storage failed", 502)

    cursor.execute(
        """
        UPDATE carouselitems
        SET title = %(title)s, description = %(description)s, link = %(link)s,
            enddate = %(endDate)s, imageversion = %(version)s,
            updatedby = %(email)s, updated = now()
        WHERE carouselitemid = %(id)s
        """,
        {**fields, "version": version, "email": authenticated_email(), "id": item_id},
    )
    return flask.jsonify(_admin_item(_fetch_item(cursor, item_id))), 200


@server.application.route("/api/v2/carousel/<int:item_id>/archive/", methods=["POST"])
@admin_required
def archive_carousel_item(item_id):
    cursor = server.model.Cursor()
    item = _fetch_item(cursor, item_id)
    if not item:
        return _error("carousel item not found", 404)
    if item["effectiveStatus"] == "archive":
        return _error("carousel item is already archived", 409)

    cursor.execute(
        """
        UPDATE carouselitems
        SET status = 'archive', position = NULL, archivedat = now(),
            updatedby = %(email)s, updated = now()
        WHERE carouselitemid = %(id)s
        """,
        {"email": authenticated_email(), "id": item_id},
    )
    return flask.jsonify(_admin_item(_fetch_item(cursor, item_id))), 200


@server.application.route("/api/v2/carousel/<int:item_id>/restore/", methods=["POST"])
@admin_required
def restore_carousel_item(item_id):
    cursor = server.model.Cursor()
    item = _fetch_item(cursor, item_id)
    if not item:
        return _error("carousel item not found", 404)
    if item["effectiveStatus"] == "live":
        return _error("carousel item is already live", 409)

    data = flask.request.get_json(silent=True) or {}
    end_date, error = _parse_end_date(data.get("endDate"), allow_past=False)
    if error:
        return _error(error, 400)

    cursor.execute(
        """
        UPDATE carouselitems
        SET status = 'live', enddate = %(endDate)s, archivedat = NULL,
            updatedby = %(email)s, updated = now()
        WHERE carouselitemid = %(id)s
        """,
        {"endDate": end_date, "email": authenticated_email(), "id": item_id},
    )
    _place_by_end_date_rule(cursor, item_id)
    return flask.jsonify(_admin_item(_fetch_item(cursor, item_id))), 200


@server.application.route("/api/v2/carousel/<int:item_id>/", methods=["DELETE"])
@admin_required
def delete_carousel_item(item_id):
    cursor = server.model.Cursor()
    item = _fetch_item(cursor, item_id)
    if not item:
        return _error("carousel item not found", 404)

    try:
        images.delete_image(item["imagePublicID"])
    except Exception as error:
        print(f"Carousel image delete failed: {error}")
        return _error("image storage failed", 502)

    cursor.execute(
        "DELETE FROM carouselitems WHERE carouselitemid = %(id)s", {"id": item_id}
    )
    return flask.jsonify({"message": "carousel item removed"}), 200


@server.application.route("/api/v2/carousel/order/", methods=["PUT"])
@admin_required
def put_carousel_order():
    data = flask.request.get_json(silent=True) or {}
    order = data.get("order")
    if not isinstance(order, list):
        return _error("order must be a list of carousel item ids", 400)

    cursor = server.model.Cursor()
    live_ids = {row["carouselItemID"] for row in _fetch_live(cursor)}
    if len(order) != len(set(order)) or set(order) != live_ids:
        return _error("live items changed since this order was loaded", 409)

    _write_positions(cursor, order)
    return flask.jsonify([_admin_item(row) for row in _fetch_live(cursor)]), 200
