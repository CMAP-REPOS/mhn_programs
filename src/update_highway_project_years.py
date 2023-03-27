#!/usr/bin/env python
'''
    update_highway_project_years.py
    Author: npeterson
    Revised: 3/29/22
    ---------------------------------------------------------------------------
    This script updates the completion years of projects to be included in
    Conformity analyses. The final completion year file is received from the
    TIP division after all project changes have been processed.

    Input files (pre-requisites for running this script):
    1. CSV containing TIPIDs & completion years of codable Conformed projects.
    2. CSV containing TIPIDs & completion years of codable Exempt projects.
    3. CSV containing TIPIDs of Conformed or Exempt projects deemed uncodable.

    Output files, if errors encountered:
    1. Output/in_year_not_mhn.txt: projects in hwyproj_year.csv but not in
       MHN.hwyproj (excluding those in uncodable CSV).
    2. Output/in_mhn_not_year.txt: projects coded in MHN.hwyproj with
       COMPLETION_YEAR != 9999 that should not be included in Conformity.

'''
import os
import re
import arcpy
from MHN import MasterHighwayNetwork  # Custom class for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
mhn_gdb_path = arcpy.GetParameterAsText(0)           # MHN geodatabase
MHN = MasterHighwayNetwork(mhn_gdb_path)
mrn_gdb_path = arcpy.GetParameterAsText(1)           # MRN geodatabase
mrn_future_fc = os.path.join(mrn_gdb_path, 'railnet', 'future')
people_mover_table = os.path.join(mrn_gdb_path, 'people_mover')
tipid_conformed_csv = arcpy.GetParameterAsText(2)    # CSV of coded conformed projects
tipid_exempt_csv = arcpy.GetParameterAsText(3)       # CSV of coded exempt projects
tipid_uncodable_csv = arcpy.GetParameterAsText(4)    # CSV of uncodable projects

#arcpy.AddWarning('\nCurrently updating {0}.'.format(MHN.gdb))

if not arcpy.Exists(mrn_gdb_path):
    MHN.die("{0} doesn't exist!".format(mrn_gdb_path))
if not arcpy.Exists(mrn_future_fc):
    MHN.die("{0} doesn't exist!".format(mrn_future_fc))
if not arcpy.Exists(people_mover_table):
    MHN.die("{0} doesn't exist!".format(people_mover_table))
if not os.path.exists(tipid_conformed_csv):
    MHN.die("{0} doesn't exist!".format(tipid_conformed_csv))
if not os.path.exists(tipid_exempt_csv):
    MHN.die("{0} doesn't exist!".format(tipid_exempt_csv))
if not os.path.exists(tipid_uncodable_csv):
    MHN.die("{0} doesn't exist!".format(tipid_uncodable_csv))


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
tipid_all_csv = os.path.join(MHN.temp_dir, 'tipid_all.csv')
early_scenarios_csv = os.path.join(MHN.temp_dir, 'early_transit_scenarios.csv')
late_scenarios_csv = os.path.join(MHN.temp_dir, 'late_transit_scenarios.csv')
unknown_trans_ids_csv = os.path.join(MHN.temp_dir, 'unknown_transit_tipids.csv')
in_year_not_mhn_txt = os.path.join(MHN.temp_dir, 'in_year_not_mhn.txt')
in_mhn_not_year_txt = os.path.join(MHN.temp_dir, 'in_mhn_not_year.txt')


# -----------------------------------------------------------------------------
#  Clean up old temp/output files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(tipid_all_csv)
MHN.delete_if_exists(early_scenarios_csv)
MHN.delete_if_exists(in_year_not_mhn_txt)
MHN.delete_if_exists(in_mhn_not_year_txt)


