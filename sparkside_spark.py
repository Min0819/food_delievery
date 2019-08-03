import socket
from pyspark import SparkContext
from pyspark.streaming import StreamingContext
from datetime import datetime, timedelta
from pprint import pprint
import googlemaps
import sys
import json 
import requests
## set the driver's start position
CURRENT_POSITION = [(28.4733589,-81.465559)]
## google maps api set
## put your API key to 'key = '
gmaps = googlemaps.Client(key='')##put your key here
TCP_IP = socket.gethostname()
TCP_PORT = 9998
# Create a local StreamingContext with two working threads and a batch interval of 1 seconds
sc = SparkContext(master = "local[2]", appName = "bus")
sc.setLogLevel("ERROR")
ssc = StreamingContext(sc, 2)
# Create a DStream that will connect to hostname:port, like localhost:9999
lines = ssc.socketTextStream(TCP_IP, TCP_PORT)

## extract useful data from order
def get_orders(x):
    fields = x.split(",")
    OrderID = fields[0]
    price = float(fields[-1])
    restaurant= (float(fields[1]), float(fields[2]))
    destination = (float(fields[3]), float(fields[4]))
    return [(OrderID, [restaurant,destination,price])]
## compute distance matrix
def compute_graph(positions):
    ## store all the locations
    real_position = []
    for i in range(len(positions)):
        ## put restaurant location
        real_position.append(positions[i][1][0])
        ## put customers location
        real_position.append(positions[i][1][1])
    ## add start point
    mapcompute = CURRENT_POSITION+real_position

    ## google maps api distance matrix
    now = datetime.now()
    directions_result = gmaps.distance_matrix(mapcompute,mapcompute,mode="driving",departure_time=now)
    ## build the graph, extract distance information from request result.
    graph = [[0 for i in range(len(mapcompute))]for j in range(len(mapcompute))]
    for i in range(len(mapcompute)):
        for j in range(len(mapcompute)):
            distance = directions_result['rows'][i]['elements'][j]['duration']['value']
            graph[i][j] = distance
    ## append the graph to the end of rdd
    positions.append(graph)
    positions.append(mapcompute)
    return positions
def compute_score_list(graph):

    orders = graph[:-2]
    real_graph = graph[-2]
    positions = graph[-1]
    result = []
    ## compute priority of orders
    for i in range(1,len(real_graph[0]),2):
        ## get orders' reward
        price = orders[i//2][1][2]
        ## reward/time_consumed
        scores = price*60/(real_graph[0][i]+real_graph[i][i+1])
        result.append((orders[i//2][0],scores,i))
    result.sort(key = lambda x : -x[1])
    graph.append(result)
    return graph

def compute_1_order(x):
    k = 1 
    return compute_k_order(x,k)

def compute_2_order(x):
    k = 2
    return compute_k_order(x,k)
    
def compute_3_order(x):
    k = 3
    return compute_k_order(x,k)
    
def compute_4_order(x):
    k = 4
    return compute_k_order(x,k)
## compute route
def compute_k_order(x,k):
    score_list = x[-1]
    positions = x[-2]
    graph = x[-3]

    orders = x[:-3]
    if k >=len(orders):
        k = len(orders)
    ## order_used is the index of order which we choose to make the plan in the graph
    order_used = []
    ## new_orders contains full information of order we choose
    new_orders = []
    for i in range(min(k,len(orders))):
        order_used.append(score_list[i][2])
    money = 0 
    ##compute total reward
    for index in order_used:
        i = index //2 
        money += orders[i][1][2]
        new_orders.append(orders[i])

    path = [0]
    total_time = 0
    order_finished = 0
    current_point = 0
    next_points = []
    ##build next points list
    for i in order_used:
        next_points.append(i)
    ## greedy algorithm to compute route
    ## path is the index list of each location in the graph
    while order_finished <k and len(next_points) != 0 :
        min_distance = sys.maxsize
        delete_point = None 
        for point in next_points:
            tmp_distance = graph[current_point][point]
            if tmp_distance < min_distance:
                min_distance = tmp_distance
                delete_point = point  
        if delete_point:
            path.append(delete_point)
            total_time += min_distance
            next_points.remove(delete_point)
            current_point = delete_point
            if delete_point %2 ==1:
                next_points.append(delete_point+1)
            else:
                order_finished + 1
    route = []
    result = []
    plan = ['start']
    ## according to the index we put real location tuple into the route
    ## and construct the plan
    for i in path:
        route.append(positions[i])
        if i > 0:
            order_num = orders[(i-1)//2][0]
            if i %2 == 1:
                plan.append('take order '+ order_num)
            else:
                plan.append('deliver order '+ order_num)
    score = money*60.0/total_time
    result.append(plan)
    result.append(score)
    result.append(route)
    result.append(new_orders)

    return [result]
## select the plan with highest score
def select_top(x):
    x.sort(key = lambda a: -a[1])
    return x[0] 
## send the result to server
def send(x):
    plan = x[0]
    score = x[1]
    route = x[2]
    orders = x[3]
    result = dict()
    result['plan'] = plan
    result['score'] = score
    result['route'] = route
    result['orders'] = orders 
    result = json.dumps(result)
    r = requests.post('http://127.0.0.1:6789/send', data = result)
    print(r.status_code)
    return x
# Split each order string and form a order dictionary
orders = lines.map(get_orders)
## construct window
orders_window = orders.window(4,4)
positions = orders_window.reduce(lambda a, b: a + b)

graph = positions.map(compute_graph)
score_list = graph.map(compute_score_list)
##plan_n means the plan choosing top n orders
plan_1 = score_list.map(compute_1_order)
plan_2 = score_list.map(compute_2_order)
plan_3 = score_list.map(compute_3_order)
plan_4 = score_list.map(compute_4_order)
## union all plan to one list
all_plans = plan_1.union(plan_2)
all_plans = all_plans.union(plan_3)
all_plans = all_plans.union(plan_4)
all_plans = all_plans.reduce(lambda a,b :a+b)
## select the highest score
final_plan = all_plans.map(select_top)
## send it to server
final_plan = final_plan.map(send)
final_plan.pprint()

ssc.start()             # Start the computation
ssc.awaitTermination()  # Wait for the computation to terminate
#############

