#!/usr/bin/env python
'''
    update_highway_project_years.py
    Author: npeterson
    Revised: 7/1/13
    ---------------------------------------------------------------------------
    This script updates the completion years of projects to be included in
    Conformity analyses. The final completion year file is received from the
    TIP division after all project changes have been processed.

    Input files (pre-requisites for running this script):
    1. CSV containing TIPIDs & completion years of conformed projects.
    2. CSV containing TIPIDs of conformed projects deemed uncodable.

    Output files, if errors encountered:
    1. Output/in_year_not_mhn.txt: projects in hwyproj_year.csv but not in
       MHN.hwyproj (excluding those in uncodable_hwyproj.csv).
    2. Output/in_mhn_not_year.txt: projects coded in MHN.hwyproj with
       COMPLETION_YEAR != 9999 that are not to be included in Conformity.

'''
import os
import csv
import sys
import arcpy
import MHN

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
hwyproj_year_csv = arcpy.GetParameterAsText(0).replace('\\','/')
uncodable_hwyproj_csv = arcpy.GetParameterAsText(1).replace('\\','/')
mrn_gdb = arcpy.GetParameterAsText(2).replace('\\','/')
mrn_future_fc = ''.join((mrn_gdb, '/railnet/future'))
people_mover_table = ''.join((mrn_gdb, '/people_mover'))
sas1_name = 'update_highway_project_years_2'

if not arcpy.Exists(mrn_gdb):
    MHN.die("{0} doesn't exist!".format(mrn_gdb))
if not arcpy.Exists(mrn_future_fc):
    MHN.die("{0} doesn't exist!".format(mrn_future_fc))
if not arcpy.Exists(people_mover_table):
    MHN.die("{0} doesn't exist!".format(people_mover_table))
if not os.path.exists(hwyproj_year_csv):
    MHN.die("{0} doesn't exist!".format(hwyproj_year_csv))
if not os.path.exists(uncodable_hwyproj_csv):
    MHN.die("{0} doesn't exist!".format(uncodable_hwyproj_csv))


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = ''.join((MHN.temp_dir, '/', sas1_name, '.log'))
sas1_lst = ''.join((MHN.temp_dir, '/', sas1_name, '.lst'))
sas1_output = ''.join((MHN.temp_dir, '/hwyproj_year_adj.csv'))
in_year_not_mhn_txt = ''.join((MHN.out_dir, '/in_year_not_mhn.txt'))
in_mhn_not_year_txt = ''.join((MHN.out_dir, '/in_mhn_not_year.txt'))


# -----------------------------------------------------------------------------
#  Clean up old temp/output files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(sas1_output)
MHN.delete_if_exists(in_year_not_mhn_txt)
MHN.delete_if_exists(in_mhn_not_year_txt)


# -----------------------------------------------------------------------------
#  Generate DBFs and call SAS program to check future transit years.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Checking future transit projects...'.format('\n'))

def make_future_transit_dbf(input_table, output_dbf):
    ''' Copy all header rows from a future bus/rail fc/table to a DBF. '''
    arcpy.CopyRows_management(input_table, output_dbf)
    with arcpy.da.UpdateCursor(output_dbf, ['NOTES']) as cursor:
        for row in cursor:
            row[0] = row[0].replace('-', '')  # Remove dashes from TIPIDs
            cursor.updateRow(row)
    return output_dbf

future_bus_dbf = '/'.join((MHN.imp_dir, 'future_bus.dbf'))
make_future_transit_dbf(MHN.bus_future, future_bus_dbf)

future_rail_dbf = '/'.join((MHN.imp_dir, 'future_rail.dbf'))
make_future_transit_dbf(mrn_future_fc, future_rail_dbf)

people_mover_dbf = '/'.join((MHN.imp_dir, 'people_mover.dbf'))
make_future_transit_dbf(people_mover_table, people_mover_dbf)

sas1_sas = ''.join((MHN.prog_dir, '/', sas1_name, '.sas'))
sas1_args = [hwyproj_year_csv, future_rail_dbf, future_bus_dbf, sas1_output]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif not os.path.exists(sas1_output):
    MHN.die('{0} did not run successfully. Please review {1}.'.format(sas1_sas, sas1_log))
elif os.path.exists(sas1_lst):
    MHN.die('Problems with future transit coding. Please review {0}.'.format(sas1_lst))
else:
    arcpy.Delete_management(sas1_log)
    arcpy.Delete_management(future_rail_dbf)
    arcpy.Delete_management(people_mover_dbf)
    arcpy.Delete_management(future_bus_dbf)


