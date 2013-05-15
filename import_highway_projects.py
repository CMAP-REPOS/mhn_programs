#!/usr/bin/env python
'''
    import_highway_projects.py
    Author: npeterson
    Revised: 5/9/2013
    ---------------------------------------------------------------------------
    Import highway project coding from an Excel spreadsheet. SAS can currently
    only handle .xls and not .xlsx.

'''
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
mhn_links_txt = ''.join((MHN.temp_dir, '/mhn_links.txt'))
projects_csv = ''.join((MHN.temp_dir, '/projects.csv'))


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(mhn_links_txt)
MHN.delete_if_exists(projects_csv)


# -----------------------------------------------------------------------------
#  Use SAS program to validate coding before import.
# -----------------------------------------------------------------------------
mhn_links_attr = ['ANODE', 'BNODE', 'BASELINK']
mhn_links_query = '''"BASELINK" IN ('0', '1')'''  # Ignore BASELINK > 1
mhn_links_view = MHN.make_skinny_table_view(MHN.arc, 'mhn_links_view', mhn_links_attr, mhn_links_query)
MHN.write_attribute_csv(mhn_links_view, mhn_links_txt, mhn_links_attr)

sas1_sas = ''.join((MHN.prog_dir + '/', sas1_name,'.sas'))
sas1_args = [xls, mhn_links_txt, projects_csv, sas1_lst]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif os.path.exists(sas1_lst):
    MHN.die('Problems with project coding. Please see {0}.'.format(sas2_lst))
else:
    arcpy.Delete_management(sas1_log)


# -----------------------------------------------------------------------------
#  Read SAS output and update hwyproj features/itinerary.
# -----------------------------------------------------------------------------

