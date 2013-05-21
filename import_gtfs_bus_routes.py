#!/usr/bin/env python
'''
    import_gtfs_bus_routes.py
    Author: npeterson
    Revised: 5/21/2013
    ---------------------------------------------------------------------------
    This program is used to update the itineraries of bus routes, with data
    from specified header & itinerary coding CSVs.

'''
import csv
import os
import sys
import arcpy
import MHN

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
header_csv = arcpy.GetParameterAsText(0)  # CSV containing bus header coding
itin_csv = arcpy.GetParameterAsText(1)    # CSV containing bus itin coding
sas1_name = 'import_gtfs_bus_routes_2'
