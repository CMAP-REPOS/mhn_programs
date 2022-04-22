#!/usr/bin/env python
'''
    generate_directional_links.py
    Author: npeterson
    Revised: 6/14/13
    ---------------------------------------------------------------------------
    Takes a bi-directional network feature class (i.e. MHN arcs) and generates
    a directional one based on the values in the DIRECTIONS field. All
    direction-dependent attributes will also be adjusted.

'''
import arcpy
arcpy.env.OverwriteOutput = True

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
mem = 'in_memory'

in_arc = arcpy.GetParameterAsText(0)
out_arc = arcpy.GetParameterAsText(1)
temp_arc_1 = ''.join((mem, '/temp_arc_1'))
temp_arc_2 = ''.join((mem, '/temp_arc_2'))
temp_arc_3 = ''.join((mem, '/temp_arc_3'))

dir_fields = ['TYPE', 'AMPM', 'POSTEDSPEED', 'THRULANES', 'THRULANEWIDTH',
              'PARKLANES', 'PARKRES']


# -----------------------------------------------------------------------------
#  Define some useful functions.
# -----------------------------------------------------------------------------
def delete_dir2_fields(temp_arc):
    ''' Delete all <FIELDNAME>2 fields, leaving only the A-to-B directional
        values. '''
    arcpy.DeleteField_management(temp_arc, ['{0}2'.format(field) for field in dir_fields])
    arcpy.DeleteField_management(temp_arc, ['DIRECTIONS'])
    return temp_arc

def invert_bearing(bearing):
    ''' Return the opposite of a specified cardinal direction. '''
    bearings = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')
    index = bearings.index(bearing)
    inv_index = (index + 4) % 8
    inv_bearing = bearings[inv_index]
    return inv_bearing


# -----------------------------------------------------------------------------
#  Copy all input arcs into temp fc for primary direction.
# -----------------------------------------------------------------------------
arc_dir1_lyr = 'arc_dir1_lyr'
arcpy.MakeFeatureLayer_management(in_arc, arc_dir1_lyr)
arcpy.CopyFeatures_management(arc_dir1_lyr, temp_arc_1)
delete_dir2_fields(temp_arc_1)


# -----------------------------------------------------------------------------
#  Process DIRECTIONS = 2 & DIRECTIONS = 3.
# -----------------------------------------------------------------------------
arc_dirs23_lyr = 'arc_dirs23_lyr'
arcpy.MakeFeatureLayer_management(in_arc, arc_dirs23_lyr, """ "DIRECTIONS" IN ('2', '3') """)
arcpy.CopyFeatures_management(arc_dirs23_lyr, temp_arc_2)
arcpy.FlipLine_edit(temp_arc_2)  # Reverse digitized direction
with arcpy.da.UpdateCursor(temp_arc_2, ['ANODE', 'BNODE', 'ABB', 'BEARING']) as cursor:
    for row in cursor:
        anode = row[1]  # Switch ANODE and BNODE
        bnode = row[0]
        baselink = row[2][-1]
        abb = '{0}-{1}-{2}'.format(anode, bnode, baselink)  # Generate new ABB
        bearing = invert_bearing(row[3])
        cursor.updateRow([anode, bnode, abb, bearing])

arc_dir3_lyr = 'arc_dir3_lyr'
arcpy.MakeFeatureLayer_management(temp_arc_2, arc_dir3_lyr, """ "DIRECTIONS" = '3' """)
for field in dir_fields:
    field1 = '{0}1'.format(field)
    field2 = '{0}2'.format(field)
    arcpy.CalculateField_management(arc_dir3_lyr, field1, '!{0}!'.format(field2), 'PYTHON')

delete_dir2_fields(temp_arc_2)


# -----------------------------------------------------------------------------
#  Append reversed links to temp fc and copy to output fc.
# -----------------------------------------------------------------------------
arcpy.Append_management([temp_arc_2], temp_arc_1)
arcpy.CopyFeatures_management(temp_arc_1, out_arc)
arcpy.Delete_management(mem)
