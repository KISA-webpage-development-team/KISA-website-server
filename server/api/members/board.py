"""/about/members board roster.

A board year is identified by its start year (2026 is the 26-27 board) and is
shown publicly only once published. Entries are standalone records; each has a
tier ('president' or 'member') and a position that orders it within its tier.
"""
import flask
import server
from ..helpers import admin_required, authenticated_email

TIERS = ("president", "member")
MIN_START_YEAR = 2000
MAX_START_YEAR = 2100
MIN_CLASS_YEAR = 1950
MAX_CLASS_YEAR = 2100

ENTRY_COLUMNS = """
    boardmemberid, startyear, name, major, classyear, roles, islead, tier,
    position, createdby, updatedby, created, updated
"""

# President tier first, then stored position.
ENTRY_ORDER = "(tier = 'member'), position, boardmemberid"


def _error(message, status):
    return flask.jsonify({"error": message}), status


def _isoformat(value):
    return value.isoformat() if value is not None else None


def _label(start_year):
    return f"{start_year % 100:02d}-{(start_year + 1) % 100:02d}"


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _public_entry(row):
    return {
        "boardMemberID": row["boardMemberID"],
        "name": row["name"],
        "major": row["major"],
        "classYear": row["classYear"],
        "roles": row["roles"],
        "isLead": row["isLead"],
        "tier": row["tier"],
    }


def _admin_entry(row):
    return {
        **_public_entry(row),
        "startYear": row["startYear"],
        "position": row["position"],
        "createdBy": row["createdBy"],
        "updatedBy": row["updatedBy"],
        "created": _isoformat(row["created"]),
        "updated": _isoformat(row["updated"]),
    }


def _fetch_year(cursor, start_year):
    cursor.execute(
        "SELECT startyear, published FROM boardyears WHERE startyear = %(year)s",
        {"year": start_year},
    )
    return cursor.fetchone()


def _fetch_entry(cursor, entry_id):
    cursor.execute(
        f"SELECT {ENTRY_COLUMNS} FROM boardmembers WHERE boardmemberid = %(id)s",
        {"id": entry_id},
    )
    return cursor.fetchone()


def _fetch_entries(cursor, start_year):
    cursor.execute(
        f"SELECT {ENTRY_COLUMNS} FROM boardmembers WHERE startyear = %(year)s ORDER BY {ENTRY_ORDER}",
        {"year": start_year},
    )
    return cursor.fetchall()


def _fetch_years(cursor, published_only):
    """Board years newest first, each with its entries in display order."""
    where = "WHERE published" if published_only else ""
    cursor.execute(f"SELECT startyear, published FROM boardyears {where} ORDER BY startyear DESC", {})
    years = cursor.fetchall()
    cursor.execute(
        f"""
        SELECT {ENTRY_COLUMNS} FROM boardmembers
        WHERE startyear IN (SELECT startyear FROM boardyears {where})
        ORDER BY startyear, {ENTRY_ORDER}
        """,
        {},
    )
    entries = {}
    for row in cursor.fetchall():
        entries.setdefault(row["startYear"], []).append(row)
    return [(year, entries.get(year["startYear"], [])) for year in years]


def _public_year(year, entries):
    return {
        "startYear": year["startYear"],
        "label": _label(year["startYear"]),
        "entries": [_public_entry(row) for row in entries],
    }


def _admin_year(year, entries):
    return {
        "startYear": year["startYear"],
        "label": _label(year["startYear"]),
        "published": year["published"],
        "entries": [_admin_entry(row) for row in entries],
    }


def _admin_year_response(cursor, start_year, status=200):
    year = _fetch_year(cursor, start_year)
    return flask.jsonify(_admin_year(year, _fetch_entries(cursor, start_year))), status


