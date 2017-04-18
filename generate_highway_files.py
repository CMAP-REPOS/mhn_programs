#!/usr/bin/env python
'''
    generate_highway_files.py
    Author: npeterson
    Revised: 5/11/17
    ---------------------------------------------------------------------------
    This program creates the Emme highway batchin files needed to model a
    scenario network. The scenario, output path and CT-RAMP flag are passed to
    the script as arguments from the tool. Creates l1, l2, n1, n2 files for all
    TOD periods, as well as highway.linkshape.

'''
import os
import sys
import arcpy
from operator import itemgetter
from MHN import MasterHighwayNetwork  # Custom class for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
mhn_gdb_path = arcpy.GetParameterAsText(0)          # MHN geodatabase
MHN = MasterHighwayNetwork(mhn_gdb_path)
scen_list = arcpy.GetParameterAsText(1).split(';')  # Semicolon-delimited string, e.g. '100;200'
root_path = arcpy.GetParameterAsText(2)             # String, no default
create_tollsys_flag = arcpy.GetParameter(3)         # Boolean, default = True
abm_output = arcpy.GetParameter(4)                  # Boolean, default = False
if os.path.exists(root_path):
    hwy_path = MHN.ensure_dir(os.path.join(root_path, 'highway'))
else:
    MHN.die("{0} doesn't exist!".format(root_path))
sas1_name = 'coding_overlap'
sas2_name = 'generate_highway_files_2'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
overlap_year_csv = os.path.join(MHN.temp_dir, 'overlap_year.csv')
overlap_transact_csv = os.path.join(MHN.temp_dir, 'overlap_transact.csv')
overlap_network_csv = os.path.join(MHN.temp_dir, 'overlap_network.csv')
sas1_log = os.path.join(MHN.temp_dir, '{0}.log'.format(sas1_name))
sas1_lst = os.path.join(MHN.temp_dir, '{0}.lst'.format(sas1_name))
# sas2_log & sas2_lst are scenario-dependent, defined below


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(overlap_year_csv)
MHN.delete_if_exists(overlap_transact_csv)
MHN.delete_if_exists(overlap_network_csv)
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)


# -----------------------------------------------------------------------------
#  Write tollsys.flag file, if desired.
# -----------------------------------------------------------------------------
if create_tollsys_flag or abm_output:
    arcpy.AddMessage('\nGenerating tollsys.flag file...')
    tollsys_flag = os.path.join(hwy_path, 'tollsys.flag')
    MHN.write_arc_flag_file(tollsys_flag, '"TOLLSYS" = 1')


# -----------------------------------------------------------------------------
# Generate any scenario-independent, ABM-specific files, if desired.
# -----------------------------------------------------------------------------
if abm_output:

    # hwy_node_zones.csv
    arcpy.AddMessage('\nGenerating hwy_node_zones.csv file...')
    def generate_node_zones_csv(out_csv):
        ''' Write a CSV listing the zone and subzone each node falls in. '''
        out_attr = ['NODE', MHN.zone_attr, MHN.subzone_attr]
        node_lyr = 'node_lyr'
        MHN.make_skinny_table_view(MHN.node, node_lyr, out_attr)
        with open(out_csv, 'wt') as w:
            w.write('node,zone09,subzone09\n')
            with arcpy.da.SearchCursor(node_lyr, out_attr, sql_clause=(None, 'ORDER BY NODE')) as c:
                for r in c:
                    w.write('{0},{1},{2}\n'.format(*r))
        return out_csv
    node_zones_csv = os.path.join(hwy_path, 'hwy_node_zones.csv')
    generate_node_zones_csv(node_zones_csv)


# -----------------------------------------------------------------------------
#  Check for hwyproj_coding lane conflicts/reductions in future networks.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nChecking for conflicting highway project coding (i.e. lane reductions) and missing project years...\n')
hwyproj_id_field = MHN.route_systems[MHN.hwyproj][1]

