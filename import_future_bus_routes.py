#!/usr/bin/env python
'''
    import_future_bus_routes.py
    Author: npeterson
    Revised: 2/6/14
    ---------------------------------------------------------------------------
    Import future bus route coding from an Excel spreadsheet, with "header" and
    "itinerary" worksheets. SAS can currently only handle .xls and not .xlsx.

'''
import csv
import os
import sys
import arcpy
import MHN

arcpy.AddWarning('\nCurrently updating {0}.'.format(MHN.gdb))

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
xls = arcpy.GetParameterAsText(0)  # Spreadsheet containing future bus coding
sas1_name = 'import_future_bus_routes_2'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = os.path.join(MHN.temp_dir, '{0}.log'.format(sas1_name))
sas1_lst = os.path.join(MHN.temp_dir, '{0}.lst'.format(sas1_name))
year_csv = os.path.join(MHN.temp_dir, 'year.csv')
transact_csv = os.path.join(MHN.temp_dir, 'transact.csv')
network_csv = os.path.join(MHN.temp_dir, 'network.csv')
future_itin_csv = os.path.join(MHN.temp_dir, 'future_itin.csv')
future_route_csv = os.path.join(MHN.temp_dir, 'future_route.csv')


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(year_csv)
MHN.delete_if_exists(transact_csv)
MHN.delete_if_exists(network_csv)
MHN.delete_if_exists(future_itin_csv)
MHN.delete_if_exists(future_route_csv)


# -----------------------------------------------------------------------------
#  Verify that all projects have a non-zero, non-null completion year.
# -----------------------------------------------------------------------------
invalid_hwyproj = MHN.get_yearless_hwyproj()
if invalid_hwyproj:
    MHN.die('The following highway projects have no completion year: {0}'.format(', '.join(invalid_hwyproj)))


# -----------------------------------------------------------------------------
#  Export highway project coding info to determine future arc availability.
# -----------------------------------------------------------------------------
hwyproj_id_field = MHN.route_systems[MHN.hwyproj][1]

# Export projects with valid completion years.
year_attr = (hwyproj_id_field, 'COMPLETION_YEAR')
year_query = '{0} <= {1}'.format("COMPLETION_YEAR", MHN.max_year)
year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'year_view', year_attr, year_query)
MHN.write_attribute_csv(year_view, year_csv, year_attr)
projects = MHN.make_attribute_dict(year_view, hwyproj_id_field, attr_list=[])
arcpy.Delete_management(year_view)

# Export coding for valid projects.
transact_attr = (hwyproj_id_field, 'ABB', 'ACTION_CODE', 'NEW_DIRECTIONS')
transact_query = ''' "{0}" IN ('{1}') '''.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in projects)))
transact_view = MHN.make_skinny_table_view(MHN.route_systems[MHN.hwyproj][0], 'transact_view', transact_attr, transact_query)
MHN.write_attribute_csv(transact_view, transact_csv, transact_attr)
project_arcs = MHN.make_attribute_dict(transact_view, 'ABB', attr_list=[])
arcpy.Delete_management(transact_view)

# Export base year arc attributes.
network_attr = (
    'ANODE', 'BNODE', 'BASELINK', 'ABB', 'DIRECTIONS', 'TYPE1', 'TYPE2',
    'AMPM1', 'AMPM2', 'POSTEDSPEED1', 'POSTEDSPEED2', 'THRULANES1', 'THRULANES2',
    'THRULANEWIDTH1', 'THRULANEWIDTH2', 'PARKLANES1', 'PARKLANES2',
    'SIGIC', 'CLTL', 'RRGRADECROSS', 'TOLLDOLLARS', 'MODES', 'MILES'
)
network_query = ''' "BASELINK" = '1' OR "ABB" IN ('{0}') '''.format("','".join((arc_id for arc_id in project_arcs if arc_id[-1] != '1')))
network_view = MHN.make_skinny_table_view(MHN.arc, 'network_view', network_attr, network_query)
MHN.write_attribute_csv(network_view, network_csv, network_attr)
arcpy.Delete_management(network_view)


# -----------------------------------------------------------------------------
#  Use SAS program to validate coding before import.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Validating coding in {1}...'.format('\n', xls))

sas1_sas = os.path.join(MHN.prog_dir, '{0}.sas'.format(sas1_name))
sas1_args = [xls, MHN.temp_dir, future_itin_csv, future_route_csv, str(MHN.max_poe), sas1_lst]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif os.path.exists(sas1_lst):
    MHN.die('Problems with future bus route coding. Please see {0}.'.format(sas1_lst))
else:
    os.remove(sas1_log)
    os.remove(year_csv)
    os.remove(transact_csv)
    os.remove(network_csv)


# -----------------------------------------------------------------------------
#  Generate temp route fc/itin table from SAS output.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Building updated route & itin table in memory...'.format('\n'))

temp_routes_name = 'temp_routes_fc'
temp_routes_fc = os.path.join(MHN.mem, temp_routes_name)
arcpy.CreateFeatureclass_management(MHN.mem, temp_routes_name, 'POLYLINE', MHN.bus_future)

temp_itin_name = 'temp_itin_table'
temp_itin_table = os.path.join(MHN.mem, temp_itin_name)
arcpy.CreateTable_management(MHN.mem, temp_itin_name, MHN.route_systems[MHN.bus_future][0])

# Update itin table directly from CSV, while determining coded arcs' IDs.
common_id_field = MHN.route_systems[MHN.bus_future][1]
order_field = MHN.route_systems[MHN.bus_future][2]
route_arcs = {}

