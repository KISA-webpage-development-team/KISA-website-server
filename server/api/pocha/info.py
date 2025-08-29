import flask
import server
import datetime
from ..helpers import token_required
from collections import defaultdict

from .image_helpers import move_image_to_pocha_folder, delete_temp_image, delete_existing_menu_image

# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/info


@server.application.route("/api/v2/pocha/status-info/", methods=["GET"])
def get_pocha():
    # retrieve the current time from the client request
    currentTime = flask.request.args.get("date", type=datetime.datetime.fromisoformat)

    if not currentTime:
        return flask.jsonify({"error": "current time not specified"}), 400

    # fetch last row from pocha table
    cursor = server.model.Cursor()
    cursor.execute("SELECT * FROM pocha ORDER BY pochaId DESC LIMIT 1", {})
    pocharow = cursor.fetchone()

    # Case 1: there is no scheduled pocha
    # if endTime <= currentTime || queryResult == None
    if pocharow == None or pocharow["endDate"] <= currentTime:
        return flask.jsonify({}), 204

    # Case 2-1: there is scheduled pocha
    # if currentTime < startTime
    if currentTime < pocharow["startDate"]:
        pocharow["ongoing"] = False
        return flask.jsonify(pocharow), 200

    # Case 2-2: there is ongoing pocha
    # if startTime <= currentTime < endTime
    if currentTime < pocharow["endDate"] and pocharow["startDate"] <= currentTime:
        pocharow["ongoing"] = True
        return flask.jsonify(pocharow), 200


# input
# {
#  "email": "string",
#  "startDate": "YYYY-MM-DDTHH:MM:SS",
#  "endDate": "YYYY-MM-DDTHH:MM:SS",
#  "title": "string",
#  "description": "string"
#  "menus": [
#      {
#          "nameKor": "string",
#          "nameEng": "string",
#          "category": "string",
#          "price": float,
#          "stock": int,
#          "isImmediatePrep": boolean,
#          "ageCheckRequired": boolean (optional, default to false)
#      }
#  ]
# }

# CREATE TABLE ebdb.pocha (
#     pochaID INT AUTO_INCREMENT PRIMARY KEY,
#     startDate DATETIME NOT NULL,
#     endDate DATETIME NOT NULL,
#     title VARCHAR(32) NOT NULL,
#     description VARCHAR(1024) NOT NULL
# );
# CREATE TABLE ebdb.menu (
#     menuID INT AUTO_INCREMENT PRIMARY KEY,
#     nameKor VARCHAR(32) NOT NULL,
#     nameEng VARCHAR(32) NOT NULL,
#     category VARCHAR(32) NOT NULL,
#     price DOUBLE(5,2) NOT NULL,
#     stock INT NOT NULL,
#     isImmediatePrep TINYINT NOT NULL,
#     parentPochaID INT NOT NULL,
#     ageCheckRequired TINYINT NOT NULL DEFAULT 0,
#     imageURL VARCHAR(512) DEFAULT NULL,
#     FOREIGN KEY (parentPochaID) REFERENCES ebdb.pocha(pochaID) ON DELETE CASCADE
# );


@server.application.route("/api/v2/pocha/", methods=["POST"])
@token_required
def create_pocha():
    data = flask.request.json

    cursor = server.model.Cursor()

    email = data.get("email")

    # VALIDATION: email required
    if not email:
        return flask.jsonify({"message": "email is required"}), 400

    # 1. if user is admin (if not, return 403)
    cursor.execute("SELECT * FROM admins WHERE email = %(email)s", {"email": email})
    admin_email = cursor.fetchone()

    if not admin_email:
        return flask.jsonify({"message": "user is not admin"}), 403

    # 2. create new pocha item ('pocha' table) with request body
    startDate = data.get("startDate")
    endDate = data.get("endDate")
    title = data.get("title")
    description = data.get("description")

    # VALIDATION: pocha info fields required
    if not startDate or not endDate or not title or not description:
        return flask.jsonify({"error": "invalid input: all fields are required"}), 400

    # VALIDATION: startDate should be later than endDate
    if startDate >= endDate:
        return flask.jsonify(
            {"error": "invalid input: startDate must be earlier than endDate"}
        ), 400

    # VALIDATION: there should be valid menu items
    menu_items = data.get("menus")
    if not menu_items:
        return flask.jsonify(
            {"error": "invalid input: at least one menu item is required"}
        ), 400

    for item in menu_items:
        nameKor = item.get("nameKor")
        nameEng = item.get("nameEng")
        category = item.get("category")
        price = item.get("price")
        stock = item.get("stock")
        isImmediatePrep = item.get("isImmediatePrep")

        if not (
            nameKor
            and nameEng
            and category
            and price is not None
            and stock is not None
            and isImmediatePrep is not None
        ):
            return flask.jsonify(
                {"error": "invalid input: all menu item fields are required"}
            ), 400

        if price < 0 or stock < 0:
            return flask.jsonify(
                {"error": "invalid input: price and stock must be non-negative"}
            ), 400

    # EXECUTE
    cursor.execute(
        """
        INSERT INTO pocha (startDate, endDate, title, description)
        VALUES (%(startDate)s, %(endDate)s, %(title)s, %(description)s)
        """,
        {
            "startDate": startDate,
            "endDate": endDate,
            "title": title,
            "description": description,
        },
    )
    new_pocha_id = cursor.lastrowid()

    # 3. create menu items for the new pocha
    # EXECUTE
    for item in menu_items:
        nameKor = item.get("nameKor")
        nameEng = item.get("nameEng")
        category = item.get("category")
        price = item.get("price")
        stock = item.get("stock")
        isImmediatePrep = item.get("isImmediatePrep")
        ageCheckRequired = item.get("ageCheckRequired", False)
        imageURL = item.get("imageURL") # Get imageURL from the item

        cursor.execute(
            """
            INSERT INTO menu (nameKor, nameEng, category, price, stock, isImmediatePrep, parentPochaID, ageCheckRequired)
            VALUES (%(nameKor)s, %(nameEng)s, %(category)s, %(price)s, %(stock)s, %(isImmediatePrep)s, %(parentPochaID)s, %(ageCheckRequired)s)
            """,
            {
                "nameKor": nameKor,
                "nameEng": nameEng,
                "category": category,
                "price": price,
                "stock": stock,
                "isImmediatePrep": isImmediatePrep,
                "parentPochaID": new_pocha_id,
                "ageCheckRequired": ageCheckRequired,
            },
        )
        
        new_menu_id = cursor.lastrowid()
        
        # If imageURL exists, move it from temp to pocha folder
        if imageURL:
            new_image_url = move_image_to_pocha_folder(imageURL, new_menu_id)
            if new_image_url: 
                delete_temp_image(imageURL)

    return flask.jsonify({"message": f"Pocha '{title}' created successfully"}), 201


