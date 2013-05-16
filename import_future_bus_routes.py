#!/usr/bin/env python
'''
    import_future_bus_routes.py
    Author: npeterson
    Revised: 5/16/2013
    ---------------------------------------------------------------------------
    Import future bus route coding from an Excel spreadsheet, with "header" and
    "itinerary" worksheets. SAS can currently only handle .xls and not .xlsx.

'''
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


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(year_csv)
MHN.delete_if_exists(transact_csv)
MHN.delete_if_exists(network_csv)


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
arcpy.Delete_management(transact_view)

# Export base year arc attributes.
network_attr = (
    'ANODE', 'BNODE', 'BASELINK', 'ABB', 'DIRECTIONS', 'TYPE1', 'TYPE2',
    'AMPM1', 'AMPM2', 'POSTEDSPEED1', 'POSTEDSPEED2', 'THRULANES1', 'THRULANES2',
    'THRULANEWIDTH1', 'THRULANEWIDTH2', 'PARKLANES1', 'PARKLANES2',
    'SIGIC', 'CLTL', 'RRGRADECROSS', 'TOLLDOLLARS', 'MODES', 'MILES'
)
network_query = '"BASELINK" = \'1\''
network_view = MHN.make_skinny_table_view(MHN.arc, 'network_view', network_attr, network_query)
MHN.write_attribute_csv(network_view, network_csv, network_attr)
arcpy.Delete_management(network_view)


# -----------------------------------------------------------------------------
#  Use SAS program to validate coding before import.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Validating coding in {1}...'.format('\n', xls))

sas1_sas = ''.join((MHN.prog_dir + '/', sas1_name,'.sas'))
sas1_args = [xls, MHN.temp_dir, MHN.prog_dir, MHN.max_poe]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif not os.path.exists(projects_csv):
    MHN.die('{0} did not finish successfully! Please see {1}'.format(sas1_sas, sas1_log))
elif os.path.exists(sas1_lst):
    MHN.die('Problems with project coding. Please see {0}.'.format(sas1_lst))
else:
    os.remove(sas1_log)
    arcpy.Delete_management(year_csv)
    arcpy.Delete_management(transact_csv)
    arcpy.Delete_management(network_csv)
