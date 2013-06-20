#!/usr/bin/env python
'''
    shortest_path.py
    Authors: cheither & npeterson
    Revised: 5/6/13
    ---------------------------------------------------------------------------
    This script finds the shortest path between two nodes, given the available
    network. The source of the shortest path function is:

      <http://rebrained.com/?p=392> (accessed 09/2011) - author unknown

    The function uses a brute force method to determine the shortest path: a
    bit inelegant but effective.

'''
from __future__ import print_function
import csv
import sys

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
anode = sys.argv[1]
bnode = sys.argv[2]
link_dict_txt = sys.argv[3]
short_path_txt = sys.argv[4]
sys.setrecursionlimit(6000)  # Max. iterations (sys default = 1000)


# -----------------------------------------------------------------------------
#  Find shortest path.
# -----------------------------------------------------------------------------
graph = {}
reader = csv.reader(open(link_dict_txt), delimiter='$')
for row in reader:
    graph[eval(row[0])] = eval(row[1]) # Assign key/value pairs

def shortestpath(graph, start, end, visited=[], distances={}, predecessors={}):
    ''' Function written by unknown author to find shortest path between 2
        nodes in a graph; implementation of Dijkstra's algorithm. '''
    if not visited:
        distances[start] = 0  # Set distance to 0 for first pass
    if start == end:  # We've found our end node, now find the path to it, and return
        path = []
        while end != None:
            path.append(end)
            end = predecessors.get(end, None)
        return distances[start], path[::-1]
    for neighbor in graph[start]:  # Process neighbors, keep track of predecessors
        if neighbor not in visited:
            neighbordist = distances.get(neighbor, sys.maxsize)
            tentativedist = distances[start] + graph[start][neighbor]
            if tentativedist < neighbordist:
                distances[neighbor] = tentativedist
                predecessors[neighbor] = start
    visited.append(start)  # Mark the current node as visited
    unvisiteds = dict((k, distances.get(k, sys.maxsize)) for k in graph if k not in visited)  # Finds the closest unvisited node to the start
    closestnode = min(unvisiteds, key=unvisiteds.get)
    return shortestpath(graph, closestnode, end, visited, distances, predecessors)  # Start processing the closest node

print(str(anode) + ',' + str(bnode))

outFile = open(short_path_txt, 'a')
outFile.write(str(shortestpath(graph, eval(anode), eval(bnode))) + '\n')
outFile.close()

print('DONE')
