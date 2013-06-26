#!/usr/bin/env python
'''
    export_future_network.py
    Author: npeterson
    Revised: 6/26/13
    ---------------------------------------------------------------------------
    Build the MHN to its coded state for a specified year, and save the future
    arcs and nodes in a specified GDB.

'''
import os
import sys
import arcpy
import MHN

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
# Get the build year, and verify that it can actually be built.
build_year = arcpy.GetParameter(0)  # Integer, default = 2013
if build_year < MHN.base_year:
    MHN.die(('The MHN currently has a base year of {0}, so its prior state is '
             'unknown. Please try {0} or later.').format(MHN.base_year))

# Get the output GDB, and create it if it doesn't exist.
out_gdb = arcpy.GetParameterAsText(1)  # String, no default
if not arcpy.Exists(out_gdb):
    gdb_path = os.path.dirname(out_gdb)
    gdb_name = os.path.basename(out_gdb)
    if gdb_name.endswith(.gdb):
        arcpy.CreateFileGDB_management(gdb_path, gdb_name)
    elif gdb_name.endswith(.mdb):
        arcpy.CreatePersonalGDB_management(gdb_path, gdb_name)
    else:
        MHN.die('{0} is not a geodatabase!'.format(out_gdb))