@server.application.route("/api/v2/pocha/<int:pochaid>/", methods=["PUT"])
@token_required
def update_pocha(pochaid):
    data = flask.request.json

    cursor = server.model.Cursor()

    email = data.get("email")

    # VALIDATION: email required
    if not email:
        return flask.jsonify({"message": "email is required"}), 400

    # 1. if user is admin (if not, return 403)
    cursor.execute("SELECT * FROM admins WHERE email = %(email)s", {"email": email})
    admin_email = cursor.fetchone()

    if not admin_email:
        return flask.jsonify({"message": "user is not admin"}), 403

    # 2. check if pocha exists
    cursor.execute(
        "SELECT * FROM pocha WHERE pochaID = %(pochaid)s", {"pochaid": pochaid}
    )
    existing_pocha = cursor.fetchone()

    if not existing_pocha:
        return flask.jsonify({"error": "Pocha not found"}), 404

    # 3. validate pocha info fields from request body
    startDate = data.get("startDate")
    endDate = data.get("endDate")
    title = data.get("title")
    description = data.get("description")

    # VALIDATION: pocha info fields required
    if not startDate or not endDate or not title or not description:
        return flask.jsonify({"error": "invalid input: all fields are required"}), 400

    # VALIDATION: startDate should be earlier than endDate
    if startDate >= endDate:
        return flask.jsonify(
            {"error": "invalid input: startDate must be earlier than endDate"}
        ), 400

    # VALIDATION: there should be valid menu items
    menu_items = data.get("menus")
    if not menu_items:
        return flask.jsonify(
            {"error": "invalid input: at least one menu item is required"}
        ), 400

    for item in menu_items:
        nameKor = item.get("nameKor")
        nameEng = item.get("nameEng")
        category = item.get("category")
        price = item.get("price")
        stock = item.get("stock")
        isImmediatePrep = item.get("isImmediatePrep")

        if not (
            nameKor
            and nameEng
            and category
            and price is not None
            and stock is not None
            and isImmediatePrep is not None
        ):
            return flask.jsonify(
                {"error": "invalid input: all menu item fields are required"}
            ), 400

        if price < 0 or stock < 0:
            return flask.jsonify(
                {"error": "invalid input: price and stock must be non-negative"}
            ), 400

    # 4. update existing pocha info
    cursor.execute(
        """
        UPDATE pocha SET startDate = %(startDate)s, endDate = %(endDate)s, title = %(title)s, description = %(description)s
        WHERE pochaID = %(pochaid)s
        """,
        {
            "startDate": startDate,
            "endDate": endDate,
            "title": title,
            "description": description,
            "pochaid": pochaid,
        },
    )

    # 5. Handle menu items update (instead of delete and recreate)
    # Get existing menu items for this pocha
    cursor.execute(
        "SELECT menuID, nameKor, nameEng, category, price, stock, isImmediatePrep, ageCheckRequired FROM menu WHERE parentPochaID = %(pochaid)s",
        {"pochaid": pochaid}
    )
    existing_menus = cursor.fetchall()
    
    # Create a map of existing menus by name for easy lookup
    existing_menu_map = {}
    for existing_menu in existing_menus:
        # Use nameKor as the key since it should be unique within a pocha
        key = existing_menu['nameKor']
        existing_menu_map[key] = existing_menu
    
    # Track which existing menus we've processed
    processed_existing_menus = set()
    
    # Process each menu item from the request
    for item in menu_items:
        nameKor = item.get("nameKor")
        nameEng = item.get("nameEng")
        category = item.get("category")
        price = item.get("price")
        stock = item.get("stock")
        isImmediatePrep = item.get("isImmediatePrep")
        ageCheckRequired = item.get("ageCheckRequired", False)
        imageURL = item.get("imageURL")

        # 이미 존재하는 메뉴 항목 처리
        if nameKor in existing_menu_map:
            # Update existing menu item
            existing_menu = existing_menu_map[nameKor]
            existing_menu_id = existing_menu['menuID']
            processed_existing_menus.add(nameKor)
            
            cursor.execute(
                """
                UPDATE menu SET nameEng = %(nameEng)s, category = %(category)s, price = %(price)s, 
                stock = %(stock)s, isImmediatePrep = %(isImmediatePrep)s, ageCheckRequired = %(ageCheckRequired)s
                WHERE menuID = %(menuID)s
                """,
                {
                    "nameEng": nameEng,
                    "category": category,
                    "price": price,
                    "stock": stock,
                    "isImmediatePrep": isImmediatePrep,
                    "ageCheckRequired": ageCheckRequired,
                    "menuID": existing_menu_id,
                },
            )
            
            # Handle image update if provided
            if imageURL and len(imageURL) > 0:
                print(f"Updating image for existing menu: {nameKor}, menuID: {existing_menu_id}")
                new_image_url = move_image_to_pocha_folder(imageURL, existing_menu_id, is_update=True)
                if new_image_url:
                    delete_temp_image(imageURL)
                    # Update imageURL in the database
                    cursor.execute(
                        """
                        UPDATE menu SET imageURL = %(imageURL)s WHERE menuID = %(menuID)s
                        """,
                        {
                            "imageURL": new_image_url,
                            "menuID": existing_menu_id,
                        },
        
                    )

        # 기존에 없던 신규 메뉴 항목 처리
        else:
            # Insert new menu item
            cursor.execute(
                """
                INSERT INTO menu (nameKor, nameEng, category, price, stock, isImmediatePrep, parentPochaID, ageCheckRequired)
                VALUES (%(nameKor)s, %(nameEng)s, %(category)s, %(price)s, %(stock)s, %(isImmediatePrep)s, %(parentPochaID)s, %(ageCheckRequired)s)
                """,
                {
                    "nameKor": nameKor,
                    "nameEng": nameEng,
                    "category": category,
                    "price": price,
                    "stock": stock,
                    "isImmediatePrep": isImmediatePrep,
                    "parentPochaID": pochaid,
                    "ageCheckRequired": ageCheckRequired,
                },
            )
            
            #가장 최근에 추가된 신규 메뉴 ID
            new_menu_id = cursor.lastrowid()
            
            # Handle image for new menu item
            if imageURL and len(imageURL) > 0:
                print(f"Adding image for new menu: {nameKor}, menuID: {new_menu_id}")
                new_image_url = move_image_to_pocha_folder(imageURL, new_menu_id, is_update=False)
                if new_image_url:
                    delete_temp_image(imageURL)
    
    # Delete menu items that are no longer in the updated list
    for existing_menu in existing_menus:
        if existing_menu['nameKor'] not in processed_existing_menus:
            menu_id_to_delete = existing_menu['menuID']
            print(f"Deleting menu item: {existing_menu['nameKor']}, menuID: {menu_id_to_delete}")
            
            # Delete associated image if it exists
            delete_existing_menu_image(menu_id_to_delete)
            
            # Delete the menu item
            cursor.execute(
                "DELETE FROM menu WHERE menuID = %(menuID)s",
                {"menuID": menu_id_to_delete}
            )

    return flask.jsonify({"message": f"Pocha '{title}' updated successfully"}), 200


@server.application.route("/api/v2/pocha/menu/<int:pochaid>/", methods=["GET"])
# @token_required
def get_pocha_menu(pochaid):
    # error handling: there is no pocha with the given pochaid
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT * FROM pocha WHERE pochaID = %(pochaid)s
        """,
        {"pochaid": pochaid},
    )
    existing_pocha = cursor.fetchone()
    if not existing_pocha:
        return flask.jsonify({"error": "Pocha not found"}), 404

    # fetch all rows with parentPochaID == pochaid from menu table
    cursor.execute(
        """
        SELECT * FROM menu WHERE parentPochaID = %(pochaid)s
        """,
        {"pochaid": pochaid},
    )
    menus = cursor.fetchall()

    # sort raw table data by its categories into a temporary dictionary
    category_dict = defaultdict(list)
    for menu in menus:
        category = menu["category"]
        del menu["category"]
        category_dict[category].append(menu)

    # build response in right format
    response = []
    for key in category_dict:
        response.append({"category": key, "menusList": category_dict[key]})

    return flask.jsonify(response), 200
