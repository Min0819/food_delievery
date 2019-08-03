# Food Delivery Application Earn-Hub designed for Drivers in PySpark Environment
## How to run the code
1. This program is running on python3.6 and pyspark, and make sure you have: flask googlemaps firebase_admin
if not, please:
	pip install flask
	pip install googlemaps
	pip install firebase_admin
and also set the firebase in your google cloud platform

2. To run the program, make sure the port 9998 and 6789 are not used, and also add your google api key to the sparkside_spark.py
	(1) add google api key in sparkside_spark.py
	(2) python api.py
	(3) python server.py
	(4) python sparkside_spark.py
	(5) open the index.html
  
## Problem Description
Food Delivery is currently a high demand service, provided by many ordering apps like Grubhub, Uber Eats, etc. There are several ways food delivery fleet is managed. One popular way is like Uber Eats. All drivers operate independently and are not dispatched by a central agency like restaurant owners or the ordering app. The Ordering App simply provides information of delivery requests within a certain area around the drivers and drivers need to select which request they want to accept. However, in this case, drivers need to make their own plans for order pick-up and delivery to maximize their profits. This sometimes can be hard for drivers because they don’t usually see all the orders in the area as a big picture and some drivers may not be familiar with the roads and locations in the area. Furthermore, it is hard for them to consider multiple factors together such as delivery fares, distance, time, when deciding on a particular order. In most of the time, drivers would simply accept the closest one or the one that occurred first in their apps. Therefore, we would like to design an application for drivers to help them select and combine multiple orders, then plan pick up/delivery routes, such that they get the most profit out of each ride. The idea of this aggregated routes planning is motivated by carpooling like Uber Carpool. Uber carpool enables drivers to plan a route based on their start and end points while incorporating other passengers’ route into their route without too much detour. Similar function can be applied to food delivery where in that scenario, “passengers” that the driver pick up are food orders.
 
## Challenges faced and Design choices
This application is aimed at processing real-time delivery requests. The delivery requests are provided by the ordering apps that the driver is registered with. However, due to privacy reasons, ordering apps do not disclose specific delivery requests to non-registered users. Therefore, for our project, we cannot receive real-world delivery requests through ordering apps API. To simulate the real-world process, we decided to download some datasets which includes synthetic online ordering information within Orlando [1] [2]. Using this dataset, we will create sender and receiver TCP ports on cloud to simulate the real-time streaming data.