itin_fields = (
    common_id_field, order_field, 'ITIN_A', 'ITIN_B', 'ABB', 'LAYOVER',
    'DWELL_CODE', 'ZONE_FARE', 'LINE_SERV_TIME', 'TTF'
)

with arcpy.da.InsertCursor(temp_itin_table, itin_fields) as cursor:
    raw_itin = open(future_itin_csv, 'r')
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
os.remove(future_itin_csv)

# Update itinerary F_MEAS & T_MEAS.
MHN.calculate_itin_measures(temp_itin_table)

# Generate route features one at a time.
# (Note: not using the MHN.build_geometry_dict() method for bus_future, because
#  the time saved in construction is lost in dict-building for small coding
#  tables.)
for route_id in sorted(route_arcs.keys()):

    # Dissolve route arcs into a single route feature, and append to temp FC.
    route_arc_ids = route_arcs[route_id]
    route_arcs_lyr = 'route_arcs_lyr'
    route_arcs_query = ''' "ABB" IN ('{0}') '''.format("','".join(route_arc_ids))
    arcpy.MakeFeatureLayer_management(MHN.arc, route_arcs_lyr, route_arcs_query)
    route_dissolved = os.path.join(MHN.mem, 'route_dissolved')
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
    'SCENARIO', 'REPLACE', 'TOD', 'NOTES'
)

with open(future_route_csv, 'r') as raw_routes:
    routes = csv.DictReader(raw_routes)
    for route in routes:
        attr_list = [route[field] for field in route_fields]
        header_attr[route[common_id_field]] = attr_list
os.remove(future_route_csv)

with arcpy.da.UpdateCursor(temp_routes_fc, route_fields) as cursor:
    for row in cursor:
        common_id = row[0]
        attr_list = header_attr[common_id]
        row[1:] = attr_list[1:]
        if row[route_fields.index('REPLACE')] == 'X':
            row[route_fields.index('REPLACE')] = ' '
        if row[route_fields.index('NOTES')] == 'X':
            row[route_fields.index('NOTES')] = ' '
        cursor.updateRow(row)


# -----------------------------------------------------------------------------
#  Merge temp routes with unaltered ones.
# -----------------------------------------------------------------------------
unaltered_routes_query = ''' "{0}" NOT IN ('{1}') '''.format(common_id_field, "','".join(route_arcs.keys()))

unaltered_routes_lyr = 'unaltered_routes_lyr'
arcpy.MakeFeatureLayer_management(MHN.bus_future, unaltered_routes_lyr, unaltered_routes_query)
updated_routes_fc = os.path.join(MHN.mem, 'updated_routes_fc')
arcpy.Merge_management((unaltered_routes_lyr, temp_routes_fc), updated_routes_fc)

unaltered_itin_view = 'unaltered_itin_view'
arcpy.MakeTableView_management(MHN.route_systems[MHN.bus_future][0], unaltered_itin_view, unaltered_routes_query)
updated_itin_table = os.path.join(MHN.mem, 'updated_itin_table')
arcpy.Merge_management((unaltered_itin_view, temp_itin_table), updated_itin_table)


# -----------------------------------------------------------------------------
#  Commit the changes only after everything else has run successfully.
# -----------------------------------------------------------------------------
backup_gdb = MHN.gdb[:-4] + '_' + MHN.timestamp() + '.gdb'
arcpy.Copy_management(MHN.gdb, backup_gdb)
arcpy.AddMessage('{0}Geodatabase temporarily backed up to {1}. (If import fails for any reason, replace {2} with this.)'.format('\n',backup_gdb, MHN.gdb))

arcpy.AddMessage('\nSaving changes to disk...')

# Replace header feature class.
arcpy.AddMessage('-- ' + MHN.bus_future + '...')
arcpy.TruncateTable_management(MHN.bus_future)
arcpy.Delete_management(MHN.bus_future)
arcpy.CopyFeatures_management(updated_routes_fc, MHN.bus_future)
arcpy.Delete_management(updated_routes_fc)

# Replace itinerary table.
itin_table = MHN.route_systems[MHN.bus_future][0]
arcpy.AddMessage('-- ' + itin_table + '...')
arcpy.TruncateTable_management(itin_table)
arcpy.Delete_management(itin_table)
itin_path = MHN.break_path(itin_table)
arcpy.CreateTable_management(itin_path['dir'], itin_path['name'], updated_itin_table)
arcpy.Append_management(updated_itin_table, itin_table, 'TEST')
arcpy.Delete_management(updated_itin_table)

# Rebuild relationship class.
arcpy.AddMessage('{0}Rebuilding relationship classes...'.format('\n'))
bus_future_name = MHN.break_path(MHN.bus_future)['name']
itin_table_name = MHN.break_path(itin_table)['name']
rel_arcs = os.path.join(MHN.gdb, 'rel_arcs_to_{0}'.format(itin_table_name))
rel_sys = os.path.join(MHN.gdb, 'rel_{0}_to_{1}'.format(itin_table_name.rsplit('_',1)[0], itin_table_name.rsplit('_',1)[1]))
arcpy.CreateRelationshipClass_management(MHN.arc, itin_table, rel_arcs, 'SIMPLE', itin_table_name, MHN.arc_name, 'NONE', 'ONE_TO_MANY', 'NONE', 'ABB', 'ABB')
arcpy.CreateRelationshipClass_management(MHN.bus_future, itin_table, rel_sys, 'COMPOSITE', itin_table_name, bus_future_name, 'FORWARD', 'ONE_TO_MANY', 'NONE', common_id_field, common_id_field)

# Clean up.
arcpy.Compact_management(MHN.gdb)
arcpy.Delete_management(MHN.mem)
arcpy.Delete_management(backup_gdb)
arcpy.AddMessage('\nChanges successfully applied!\n')