# -----------------------------------------------------------------------------
#  Merge codable Conformed project years with codable Exempt project years,
#  and check for duplicates with different completion years.
# -----------------------------------------------------------------------------
with open(tipid_all_csv, 'w') as merged:
    with open(tipid_conformed_csv, 'r') as conformed:
        for line in conformed:
            if int(line.split(',')[1]) > MHN.base_year:
                merged.write(line)
    with open(tipid_exempt_csv, 'r') as exempt:
        merged.write(exempt.read())

# Identify any duplicates with differing completion years
proj_years = {}
duplicates = []
with open(tipid_all_csv, 'r') as r:
    for line in r:
        tipid_str, completion_year_str = line.strip().split(',')[:2]  # rows from year.csv have a 3rd column that is ignored here
        tipid = int(tipid_str)
        completion_year = int(completion_year_str)
        if tipid in proj_years and completion_year != proj_years[tipid]:
            duplicates.append(tipid)
        else:
            proj_years[tipid] = completion_year

# Report duplicates and stop processing, if any exist
if duplicates:
    duplicate_message = 'Duplicate TIPID(s) with different completion years in {0} and/or {1}: {2}!'
    MHN.die(duplicate_message.format(tipid_conformed_csv, tipid_exempt_csv, ', '.join((str(k) for k in duplicates))))

os.remove(tipid_all_csv)


# -----------------------------------------------------------------------------
#  Check future transit projects for improper scenario coding.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Checking future transit projects...'.format('\n'))

def clear_transit_project_years(proj_years_dict, hwyproj_ids, rail_fc, bus_fc, mover_table,
                                early_scenarios_csv, late_scenarios_csv, unknown_trans_ids_csv):
    ''' Remove transit project TIPIDs from the dict after verifying that their
        scenarios specified in the MHN/MRN are no earlier than their completion
        years. '''

    # Get earliest scenario referenced for each bus, rail and people mover TIPID
    rail_proj_scens = get_trans_proj_scens(rail_fc)
    bus_proj_scens = get_trans_proj_scens(bus_fc)
    mover_proj_scens = get_trans_proj_scens(mover_table)

    # Combine separate rail, bus & people mover dicts into one
    trans_proj_scens = rail_proj_scens.copy()
    for tipid, scen in bus_proj_scens.items():
        if tipid not in trans_proj_scens or scen < trans_proj_scens[tipid]:
            trans_proj_scens[tipid] = scen
    for tipid, scen in mover_proj_scens.items():
        if tipid not in trans_proj_scens or scen < trans_proj_scens[tipid]:
            trans_proj_scens[tipid] = scen

    # Compare transit project scenarios against project completion years.
    # If any errors exist, write them to file and stop processing.
    early_scenarios = set()
    late_scenarios = set()
    unknown_tipids = set()
    for tipid, scen in trans_proj_scens.items():
        if tipid in proj_years_dict and MHN.scenario_years[str(scen)] < proj_years_dict[tipid]:
            early_scenarios.add(tipid)
        elif tipid in proj_years_dict and MHN.scenario_years.get(str(scen - 100), MHN.base_year) > proj_years_dict[tipid]:
            late_scenarios.add(tipid)
        elif tipid not in proj_years_dict and MHN.scenario_years[str(scen)] < MHN.max_year:
            unknown_tipids.add(tipid)

    if early_scenarios:
        with open(early_scenarios_csv, 'w') as w:
            w.write('TIPID,COMPLETION_YEAR,FIRST_SCENARIO\n')
            for tipid in sorted(early_scenarios):
                w.write('{0},{1},{2}\n'.format(MHN.tipid_from_int(tipid), proj_years_dict[tipid], trans_proj_scens[tipid]))
        MHN.die((
            '''ERROR: Some transit projects (future bus, rail and/or people '''
            '''mover) reference a scenario that is earlier than their TIPID's '''
            '''specified completion year. See {0} for details.'''
        ).format(early_scenarios_csv))

    if late_scenarios:
        with open(late_scenarios_csv, 'w') as w:
            w.write('TIPID,COMPLETION_YEAR,FIRST_SCENARIO\n')
            for tipid in sorted(late_scenarios):
                w.write('{0},{1},{2}\n'.format(MHN.tipid_from_int(tipid), proj_years_dict[tipid], trans_proj_scens[tipid]))
        MHN.die((
            '''ERROR: Some transit projects (future bus, rail and/or people '''
            '''mover) reference a scenario that is much later than their TIPID's '''
            '''specified completion year. See {0} for details.'''
        ).format(late_scenarios_csv))

    if unknown_tipids:
        with open(unknown_trans_ids_csv, 'w') as w:
            w.write('TIPID,FIRST_SCENARIO\n')
            for tipid in sorted(unknown_tipids):
                w.write('{0},{1}\n'.format(MHN.tipid_from_int(tipid), trans_proj_scens[tipid]))
        MHN.die((
            '''ERROR: Some transit projects (future bus, rail and/or people '''
            '''mover) have a TIPID that is not present in {0} or {1}. See {2} '''
            '''for details.'''
        ).format(tipid_conformed_csv, tipid_exempt_csv, unknown_trans_ids_csv))

    # Ignore transit projects that also have a highway component (e.g. new busway links)
    trans_proj_with_hwy_component = set(hwyproj_ids) & set(trans_proj_scens.keys())
    for tipid in trans_proj_with_hwy_component:
        del trans_proj_scens[tipid]

    # Remove transit TIPIDs from project years dictionary
    hwyproj_years_dict = proj_years_dict.copy()
    for tipid in trans_proj_scens.keys():
        hwyproj_years_dict.pop(tipid, None)

    return hwyproj_years_dict


