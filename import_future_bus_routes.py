#!/usr/bin/env python
'''
    import_future_bus_routes.py
    Author: npeterson
    Revised: 5/20/2013
    ---------------------------------------------------------------------------
    Import future bus route coding from an Excel spreadsheet, with "header" and
    "itinerary" worksheets. SAS can currently only handle .xls and not .xlsx.

'''
import csv
import os
import sys
import arcpy
import MHN

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
xls = arcpy.GetParameterAsText(0)  # Spreadsheet containing project coding
sas1_name = 'import_future_bus_routes_2'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = ''.join((MHN.temp_dir, '/', sas1_name, '.log'))
sas1_lst = ''.join((MHN.temp_dir, '/', sas1_name, '.lst'))
year_csv = '/'.join((MHN.temp_dir, 'year.csv'))
transact_csv = '/'.join((MHN.temp_dir, 'transact.csv'))
network_csv = '/'.join((MHN.temp_dir, 'network.csv'))
future_itin_csv = '/'.join((MHN.temp_dir, 'future_itin.csv'))
future_route_csv = '/'.join((MHN.temp_dir, 'future_route.csv'))


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
transact_query = '"{0}" IN (\'{1}\')'.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in projects)))
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
network_query = '"BASELINK" = \'1\' OR "ABB" IN (\'{0}\')'.format("','".join((arc_id for arc_id in project_arcs)))
network_view = MHN.make_skinny_table_view(MHN.arc, 'network_view', network_attr, network_query)
MHN.write_attribute_csv(network_view, network_csv, network_attr)
arcpy.Delete_management(network_view)


# -----------------------------------------------------------------------------
#  Use SAS program to validate coding before import.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Validating coding in {1}...'.format('\n', xls))

sas1_sas = ''.join((MHN.prog_dir + '/', sas1_name,'.sas'))
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
temp_routes_fc = '/'.join((MHN.gdb, temp_routes_name))
arcpy.CreateFeatureclass_management(MHN.gdb, temp_routes_name, 'POLYLINE', MHN.bus_future)

temp_itin_name = 'temp_itin_table'
temp_itin_table = '/'.join((MHN.gdb, temp_itin_name))
arcpy.CreateTable_management(MHN.gdb, temp_itin_name, MHN.route_systems[MHN.bus_future][0])

# Update itin table directly from CSV, while determining coded arcs' IDs.
common_id_field = MHN.route_systems[MHN.bus_future][1]  # 'TRANSIT_LINE'
order_field = MHN.route_systems[MHN.bus_future][2]      # 'ITIN_ORDER'
route_arcs = {}

itin_fields = (
    common_id_field, 'ITIN_A', 'ITIN_B', 'ABB', order_field, 'LAYOVER',
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
### TO DO ###

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

    # Fill other fields with data in future_route_csv.
    ### TO DO ###


# -----------------------------------------------------------------------------
#  Merge updated routes with unaltered ones.
# -----------------------------------------------------------------------------
# Copy features and coding of unaltered projects in MHN.
unaltered_routes_query = '"{0}" NOT IN (\''.format(common_id_field) + "','".join(route_arcs.keys()) + "')"

unaltered_routes_lyr = 'unaltered_routes_lyr'
arcpy.MakeFeatureLayer_management(MHN.bus_future, unaltered_routes_lyr, unaltered_routes_query)

unaltered_itin_view = 'unaltered_itin_view'
arcpy.MakeTableView_management(MHN.route_systems[MHN.bus_future][0], unaltered_itin_view, unaltered_routes_query)

# Append routes/itin from temp FC/table.
updated_routes_fc = '/'.join((MHN.mem, 'updated_routes_fc'))
arcpy.Merge_management((unaltered_routes_lyr, temp_routes_fc), updated_routes_fc)

updated_itin_table = '/'.join((MHN.mem, 'updated_itin_table'))
arcpy.Merge_management((unaltered_itin_view, temp_itin_table), updated_itin_table)


# -----------------------------------------------------------------------------
#  Commit the changes only after everything else has run successfully.
# -----------------------------------------------------------------------------
backup_gdb = MHN.gdb[:-4] + '_' + MHN.timestamp() + '.gdb'
arcpy.Copy_management(MHN.gdb, backup_gdb)
arcpy.AddMessage('{0}Geodatabase temporarily backed up to {1}. (If import fails for any reason, replace {2} with this.)'.format('\n',backup_gdb, MHN.gdb))

arcpy.AddMessage('{0}Saving changes to disk...'.format('\n'))

### TO DO ###
