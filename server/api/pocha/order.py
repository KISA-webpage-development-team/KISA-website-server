import flask
import server
from ..helpers import token_required, check_orderItems_and_delete
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/order

@server.application.route('/api/v2/pocha/orders/<string:email>/<int:pochaID>/', methods=['GET'])
# @token_required
def get_user_orders(email, pochaID):
    '''
    Fetch user's active orders by email and pochaID
    '''
    # check if active order exists 
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT orderID FROM `order`
        WHERE email = %(email)s 
        AND parentPochaID = %(parentPochaID)s 
        AND isPaid = %(isPaid)s
        """,
        {
            'email': email,
            'parentPochaID': pochaID,
            'isPaid': True
        }
    )
    active_order = cursor.fetchall()

    # fetch all orderItems with orderID
    

    '''
    {
        pending: { // status 마다 
            orderItemID : int,
            status : string,
            quantity: int,
            menu: { //category 빼고 다 
                menuID: number;
                nameKor: string;
                nameEng: string;
                price: number;
                stock: number;
                isImmediatePrep: boolean;
                parentPochaId: number;
            };
        },
        preparing: { ...  위와 같다. }
        ready: { ...  위와 같다. }
    }
    '''
    pass