def _parse_entry(data):
    """Validates the editable entry fields. Returns (fields, error message or None)."""
    name = data.get("name")
    major = data.get("major")
    class_year = data.get("classYear")
    roles = data.get("roles")
    is_lead = data.get("isLead", False)
    tier = data.get("tier")

    if not isinstance(name, str) or not name.strip():
        return None, "name is required"
    if not isinstance(major, str) or not major.strip():
        return None, "major is required"
    if not _is_int(class_year) or not MIN_CLASS_YEAR <= class_year <= MAX_CLASS_YEAR:
        return None, "classYear must be a four-digit year"
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        return None, "roles must be a list of strings"
    roles = [role.strip() for role in roles if role.strip()]
    if not roles:
        return None, "at least one role is required"
    if not isinstance(is_lead, bool):
        return None, "isLead must be a boolean"
    if tier not in TIERS:
        return None, "tier must be 'president' or 'member'"

    return {
        "name": name.strip(),
        "major": major.strip(),
        "classYear": class_year,
        "roles": roles,
        "isLead": is_lead,
        "tier": tier,
    }, None


def _next_position(cursor, start_year, tier):
    cursor.execute(
        """
        SELECT COALESCE(MAX(position) + 1, 0) AS next FROM boardmembers
        WHERE startyear = %(year)s AND tier = %(tier)s
        """,
        {"year": start_year, "tier": tier},
    )
    return cursor.fetchone()["next"]


# ---- public -------------------------------------------------------------------

@server.application.route("/api/v2/members/", methods=["GET"])
def get_board():
    cursor = server.model.Cursor()
    years = _fetch_years(cursor, published_only=True)
    return flask.jsonify([_public_year(year, entries) for year, entries in years]), 200


# ---- admin: board years -------------------------------------------------------

@server.application.route("/api/v2/members/admin/", methods=["GET"])
@admin_required
def get_board_admin():
    cursor = server.model.Cursor()
    years = _fetch_years(cursor, published_only=False)
    return flask.jsonify([_admin_year(year, entries) for year, entries in years]), 200


@server.application.route("/api/v2/members/years/", methods=["POST"])
@admin_required
def create_board_year():
    data = flask.request.get_json(silent=True) or {}
    start_year = data.get("startYear")
    copy_from = data.get("copyFrom")
    if not _is_int(start_year) or not MIN_START_YEAR <= start_year <= MAX_START_YEAR:
        return _error("startYear must be a four-digit year", 400)
    if copy_from is not None and not _is_int(copy_from):
        return _error("copyFrom must be a board year", 400)

    cursor = server.model.Cursor()
    if copy_from is not None and not _fetch_year(cursor, copy_from):
        return _error("copyFrom board year not found", 400)

    cursor.execute(
        "INSERT INTO boardyears (startyear) VALUES (%(year)s) ON CONFLICT (startyear) DO NOTHING",
        {"year": start_year},
    )
    if cursor.rowcount() == 0:
        return _error("board year already exists", 409)

    if copy_from is not None:
        cursor.execute(
            """
            INSERT INTO boardmembers
                (startyear, name, major, classyear, roles, islead, tier, position,
                 createdby, updatedby)
            SELECT %(year)s, name, major, classyear, roles, islead, tier, position,
                   %(email)s, %(email)s
            FROM boardmembers WHERE startyear = %(from)s
            ORDER BY boardmemberid
            """,
            {"year": start_year, "from": copy_from, "email": authenticated_email()},
        )
    return _admin_year_response(cursor, start_year, 201)


def _set_published(start_year, published):
    cursor = server.model.Cursor()
    year = _fetch_year(cursor, start_year)
    if not year:
        return _error("board year not found", 404)
    if year["published"] == published:
        state = "published" if published else "unpublished"
        return _error(f"board year is already {state}", 409)
    cursor.execute(
        "UPDATE boardyears SET published = %(published)s WHERE startyear = %(year)s",
        {"published": published, "year": start_year},
    )
    return _admin_year_response(cursor, start_year)


@server.application.route("/api/v2/members/years/<int:start_year>/publish/", methods=["POST"])
@admin_required
def publish_board_year(start_year):
    return _set_published(start_year, True)


@server.application.route("/api/v2/members/years/<int:start_year>/unpublish/", methods=["POST"])
@admin_required
def unpublish_board_year(start_year):
    return _set_published(start_year, False)


