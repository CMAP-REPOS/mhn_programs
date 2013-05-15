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
#  Read SAS output and update hwyproj features/itinerary.
# -----------------------------------------------------------------------------
# Keys available in coding:
# 'TIPID', 'ACTION_CODE', 'REP_ANODE', 'REP_BNODE', 'NEW_TYPE1', 'NEW_TYPE2',
# 'NEW_THRULANEWIDTH1', 'NEW_THRULANEWIDTH2', 'NEW_THRULANES1', 'NEW_THRULANES2',
# 'NEW_POSTEDSPEED1', 'NEW_POSTEDSPEED2', 'NEW_AMPM1', 'NEW_AMPM2', 'NEW_MODES',
# 'NEW_TOLLDOLLARS', 'NEW_DIRECTIONS', 'ADD_PARKLANES1', 'ADD_PARKLANES2',
# 'ADD_SIGIC', 'ADD_CLTL', 'ADD_RRGRADECROSS', 'TOD' & 'ABB'

with open(projects_csv, 'r') as raw_coding:
    coding = csv.DictReader(raw_coding)
    tipids = (list(set([row['TIPID'] for row in coding])))
