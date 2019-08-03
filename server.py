from flask import Flask, request
import googlemaps
import sys
import firebase_admin

from firebase_admin import credentials
from firebase_admin import firestore

import json
app = Flask(__name__)

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {
  'projectId': 'big-data-analysis-ximing',
})

db= firestore.client()
doc_ref = db.collection(u'orderdata').document(u'orders')

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/send', methods=['GET', 'POST'])
def receive_data():
    if request.method == 'POST':
        data = request.data
        result = json.loads(data)
        plan = result['plan']
        score = result['score']
        route = result['route']
        orders = result['orders']

        store_data(plan,score,route,orders)
        return 'success'
    return "please use post method"
def store_data(plan,score,route,orders):
    newRoute = []
    for tuple in route:
        newRoute.append(tuple[0])
        newRoute.append(tuple[1])
    newOrder = {}
    for order in orders:
        temporder = []
        temporder.append(order[1][0][0])
        temporder.append(order[1][0][1])
        temporder.append(order[1][1][0])
        temporder.append(order[1][1][1])
        temporder.append(order[1][2])
        newOrder[order[0]] = temporder
    # newOrder["OrderId"] = orders[0][0]
    # source = []
    # source.append(orders[0][1][0][0])
    # source.append(orders[0][1][0][1])
    # destination = []
    # destination.append(orders[0][1][1][0])
    # destination.append(orders[0][1][1][1])
    # newOrder['source'] = source
    # newOrder['destination'] = destination
    # newOrder['price'] = orders[0][1][2]
    print(newRoute)
    print(newOrder)
    print(score)
    doc_ref.set({
    u'plan': plan,
    u'score': score,
    u'route': newRoute,
    u'orders': newOrder})
    return "stored"
if __name__ == '__main__':
    app.run(debug=True, port=6789)
