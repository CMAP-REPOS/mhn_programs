#!/usr/bin/env python
'''
    update_mhn_base_year.py
    Author: npeterson
    Revised: 9/5/17
    ---------------------------------------------------------------------------
    Build the MHN to its coded state for a new base year, and save the future
    arcs and nodes in a specified GDB. Copy all highway project coding with
    completion years later than new base year. Also copy future bus coding.

    After running this tool, bus itineraries should be imported from scratch,
    into the new GDB, using the Import GTFS Bus Routes tool. The Incorporate
    Edits tool should also be run to rebuild all of the relationship classes
    and ensure nodes, highway project geometries, etc. are correct.

'''
import os
import sys
import arcpy

sys.path.append(os.path.abspath(os.path.join(sys.path[0], '..')))  # Add mhn_programs dir to path, so MHN.py can be imported
from MHN import MasterHighwayNetwork  # Custom class for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
mhn_gdb_path = arcpy.GetParameterAsText(0)  # Input MHN gdb path
in_mhn = MasterHighwayNetwork(mhn_gdb_path)  # Initialize input MHN object

# Get the build year, and verify that it can actually be built.
build_year = arcpy.GetParameter(1)  # Integer, default = 2015
if build_year <= in_mhn.base_year:
    in_mhn.die(('The MHN currently has a base year of {0}. Try a year later than {0}.').format(in_mhn.base_year))

# Get the output GDB and feature dataset, and create if non-existent.
gdb_path = arcpy.GetParameterAsText(2)  # Folder, no default
gdb_name = arcpy.GetParameterAsText(3)  # String, no default
if not gdb_name.endswith('.gdb'):
    gdb_name = '{}.gdb'.format(gdb_name)
out_gdb = os.path.join(gdb_path, gdb_name)  # Output MHN gdb path

# Other parameters
sas1_name = 'process_highway_coding'  # Also used by export_future_network.py


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = os.path.join(in_mhn.temp_dir, '{}.log'.format(sas1_name))
sas1_lst = os.path.join(in_mhn.temp_dir, '{}.lst'.format(sas1_name))
year_csv = os.path.join(in_mhn.temp_dir, 'year.csv')
transact_csv = os.path.join(in_mhn.temp_dir, 'transact.csv')
network_csv = os.path.join(in_mhn.temp_dir, 'network.csv')
update_link_csv = os.path.join(in_mhn.temp_dir, 'update_link.csv')  # SAS output
flag_node_csv = os.path.join(in_mhn.temp_dir, 'flag_node.csv')      # SAS output


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
in_mhn.delete_if_exists(sas1_log)
in_mhn.delete_if_exists(sas1_lst)
in_mhn.delete_if_exists(year_csv)
in_mhn.delete_if_exists(transact_csv)
in_mhn.delete_if_exists(network_csv)
in_mhn.delete_if_exists(update_link_csv)
in_mhn.delete_if_exists(flag_node_csv)


# -----------------------------------------------------------------------------
#  Copy input MHN GDB to output location for modification.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nInitializing {}...'.format(out_gdb))
if arcpy.Exists(out_gdb):
    arcpy.Delete_management(out_gdb)
arcpy.Copy_management(in_mhn.gdb, out_gdb)
out_mhn = MasterHighwayNetwork(out_gdb)  # Initialize output MHN object

# Remove relationship classes
rc_names = [
    'rel_arcs_to_bus_base_itin',
    'rel_arcs_to_bus_current_itin',
    'rel_arcs_to_bus_future_itin',
    'rel_arcs_to_hwyproj_coding',
    'rel_bus_base_to_itin',
    'rel_bus_current_to_itin',
    'rel_bus_future_to_itin',
    'rel_hwyproj_to_coding',
    'rel_nodes_to_parknride',
]
for rc_name in rc_names:
    rc = os.path.join(out_mhn.gdb, rc_name)
    arcpy.Delete_management(rc)


# -----------------------------------------------------------------------------
#  Write data relevant to specified year and pass to SAS for processing.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nPreparing {} network attributes...'.format(build_year))