# Export projects with valid completion years.
overlap_year_attr = [hwyproj_id_field, 'COMPLETION_YEAR']
overlap_year_query = '"COMPLETION_YEAR" NOT IN (0,9999)'
overlap_year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'overlap_year_view', overlap_year_attr, overlap_year_query)
MHN.write_attribute_csv(overlap_year_view, overlap_year_csv, overlap_year_attr)
overlap_projects = [r[0] for r in arcpy.da.SearchCursor(overlap_year_view, [hwyproj_id_field])]
arcpy.Delete_management(overlap_year_view)

# Export coding for valid projects.
overlap_transact_attr = [
    hwyproj_id_field, 'ACTION_CODE', 'NEW_DIRECTIONS', 'NEW_TYPE1', 'NEW_TYPE2', 'NEW_AMPM1', 'NEW_AMPM2', 'NEW_POSTEDSPEED1',
    'NEW_POSTEDSPEED2', 'NEW_THRULANES1', 'NEW_THRULANES2', 'NEW_THRULANEWIDTH1', 'NEW_THRULANEWIDTH2', 'ADD_PARKLANES1',
    'ADD_PARKLANES2', 'ADD_SIGIC', 'ADD_CLTL', 'ADD_RRGRADECROSS', 'NEW_TOLLDOLLARS', 'NEW_MODES', 'ABB', 'REP_ANODE', 'REP_BNODE'
]
overlap_transact_query = ''' "{0}" IN ('{1}') '''.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in overlap_projects)))
overlap_transact_view = MHN.make_skinny_table_view(MHN.route_systems[MHN.hwyproj][0], 'overlap_transact_view', overlap_transact_attr, overlap_transact_query)
MHN.write_attribute_csv(overlap_transact_view, overlap_transact_csv, overlap_transact_attr)
overlap_project_arcs = [r[0] for r in arcpy.da.SearchCursor(overlap_transact_view, ['ABB'])]
arcpy.Delete_management(overlap_transact_view)

# Export base year arc attributes.
overlap_network_attr = [
    'ANODE', 'BNODE', 'ABB', 'DIRECTIONS', 'TYPE1', 'TYPE2', 'AMPM1', 'AMPM2', 'POSTEDSPEED1', 'POSTEDSPEED2',
    'THRULANES1', 'THRULANES2', 'THRULANEWIDTH1', 'THRULANEWIDTH2', 'PARKLANES1', 'PARKLANES2', 'SIGIC',
    'CLTL', 'RRGRADECROSS', 'TOLLDOLLARS', 'MODES', 'MILES'
]
overlap_network_query = ''' "BASELINK" = '1' OR "ABB" IN ('{0}') '''.format("','".join((abb for abb in overlap_project_arcs if abb[-1] != '1')))
overlap_network_view = MHN.make_skinny_table_view(MHN.arc, 'overlap_network_view', overlap_network_attr, overlap_network_query)
MHN.write_attribute_csv(overlap_network_view, overlap_network_csv, overlap_network_attr)
arcpy.Delete_management(overlap_network_view)

# Process attribute tables with coding_overlap.sas.
sas1_sas = ''.join((MHN.prog_dir, '/', sas1_name, '.sas'))
sas1_args = [MHN.temp_dir]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{0} did not run!'.format(sas1_sas))
elif os.path.exists(sas1_lst):
    MHN.die('Please review {0} for potential coding errors.'.format(sas1_lst))
else:
    os.remove(sas1_log)
    os.remove(overlap_year_csv)
    os.remove(overlap_transact_csv)
    os.remove(overlap_network_csv)


