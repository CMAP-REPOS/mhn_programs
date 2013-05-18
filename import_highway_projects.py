#!/usr/bin/env python
'''
    import_highway_projects.py
    Author: npeterson
    Revised: 5/16/2013
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
arcpy.AddMessage('{0}Validating coding in {1}...'.format('\n', xls))
mhn_links_attr = ['ANODE', 'BNODE', 'BASELINK']
mhn_links_query = '"BASELINK" IN (\'0\', \'1\')'  # Ignore BASELINK > 1
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
    os.remove(sas1_log)
    os.remove(mhn_links_csv)


# -----------------------------------------------------------------------------
#  Generate temp feature class/coding table from SAS output.
# -----------------------------------------------------------------------------
arcpy.AddMessage('{0}Building updated coding table & feature class in memory...'.format('\n'))

temp_projects_name = 'temp_routes_fc'
temp_projects_fc = '/'.join((MHN.mem, temp_projects_name))
arcpy.CreateFeatureclass_management(MHN.mem, temp_projects_name, 'POLYLINE', MHN.hwyproj)

temp_coding_name = 'temp_coding_table'
temp_coding_table = '/'.join((MHN.mem, temp_coding_name))
arcpy.CreateTable_management(MHN.mem, temp_coding_name, MHN.route_systems[MHN.hwyproj][0])

# Update coding table directly from CSV, while determining coded arcs' IDs.
common_id_field = MHN.route_systems[MHN.hwyproj][1]  # 'TIPID'
project_arcs = {}

coding_fields = (
    common_id_field, 'ACTION_CODE', 'REP_ANODE', 'REP_BNODE', 'NEW_TYPE1', 'NEW_TYPE2',
    'NEW_THRULANEWIDTH1', 'NEW_THRULANEWIDTH2', 'NEW_THRULANES1', 'NEW_THRULANES2',
    'NEW_POSTEDSPEED1', 'NEW_POSTEDSPEED2', 'NEW_AMPM1', 'NEW_AMPM2', 'NEW_MODES',
    'NEW_TOLLDOLLARS', 'NEW_DIRECTIONS', 'ADD_PARKLANES1', 'ADD_PARKLANES2',
    'ADD_SIGIC', 'ADD_CLTL', 'ADD_RRGRADECROSS', 'TOD', 'ABB'
)

with arcpy.da.InsertCursor(temp_coding_table, coding_fields) as cursor:
    raw_coding = open(projects_csv, 'r')
    coding = csv.DictReader(raw_coding)
    for arc_attr_dict in coding:
        project_id = arc_attr_dict[common_id_field]
        arc_id = arc_attr_dict['ABB']
        if project_id not in project_arcs.keys():
            project_arcs[project_id] = [arc_id]
        else:
            project_arcs[project_id].append(arc_id)
        arc_attr = [arc_attr_dict[field] for field in coding_fields]
        cursor.insertRow(arc_attr)
    raw_coding.close()
    os.remove(projects_csv)

# Generate project features one at a time.
for project_id in project_arcs.keys():

    # Get project completion year, if already in MHN.
    completion_year = None
    existing_project_query = '"{0}" = \'{1}\''.format(common_id_field, project_id)
    existing_project_lyr = MHN.make_skinny_table_view(MHN.hwyproj, 'existing_project_lyr', ['COMPLETION_YEAR'], existing_project_query)
    existing_project_count = int(arcpy.GetCount_management(existing_project_lyr).getOutput(0))
    if existing_project_count > 0:
        completion_year = [attr[0] for attr in arcpy.da.SearchCursor(existing_project_lyr, ['COMPLETION_YEAR'])][0]

    # Dissolve project arcs into a single project feature, and append to temp FC.
    project_arc_ids = project_arcs[project_id]
    project_arcs_lyr = 'project_arcs_lyr'
    project_arcs_query = '"ABB" IN (\'' + "','".join(project_arc_ids) + "')"
    arcpy.MakeFeatureLayer_management(MHN.arc, project_arcs_lyr, project_arcs_query)
    project_dissolved = '/'.join((MHN.mem, 'project_dissolved'))
    arcpy.Dissolve_management(project_arcs_lyr, project_dissolved)
    arcpy.AddField_management(project_dissolved, common_id_field, 'TEXT', field_length=10)
    arcpy.AddField_management(project_dissolved, 'COMPLETION_YEAR', 'SHORT')  # Make types/lengths dynamic?
    with arcpy.da.UpdateCursor(project_dissolved, [common_id_field, 'COMPLETION_YEAR']) as cursor:
        for row in cursor:
            row[0] = project_id
            if completion_year:
                row[1] = completion_year
            cursor.updateRow(row)
    arcpy.Append_management(project_dissolved, temp_projects_fc, 'NO_TEST')


# -----------------------------------------------------------------------------
#  Merge updated projects with unaffected projects.
# -----------------------------------------------------------------------------
# Copy features and coding of unaffected projects in MHN.
unaffected_projects_query = '"{0}" NOT IN (\''.format(common_id_field) + "','".join(project_arcs.keys()) + "')"

unaffected_projects_lyr = 'unaffected_projects_lyr'
arcpy.MakeFeatureLayer_management(MHN.hwyproj, unaffected_projects_lyr, unaffected_projects_query)

unaffected_coding_view = 'unaffected_coding_view'
arcpy.MakeTableView_management(MHN.route_systems[MHN.hwyproj][0], unaffected_coding_view, unaffected_projects_query)

# Append features/coding from temp FC/table.
updated_projects_fc = '/'.join((MHN.mem, 'updated_projects_fc'))
arcpy.Merge_management((unaffected_projects_lyr, temp_projects_fc), updated_projects_fc)

updated_coding_table = '/'.join((MHN.mem, 'updated_coding_table'))
arcpy.Merge_management((unaffected_coding_view, temp_coding_table), updated_coding_table)


# -----------------------------------------------------------------------------
#  Commit the changes only after everything else has run successfully.
# -----------------------------------------------------------------------------
backup_gdb = MHN.gdb[:-4] + '_' + MHN.timestamp() + '.gdb'
arcpy.Copy_management(MHN.gdb, backup_gdb)
arcpy.AddMessage('{0}Geodatabase temporarily backed up to {1}. (If import fails for any reason, replace {2} with this.)'.format('\n',backup_gdb, MHN.gdb))

arcpy.AddMessage('{0}Saving changes to disk...'.format('\n'))

# Replace hwyproj feature class:
arcpy.AddMessage('-- ' + MHN.hwyproj + '...')
arcpy.TruncateTable_management(MHN.hwyproj)
arcpy.Delete_management(MHN.hwyproj)
arcpy.CopyFeatures_management(updated_projects_fc, MHN.hwyproj)
arcpy.Delete_management(updated_projects_fc)

# Replace hwyproj_coding table:
coding_table = MHN.route_systems[MHN.hwyproj][0]
arcpy.AddMessage('-- ' + coding_table + '...')
arcpy.TruncateTable_management(coding_table)
arcpy.Delete_management(coding_table)
coding_table_path = MHN.break_path(coding_table)
arcpy.CreateTable_management(coding_table_path['dir'], coding_table_path['name'], updated_coding_table)
arcpy.Append_management(updated_coding_table, coding_table, 'TEST')
arcpy.Delete_management(updated_coding_table)

# Rebuild relationship classes.
arcpy.AddMessage('{0}Rebuilding relationship classes...'.format('\n'))
hwyproj_name = MHN.break_path(MHN.hwyproj)['name']
coding_table_name = MHN.break_path(coding_table)['name']
rel_arcs = MHN.gdb + '/rel_arcs_to_' + coding_table_name
rel_sys = MHN.gdb + '/rel_' + coding_table_name.rsplit('_',1)[0] + '_to_' + coding_table_name.rsplit('_',1)[1]
arcpy.CreateRelationshipClass_management(MHN.arc, coding_table, rel_arcs, 'SIMPLE', coding_table_name, MHN.arc_name, 'NONE', 'ONE_TO_MANY', 'NONE', 'ABB', 'ABB')
arcpy.CreateRelationshipClass_management(MHN.hwyproj, coding_table, rel_sys, 'COMPOSITE', coding_table_name, hwyproj_name, 'FORWARD', 'ONE_TO_MANY', 'NONE', common_id_field, common_id_field)

# Clean up.
arcpy.Compact_management(MHN.gdb)
arcpy.Delete_management(MHN.mem)
arcpy.Delete_management(backup_gdb)
arcpy.AddMessage('{0}Highway project coding successfully imported!{0}'.format('\n'))
