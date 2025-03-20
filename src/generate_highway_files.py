#!/usr/bin/env python
'''
    generate_highway_files.py
    Author: npeterson
    Revised: 1/25/22
    ---------------------------------------------------------------------------
    This program creates the Emme highway batchin files needed to model a
    scenario network. The scenario, output path and CT-RAMP flag are passed to
    the script as arguments from the tool. Creates l1, l2, n1, n2 files for all
    TOD periods, as well as highway.linkshape.

'''
import os
import arcpy
from operator import itemgetter
import numpy as np
import pandas as pd
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
rsp_eval = arcpy.GetParameter(5)                    # Boolean, default = False
rsp_column = arcpy.GetParameterAsText(6)            # String, default = None
rsp_number = arcpy.GetParameterAsText(7)            # String, default = None
excl_roadway_csv = arcpy.GetParameterAsText(8)      # String, default = None
nobuild_year = arcpy.GetParameterAsText(9)          # String, default = None
horizon_year = arcpy.GetParameterAsText(10)

if os.path.exists(root_path):
    hwy_path = MHN.ensure_dir(os.path.join(root_path, 'highway'))
else:
    MHN.die("{} doesn't exist!".format(root_path))
sas1_name = 'coding_overlap'
sas2_name = 'generate_highway_files_2'

# -----------------------------------------------------------------------------
# if for rsp evaluation, set up parameters
# -----------------------------------------------------------------------------
if rsp_eval == True: 
    
    excl_roadway = []
    if excl_roadway_csv: #grab excluded hwy projects, if any
        with open(excl_roadway_csv, 'r') as f:
            for line in f:
                excl_roadway.append(line.strip())          
        
        # for nobuild_year and horizon_year, find the closest 
        # lesser scen year, and export networks as that scen year.
        # (e.g., if nobuild_year=2034, networks will be 2034, 
        # 'scenyear' export folder will be '300' (2030))
        
        mhn_yrmin = min(MHN.scenario_years.values())
        mhn_yrmax = max(MHN.scenario_years.values())
        
        scens = sorted(MHN.scenario_years.keys())
        for scen in scens: #for nobuild year
            if int(nobuild_year) >= MHN.scenario_years[scen]:
                rsp_scen = scen
            else:
                break #stop looking when scen year is larger than nobuild_year
        

        if int(nobuild_year) < mhn_yrmin or int(nobuild_year) > mhn_yrmax:
            MHN.die('Chosen no-build year is not valid! '
                    + f'Choose a number between {mhn_yrmin} and {mhn_yrmax}, inclusive.')
        
        for scen in scens: #for horizon year
            if int(horizon_year) >= MHN.scenario_years[scen]:
                horiz_scen = scen
            else:
                break #stop looking when scen year is larger than horizon_year
        
        if int(horizon_year) < mhn_yrmin or int(horizon_year) > mhn_yrmax:
            MHN.die('Chosen horizon year is not valid!'
                    + f'Choose a number between {mhn_yrmin} and {mhn_yrmax}, inclusive.'
                    )
            
    rsp_info_message = f'''
    RSP evaluation:
        - RSP ID: {rsp_number}
        - Network "no-build" year: {nobuild_year} (scen. {rsp_scen})
        - Horizon year: {horizon_year} (scen. {scen})
    
    Project IDs to be excluded from export:
    {", ".join(id for id in excl_roadway)}
    '''
    arcpy.AddMessage(rsp_info_message)
    scen_list = [rsp_scen] #ignore "scenario years" parameter if RSP eval; only export rsp_scen

# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
overlap_year_csv = os.path.join(MHN.temp_dir, 'overlap_year.csv')
overlap_transact_csv = os.path.join(MHN.temp_dir, 'overlap_transact.csv')
overlap_network_csv = os.path.join(MHN.temp_dir, 'overlap_network.csv')
sas1_log = os.path.join(MHN.temp_dir, '{}.log'.format(sas1_name))
sas1_lst = os.path.join(MHN.temp_dir, '{}.lst'.format(sas1_name))


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
                    w.write('{},{},{}\n'.format(*r))
        return out_csv
    node_zones_csv = os.path.join(hwy_path, 'hwy_node_zones.csv')
    generate_node_zones_csv(node_zones_csv)

