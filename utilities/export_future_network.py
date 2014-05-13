#!/usr/bin/env python
'''
    export_future_network.py
    Author: npeterson
    Revised: 5/13/14
    ---------------------------------------------------------------------------
    Build the MHN to its coded state for a specified year, and save the future
    arcs and nodes in a specified GDB. This is particularly for building the
    networks for processing current GTFS bus runs.

'''
import os
import sys
import arcpy

# Import MHN module from parent directory
import inspect
util_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
prog_dir = os.path.dirname(util_dir)
sys.path.insert(0, prog_dir)
import MHN

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
# Get the build year, and verify that it can actually be built.
build_year = arcpy.GetParameter(0)  # Integer, default = 2013
if build_year < MHN.base_year:
    MHN.die(('The MHN currently has a base year of {0}, so its prior state is '
             'unknown. Please try {0} or later.').format(MHN.base_year))

# Get the output GDB and feature dataset, and create if non-existent.
gdb_path = arcpy.GetParameterAsText(1)  # Folder, no default
gdb_name = arcpy.GetParameterAsText(2)  # String, no default
if not gdb_name.endswith('.gdb'):
    gdb_name = '{0}.gdb'.format(gdb_name)
out_gdb = os.path.join(gdb_path, gdb_name)
if not arcpy.Exists(out_gdb):
    arcpy.CreateFileGDB_management(gdb_path, gdb_name)

out_fd_name = 'hwynet_{0}'.format(build_year)
out_fd = os.path.join(out_gdb, out_fd_name)
sr = arcpy.Describe(MHN.hwynet).spatialReference
if not arcpy.Exists(out_fd):
    arcpy.CreateFeatureDataset_management(out_gdb, out_fd_name, sr)

# Other parameters
sas1_name = 'export_future_network_2'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = os.path.join(MHN.temp_dir, '{0}.log'.format(sas1_name))
sas1_lst = os.path.join(MHN.temp_dir, '{0}.lst'.format(sas1_name))
year_csv = os.path.join(MHN.temp_dir, 'year.csv')
transact_csv = os.path.join(MHN.temp_dir, 'transact.csv')
network_csv = os.path.join(MHN.temp_dir, 'network.csv')
update_link_csv = os.path.join(MHN.temp_dir, 'update_link.csv')  # SAS output
flag_node_csv = os.path.join(MHN.temp_dir, 'flag_node.csv')      # SAS output


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(year_csv)
MHN.delete_if_exists(transact_csv)
MHN.delete_if_exists(network_csv)
MHN.delete_if_exists(update_link_csv)
MHN.delete_if_exists(flag_node_csv)


# -----------------------------------------------------------------------------
#  Write data relevant to specified year and pass to SAS for processing.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nPreparing {0} network attributes...'.format(build_year))

# Export coding for highway projects completed by scenario year.
hwyproj_id_field = MHN.route_systems[MHN.hwyproj][1]
year_attr = [hwyproj_id_field,'COMPLETION_YEAR']
year_query = '"COMPLETION_YEAR" <= {0}'.format(build_year)
year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'year_view', year_attr, year_query)
MHN.write_attribute_csv(year_view, year_csv, year_attr)
hwy_projects = MHN.make_attribute_dict(year_view, hwyproj_id_field, attr_list=[])
arcpy.Delete_management(year_view)

transact_attr = [hwyproj_id_field,'ACTION_CODE','NEW_DIRECTIONS','NEW_TYPE1','NEW_TYPE2','NEW_AMPM1','NEW_AMPM2','NEW_POSTEDSPEED1',
                 'NEW_POSTEDSPEED2','NEW_THRULANES1','NEW_THRULANES2','NEW_THRULANEWIDTH1','NEW_THRULANEWIDTH2','ADD_PARKLANES1',
                 'ADD_PARKLANES2','ADD_SIGIC','ADD_CLTL','ADD_RRGRADECROSS','NEW_TOLLDOLLARS','NEW_MODES','TOD','ABB','REP_ANODE','REP_BNODE']
transact_query = '"{0}" IN (\'{1}\')'.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in hwy_projects)))
transact_view = MHN.make_skinny_table_view(MHN.route_systems[MHN.hwyproj][0], 'transact_view', transact_attr, transact_query)
MHN.write_attribute_csv(transact_view, transact_csv, transact_attr)
hwy_abb = MHN.make_attribute_dict(transact_view, 'ABB', attr_list=[])
arcpy.Delete_management(transact_view)

# Export arc & node attributes of all baselinks and skeletons used in
# projects completed by scenario year.
network_attr = ['ANODE','BNODE','ABB','DIRECTIONS','TYPE1','TYPE2','AMPM1','AMPM2','POSTEDSPEED1','POSTEDSPEED2',
                'THRULANES1','THRULANES2','THRULANEWIDTH1','THRULANEWIDTH2','PARKLANES1','PARKLANES2','BASELINK',
                'SIGIC','CLTL','RRGRADECROSS','TOLLDOLLARS','MODES','MILES']