# Export coding for highway projects completed by scenario year.
hwyproj_id_field = in_mhn.route_systems[in_mhn.hwyproj][1]
year_attr = [hwyproj_id_field,'COMPLETION_YEAR']
year_query = '"COMPLETION_YEAR" <= {}'.format(build_year)
year_view = in_mhn.make_skinny_table_view(in_mhn.hwyproj, 'year_view', year_attr, year_query)
in_mhn.write_attribute_csv(year_view, year_csv, year_attr)
hwy_projects = in_mhn.make_attribute_dict(year_view, hwyproj_id_field, attr_list=[])
arcpy.Delete_management(year_view)

transact_attr = [hwyproj_id_field,'ACTION_CODE','NEW_DIRECTIONS','NEW_TYPE1','NEW_TYPE2','NEW_AMPM1','NEW_AMPM2','NEW_POSTEDSPEED1',
                 'NEW_POSTEDSPEED2','NEW_THRULANES1','NEW_THRULANES2','NEW_THRULANEWIDTH1','NEW_THRULANEWIDTH2','ADD_PARKLANES1',
                 'ADD_PARKLANES2','ADD_SIGIC','ADD_CLTL','ADD_RRGRADECROSS','NEW_TOLLDOLLARS','NEW_MODES','TOD','ABB','REP_ANODE','REP_BNODE']
transact_query = '''"{0}" IN ('{1}')'''.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in hwy_projects)))
transact_view = in_mhn.make_skinny_table_view(in_mhn.route_systems[in_mhn.hwyproj][0], 'transact_view', transact_attr, transact_query)
in_mhn.write_attribute_csv(transact_view, transact_csv, transact_attr)
hwy_abb = in_mhn.make_attribute_dict(transact_view, 'ABB', attr_list=[])
arcpy.Delete_management(transact_view)

# Export arc & node attributes of all baselinks and skeletons used in
# projects completed by scenario year.
network_attr = ['ANODE','BNODE','ABB','DIRECTIONS','TYPE1','TYPE2','AMPM1','AMPM2','POSTEDSPEED1','POSTEDSPEED2',
                'THRULANES1','THRULANES2','THRULANEWIDTH1','THRULANEWIDTH2','PARKLANES1','PARKLANES2','BASELINK',
                'SIGIC','CLTL','RRGRADECROSS','TOLLDOLLARS','MODES','MILES']
network_query = '''"BASELINK" = '1' OR "ABB" IN ('{}')'''.format("','".join((abb for abb in hwy_abb if abb[-1] != '1')))
network_lyr = in_mhn.make_skinny_feature_layer(in_mhn.arc, 'network_lyr', network_attr, network_query)
in_mhn.write_attribute_csv(network_lyr, network_csv, network_attr)

# Process attribute tables with export_future_network_2.sas.
sas1_sas = os.path.join(in_mhn.util_dir, '{}.sas'.format(sas1_name))
sas1_args = [network_csv, transact_csv, year_csv, update_link_csv, flag_node_csv, build_year, in_mhn.max_poe, in_mhn.base_year]
in_mhn.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    in_mhn.die('{} did not run!'.format(sas1_sas))
else:
    #os.remove(sas1_log)
    in_mhn.delete_if_exists(sas1_lst)
    #os.remove(year_csv)
    #os.remove(transact_csv)
    #os.remove(network_csv)


# -----------------------------------------------------------------------------
#  Update links/nodes from SAS output in output GDB.
# -----------------------------------------------------------------------------
# Build updated links in memory.
arcpy.AddMessage('\nUpdating links to {} conditions...'.format(build_year))

update_link_dict = {}
with open(update_link_csv, 'r') as reader:
    firstline = True
    for row in reader:
        if firstline:
            firstline = False
            continue
        attr = row.strip().split(',')
        abb = attr[0]
        update_link_dict[abb] = attr

deleted_abb = set()
changed_abb = {}

update_link_attr = ['ABB','DIRECTIONS','TYPE1','TYPE2','AMPM1','AMPM2','POSTEDSPEED1','POSTEDSPEED2',
                    'THRULANES1','THRULANES2','THRULANEWIDTH1','THRULANEWIDTH2','PARKLANES1','PARKLANES2',
                    'BASELINK','SIGIC','CLTL','TOLLDOLLARS','MODES']