@server.application.route("/api/v2/members/years/<int:start_year>/", methods=["DELETE"])
@admin_required
def delete_board_year(start_year):
    cursor = server.model.Cursor()
    year = _fetch_year(cursor, start_year)
    if not year:
        return _error("board year not found", 404)
    if year["published"]:
        return _error("unpublish the board year before deleting it", 409)
    cursor.execute("DELETE FROM boardyears WHERE startyear = %(year)s", {"year": start_year})
    return flask.jsonify({"message": "board year deleted"}), 200


@server.application.route("/api/v2/members/years/<int:start_year>/order/", methods=["PUT"])
@admin_required
def put_board_order(start_year):
    data = flask.request.get_json(silent=True) or {}
    order = data.get("order")
    if not isinstance(order, list):
        return _error("order must be a list of entry ids", 400)

    cursor = server.model.Cursor()
    if not _fetch_year(cursor, start_year):
        return _error("board year not found", 404)
    entry_ids = {row["boardMemberID"] for row in _fetch_entries(cursor, start_year)}
    if len(order) != len(set(order)) or set(order) != entry_ids:
        return _error("entries changed since this order was loaded", 409)

    # Entries are ordered by tier before position, so one sequence across both
    # tiers keeps each tier in the order given.
    for position, entry_id in enumerate(order):
        cursor.execute(
            "UPDATE boardmembers SET position = %(position)s WHERE boardmemberid = %(id)s",
            {"position": position, "id": entry_id},
        )
    return _admin_year_response(cursor, start_year)


# ---- admin: entries -----------------------------------------------------------

@server.application.route("/api/v2/members/years/<int:start_year>/entries/", methods=["POST"])
@admin_required
def create_board_entry(start_year):
    data = flask.request.get_json(silent=True) or {}
    fields, error = _parse_entry(data)
    if error:
        return _error(error, 400)

    cursor = server.model.Cursor()
    if not _fetch_year(cursor, start_year):
        return _error("board year not found", 404)

    email = authenticated_email()
    cursor.execute(
        """
        INSERT INTO boardmembers
            (startyear, name, major, classyear, roles, islead, tier, position,
             createdby, updatedby)
        VALUES (%(year)s, %(name)s, %(major)s, %(classYear)s, %(roles)s, %(isLead)s,
                %(tier)s, %(position)s, %(email)s, %(email)s)
        RETURNING boardmemberid
        """,
        {
            **fields,
            "year": start_year,
            "position": _next_position(cursor, start_year, fields["tier"]),
            "email": email,
        },
    )
    entry_id = cursor.fetchone()["boardMemberID"]
    return flask.jsonify(_admin_entry(_fetch_entry(cursor, entry_id))), 201


@server.application.route("/api/v2/members/entries/<int:entry_id>/", methods=["PUT"])
@admin_required
def update_board_entry(entry_id):
    cursor = server.model.Cursor()
    entry = _fetch_entry(cursor, entry_id)
    if not entry:
        return _error("board entry not found", 404)

    data = flask.request.get_json(silent=True) or {}
    fields, error = _parse_entry(data)
    if error:
        return _error(error, 400)

    # An entry moved to the other tier goes to the end of that tier.
    position = entry["position"]
    if fields["tier"] != entry["tier"]:
        position = _next_position(cursor, entry["startYear"], fields["tier"])

    cursor.execute(
        """
        UPDATE boardmembers
        SET name = %(name)s, major = %(major)s, classyear = %(classYear)s,
            roles = %(roles)s, islead = %(isLead)s, tier = %(tier)s,
            position = %(position)s, updatedby = %(email)s, updated = now()
        WHERE boardmemberid = %(id)s
        """,
        {**fields, "position": position, "email": authenticated_email(), "id": entry_id},
    )
    return flask.jsonify(_admin_entry(_fetch_entry(cursor, entry_id))), 200


@server.application.route("/api/v2/members/entries/<int:entry_id>/", methods=["DELETE"])
@admin_required
def delete_board_entry(entry_id):
    cursor = server.model.Cursor()
    if not _fetch_entry(cursor, entry_id):
        return _error("board entry not found", 404)
    cursor.execute("DELETE FROM boardmembers WHERE boardmemberid = %(id)s", {"id": entry_id})
    return flask.jsonify({"message": "board entry deleted"}), 200
