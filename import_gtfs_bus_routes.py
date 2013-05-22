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


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(transact_csv)
MHN.delete_if_exists(network_csv)
MHN.delete_if_exists(nodes_csv)


# -----------------------------------------------------------------------------
#  Set route system-specific variables.
# -----------------------------------------------------------------------------
if which_bus = 'base':
    header = MHN.bus_base
elif which_bus = 'current':
    header = MHN.bus_current
else:
    MHN.die('Route system must be either "base" or "current", not {0}!'.format(which_bus))

itin = MHN.route_systems[header][0]
common_id_field = MHN.route_systems[header][1]
order_field = MHN.route_systems[header][2]
min_route_id = MHN.route_systems[header][3]
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

# Export bus year arc attributes.
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
arcpy.AddMessage('{0}Validating coding in {1}...'.format('\n', xls))

sas1_sas = ''.join((MHN.prog_dir + '/', sas1_name,'.sas'))
sas1_args = [raw_header_csv, raw_itin_csv, MHN.temp_dir, header_csv, itin_csv, str(min_route_id), str(MHN.max_poe), sas1_lst]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif os.path.exists(sas1_lst):
    MHN.die('Problems with bus_{0} route coding. Please see {1}.'.format(which_bus, sas1_lst))
else:
    os.remove(sas1_log)
    os.remove(transact_csv)
    os.remove(network_csv)
    os.remove(nodes_csv)