with arcpy.da.UpdateCursor(out_mhn.arc, update_link_attr) as c:
    abb_index = update_link_attr.index('ABB')
    baselink_index = update_link_attr.index('BASELINK')
    for r in c:
        abb = r[abb_index]  # Not updated with BASELINK changes by SAS script
        if abb in update_link_dict:
            baselink = update_link_dict[abb][baselink_index]
            action = update_link_dict[abb][-1]  # ACTION_CODE is final column
            if action == '3':
                deleted_abb.add(abb)
                c.deleteRow()
            else:
                new_abb = abb[:-1] + baselink
                if new_abb != abb:
                    changed_abb[abb] = new_abb
                    update_link_dict[abb][0] = new_abb
                c.updateRow(update_link_dict[abb][:-1])  # Omit ACTION_CODE

# Remove hwyproj features and coding for already-built highway projects
arcpy.AddMessage('\nRemoving highway projects built by {}...'.format(build_year))
built_tipids = set(r[0] for r in arcpy.da.SearchCursor(out_mhn.hwyproj, ['TIPID', 'COMPLETION_YEAR'], year_query))

with arcpy.da.UpdateCursor(out_mhn.hwyproj, ['TIPID']) as c:
    for r in c:
        tipid = r[0]
        if tipid in built_tipids:
            c.deleteRow()

coding = out_mhn.route_systems[out_mhn.hwyproj][0]
with arcpy.da.UpdateCursor(coding, ['TIPID']) as c:
    for r in c:
        tipid = r[0]
        if tipid in built_tipids:
            c.deleteRow()

# Update coding/itinerary ABB values as necessary.
arcpy.AddMessage('\nUpdating changed ABB values in highway project coding and bus itineraries...')
tables = [v[0] for v in out_mhn.route_systems.itervalues()]
for table in tables:
    with arcpy.da.UpdateCursor(table, ['ABB']) as c:
        for r in c:
            abb = r[0]
            if abb in deleted_abb:
                r[0] = ' '
            elif abb in changed_abb:
                r[0] = changed_abb[abb]
            c.updateRow(r)

# Identify any highway projects whose coding has been invalidated by base year update.
out_coding_table = out_mhn.route_systems[out_mhn.hwyproj][0]
bad_coding_sql = ''' "ABB" = ' ' '''
bad_coding = {r[0]: [] for r in arcpy.da.SearchCursor(out_coding_table, ['TIPID', 'ABB'], bad_coding_sql)}

if bad_coding:
    # Identify the specific links with bad coding
    in_coding_table = in_mhn.route_systems[in_mhn.hwyproj][0]
    bad_coding_sql_2 = ''' "TIPID" IN ('{}') '''.format("','".join(t for t in bad_coding))
    with arcpy.da.SearchCursor(in_coding_table, ['TIPID', 'ABB'], bad_coding_sql_2) as c:
        for tipid, abb in c:
            if abb in deleted_abb:
                bad_coding[tipid].append(abb)

    # Report TIPIDs/ABBs with invalidated coding
    arcpy.AddWarning(
        '\nThe highway project coding for the following TIPIDs includes links '
        'that will not exist after the base year update. Export the projects\' '
        'coding from the *input* MHN geodatabase, modify it to move the bad '
        'coding onto the appropriate replacement links, import it into the '
        '*output* geodatabase, then run the Incorporate Edits tool (also on '
        'the output geodatabase). Without updating this coding, the output '
        'geodatabase will remain unusable.'
    )
    for tipid in sorted(bad_coding):
        arcpy.AddWarning('  -- TIPID {0}: ABB {1}'.format(tipid, ', '.join(bad_coding[tipid])))
    arcpy.AddWarning(' ')

else:
    #  Clean up
    os.remove(update_link_csv)
    os.remove(flag_node_csv)
    arcpy.Delete_management(in_mhn.mem)
    arcpy.AddMessage('\nAll done!\n')
    arcpy.AddWarning((
        'IMPORTANT: The Incorporate Edits tool *must* be run on {} to make it '
        'usable. It is also recommended that the base/current bus itineraries '
        'be imported from scratch. Do not forget to change the MHN.base_year '
        'variable in MHN.py once you are satisfied with the updated network.'
        '\n').format(out_mhn.gdb))