def get_trans_proj_scens(table):
    ''' Helper function to pull TIPIDs and scenarios from table rows. '''
    tipid_scens = {}

    # Iterate through headers with valid TIPIDs & scenarios
    fields = ['NOTES', 'SCENARIO']
    sql = ''' "NOTES" LIKE '%__-__-____%' AND "SCENARIO" NOT IN ('9') '''
    with arcpy.da.SearchCursor(table, fields, sql) as cursor:
        for row in cursor:

            # Parse referenced TIPIDs
            tipids = []
            notes = re.split(':|;', row[0])  # Split at colon or semicolon
            for note in notes:
                note = note.strip()
                if MHN.is_tipid(note):
                    tipids.append(MHN.tipid_to_int(note))

            # Identify earliest referenced scenario
            scens = [int('{0}00'.format(scen)) for scen in row[1]]
            first_scen = min(scens)

            for tipid in tipids:
                if tipid not in tipid_scens or first_scen < tipid_scens[tipid]:
                    tipid_scens[tipid] = first_scen

    return tipid_scens

# Remove transit-only (bus or rail) projects after checking their scenario codes
common_id_field = MHN.route_systems[MHN.hwyproj][1]
coded_hwyproj = [int(r[0]) for r in arcpy.da.SearchCursor(MHN.hwyproj, [common_id_field])]
hwyproj_years = clear_transit_project_years(
    proj_years, coded_hwyproj, mrn_future_fc, MHN.bus_future, people_mover_table,
    early_scenarios_csv, late_scenarios_csv, unknown_trans_ids_csv
)


# -----------------------------------------------------------------------------
#  Read uncodable projects into dictionary.
# -----------------------------------------------------------------------------
uncodable_proj = set() #[]
with open(tipid_uncodable_csv, 'r') as no_code:
    for row in no_code:
        tipid = int(row.strip().split(',')[0])
        uncodable_proj.add(tipid)


# -----------------------------------------------------------------------------
#  Check for inappropriately coded projects.
# -----------------------------------------------------------------------------
hwyproj_view = 'hwyproj_view'
arcpy.MakeTableView_management(MHN.hwyproj, hwyproj_view)

