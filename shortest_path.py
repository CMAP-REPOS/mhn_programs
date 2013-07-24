#!/usr/bin/env python
'''
    shortest_path.py
    Authors: cheither & npeterson
    Revised: 7/23/13
    ---------------------------------------------------------------------------
    This script finds the shortest path between two nodes, using a network
    graph read in from a CSV. It is essentially a wrapper of the MHN module's
    find_shortest_path() function, to facilitate calls from SAS programs.

'''
from __future__ import print_function
import csv
import sys
# Do NOT import MHN and call MHN.find_shortest_path()! Importing MHN for each
# anode-bnode pair takes *forever* when run outside of ArcGIS (i.e. from SAS).

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
# Use copy of find_shortest_path() from MHN.py to avoid costly arcpy imports:
def find_shortest_path(graph, start, end, visited=None, distances=None, predecessors=None):
    ''' Recursive function written by nolfonzo@gmail.com to find shortest path
        between 2 nodes in a graph; implementation of Dijkstra's algorithm.
        Based on <http://rebrained.com/?p=392>, accessed 9/2011.

        Example graph dictionary (sub-dicts contain distances):

            {'a': {'w': 14, 'x': 7, 'y': 9},
             'b': {'w': 9, 'z': 6},
             'w': {'a': 14, 'b': 9, 'y': 2},
             'x': {'a': 7, 'y': 10, 'z': 15},
             'y': {'a': 9, 'w': 2, 'x': 10, 'z': 11},
             'z': {'b': 6, 'x': 15, 'y': 11}}
    '''
    if visited == None:
        visited = []
    if distances == None:
        distances = {}
    if predecessors == None:
        predecessors = {}
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
            neighbor_dist = distances.get(neighbor, float('infinity'))
            tentative_dist = distances[start] + graph[start][neighbor]
            if tentative_dist < neighbor_dist:
                distances[neighbor] = tentative_dist
                predecessors[neighbor] = start
    visited.append(start)  # Mark the current node as visited
    unvisiteds = dict((k, distances.get(k, float('infinity'))) for k in graph if k not in visited)  # Finds the closest unvisited node to the start
    closest_node = min(unvisiteds, key=unvisiteds.get)
    return find_shortest_path(graph, closest_node, end, visited, distances, predecessors)  # Start processing the closest node

graph = {}
reader = csv.reader(open(link_dict_txt), delimiter='$')
for row in reader:
    graph[eval(row[0])] = eval(row[1]) # Assign key/value pairs

print('Finding shortest path from {0} to {1}...'.format(anode, bnode))

short_path = open(short_path_txt, 'a')
short_path.write(str(find_shortest_path(graph, eval(anode), eval(bnode))) + '\n')
short_path.close()

print('DONE')
