# -*- coding: utf-8 -*-
"""
Created on Sat Apr 20 13:12:00 2019

@author: Aijia Gao
"""

import socket
import csv
import time

TCP_IP = socket.gethostname()
TCP_PORT = 9998
# socket.setdefaulttimeout(30)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('Socket created')
s.bind((TCP_IP, TCP_PORT))
print('Socket bind complete')
s.listen(1)
print('Socket now listening')
print("Waiting for TCP connection...")

c, addr = s.accept()
print('Got connection from', addr)
print('Start sending...')

filename = 'Food_Order.csv'
#iteration = 0
#orders = []
with open(filename, 'r') as csvfile: 
# creating a csv reader object 
    csvreader = csv.reader(csvfile) 
    #line_counts = 0
# extracting field names through first row 
    fields = next(csvreader)
    print(fields)
# extracting each data row one by one 
    for row in csvreader:
        #line_counts +=1
        order = ','.join(row)
        order+='\n'
        #orders.append(order)
        #print(order)
        c.sendall(order.encode('utf_8'))
        time.sleep(1)
    
csvfile.close()

# for i in orders:
#     #iteration+=1
#     c.sendall(i.encode('utf-8'))
#     time.sleep(1)

s.close()