Another challenge is latency induced by Google Map API [3]. In our planning algorithm, we need to first compute a score for each order, which requires travel time between its pick-up and delivery location. This requires sending API requests to Google Map for each individual order to get the travel time. However, Google Map API on average has a latency of about 0.7s based on our testing. This latency is not considered long in most route planning apps, since usually they only calculate one route at a time. For our application, the latency will scale up linearly with the number of orders we receive, which is not desirable. To overcome this issue, during our testing, we discover that the latency does not change if we send a two-point planning request or a multiple-points planning request. Therefore, our algorithm utilizes windowing to create batch of orders to reduce API requests. We also eliminate redundant API requests in the subsequent operator by storing the point-to-point travel time for all pair of locations in a graph matrix and append this as new tuples to the end of the order Dstream. In this way, we can simply look up the travel time between any two locations (for example, restaurant of order 2 and destination of order 1 without firing a new API request.
One key component of our application is optimizing routes between multiple locations such that the total profit per unit of time is the maximum. This optimization problem is a variant to the famous Travelling Salesman Problem [4], which is an NP-hard problem. Therefore, we select greedy approach to approximate the optimal solution. 

## Description of the application
Our application utilizes Spark Streaming. Below are the operations that our application performs. A computation graph is provided at the end.

All orders in the incoming Dstream will be aggregated into tumbling windows. The window size could be adjustable based on the frequency of incoming streaming data, but for our project, we utilized a fixed size window.

The pick-up and delivery locations of all orders within one window will be extracted into a list. This list will then be sent to Google Map API to get point-to-point travel time. The time returned by Google Map are used to construct a graph matrix of size N×N in the form shown below. N is the total number of locations in the list which is 2× number of orders +1 (driver’s current location). Each row and column correspond to one location in the list and the corresponding matrix entry is the time needed to travel between these two points. In the example shown below, there are two orders (N=5). A1 and A2 are the pick-up restaurants for each order. B1 and B2 are the delivery destinations. A0 is the current location of the driver. 

![image](https://github.com/Min0819/food_delievery/master/Image/p1.png)  
  
Note that the diagonal entries are all zero but this matrix is not a diagonal matrix. Time from A to B may not be the same as B to A, possibly due to one-way roads. The graph matrix will then be appended to the end of the output Dstream for later use. 

Based on delivery fee, travel time from driver’s current location to pick-up restaurant, and travel time from restaurant to destination, each order is assigned with an overall score which is the dollar earned per unit time ($/min). For example, for the first order:
                         S_1=  (Delivery fee of order 1)/(t_01+ t_12 )
The higher the score is, the more profitable the order is. Then, all orders will be ranked based on their scores, and the sorted score list is appended to the end of the output. 

Then the application will try to combine multiple orders and calculate an efficient pick-up and delivery route to accomplish them in a way that maximize the total score. As mentioned above, this problem is similar to the Travelling Salesman Problem, which is NP-hard to optimize. Therefore, we will use a greedy algorithm to come up with an approximation. The planning task is then divided into two tasks. We will assume that the drivers will accept up to k orders at a time. This parameter can be adjustable by the drivers but for our project, we simplify the process by assuming a fixed number.  We first use forward selection which is a greedy algorithm to combine multiple orders. We always start by including the top ranked order (the most profitable one) in the ranked list. Then, for different k, we keep adding the next order on the ranked list (the next most profitable one). For each order set with different k, it will have a different list of locations, so the application will plan a new multi-location route based on the new location list and calculate new scores for each set. This task will be distributed to multiple operators to optimize throughput. Each operator is responsible for planning for a specific k. Each operator takes different number of orders, and performs the computation in parallel. Then, we collect the scores calculated by each operator, and recommend the delivery plan with highest score to the drivers.

Each operator is responsible for optimizing a multi-location route and compute new score for the order set of different size k. The multi-location route can be planned by Google Map API, but we need to provide it with the order of the locations. To come up with the optimal order is also a NP-hard problem, so we will again use a greedy approach. Starting from the driver’s current location, the set of the next point includes all the restaurants. Among this set, we pick the one that is the closest based on the travel time stored in the graph matrix. Then, after we move to the first restaurant, the set of next points will be updated, removing that restaurant from the set and adding the delivery destination of that order to the set. The delivery destination will only be added at the time when its corresponding restaurant is removed from the set (meaning that restaurant has been visited). Following this algorithm, we will result in a list of ordered locations. This list is then sent to Google Map API to compute an efficient route. The total travel time to complete the whole journey is returned by Google Map and it is used to calculated the new combined score for this order set. The new combined score is calculated as:

![image](https://github.com/Min0819/food_delievery/master/Image/p2.png)

tk is the total travel time of delivering all orders in the set based on the new route. 

Finally, the best schedule will be sent to the front end and display on the user interface.

![image](https://github.com/Min0819/food_delievery/master/Image/p3.png)

## Future work
First of all, the algorithms we used to approximate the optimal solution of multi-location route planning can be further improved. In our application, we used a variant of forward selection which adds orders into the set based on its ranking. This is not exactly the same as what forward selection do. In forward selection, it does not require the orders to be ranked. Starting with zero order, the algorithm searched all orders and iteratively add orders that gives the highest combined score for increasing sizes. This algorithm could potentially give better combination because it has a larger search space. However, it is more expensive in terms of computation and it is not easy to implement in a distributed way. Therefore, there is a trade-off between accuracy and throughput. The planning algorithm used for multi-location route can also be improved, but again, there is a tradeoff between throughput and accuracy. There are currently many multi-location planning algorithms which can be explored [4]. 

Another improvement to our application is that we can include pick up/delivery time scheduling. Currently, our application assumes that there is not wait time for drivers to pick up the food from restaurants so the application only tries to minimize time spent on route for delivery. However, this is not realistic in the real world. Uber has proposed a method to improve time efficiency between each delivery request, using trip state inference and machine learning [5]. Their machine learning model tries to learn how to dispatch drivers to each restaurant that will minimize their wait time. This can be included in our application to decide when is the best time to dispatch the driver to a particular restaurant when they need to pick-up from multiple restaurants. Combining with the route planning, our application can then provide a route to pick-up and drop-off orders, along with a schedule to pick-up and drop-off orders. 

Besides the design of optimization algorithm, there are also future work to improve the scalability of our application. Currently, our application only considers a single driver in a certain area. However, in reality, there are multiple drivers serving the area simultaneously. Therefore, there will be a problem of “order-collision” where drivers that are close to each other all try to accept the same sets of delivery requests. Our application currently cannot handle this problem. There are some recent research papers trying to solve the delivery routing problem with multiple drivers with different optimization objectives [6] [7]. Future work can be done to investigate them and adapt based on the goals of our application. 

## References
[1] 	S. Mehta, "Zomato Restaurants Data," Kaggle, 13 March 2018. [Online]. Available: https://www.kaggle.com/shrutimehta/zomato-restaurants-data. [Accessed April 2019].
[2] 	Lorinda, "Building Permits issued," City of Orlando, 18 April 2018. [Online]. Available: https://data.cityoforlando.net/Permitting/Building-Permits-Issued/k5wb-xgjc. [Accessed April 2019].
[3] 	"Developer Guide," Google Maps Platform, 16 January 2019. [Online]. Available: https://developers.google.com/maps/documentation/distance-matrix/intro. [Accessed April 2019].
[4] 	"Travelling Salesman Problem," Wikipedia, [Online]. Available: https://en.wikipedia.org/wiki/Travelling_salesman_problem. [Accessed April 2019].
[5] 	R. Waliany and L. Kang, "How Trip Inferences and Machine Learning Optimize Delivery Times on Uber Eats," Uber Engineering, 15 June 2018. [Online]. Available: https://eng.uber.com/uber-eats-trip-optimization/. [Accessed April 2019].
[6] 	Y. Liu and B. Guo, "FooDNet: Toward an Optimized Food Delivery Network based on Spatial Crowdsourcing," IEEE TRANSACTIONS ON MOBILE COMPUTING, vol. 18, no. 6, pp. 1288-1301, June 2019. 
[7] 	D. Reyes and A. Erera, "The Meal Delivery Routing Problem," 1 March 2018. [Online]. Available: http://www.optimization-online.org/DB_FILE/2018/04/6571.pdf. [Accessed April 2019].