# -----------------------------------------------------------------------------
#  Check for hwyproj_coding lane conflicts/reductions in future networks.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nChecking for conflicting highway project coding '
                 + '(i.e. lane reductions) and missing project years...\n')
hwyproj_id_field = MHN.route_systems[MHN.hwyproj][1]

# Export projects with valid completion years.
overlap_year_attr = [hwyproj_id_field, 'COMPLETION_YEAR']
overlap_year_query = '"COMPLETION_YEAR" NOT IN (0,9999)'
overlap_year_view = MHN.make_skinny_table_view(
    MHN.hwyproj, 'overlap_year_view', 
    overlap_year_attr, overlap_year_query)
MHN.write_attribute_csv(overlap_year_view, overlap_year_csv, 
                        overlap_year_attr)
overlap_projects = [r[0] for r in arcpy.da.SearchCursor(overlap_year_view, [hwyproj_id_field])]
arcpy.Delete_management(overlap_year_view)

# Export coding for valid projects.
overlap_transact_attr = [
    hwyproj_id_field, 'ACTION_CODE', 'NEW_DIRECTIONS', 'NEW_TYPE1', 
    'NEW_TYPE2', 'NEW_AMPM1', 'NEW_AMPM2', 'NEW_POSTEDSPEED1',
    'NEW_POSTEDSPEED2', 'NEW_THRULANES1', 'NEW_THRULANES2', 
    'NEW_THRULANEWIDTH1', 'NEW_THRULANEWIDTH2', 'ADD_PARKLANES1',
    'ADD_PARKLANES2', 'ADD_SIGIC', 'ADD_CLTL', 'ADD_RRGRADECROSS',
    'NEW_TOLLDOLLARS', 'NEW_MODES', 'ABB', 'REP_ANODE', 'REP_BNODE'
]
overlap_transact_query = ''' "{}" IN ('{}') '''.format(
    hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in overlap_projects)))
overlap_transact_view = MHN.make_skinny_table_view(
    MHN.route_systems[MHN.hwyproj][0], 'overlap_transact_view', 
    overlap_transact_attr, overlap_transact_query)
MHN.write_attribute_csv(
    overlap_transact_view, overlap_transact_csv, 
    overlap_transact_attr)
overlap_project_arcs = [r[0] for r in arcpy.da.SearchCursor(overlap_transact_view, ['ABB'])]
arcpy.Delete_management(overlap_transact_view)

# Export base year arc attributes.
overlap_network_attr = [
    'ANODE', 'BNODE', 'ABB', 'DIRECTIONS', 'TYPE1', 'TYPE2', 'AMPM1', 
    'AMPM2', 'POSTEDSPEED1', 'POSTEDSPEED2','THRULANES1', 'THRULANES2', 
    'THRULANEWIDTH1', 'THRULANEWIDTH2', 'PARKLANES1', 'PARKLANES2', 
    'SIGIC', 'CLTL', 'RRGRADECROSS', 'TOLLDOLLARS', 'MODES', 'MILES'
]
overlap_network_query = ''' "BASELINK" = '1' OR "ABB" IN ('{}') '''.format(
    "','".join((abb for abb in overlap_project_arcs if abb[-1] != '1')))
overlap_network_view = MHN.make_skinny_table_view(
    MHN.arc, 'overlap_network_view',
    overlap_network_attr, overlap_network_query)
MHN.write_attribute_csv(
    overlap_network_view, overlap_network_csv, 
    overlap_network_attr)
arcpy.Delete_management(overlap_network_view)

# Process attribute tables with coding_overlap.sas.
sas1_sas = ''.join((MHN.src_dir, '/', sas1_name, '.sas'))
sas1_args = [MHN.temp_dir]
MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
if not os.path.exists(sas1_log):
    MHN.die('{} did not run!'.format(sas1_sas))
