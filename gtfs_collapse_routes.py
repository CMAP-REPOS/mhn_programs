#!/usr/bin/env python
'''
    gtfs_collapse_routes.py
    Authors: cheither & npeterson
    Revised: 4/29/13
    ---------------------------------------------------------------------------
    This script reads a file of bus run itinerary data and determines which
    runs are similar enough to be combined to create an AM Peak bus network.
    The input file has the following format:

      route-id, linename, itin_a1-itin_b1-dwcode1, itin_a2-itin_b2-dwcode2, ...

'''
from __future__ import print_function
import csv
import os
import sys

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
threshold = 85                                             ### Threshold to compare runs & determine they are similar enough to combine.
infl = sys.argv[1]
groups = sys.argv[2]

if os.path.exists(groups):
    os.remove(groups)


# -----------------------------------------------------------------------------
#  Process feed data transit runs.
# -----------------------------------------------------------------------------
lines = list(csv.reader(open(infl)))
a = []; b = []; a0 = []; b0 = []                           ### Create a set of empty lists.
z = len(lines)
grp = 1                                                    ### Group identifier.
print('PROCESSING ' + str(z) + ' RUNS.')

for qq in lines[:]:                                        ### Make a slice copy to safely modify the list while iterating over it.
    if z > 0:
        a = lines[0]
        a0 = a[1]                                          ### Get route name for base run.
        zz = len(lines) - 1
        i = 1
        ## --> write first run and group to output file
        outFile = open(groups, 'a')
        outFile.write(a0 + ',' + str(grp) + '\n')
        outFile.close()

        for q in range(zz):
            b = lines[i]
            b0 = b[1]
            if a[0] == b[0]:                               ### Compare route ids from each run.
                a1 = set(a)                                ### Remove duplicate elements for comparison.
                b1 = set(b)
                x = len(a1) - 1                            ### Number of elements in base run itinerary (minus 1 to account for name).
                y = len(a1 & b1)                           ### Number of common elements between base and comparison runs * 100.
                yy = y * 100                               ### Y times 100 to yield an integer answer.
                yxratio = yy / x                           ### Ratio of common elements to base run itinerary.

                if yxratio >= threshold:
                    lines.pop(i)                           ### Remove run from further analysis.
                    z = len(lines)
                    ## --> write group to output file
                    outFile = open(groups, 'a')
                    outFile.write(b0 + ',' + str(grp) + ',' + str(yxratio) + '\n')
                    outFile.close()
                else:
                    i += 1
                del a1; del b1
            else:
                i += 1
            del b; del b0                                  ### Empty lists.

        del a; del a0                                      ### Empty lists.
        lines.pop(0)
        z = len(lines)
        grp += 1

print('DONE!')
