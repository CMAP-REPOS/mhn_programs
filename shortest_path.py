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
import MHN

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
print('Finding shortest path from {0} to {1}...'.format(anode, bnode))

graph = {}
reader = csv.reader(open(link_dict_txt), delimiter='$')
for row in reader:
    graph[eval(row[0])] = eval(row[1]) # Assign key/value pairs

short_path = open(short_path_txt, 'a')
short_path.write(str(MHN.find_shortest_path(graph, eval(anode), eval(bnode))) + '\n')
short_path.close()

print('DONE')