# Select projects in MHN but not in year.csv:
unmatched_hwyproj_query = ''' "{0}" NOT IN ('{1}') '''.format(common_id_field, "','".join((str(k) for k in hwyproj_years.keys())))
arcpy.SelectLayerByAttribute_management(hwyproj_view, selection_type='NEW_SELECTION', where_clause=unmatched_hwyproj_query)

# Ignore out-of-region projects:
out_of_region_query = ''' "{0}" LIKE '14______' '''.format(common_id_field)
arcpy.SelectLayerByAttribute_management(hwyproj_view, selection_type='REMOVE_FROM_SELECTION', where_clause=out_of_region_query)

# Ignore projects not being conformed:
not_conformed_query = '"COMPLETION_YEAR" > {0}'.format(MHN.max_year)
arcpy.SelectLayerByAttribute_management(hwyproj_view, selection_type='REMOVE_FROM_SELECTION', where_clause=not_conformed_query)

# Report any MHN projects not in year lists:
if int(arcpy.GetCount_management(hwyproj_view).getOutput(0)) == 0:
    arcpy.AddMessage((
        '''{0}All in-region, conformed projects coded in MHN are listed in '''
        '''{1} or {2}!'''
        ).format('\n', tipid_conformed_csv, tipid_exempt_csv))
else:
    with open(in_mhn_not_year_txt, 'w') as miscoded_output:
        with arcpy.da.SearchCursor(hwyproj_view, [common_id_field, 'COMPLETION_YEAR']) as cursor:
            for row in cursor:
                miscoded_output.write('{0},{1}\n'.format(row[0], row[1]))
    arcpy.AddWarning((
        '''{0}WARNING: Some in-region, conformed projects coded in MHN are '''
        '''not listed in {1} or {2}. See {3} for details.'''
        ).format('\n', tipid_conformed_csv, tipid_exempt_csv, in_mhn_not_year_txt))

arcpy.Delete_management(hwyproj_view)


# -----------------------------------------------------------------------------
#  Check for still-uncoded projects.
# -----------------------------------------------------------------------------
uncoded_hwyproj = [tipid for tipid in hwyproj_years if tipid not in coded_hwyproj and tipid not in uncodable_proj]
if len(uncoded_hwyproj) == 0:
    arcpy.AddMessage((
        '''{0}All projects listed in {1} and {2} are coded in MHN!'''
        ).format('\n', tipid_conformed_csv, tipid_exempt_csv))
else:
    with open(in_year_not_mhn_txt, 'w') as uncoded_output:
        for tipid in sorted(uncoded_hwyproj):
            uncoded_output.write('{0}\n'.format(tipid))
    arcpy.AddWarning((
        '''{0}WARNING: Some projects in {1} or {2} but not {3} are not yet '''
        '''coded in MHN. See {4} for details.'''
        ).format('\n', tipid_conformed_csv, tipid_exempt_csv, tipid_uncodable_csv, in_year_not_mhn_txt))


# -----------------------------------------------------------------------------
#  Update completion years of MHN projects found in year lists.
# -----------------------------------------------------------------------------
arcpy.AddMessage((
    '''{0}Updating COMPLETION_YEAR values for projects coded in MHN that '''
    '''are listed in {1} or {2}...'''
    ).format('\n', tipid_conformed_csv, tipid_exempt_csv))
edit = arcpy.da.Editor(MHN.gdb)
edit.startEditing()
edit.startOperation()
with arcpy.da.UpdateCursor(MHN.hwyproj, [common_id_field, 'COMPLETION_YEAR']) as c:
    for r in c:
        tipid = int(r[0])
        if tipid in hwyproj_years:
            r[1] = hwyproj_years[tipid]
        c.updateRow(r)
edit.stopOperation()
edit.stopEditing(True)


# -----------------------------------------------------------------------------
#  Clean up.
# -----------------------------------------------------------------------------
arcpy.Delete_management(MHN.mem)
arcpy.AddMessage('{0}All done!{0}'.format('\n'))
