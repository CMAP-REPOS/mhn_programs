#!/usr/bin/env python
'''
    import_highway_projects.py
    Author: npeterson
    Revised: 5/15/2013
    ---------------------------------------------------------------------------
    Import highway project coding from an Excel spreadsheet. SAS can currently
    only handle .xls and not .xlsx.

'''
import csv
import os
import sys
import arcpy
import MHN  # Custom library for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
xls = arcpy.GetParameterAsText(0)  # Spreadsheet containing project coding
sas1_name = 'import_highway_projects_2'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = ''.join((MHN.temp_dir, '/', sas1_name, '.log'))
sas1_lst = ''.join((MHN.temp_dir, '/', sas1_name, '.lst'))
mhn_links_csv = ''.join((MHN.temp_dir, '/mhn_links.csv'))
projects_csv = ''.join((MHN.temp_dir, '/projects.csv'))


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(mhn_links_csv)
MHN.delete_if_exists(projects_csv)


# -----------------------------------------------------------------------------
#  Use SAS program to validate coding before import.
# -----------------------------------------------------------------------------
mhn_links_attr = ['ANODE', 'BNODE', 'BASELINK']
mhn_links_query = '''"BASELINK" IN ('0', '1')'''  # Ignore BASELINK > 1
mhn_links_view = MHN.make_skinny_table_view(MHN.arc, 'mhn_links_view', mhn_links_attr, mhn_links_query)
MHN.write_attribute_csv(mhn_links_view, mhn_links_csv, mhn_links_attr)

sas1_sas = ''.join((MHN.prog_dir + '/', sas1_name,'.sas'))
sas1_args = [xls, mhn_links_csv, projects_csv, sas1_lst]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif not os.path.exists(projects_csv):
    MHN.die('{0} did not finish successfully! Please see {1}'.format(sas1_sas, sas1_log))
elif os.path.exists(sas1_lst):
    MHN.die('Problems with project coding. Please see {0}.'.format(sas1_lst))
else:
    arcpy.Delete_management(sas1_log)


# -----------------------------------------------------------------------------
#  Update hwyproj features/coding from temporary FC/table.
# -----------------------------------------------------------------------------
temp_routes_name = 'temp_routes_fc'
temp_routes_fc = '/'.join((MHN.mem, temp_routes_name))
arcpy.CreateFeatureClass_management(MHN.mem, temp_routes_name, 'POLYLINE', MHN.hwyproj)

temp_coding_name = 'temp_coding_table'
temp_coding_table = '/'.join((MHN.mem, temp_coding_name))
arcpy.CreateTable_management(MHN.mem, temp_coding_name, MHN.route_systems[MHN.hwyproj][0])

# Get affected TIPIDs.
raw_coding = open(projects_csv, 'r')
coding = csv.DictReader(raw_coding)
common_id_field = MHN.route_systems[MHN.hwyproj][1]  # 'TIPID'
project_ids = set([row[common_id_field] for row in coding])
raw_coding.close()

# Update temp route FC and coding table one project at a time.
for project_id in project_ids:
    arcs = []
    with open(projects_csv, 'r') as raw_coding:
        coding = csv.DictReader(raw_coding)
        arcs = [arc for arc in coding if row[common_id_field] == project_id]
    arc_ids = (arc['ABB'] for arc in arcs)
    arcs_layer = 'arc_layer'
    arcs_query = '"ABB" IN \'' + "','".join(arc_ids) + "')"
    arcpy.MakeFeatureLayer_management(MHN.arc, arcs_layer, arcs_query)
    
    # Create route feature.
    arcs_dissolved = '/'.join((MHN.mem, 'arcs_dissolved'))
    arcpy.Dissolve_management(arcs_layer, arcs_dissolved)
    arcpy.AddField_management(arcs_dissolved, common_id_field, 'TEXT', field_length=10)  # Make type/length dynamic?
    with arcpy.da.UpdateCursor(arcs_dissolved, [common_id_field]) as cursor:
        for row in cursor:
            row[0] = project_id
            cursor.updateRow(row)
    arcpy.Append_management(arcs_dissolved, temp_routes_fc, 'NO_TEST')
    
    # Update coding table.
    coding_fields = (
        common_id_field, 'ACTION_CODE', 'REP_ANODE', 'REP_BNODE','NEW_TYPE1','NEW_TYPE2',
        'NEW_THRULANEWIDTH1', 'NEW_THRULANEWIDTH2', 'NEW_THRULANES1', 'NEW_THRULANES2',
        'NEW_POSTEDSPEED1', 'NEW_POSTEDSPEED2', 'NEW_AMPM1', 'NEW_AMPM2', 'NEW_MODES',
        'NEW_TOLLDOLLARS', 'NEW_DIRECTIONS', 'ADD_PARKLANES1', 'ADD_PARKLANES2',
        'ADD_SIGIC', 'ADD_CLTL', 'ADD_RRGRADECROSS', 'TOD', 'ABB'
    )
    with arcpy.da.InsertCursor(temp_coding_table, coding_fields) as cursor:
        for arc_id in arc_ids:
            arc_dict = (arc for arc in arcs if row['ABB'] == arc_id)[0]  # There can be only one instance of each ABB per TIPID.
            arc_values = (arc_dict[field] for field in coding_fields)
            cursor.insertRow(values)

# Create in-memory copy of hwyproj hwyproj_coding.

# Remove existing coding for affected TIPIDs, if necessary.

# Append features/coding from temp FC/table.

# Replace FC/table in GDB with in-memory versions.