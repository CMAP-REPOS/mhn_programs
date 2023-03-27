#!/usr/bin/env python
'''
    straighten_selected_links.py
    Author: npeterson
    Revised: 8/4/15
    ---------------------------------------------------------------------------
    Delete all non-endpoint vertices for selected links.

'''
import arcpy

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
links = arcpy.GetParameterAsText(0)

def check_selection(lyr):
    ''' Check whether specified layer has a selection. '''
    desc = arcpy.Describe(lyr)
    selected = desc.FIDSet
    if len(selected) == 0:
        return False
    else:
        return True

if check_selection(links):
    with arcpy.da.UpdateCursor(links, ['SHAPE@']) as cursor:
        for row in cursor:
            new_link = arcpy.Array()
            for part in row[0]:
                current_vertex = 0
                final_vertex = len(part)
                new_part = arcpy.Array()
                for vertex in part:
                    current_vertex += 1
                    if current_vertex == 1 or current_vertex == final_vertex:
                        new_part.add(arcpy.Point(vertex.X, vertex.Y))
                new_link.add(new_part)
            cursor.updateRow([arcpy.Polyline(new_link)])

try:
    arcpy.RefreshActiveView()
except:
    # Must be using ArcGIS Pro...
    pass
