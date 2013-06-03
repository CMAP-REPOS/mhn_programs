#!/usr/bin/env python
'''
    import_gtfs_bus_routes.py
    Author: npeterson
    Revised: 6/3/2013
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
raw_header_csv = arcpy.GetParameterAsText(0)  # Bus header coding CSV
raw_itin_csv = arcpy.GetParameterAsText(1)    # Bus itin coding CSV
which_bus = arcpy.GetParameterAsText(2)       # Import to base or current?
sas1_name = 'import_gtfs_bus_routes_2'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = ''.join((MHN.temp_dir, '/', sas1_name, '.log'))
sas1_lst = ''.join((MHN.temp_dir, '/', sas1_name, '.lst'))
transact_csv = '/'.join((MHN.temp_dir, 'transact.csv'))
network_csv = '/'.join((MHN.temp_dir, 'network.csv'))
nodes_csv = '/'.join((MHN.temp_dir, 'nodes.csv'))
header_csv = '/'.join((MHN.temp_dir, 'header.csv'))
itin_csv = '/'.join((MHN.temp_dir, 'itin.csv'))
link_dict_txt = ''.join((MHN.prog_dir, '/Import/link_dictionary.txt'))  # shortest_path.py input file (called by import_gtfs_bus_routes_2.sas)
short_path_txt = ''.join((MHN.prog_dir, '/Import/short_path.txt'))      # shortest_path.py output file
hold_check_csv = ''.join((MHN.prog_dir, '/Import/hold_check.csv'))
hold_times_csv = ''.join((MHN.prog_dir, '/Import/hold_times.csv'))
routes_processed_csv = ''.join((MHN.prog_dir, '/Import/routes_processed.csv'))


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(transact_csv)
MHN.delete_if_exists(network_csv)
MHN.delete_if_exists(nodes_csv)
MHN.delete_if_exists(header_csv)
MHN.delete_if_exists(itin_csv)
MHN.delete_if_exists(link_dict_txt)
MHN.delete_if_exists(short_path_txt)
MHN.delete_if_exists(hold_check_csv)
MHN.delete_if_exists(hold_times_csv)
MHN.delete_if_exists(routes_processed_csv)


# -----------------------------------------------------------------------------
#  Set route system-specific variables.
# -----------------------------------------------------------------------------
if which_bus == 'base':
    routes_fc = MHN.bus_base
elif which_bus == 'current':
    routes_fc = MHN.bus_current
else:
    MHN.die('Route system must be either "base" or "current", not "{0}"!'.format(which_bus))

itin = MHN.route_systems[routes_fc][0]
common_id_field = MHN.route_systems[routes_fc][1]
order_field = MHN.route_systems[routes_fc][2]
min_route_id = MHN.route_systems[routes_fc][3]
network_year = MHN.bus_years[which_bus]


# -----------------------------------------------------------------------------
#  Verify that all projects have a non-zero, non-null completion year.
# -----------------------------------------------------------------------------
#  Skip check if bus year = base year (i.e. no projects would be added anyway).
if network_year > MHN.base_year:
    invalid_hwyproj = MHN.get_yearless_hwyproj()
    if invalid_hwyproj:
        MHN.die('The following highway projects have no completion year: '
                '{0}'.format(', '.join(invalid_hwyproj)))


# -----------------------------------------------------------------------------
#  Export highway project coding info to determine future arc availability.
# -----------------------------------------------------------------------------
hwyproj_id_field = MHN.route_systems[MHN.hwyproj][1]

# Identify highway projects to be completed by bus year.
year_attr = (hwyproj_id_field, 'COMPLETION_YEAR')
year_query = '{0} <= {1}'.format("COMPLETION_YEAR", network_year)
year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'year_view', year_attr, year_query)
projects = MHN.make_attribute_dict(year_view, hwyproj_id_field, attr_list=[])
arcpy.Delete_management(year_view)

# Export coding for identified projects.
transact_attr = (hwyproj_id_field, 'ABB', 'ACTION_CODE', 'NEW_POSTEDSPEED1', 'NEW_POSTEDSPEED2', 'NEW_DIRECTIONS')
transact_query = '"{0}" IN (\'{1}\')'.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in projects)))
transact_view = MHN.make_skinny_table_view(MHN.route_systems[MHN.hwyproj][0], 'transact_view', transact_attr, transact_query)
MHN.write_attribute_csv(transact_view, transact_csv, transact_attr[1:])
project_arcs = MHN.make_attribute_dict(transact_view, 'ABB', attr_list=[])
arcpy.Delete_management(transact_view)

# Export arc attributes for bus year network.
network_attr = ('ANODE', 'BNODE', 'BASELINK', 'ABB', 'DIRECTIONS', 'TYPE1', 'TYPE2', 'POSTEDSPEED1', 'POSTEDSPEED2', 'MILES')
network_query = '"BASELINK" = \'1\' OR "ABB" IN (\'{0}\')'.format("','".join((arc_id for arc_id in project_arcs if arc_id[-1] != '1')))
network_view = MHN.make_skinny_table_view(MHN.arc, 'network_view', network_attr, network_query)
MHN.write_attribute_csv(network_view, network_csv, network_attr)
arcpy.Delete_management(network_view)

# Export node coordinates.
nodes_attr = ('NODE', 'POINT_X', 'POINT_Y')
nodes_view = MHN.make_skinny_table_view(MHN.node, 'nodes_view', nodes_attr)
MHN.write_attribute_csv(nodes_view, nodes_csv, nodes_attr)
arcpy.Delete_management(nodes_view)


# -----------------------------------------------------------------------------
#  Use SAS program to validate coding before import.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Validating coding in {1} & {2}...'.format('\n', raw_header_csv, raw_itin_csv))

sas1_sas = ''.join((MHN.prog_dir + '/', sas1_name,'.sas'))
sas1_args = [raw_header_csv, raw_itin_csv, transact_csv, network_csv, nodes_csv,
             MHN.prog_dir, header_csv, itin_csv, link_dict_txt, short_path_txt,
             hold_check_csv, hold_times_csv, routes_processed_csv,
             str(min_route_id), str(MHN.max_poe), sas1_lst]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif os.path.exists(sas1_lst):
    MHN.die('Problems with bus_{0} route coding. Please see {1}.'.format(which_bus, sas1_lst))
elif not os.path.exists(short_path_txt):
    MHN.die('{0}/shortest_path.py did not run! (Called by {0}.)'.format(MHN.prog_dir, sas2_sas))
else:
    os.remove(sas1_log)
    os.remove(transact_csv)
    os.remove(network_csv)
    os.remove(nodes_csv)


# -----------------------------------------------------------------------------
#  Generate temp route fc/itin table from SAS output.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Building updated route & itin table in memory...'.format('\n'))

temp_routes_name = 'temp_routes_fc'
temp_routes_fc = '/'.join((MHN.mem, temp_routes_name))
arcpy.CreateFeatureclass_management(MHN.mem, temp_routes_name, 'POLYLINE', routes_fc)

temp_itin_name = 'temp_itin_table'
temp_itin_table = '/'.join((MHN.mem, temp_itin_name))
arcpy.CreateTable_management(MHN.mem, temp_itin_name, MHN.route_systems[routes_fc][0])

# Update itin table directly from CSV, while determining coded arcs' IDs.
common_id_field = MHN.route_systems[routes_fc][1]
order_field = MHN.route_systems[routes_fc][2]
route_arcs = {}

itin_fields = (
    common_id_field, order_field, 'ITIN_A', 'ITIN_B', 'ABB', 'LAYOVER',
    'DWELL_CODE', 'ZONE_FARE', 'LINE_SERV_TIME', 'TTF', 'DEP_TIME', 'ARR_TIME',
    'LINK_STOPS', 'IMPUTED'
)

with arcpy.da.InsertCursor(temp_itin_table, itin_fields) as cursor:
    raw_itin = open(itin_csv, 'r')
    itin = csv.DictReader(raw_itin)
    for arc_attr_dict in itin:
        route_id = arc_attr_dict[common_id_field]
        arc_id = arc_attr_dict['ABB']
        if route_id not in route_arcs.keys():
            route_arcs[route_id] = [arc_id]
        else:
            route_arcs[route_id].append(arc_id)
        arc_attr = [arc_attr_dict[field] for field in itin_fields]
        cursor.insertRow(arc_attr)
    raw_itin.close()
os.remove(itin_csv)

# Update itinerary F_MEAS & T_MEAS.
MHN.calculate_itin_measures(temp_itin_table)

# Generate route features one at a time.
for route_id in sorted(route_arcs.keys()):

    # Dissolve route arcs into a single route feature, and append to temp FC.
    route_arc_ids = route_arcs[route_id]
    route_arcs_lyr = 'route_arcs_lyr'
    route_arcs_query = '"ABB" IN (\'' + "','".join(route_arc_ids) + "')"
    arcpy.MakeFeatureLayer_management(MHN.arc, route_arcs_lyr, route_arcs_query)
    route_dissolved = '/'.join((MHN.mem, 'route_dissolved'))
    arcpy.Dissolve_management(route_arcs_lyr, route_dissolved)
    arcpy.AddField_management(route_dissolved, common_id_field, 'TEXT', field_length=10)
    with arcpy.da.UpdateCursor(route_dissolved, [common_id_field]) as cursor:
        for row in cursor:
            row[0] = route_id
            cursor.updateRow(row)
    arcpy.Append_management(route_dissolved, temp_routes_fc, 'NO_TEST')

# Fill other fields with data from future_route_csv.
header_attr = {}

route_fields = (
    common_id_field, 'DESCRIPTION', 'MODE', 'VEHICLE_TYPE', 'HEADWAY', 'SPEED',
    'FEEDLINE', 'DIRECTION', 'CT_VEH', 'ROUTE_ID', 'START', 'AM_SHARE',
    'STARTHOUR', 'LONGNAME', 'TERMINAL'
)

with open(header_csv, 'r') as raw_routes:
    routes = csv.DictReader(raw_routes)
    for route in routes:
        attr_list = [route[field] for field in route_fields]
        header_attr[route[common_id_field]] = attr_list
os.remove(header_csv)

with arcpy.da.UpdateCursor(temp_routes_fc, route_fields) as cursor:
    for row in cursor:
        common_id = row[0]
        attr_list = header_attr[common_id]
        row[1:] = attr_list[1:]
        cursor.updateRow(row)


# -----------------------------------------------------------------------------
#  Commit the changes only after everything else has run successfully.
#  (Unlike with bus_future, ALL existing routes will be purged -- could
#  potentially add an "append" option in the future.)
# -----------------------------------------------------------------------------
backup_gdb = MHN.gdb[:-4] + '_' + MHN.timestamp() + '.gdb'
arcpy.Copy_management(MHN.gdb, backup_gdb)
arcpy.AddMessage('{0}Geodatabase temporarily backed up to {1}. (If import fails for any reason, replace {2} with this.)'.format('\n',backup_gdb, MHN.gdb))

arcpy.AddMessage('\nSaving changes to disk...')

# Replace header feature class.
arcpy.AddMessage('-- ' + routes_fc + '...')
arcpy.TruncateTable_management(routes_fc)
arcpy.Delete_management(routes_fc)
arcpy.CopyFeatures_management(temp_routes_fc, routes_fc)
arcpy.Delete_management(temp_routes_fc)

# Replace itinerary table.
itin_table = MHN.route_systems[routes_fc][0]
arcpy.AddMessage('-- ' + itin_table + '...')
arcpy.TruncateTable_management(itin_table)
arcpy.Delete_management(itin_table)
itin_path = MHN.break_path(itin_table)
arcpy.CreateTable_management(itin_path['dir'], itin_path['name'], temp_itin_table)
arcpy.Append_management(temp_itin_table, itin_table, 'TEST')
arcpy.Delete_management(temp_itin_table)

# Rebuild relationship class.
arcpy.AddMessage('{0}Rebuilding relationship classes...'.format('\n'))
bus_future_name = MHN.break_path(routes_fc)['name']
itin_table_name = MHN.break_path(itin_table)['name']
rel_arcs = MHN.gdb + '/rel_arcs_to_' + itin_table_name
rel_sys = MHN.gdb + '/rel_' + itin_table_name.rsplit('_',1)[0] + '_to_' + itin_table_name.rsplit('_',1)[1]
arcpy.CreateRelationshipClass_management(MHN.arc, itin_table, rel_arcs, 'SIMPLE', itin_table_name, MHN.arc_name, 'NONE', 'ONE_TO_MANY', 'NONE', 'ABB', 'ABB')
arcpy.CreateRelationshipClass_management(routes_fc, itin_table, rel_sys, 'COMPOSITE', itin_table_name, bus_future_name, 'FORWARD', 'ONE_TO_MANY', 'NONE', common_id_field, common_id_field)

# Clean up.
arcpy.Compact_management(MHN.gdb)
arcpy.Delete_management(MHN.mem)
arcpy.Delete_management(backup_gdb)
arcpy.AddMessage('\nChanges successfully applied!\n')
