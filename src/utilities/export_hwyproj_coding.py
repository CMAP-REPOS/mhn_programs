#!/usr/bin/env python
'''
    export_hwyproj_coding.py
    Author: npeterson
    Revised: 12/19/18
    ---------------------------------------------------------------------------
    Export highway project coding for selected projects (or all projects if
    none are selected) into a CSV that is formatted consistently with the
    highway project coding template in ../../import/coding_templates.

'''
import os
import sys
import arcpy

sys.path.append(os.path.abspath(os.path.join(sys.path[0], '..')))  # Add mhn_programs dir to path, so MHN.py can be imported
from MHN import MasterHighwayNetwork  # Custom class for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
hwyproj_lyr = arcpy.GetParameterAsText(0)
out_dir = arcpy.GetParameterAsText(1)
out_name = arcpy.GetParameterAsText(2)

out_csv = os.path.join(out_dir, out_name)
if not out_csv.lower().endswith('.csv'):
    out_csv += '.csv'

mhn_gdb_path = arcpy.Describe(hwyproj_lyr).catalogPath.split('.gdb')[0] + '.gdb'  # MHN gdb path
MHN = MasterHighwayNetwork(mhn_gdb_path)  # Initialize MHN object
hwyproj_coding_tbl = MHN.route_systems[MHN.hwyproj][0]  # Get path to related coding table
hwyproj_id_field = MHN.route_systems[MHN.hwyproj][1]  # Get common ID field name (TIPID)


# -----------------------------------------------------------------------------
#  Define helper functions.
# -----------------------------------------------------------------------------
def str_no_zeroes(x):
    ''' Return str(x) unless x is 0, in which case return an empty string. '''
    str_x = str(x)
    if str_x in ('0', '0.0'):
        return ''
    else:
        return str_x


# -----------------------------------------------------------------------------
#  Identify the selected TIPIDs and select related coding.
# -----------------------------------------------------------------------------
if MHN.check_selection(hwyproj_lyr):
    selected_tipids = set(r[0] for r in arcpy.da.SearchCursor(hwyproj_lyr, [hwyproj_id_field]))
    related_sql = "{} IN ('{}')".format(hwyproj_id_field, "','".join(selected_tipids))
    arcpy.AddMessage('\nExporting coding for the following projects:')
    for tipid in sorted(selected_tipids):
        arcpy.AddMessage('  - {}'.format(MHN.tipid_from_int(tipid)))
else:
    # No features selected, so export entire coding table
    related_sql = None
    arcpy.AddMessage('\nExporting coding for ALL projects...')


# -----------------------------------------------------------------------------
#  Write output CSV.
# -----------------------------------------------------------------------------
w = open(out_csv, 'wt')
out_cols = [
    'tipid', 'anode', 'bnode', 'action', 'type1', 'type2', 'sigic',
    'feet1', 'lanes1', 'speed1', 'rep_anode', 'rep_bnode',
    'feet2', 'lanes2', 'speed2', 'tolldollars',
    'directions', 'parklanes1', 'parklanes2', 'cltl',
    'ampm1', 'ampm2', 'modes', 'rr_grade_sep', 'tod'
]
w.write('{}\n'.format(','.join(out_cols)))  # Header row

coding_fields = [
    hwyproj_id_field, 'ABB', 'ACTION_CODE', 'NEW_TYPE1', 'NEW_TYPE2','ADD_SIGIC',
    'NEW_THRULANEWIDTH1', 'NEW_THRULANES1', 'NEW_POSTEDSPEED1', 'REP_ANODE', 'REP_BNODE',
    'NEW_THRULANEWIDTH2', 'NEW_THRULANES2', 'NEW_POSTEDSPEED2', 'NEW_TOLLDOLLARS',
    'NEW_DIRECTIONS', 'ADD_PARKLANES1', 'ADD_PARKLANES2', 'ADD_CLTL',
    'NEW_AMPM1', 'NEW_AMPM2', 'NEW_MODES', 'ADD_RRGRADECROSS', 'TOD'
]
sort_sql = "ORDER BY {}, ACTION_CODE, NEW_TYPE1, NEW_DIRECTIONS, NEW_THRULANES1, REP_ANODE, REP_BNODE, ABB".format(hwyproj_id_field)
with arcpy.da.SearchCursor(hwyproj_coding_tbl, coding_fields, related_sql, sql_clause=(None, sort_sql)) as c:
    for r in c:
        tipid = r[0]
        anode, bnode, baselink = r[1].split('-')
        attr = [str_no_zeroes(x) for x in r[2:]]
        out_row = [tipid, anode, bnode] + attr
        w.write('{}\n'.format(','.join(out_row)))

w.close()

arcpy.AddMessage('\nAll done! Project coding has been saved to {}.\n'.format(out_csv))
