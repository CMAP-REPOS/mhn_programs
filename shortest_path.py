#!/usr/bin/env python
'''
    shortest_path.py
    Authors: cheither & npeterson
    Revised: 3/27/13
    ---------------------------------------------------------------------------
    This script finds the shortest path between two nodes, using a network
    graph read in from a CSV. It is essentially a wrapper of the MHN module's
    find_shortest_path() function, to facilitate calls from SAS programs.

'''
from __future__ import print_function
import csv
import sys
import heapq
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
def find_shortest_path(graph, start, end):
    ''' Recursive function written by Chris Laffra to find shortest path
        between 2 nodes in a graph; implementation of Dijkstra's algorithm.
        Based on <http://code.activestate.com/recipes/119466/#c6>.

        Example graph dictionary (sub-dicts contain distances):

            {'a': {'w': 14, 'x': 7, 'y': 9},
             'b': {'w': 9, 'z': 6},
             'w': {'a': 14, 'b': 9, 'y': 2},
             'x': {'a': 7, 'y': 10, 'z': 15},
             'y': {'a': 9, 'w': 2, 'x': 10, 'z': 11},
             'z': {'b': 6, 'x': 15, 'y': 11}}
    '''
    queue = [(0, start, [])]
    seen = set()
    while True:
        (p_cost, node, path) = heapq.heappop(queue)
        if node not in seen:
            path = path + [node]
            seen.add(node)
            if node == end:
                return p_cost, path
            if node in graph.keys():
                for (b_node, b_cost) in graph[node].iteritems():
                    heapq.heappush(queue, (p_cost + b_cost, b_node, path))

graph = {}
reader = csv.reader(open(link_dict_txt), delimiter='$')
for row in reader:
    graph[eval(row[0])] = eval(row[1]) # Assign key/value pairs

print('Finding shortest path from {0} to {1}...'.format(anode, bnode))

short_path = open(short_path_txt, 'a')
short_path.write(str(find_shortest_path(graph, eval(anode), eval(bnode))) + '\n')
short_path.close()

print('DONE')