elif os.path.exists(sas1_lst):
    MHN.die('Please review {} for potential coding errors.'.format(sas1_lst))
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
    if rsp_eval == True:
        #for rsp eval, the queries are nobuild-based, and output location is horizon-based
        scen_year = nobuild_year #for queries
        scen_path = MHN.ensure_dir(os.path.join(hwy_path, horiz_scen)) #for output location
    else:
        scen_year = MHN.scenario_years[scen]
        scen_path = MHN.ensure_dir(os.path.join(hwy_path, scen))
        
    sas2_log = os.path.join(hwy_path, '{}_{}.log'.format(sas2_name, scen))
    sas2_lst = os.path.join(hwy_path, '{}_{}.lst'.format(sas2_name, scen))
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
    
    arcpy.AddMessage('Generating Scenario {} ({}) highway files...'.format(scen, scen_year))
    if rsp_eval == True:
        arcpy.AddMessage(f'RSP RUN: \n - development year: {nobuild_year} \n - RSP number: {rsp_number}')    
    
    # Export coding for highway projects completed by scenario year.
    hwy_year_attr = [hwyproj_id_field, 'COMPLETION_YEAR']
    yr_q = f'"COMPLETION_YEAR" <= {scen_year}'
    rsp_q = f'"{rsp_column}" = {rsp_number}'
    excl_q = f'''"{hwyproj_id_field}" NOT IN ('{"','".join(id for id in excl_roadway)}')'''
    hwy_year_query = yr_q
    if rsp_eval == True:
        if rsp_number.isnumeric(): #if selected an rsp number, include in query
            hwy_year_query = f''' ({yr_q} OR {rsp_q}) AND {excl_q}'''
        else: #if selection was "none, or no build," don't include in query
            hwy_year_query = f'''{yr_q} AND {excl_q}'''
    hwy_year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'hwy_year_view', hwy_year_attr, hwy_year_query)
    MHN.write_attribute_csv(hwy_year_view, hwy_year_csv, hwy_year_attr)
    hwy_projects = [r for r in arcpy.da.SearchCursor(hwy_year_view, [hwyproj_id_field, 'COMPLETION_YEAR'])]
    arcpy.Delete_management(hwy_year_view)

    hwy_transact_attr = [
        hwyproj_id_field, 'ACTION_CODE', 'NEW_DIRECTIONS', 'NEW_TYPE1', 
        'NEW_TYPE2', 'NEW_AMPM1', 'NEW_AMPM2', 'NEW_POSTEDSPEED1',
        'NEW_POSTEDSPEED2', 'NEW_THRULANES1', 'NEW_THRULANES2', 
        'NEW_THRULANEWIDTH1', 'NEW_THRULANEWIDTH2', 'ADD_PARKLANES1',
        'ADD_PARKLANES2', 'ADD_SIGIC', 'ADD_CLTL', 'ADD_RRGRADECROSS', 
        'NEW_TOLLDOLLARS', 'NEW_MODES', 'TOD', 'ABB', 'REP_ANODE', 'REP_BNODE'
    ]
    hwy_transact_query = ''' "{}" IN ('{}') '''.format(
        hwyproj_id_field, 
        "','".join((hwyproj_id for hwyproj_id, comp_year in hwy_projects))
        )
    hwy_transact_view = MHN.make_skinny_table_view(
        MHN.route_systems[MHN.hwyproj][0], 'hwy_transact_view', 
        hwy_transact_attr, hwy_transact_query)
    MHN.write_attribute_csv(
        hwy_transact_view, hwy_transact_csv, 
        hwy_transact_attr)
    hwy_abb = [r[0] for r in arcpy.da.SearchCursor(hwy_transact_view, ['ABB'])]
    arcpy.Delete_management(hwy_transact_view)

    # Export arc & node attributes of all baselinks and skeletons used in
    # projects completed by scenario year.
    hwy_network_attr = [
        'ANODE', 'BNODE', 'ABB', 'DIRECTIONS', 'TYPE1', 'TYPE2', 'AMPM1', 
        'AMPM2', 'POSTEDSPEED1', 'POSTEDSPEED2', 'THRULANES1', 'THRULANES2', 
        'THRULANEWIDTH1', 'THRULANEWIDTH2', 'PARKLANES1', 'PARKLANES2', 
        'PARKRES1', 'PARKRES2', 'SIGIC', 'CLTL', 'RRGRADECROSS', 'TOLLDOLLARS', 
        'MODES', 'CHIBLVD', 'TRUCKRES', 'VCLEARANCE', 'MILES'
        ]
    abb_lst = (abb for abb in hwy_abb if abb[-1] != '1')
    hwy_network_query = f'''"BASELINK" = '1' OR "ABB" IN ('{"','".join(abb_lst)}')'''
    hwy_network_lyr = MHN.make_skinny_feature_layer(
        MHN.arc, 'hwy_network_lyr', 
        hwy_network_attr, hwy_network_query)
    MHN.write_attribute_csv(hwy_network_lyr, hwy_network_csv, 
                            hwy_network_attr)
    hwy_abb_2 = [r[0] for r in arcpy.da.SearchCursor(hwy_network_lyr, ['ABB'])]

    hwy_anodes = [abb.split('-')[0] for abb in hwy_abb_2]
    hwy_bnodes = [abb.split('-')[1] for abb in hwy_abb_2]
    hwy_nodes_list = list(set(hwy_anodes).union(set(hwy_bnodes)))
    hwy_nodes_attr = ['NODE', 'POINT_X', 'POINT_Y', MHN.zone_attr, 
                      MHN.capzone_attr, MHN.imarea_attr]
    hwy_nodes_query = f'"NODE" IN ({','.join(hwy_nodes_list)})'
    hwy_nodes_view = MHN.make_skinny_table_view(
        MHN.node, 'hwy_nodes_view', 
        hwy_nodes_attr, hwy_nodes_query)
    MHN.write_attribute_csv(hwy_nodes_view, hwy_nodes_csv, hwy_nodes_attr)
    arcpy.Delete_management(hwy_nodes_view)

    # Process attribute tables with generate_highway_files_2.sas.
    sas2_sas = os.path.join(MHN.src_dir, f'{sas2_name}.sas')
    sas2_args = [hwy_path, scen, MHN.max_poe, 
                 MHN.base_year, int(abm_output), 0]
    if rsp_eval:
        sas2_args = [hwy_path, scen, MHN.max_poe, MHN.base_year, 
                     int(abm_output), horiz_scen]
    MHN.submit_sas(sas2_sas, sas2_log, sas2_lst, sas2_args)
    if not os.path.exists(sas2_log):
        MHN.die('{} did not run!'.format(sas2_sas))
    elif 'errorlevel=' in open(sas2_lst).read():
        MHN.die(f'Errors during SAS processing. Please see {sas2_log}.')
    else:
        os.remove(sas2_log)
        # NOTE: Do not delete sas2_lst: leave for reference.
        os.remove(hwy_year_csv)
        os.remove(hwy_transact_csv)
        os.remove(hwy_network_csv)
        os.remove(hwy_nodes_csv)
        arcpy.AddMessage(f'-- Scenario {scen} network files generated successfully.')
        if abm_output:
            arcpy.AddMessage(f'-- Scenario {scen} ABM toll file generated successfully.')

    results_summary = open(sas2_lst).read()
    
    #look for errors in sas report and warn user if found
    if ('NETWORK LINKS WITHOUT' in results_summary or
        'SUSPICIOUS TOLL CHARGES' in results_summary):
        arcpy.AddWarning(f'-- Some links may have incorrect coding! Please see {sas2_lst}.')

    # Calculate scenario mainline links' AM Peak lane-miles.
    scen_ampeak_l1 = os.path.join(scen_path, '{}03.l1'.format(scen))
    if rsp_eval == True:
        scen_ampeak_l1 = os.path.join(scen_path, '{}03.l1'.format(horiz_scen))
    mainline_lanemiles = {}
    with open(scen_ampeak_l1, 'r') as l1:
        for r in l1:
            attr = r.split()
            if attr[0] == 'a' and attr[7] in ('2', '4'):  # Ignore comments, t-record and non-mainline links
                ab = '{}-{}'.format(attr[1], attr[2])
                lanemiles = float(attr[3]) * int(attr[6])
                mainline_lanemiles[ab] = lanemiles

    # Create rsp_stats.txt.
    scen_rsp_tipids = {}
    scen_rsp_query = f''' "COMPLETION_YEAR" <= {scen_year} AND "RSP_ID" IS NOT NULL '''
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
            rsp_query = ''' "{}" IN ('{}') '''.format(hwyproj_id_field, "','".join(scen_rsp_tipids[rsp_id]))
            sc = arcpy.da.SearchCursor(MHN.route_systems[MHN.hwyproj][0], 
                                       ['ABB'], rsp_query)
            rsp_ab = set((r[0].rsplit('-', 1)[0] for r in sc))
            rsp_lanemiles = sum((mainline_lanemiles[ab] for ab in rsp_ab if ab in mainline_lanemiles))
            w.write('{},{},{}\n'.format(rsp_id, MHN.rsps[rsp_id], rsp_lanemiles))

    arcpy.AddMessage('-- Scenario {} rsp_stats.csv generated successfully.'.format(scen))

    # Create linkshape.in.  
    def generate_linkshape(arcs, output_dir):
        linkshape = os.path.join(output_dir, 'highway.linkshape')
        w = open(linkshape, 'w')
        w.write('c HIGHWAY LINK SHAPE FILE FOR SCENARIO {}\n'.format(scen))
        w.write('c {}\n'.format(MHN.timestamp('%d%b%y').upper()))
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
                        try:
                            vertex = part.next()
                        except:
                            # Must be using ArcGIS Pro...
                            vertex = next(part)
                        while vertex:
                            n += 1
                            writer.write(' '.join(['a', fnode, tnode, str(n), str(vertex.X), str(vertex.Y)]) + '\n')
                            try:
                                vertex = part.next()
                            except:
                                vertex = next(part)
                            if not vertex:
                                try:
                                    vertex = part.next()
                                except:
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
    arcpy.AddMessage('-- Scenario {} highway.linkshape generated successfully.\n'.format(scen))
    