# -----------------------------------------------------------------------------
#  Load completion years and uncodable projects into Python objects.
# -----------------------------------------------------------------------------
common_id_field = MHN.route_systems[MHN.hwyproj][1]

hwyproj_years = {}
with open(sas1_output, 'r') as year_adj:
    year_adj_dr = csv.DictReader(year_adj)
    for proj_dict in year_adj_dr:
        hwyproj_id = proj_dict[common_id_field]
        completion_year = int(proj_dict['COMPLETION_YEAR'])
        if hwyproj_id in hwyproj_years and completion_year != hwyproj_years[hwyproj_id]:
            MHN.die('Duplicate TIPID in {0}: {1}!'.format(hwyproj_year_csv, hwyproj_id))
        else:
            hwyproj_years[hwyproj_id] = completion_year

uncodable_hwyproj = []
with open(uncodable_hwyproj_csv, 'r') as no_code:
    for row in no_code:
        hwyproj_id = row.split(',')[0].lstrip('0')  # After switch to 'xx-xx-xxxx' format, remove lstrip!
        if hwyproj_id not in uncodable_hwyproj:
            uncodable_hwyproj.append(hwyproj_id)


# -----------------------------------------------------------------------------
#  Check for inappropriately coded projects.
# -----------------------------------------------------------------------------
# Select projects in MHN but not in year.csv:
hwyproj_view = 'hwyproj_view'
unmatched_hwyproj_query = '"{0}" NOT IN (\'{1}\')'.format(common_id_field, "','".join(hwyproj_years.keys()))
arcpy.MakeTableView_management(MHN.hwyproj, hwyproj_view, unmatched_hwyproj_query)

# Ignore out-of-region projects:
out_of_region_query = '"{0}" LIKE \'14______\''.format(common_id_field)
arcpy.SelectLayerByAttribute_management(hwyproj_view, 'REMOVE_FROM_SELECTION', out_of_region_query)

# Ignore projects not being conformed:
not_conformed_query = '"COMPLETION_YEAR" > {0}'.format(MHN.max_year)
arcpy.SelectLayerByAttribute_management(hwyproj_view, 'REMOVE_FROM_SELECTION', not_conformed_query)

# Update COMPLETION_YEAR values for MHN projects in year.csv, and report those that aren't.
if int(arcpy.GetCount_management(hwyproj_view).getOutput(0)) == 0:
    arcpy.AddMessage('{0}All in-region, conformed projects coded in MHN exist in {1}!'.format('\n', hwyproj_year_csv))
else:
    with open(in_mhn_not_year_txt, 'w') as miscoded_output:
        with arcpy.da.SearchCursor(hwyproj_view, [common_id_field, 'COMPLETION_YEAR']) as cursor:
            for row in cursor:
                miscoded_output.write('{0},{1}\n'.format(row[0], row[1]))
    arcpy.AddMessage('{0}Some projects coded in MHN are not coded in {1}. See {2} for details.'.format('\n', hwyproj_year_csv, in_mhn_not_year_txt))


# -----------------------------------------------------------------------------
#  Check for still-uncoded projects.
# -----------------------------------------------------------------------------
coded_hwyproj = MHN.make_attribute_dict(MHN.hwyproj, common_id_field, []).keys()
uncoded_hwyproj = [hwyproj_id for hwyproj_id in hwyproj_years if hwyproj_id not in coded_hwyproj and hwyproj_id not in uncodable_hwyproj]
with open(in_year_not_mhn_txt, 'w') as uncoded_output:
    for hwyproj_id in sorted(uncoded_hwyproj):
        uncoded_output.write('{0}\n'.format(hwyproj_id))
arcpy.AddMessage('{0}Some projects in {1} and not {2} are not yet coded in MHN. See {3} for details.'.format('\n', hwyproj_year_csv, uncodable_hwyproj_csv, in_year_not_mhn_txt))


# -----------------------------------------------------------------------------
#  Update completion years of MHN projects found in year.csv.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Updating COMPLETION_YEAR values for projects coded in MHN that are listed in {1}...'.format('\n', hwyproj_year_csv))
edit = arcpy.da.Editor(MHN.gdb)
edit.startEditing()
with arcpy.da.UpdateCursor(MHN.hwyproj, [common_id_field, 'COMPLETION_YEAR']) as cursor:
    for row in cursor:
        if row[0] in hwyproj_years:
            row[1] = hwyproj_years[row[0]]
        cursor.updateRow(row)
edit.stopEditing(True)


# -----------------------------------------------------------------------------
#  Clean up.
# -----------------------------------------------------------------------------
os.remove(sas1_output)
arcpy.Delete_management(MHN.mem)
arcpy.AddMessage('{0}All done!{0}'.format('\n'))