# -----------------------------------------------------------------------------
#  Write data relevant to specified scenario and pass to SAS for processing.
# -----------------------------------------------------------------------------
for scen in scen_list:
    # Set scenario-specific parameters.
    scen_year = MHN.scenario_years[scen]
    scen_path = MHN.ensure_dir(os.path.join(hwy_path, scen))
    sas2_log = os.path.join(hwy_path, '{0}_{1}.log'.format(sas2_name, scen))
    sas2_lst = os.path.join(hwy_path, '{0}_{1}.lst'.format(sas2_name, scen))
    hwy_year_csv = os.path.join(scen_path, 'year.csv')
    hwy_transact_csv = os.path.join(scen_path, 'transact.csv')
    hwy_network_csv = os.path.join(scen_path, 'network.csv')
    hwy_nodes_csv = os.path.join(scen_path, 'nodes.csv')

    MHN.delete_if_exists(sas2_log)
    MHN.delete_if_exists(sas2_lst)
    MHN.delete_if_exists(hwy_year_csv)
    MHN.delete_if_exists(hwy_transact_csv)
    MHN.delete_if_exists(hwy_network_csv)
    MHN.delete_if_exists(hwy_nodes_csv)

    arcpy.AddMessage('Generating Scenario {0} ({1}) highway files...'.format(scen, scen_year))

    # Export coding for highway projects completed by scenario year.
    hwy_year_attr = [hwyproj_id_field, 'COMPLETION_YEAR']
    hwy_year_query = '"COMPLETION_YEAR" <= {0}'.format(scen_year)
    hwy_year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'hwy_year_view', hwy_year_attr, hwy_year_query)
    MHN.write_attribute_csv(hwy_year_view, hwy_year_csv, hwy_year_attr)
    hwy_projects = [r for r in arcpy.da.SearchCursor(hwy_year_view, [hwyproj_id_field, 'COMPLETION_YEAR'])]
    arcpy.Delete_management(hwy_year_view)

    hwy_transact_attr = [
        hwyproj_id_field, 'ACTION_CODE', 'NEW_DIRECTIONS', 'NEW_TYPE1', 'NEW_TYPE2', 'NEW_AMPM1', 'NEW_AMPM2', 'NEW_POSTEDSPEED1',
        'NEW_POSTEDSPEED2', 'NEW_THRULANES1', 'NEW_THRULANES2', 'NEW_THRULANEWIDTH1', 'NEW_THRULANEWIDTH2', 'ADD_PARKLANES1',
        'ADD_PARKLANES2', 'ADD_SIGIC', 'ADD_CLTL', 'ADD_RRGRADECROSS', 'NEW_TOLLDOLLARS', 'NEW_MODES', 'TOD', 'ABB', 'REP_ANODE', 'REP_BNODE'
    ]
    hwy_transact_query = ''' "{0}" IN ('{1}') '''.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id, comp_year in hwy_projects)))
    hwy_transact_view = MHN.make_skinny_table_view(MHN.route_systems[MHN.hwyproj][0], 'hwy_transact_view', hwy_transact_attr, hwy_transact_query)
    MHN.write_attribute_csv(hwy_transact_view, hwy_transact_csv, hwy_transact_attr)
    hwy_abb = [r[0] for r in arcpy.da.SearchCursor(hwy_transact_view, ['ABB'])]
    arcpy.Delete_management(hwy_transact_view)

    # Export arc & node attributes of all baselinks and skeletons used in
    # projects completed by scenario year.
    hwy_network_attr = [
        'ANODE', 'BNODE', 'ABB', 'DIRECTIONS', 'TYPE1', 'TYPE2', 'AMPM1', 'AMPM2', 'POSTEDSPEED1', 'POSTEDSPEED2',
        'THRULANES1', 'THRULANES2', 'THRULANEWIDTH1', 'THRULANEWIDTH2', 'PARKLANES1', 'PARKLANES2', 'PARKRES1', 'PARKRES2',
        'SIGIC', 'CLTL', 'RRGRADECROSS', 'TOLLDOLLARS', 'MODES', 'CHIBLVD', 'TRUCKRES', 'VCLEARANCE', 'MILES'
        ]
    hwy_network_query = ''' "BASELINK" = '1' OR "ABB" IN ('{0}') '''.format("','".join((abb for abb in hwy_abb if abb[-1] != '1')))
    hwy_network_lyr = MHN.make_skinny_feature_layer(MHN.arc, 'hwy_network_lyr', hwy_network_attr, hwy_network_query)
    MHN.write_attribute_csv(hwy_network_lyr, hwy_network_csv, hwy_network_attr)
    hwy_abb_2 = [r[0] for r in arcpy.da.SearchCursor(hwy_network_lyr, ['ABB'])]

    hwy_anodes = [abb.split('-')[0] for abb in hwy_abb_2]
    hwy_bnodes = [abb.split('-')[1] for abb in hwy_abb_2]
    hwy_nodes_list = list(set(hwy_anodes).union(set(hwy_bnodes)))
    hwy_nodes_attr = ['NODE', 'POINT_X', 'POINT_Y', MHN.zone_attr, MHN.capzone_attr]
    hwy_nodes_query = '"NODE" IN ({0})'.format(','.join(hwy_nodes_list))
    hwy_nodes_view = MHN.make_skinny_table_view(MHN.node, 'hwy_nodes_view', hwy_nodes_attr, hwy_nodes_query)
    MHN.write_attribute_csv(hwy_nodes_view, hwy_nodes_csv, hwy_nodes_attr)
    arcpy.Delete_management(hwy_nodes_view)

    # Process attribute tables with generate_highway_files_2.sas.
    sas2_sas = os.path.join(MHN.prog_dir, '{0}.sas'.format(sas2_name))
    sas2_args = [hwy_path, scen, MHN.max_poe, MHN.base_year, int(abm_output)]
    MHN.submit_sas(sas2_sas, sas2_log, sas2_lst, sas2_args)
    if not os.path.exists(sas2_log):
        MHN.die('{0} did not run!'.format(sas2_sas))
    elif 'errorlevel=' in open(sas2_lst).read():
        MHN.die('Errors during SAS processing. Please see {0}.'.format(sas2_log))
    else:
        os.remove(sas2_log)
        # NOTE: Do not delete sas2_lst: leave for reference.
        os.remove(hwy_year_csv)
        os.remove(hwy_transact_csv)
        os.remove(hwy_network_csv)
        os.remove(hwy_nodes_csv)
        arcpy.AddMessage('-- Scenario {0} l1, l2, n1, n2 files generated successfully.'.format(scen))
        if abm_output:
            arcpy.AddMessage('-- Scenario {0} ABM toll file generated successfully.'.format(scen))

    # Calculate scenario mainline links' AM Peak lane-miles.
    scen_ampeak_l1 = os.path.join(scen_path, '{0}03.l1'.format(scen))
    mainline_lanemiles = {}
    with open(scen_ampeak_l1, 'r') as l1:
        for r in l1:
            attr = r.split()
            if attr[0] == 'a'and attr[7] in ('2', '4'):  # Ignore comments, t-record and non-mainline links
                ab = '{0}-{1}'.format(attr[1], attr[2])
                lanemiles = float(attr[3]) * int(attr[6])
                mainline_lanemiles[ab] = lanemiles

    # Create mcp_stats.txt.
    scen_mcp_tipids = {}
    scen_mcp_query = ''' "COMPLETION_YEAR" <= {0} AND "MCP_ID" IS NOT NULL '''.format(scen_year)
    with arcpy.da.SearchCursor(MHN.hwyproj, ['MCP_ID', hwyproj_id_field], scen_mcp_query) as c:
        for mcp_id, tipid in c:
            if mcp_id not in scen_mcp_tipids:
                scen_mcp_tipids[mcp_id] = set([tipid])
            else:
                scen_mcp_tipids[mcp_id].add(tipid)

    mcp_stats = os.path.join(scen_path, 'mcp_stats.csv')
    with open(mcp_stats, 'w') as w:
        w.write('MCP_ID,MCP_NAME,MAINLINE_LANEMILES\n')
        for mcp_id in sorted(scen_mcp_tipids.keys()):
            mcp_query = ''' "{0}" IN ('{1}') '''.format(hwyproj_id_field, "','".join(scen_mcp_tipids[mcp_id]))
            mcp_ab = set((r[0].rsplit('-', 1)[0] for r in arcpy.da.SearchCursor(MHN.route_systems[MHN.hwyproj][0], ['ABB'], mcp_query)))
            mcp_lanemiles = sum((mainline_lanemiles[ab] for ab in mcp_ab if ab in mainline_lanemiles))
            w.write('{0},{1},{2}\n'.format(mcp_id, MHN.mcps[mcp_id], mcp_lanemiles))

    arcpy.AddMessage('-- Scenario {0} mcp_stats.csv generated successfully.'.format(scen))

    # Create rsp_stats.txt.
    scen_rsp_tipids = {}
    scen_rsp_query = ''' "COMPLETION_YEAR" <= {0} AND "RSP_ID" IS NOT NULL '''.format(scen_year)
    with arcpy.da.SearchCursor(MHN.hwyproj, ['RSP_ID', hwyproj_id_field], scen_rsp_query) as c:
        for rsp_id, tipid in c:
            if rsp_id not in scen_rsp_tipids:
                scen_rsp_tipids[rsp_id] = set([tipid])
            else:
                scen_rsp_tipids[rsp_id].add(tipid)

    rsp_stats = os.path.join(scen_path, 'rsp_stats.csv')
    with open(rsp_stats, 'w') as w:
        w.write('RSP_ID,RSP_NAME,MAINLINE_LANEMILES\n')
        for rsp_id in sorted(scen_rsp_tipids.keys()):
            rsp_query = ''' "{0}" IN ('{1}') '''.format(hwyproj_id_field, "','".join(scen_rsp_tipids[rsp_id]))
            rsp_ab = set((r[0].rsplit('-', 1)[0] for r in arcpy.da.SearchCursor(MHN.route_systems[MHN.hwyproj][0], ['ABB'], rsp_query)))
            rsp_lanemiles = sum((mainline_lanemiles[ab] for ab in rsp_ab if ab in mainline_lanemiles))
            w.write('{0},{1},{2}\n'.format(rsp_id, MHN.rsps[rsp_id], rsp_lanemiles))

    arcpy.AddMessage('-- Scenario {0} rsp_stats.csv generated successfully.'.format(scen))

    # Create linkshape.in.
    def generate_linkshape(arcs, output_dir):
        linkshape = os.path.join(output_dir, 'highway.linkshape')
        w = open(linkshape, 'w')
        w.write('c HIGHWAY LINK SHAPE FILE FOR SCENARIO {0}\n'.format(scen))
        w.write('c {0}\n'.format(MHN.timestamp('%d%b%y').upper()))
        w.write('t linkvertices\n')

        def write_vertices(fc, writer, reversed=False):
            with arcpy.da.SearchCursor(fc, ['SHAPE@', 'ANODE', 'BNODE']) as cursor:
                for row in cursor:
                    arc = row[0]
                    if not reversed:
                        fnode = str(row[1])
                        tnode = str(row[2])
                    else:
                        fnode = str(row[2])  # ANODE now references to-node
                        tnode = str(row[1])  # BNODE now references from-node
                    writer.write(' '.join(['r', fnode, tnode]) + '\n')
                    n = 0  # Before for-loop, will not be reset if an arc is multi-part for some reason
                    for part in arc:
                        vertex = next(part)
                        while vertex:
                            n += 1
                            writer.write(' '.join(['a', fnode, tnode, str(n), str(vertex.X), str(vertex.Y)]) + '\n')
                            vertex = next(part)
                            if not vertex:
                                vertex = next(part)
            return None

        arcs_mem = os.path.join(MHN.mem, 'arcs')
        arcpy.CopyFeatures_management(arcs, arcs_mem)
        write_vertices(arcs_mem, w)

        arcs_mem_flipped = os.path.join(MHN.mem, 'arcs_flipped')
        arcs_2dir_lyr = 'arcs_2dir'
        arcpy.MakeFeatureLayer_management(arcs_mem, arcs_2dir_lyr, ''' "DIRECTIONS" <> '1' ''')
        arcpy.CopyFeatures_management(arcs_2dir_lyr, arcs_mem_flipped)
        arcpy.FlipLine_edit(arcs_mem_flipped)
        write_vertices(arcs_mem_flipped, w, reversed=True)

        w.close()
        arcpy.Delete_management(arcs_mem)
        arcpy.Delete_management(arcs_mem_flipped)
        return linkshape

    scen_linkshape = generate_linkshape(hwy_network_lyr, scen_path)
    arcpy.Delete_management(hwy_network_lyr)
    arcpy.AddMessage('-- Scenario {0} highway.linkshape generated successfully.\n'.format(scen))