#write out select link transaction file
if rsp_eval:
    if not 'NONE' in rsp_number:
        arcpy.AddMessage(f'  - Writing select link file for {rsp_number}')
        sl_dir = os.path.join(root_path, f'RCP_{rsp_number}.txt')

        proj_id_field = MHN.route_systems[MHN.hwyproj][1] #TIPID
        tipid_yr = arcpy.da.TableToNumPyArray(
            in_table = MHN.hwyproj,
            field_names=[proj_id_field,'COMPLETION_YEAR'],
            where_clause=f'"{rsp_column}" = {rsp_number}'
        )

        tipid_yr.sort(order='COMPLETION_YEAR')
        tipid = list(tipid_yr[proj_id_field])

        arcpy.AddMessage(f"TIPID(s) found for RSP {rsp_number}: \n{', '.join(t for t in tipid)}")

        tipid_q = f''' TIPID IN ('{"','".join(t for t in tipid)}') '''
        print(tipid_q)
        action_q = "ACTION_CODE IN ('1','2','4')"
        lks = arcpy.da.TableToNumPyArray(
            in_table = MHN.route_systems[MHN.hwyproj][0],
            field_names=['ABB', 'REP_ANODE', 'REP_BNODE', 'TIPID', 'ACTION_CODE'],
            where_clause= f'{tipid_q} AND {action_q}'''
            )

        lks = pd.DataFrame(lks)
        lks = pd.merge(lks, pd.DataFrame(tipid_yr), on='TIPID')

        print(f'all project coding: {len(lks)}')

        deletes_df = lks.loc[lks['ACTION_CODE'].astype(int)==3]
        print(f'{len(deletes_df)} delete links')
        delete_list = deletes_df['ABB'].unique().tolist()

        lks.drop(index=lks.loc[lks['ABB'].isin(delete_list)].index, inplace=True)

        replaces_df = lks.loc[lks['ACTION_CODE'].astype(int)==2].copy()
        print(f'{len(replaces_df)} replace links')
        replaces_df['AB'] = replaces_df['REP_ANODE'].astype(str) + '-' + replaces_df['REP_BNODE'].astype(str)
        replace_list = replaces_df['AB'].unique().tolist()

        ab_regex = '|'.join(replace_list)
        lks.drop(index=lks.loc[lks['ABB'].str.contains(ab_regex, regex=True)].index, inplace=True)

        lks.drop_duplicates(subset='ABB', inplace=True)

        def abb_to_transact(abb):
            a = abb.split('-')[0].strip()
            b = abb.split('-')[1].strip()
            return f'{a},{b}'

        lks['for_transactionfile'] = lks['ABB'].apply(abb_to_transact)
        transact_links = lks['for_transactionfile'].tolist()

        with open(sl_dir, 'w') as file:
            comment = f'~# select link: links for RCP_{rsp_number} for RCP evaluation\n'
            file.write(comment)
            for lk in transact_links:
                file.write(f'l={lk}\n')