network_query = '"BASELINK" = \'1\' OR "ABB" IN (\'{0}\')'.format("','".join((abb for abb in hwy_abb if abb[-1] != '1')))
network_lyr = MHN.make_skinny_feature_layer(MHN.arc, 'network_lyr', network_attr, network_query)
MHN.write_attribute_csv(network_lyr, network_csv, network_attr)

# Process attribute tables with export_future_network_2.sas.
sas1_sas = os.path.join(util_dir, '{0}.sas'.format(sas1_name))
sas1_args = [network_csv, transact_csv, year_csv, update_link_csv, flag_node_csv, build_year, MHN.max_poe, MHN.base_year]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
else:
    os.remove(sas1_log)
    MHN.delete_if_exists(sas1_lst)
    os.remove(year_csv)
    os.remove(transact_csv)
    os.remove(network_csv)


# -----------------------------------------------------------------------------
#  Update links/nodes from SAS output in memory before copying to output GDB.
# -----------------------------------------------------------------------------
# Build updated links in memory.
arcpy.AddMessage('\nBuilding {0} links...'.format(build_year))

update_link_dict = {}
with open(update_link_csv, 'r') as reader:
    firstline = True
    for row in reader:
        if firstline:
            firstline = False
            continue
        attr = row.strip().split(',')
        abb = attr[0]
        update_link_dict[abb] = attr

out_arc_name = 'hwynet_arc_{0}'.format(build_year)
temp_arc = os.path.join(MHN.mem, out_arc_name)
arcpy.FeatureClassToFeatureClass_conversion(MHN.arc, MHN.mem, out_arc_name)
arcpy.AddField_management(temp_arc, 'ACTION_CODE', 'TEXT', field_length=1)
arcpy.CalculateField_management(temp_arc, 'ACTION_CODE', "'0'", 'PYTHON')
update_link_attr = ['ABB','DIRECTIONS','TYPE1','TYPE2','AMPM1','AMPM2','POSTEDSPEED1','POSTEDSPEED2',
                    'THRULANES1','THRULANES2','THRULANEWIDTH1','THRULANEWIDTH2','PARKLANES1','PARKLANES2',
                    'BASELINK','SIGIC','CLTL','TOLLDOLLARS','MODES','ACTION_CODE']
with arcpy.da.UpdateCursor(temp_arc, update_link_attr) as cursor:
    abb_index = update_link_attr.index('ABB')
    for row in cursor:
        abb = row[abb_index]
        if abb in update_link_dict:
            cursor.updateRow(update_link_dict[abb])

# Copy future baselinks to output GDB.
out_arc = os.path.join(out_fd, out_arc_name)
temp_arc_lyr = 'temp_arc_lyr'
temp_arc_query = ''' "BASELINK" = '1' '''
arcpy.MakeFeatureLayer_management(temp_arc, temp_arc_lyr, temp_arc_query)
arcpy.FeatureClassToFeatureClass_conversion(temp_arc_lyr, out_fd, out_arc_name)

# Build updated nodes in memory.
arcpy.AddMessage('\nBuilding {0} nodes...'.format(build_year))

flag_node_dict = {}
with open(flag_node_csv, 'r') as reader:
    firstline = True
    for row in reader:
        if firstline:
            firstline = False
            continue
        attr = row.strip().split(',')
        node = int(attr[0])
        flag_node_dict[node] = attr

out_node_name = 'hwynet_node_{0}'.format(build_year)
temp_node = os.path.join(MHN.mem, out_node_name)
arcpy.FeatureClassToFeatureClass_conversion(MHN.node, MHN.mem, out_node_name)
for fieldname in ('ARTERIAL', 'RAMP', 'GHOST'):
    arcpy.AddField_management(temp_node, fieldname, 'SHORT')
    arcpy.CalculateField_management(temp_node, fieldname, '0', 'PYTHON')
flag_node_attr = ['NODE','ARTERIAL','RAMP','GHOST']
with arcpy.da.UpdateCursor(temp_node, flag_node_attr) as cursor:
    node_index = flag_node_attr.index('NODE')
    for row in cursor:
        node = row[node_index]
        if node in flag_node_dict:
            cursor.updateRow(flag_node_dict[node])

# Copy future nodes to output GDB.
out_node = os.path.join(out_fd, out_node_name)
#out_node_query = ''' "ARTERIAL" + "RAMP" + "GHOST" > 0 '''
temp_node_lyr = 'temp_node_lyr'
arcpy.MakeFeatureLayer_management(temp_node, temp_node_lyr)
arcpy.SelectLayerByLocation_management(temp_node_lyr, 'INTERSECT', temp_arc_lyr)
arcpy.FeatureClassToFeatureClass_conversion(temp_node_lyr, out_fd, out_node_name) #, out_node_query)


# -----------------------------------------------------------------------------
#  Clean up.
# -----------------------------------------------------------------------------
os.remove(update_link_csv)
os.remove(flag_node_csv)
arcpy.Delete_management(MHN.mem)
arcpy.AddMessage('\nAll done!\n')
