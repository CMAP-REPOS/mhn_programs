#!/usr/bin/env python
'''
    generate_highway_files.py
    Author: npeterson
    Revised: 12/17/13
    ---------------------------------------------------------------------------
    This program creates the Emme highway batchin files needed to model a
    scenario network. The scenario, output path and CT-RAMP flag are passed to
    the script as arguments from the tool. Creates l1, l2, n1, n2 files for all
    TOD periods.

'''
import os
import sys
import arcpy
import MHN  # Custom library for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
scen_code = arcpy.GetParameterAsText(0)                                      # String, default = '100'
root_path = arcpy.GetParameterAsText(1).replace('\\','/').rstrip('/') + '/'  # String, no default
create_tollsys_flag = arcpy.GetParameter(2)                                  # Boolean, default = True
if os.path.exists(root_path):
    hwy_path = MHN.ensure_dir(root_path + 'highway/')
else:
    MHN.die("{0} doesn't exist!".format(root_path))
sas1_name = 'coding_overlap'
sas2_name = 'generate_highway_files_2'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = ''.join((MHN.temp_dir, '/', sas1_name, '.log'))
sas1_lst = ''.join((MHN.temp_dir, '/', sas1_name, '.lst'))
overlap_year_csv = '/'.join((MHN.temp_dir, 'overlap_year.csv'))
overlap_transact_csv = '/'.join((MHN.temp_dir, 'overlap_transact.csv'))
overlap_network_csv = '/'.join((MHN.temp_dir, 'overlap_network.csv'))
# sas2_log & sas2_lst are scenario-dependent, defined below


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(overlap_year_csv)
MHN.delete_if_exists(overlap_transact_csv)
MHN.delete_if_exists(overlap_network_csv)


# -----------------------------------------------------------------------------
#  Write tollsys.flag file if desired.
# -----------------------------------------------------------------------------
if create_tollsys_flag:
    arcpy.AddMessage('\nGenerating tollsys.flag file...')
    tollsys_flag = ''.join((hwy_path, 'tollsys.flag'))
    MHN.write_arc_flag_file(tollsys_flag, ''' "TOLLSYS" = 1 ''')


# -----------------------------------------------------------------------------
#  Check for hwyproj_coding lane conflicts/reductions in future networks.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nChecking for conflicting highway project coding (i.e. lane reductions) and missing project years...\n')
hwyproj_id_field = MHN.route_systems[MHN.hwyproj][1]

# Export projects with valid completion years.
overlap_year_attr = [hwyproj_id_field,'COMPLETION_YEAR']
overlap_year_query = '"COMPLETION_YEAR" NOT IN (0,9999)'
overlap_year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'overlap_year_view', overlap_year_attr, overlap_year_query)
MHN.write_attribute_csv(overlap_year_view, overlap_year_csv, overlap_year_attr)
overlap_projects = MHN.make_attribute_dict(overlap_year_view, hwyproj_id_field, attr_list=[])
arcpy.Delete_management(overlap_year_view)

# Export coding for valid projects.
overlap_transact_attr = [hwyproj_id_field,'ACTION_CODE','NEW_DIRECTIONS','NEW_TYPE1','NEW_TYPE2','NEW_AMPM1','NEW_AMPM2','NEW_POSTEDSPEED1',
                         'NEW_POSTEDSPEED2','NEW_THRULANES1','NEW_THRULANES2','NEW_THRULANEWIDTH1','NEW_THRULANEWIDTH2','ADD_PARKLANES1',
                         'ADD_PARKLANES2','ADD_SIGIC','ADD_CLTL','ADD_RRGRADECROSS','NEW_TOLLDOLLARS','NEW_MODES','ABB','REP_ANODE','REP_BNODE']
overlap_transact_query = '"{0}" IN (\'{1}\')'.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in overlap_projects)))
overlap_transact_view = MHN.make_skinny_table_view(MHN.route_systems[MHN.hwyproj][0], 'overlap_transact_view', overlap_transact_attr, overlap_transact_query)
MHN.write_attribute_csv(overlap_transact_view, overlap_transact_csv, overlap_transact_attr)
overlap_project_arcs = MHN.make_attribute_dict(overlap_transact_view, 'ABB', attr_list=[])
arcpy.Delete_management(overlap_transact_view)

# Export base year arc attributes.
overlap_network_attr = ['ANODE','BNODE','ABB','DIRECTIONS','TYPE1','TYPE2','AMPM1','AMPM2','POSTEDSPEED1','POSTEDSPEED2','THRULANES1','THRULANES2',
                        'THRULANEWIDTH1','THRULANEWIDTH2','PARKLANES1','PARKLANES2','SIGIC','CLTL','RRGRADECROSS','TOLLDOLLARS','MODES','MILES']
overlap_network_query = '"BASELINK" = \'1\' OR "ABB" IN (\'{0}\')'.format("','".join((arc_id for arc_id in overlap_project_arcs if arc_id[-1] != '1')))
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
if scen_code == 'ALL':
    scen_list = sorted(MHN.scenario_years.keys())
else:
    scen_list = [scen_code]

for scen in scen_list:
    # Set scenario-specific parameters.
    scen_year = MHN.scenario_years[scen]
    scen_path = MHN.ensure_dir(hwy_path + scen + '/')
    sas2_log = ''.join((hwy_path, sas2_name, '_', scen, '.log'))
    sas2_lst = ''.join((hwy_path, sas2_name, '_', scen, '.lst'))
    hwy_year_csv = scen_path + 'year.csv'
    hwy_transact_csv = scen_path + 'transact.csv'
    hwy_network_csv = scen_path + 'network.csv'
    hwy_nodes_csv = scen_path + 'nodes.csv'

    MHN.delete_if_exists(sas2_log)
    MHN.delete_if_exists(sas2_lst)
    MHN.delete_if_exists(hwy_year_csv)
    MHN.delete_if_exists(hwy_transact_csv)
    MHN.delete_if_exists(hwy_network_csv)
    MHN.delete_if_exists(hwy_nodes_csv)

    arcpy.AddMessage('Generating Scenario {0} ({1}) highway files...'.format(scen, scen_year))

    # Export coding for highway projects completed by scenario year.
    hwy_year_attr = [hwyproj_id_field,'COMPLETION_YEAR']
    hwy_year_query = '"COMPLETION_YEAR" <= {0}'.format(scen_year)
    hwy_year_view = MHN.make_skinny_table_view(MHN.hwyproj, 'hwy_year_view', hwy_year_attr, hwy_year_query)
    MHN.write_attribute_csv(hwy_year_view, hwy_year_csv, hwy_year_attr)
    hwy_projects = MHN.make_attribute_dict(hwy_year_view, hwyproj_id_field, attr_list=[])
    arcpy.Delete_management(hwy_year_view)

    hwy_transact_attr = [hwyproj_id_field,'ACTION_CODE','NEW_DIRECTIONS','NEW_TYPE1','NEW_TYPE2','NEW_AMPM1','NEW_AMPM2','NEW_POSTEDSPEED1',
                         'NEW_POSTEDSPEED2','NEW_THRULANES1','NEW_THRULANES2','NEW_THRULANEWIDTH1','NEW_THRULANEWIDTH2','ADD_PARKLANES1',
                         'ADD_PARKLANES2','ADD_SIGIC','ADD_CLTL','ADD_RRGRADECROSS','NEW_TOLLDOLLARS','NEW_MODES','TOD','ABB','REP_ANODE','REP_BNODE']
    hwy_transact_query = '"{0}" IN (\'{1}\')'.format(hwyproj_id_field, "','".join((hwyproj_id for hwyproj_id in hwy_projects)))
    hwy_transact_view = MHN.make_skinny_table_view(MHN.route_systems[MHN.hwyproj][0], 'hwy_transact_view', hwy_transact_attr, hwy_transact_query)
    MHN.write_attribute_csv(hwy_transact_view, hwy_transact_csv, hwy_transact_attr)
    hwy_abb = MHN.make_attribute_dict(hwy_transact_view, 'ABB', attr_list=[])
    arcpy.Delete_management(hwy_transact_view)

    # Export arc & node attributes of all baselinks and skeletons used in
    # projects completed by scenario year.
    hwy_network_attr = ['ANODE','BNODE','ABB','DIRECTIONS','TYPE1','TYPE2','AMPM1','AMPM2','POSTEDSPEED1','POSTEDSPEED2','THRULANES1','THRULANES2',
                        'THRULANEWIDTH1','THRULANEWIDTH2','PARKLANES1','PARKLANES2','PARKRES1','PARKRES2','SIGIC','CLTL','RRGRADECROSS','TOLLDOLLARS',
                        'MODES','CHIBLVD','TRUCKRES','VCLEARANCE','MILES']
    hwy_network_query = '"BASELINK" = \'1\' OR "ABB" IN (\'{0}\')'.format("','".join((abb for abb in hwy_abb if abb[-1] != '1')))
    hwy_network_lyr = MHN.make_skinny_feature_layer(MHN.arc, 'hwy_network_lyr', hwy_network_attr, hwy_network_query)
    MHN.write_attribute_csv(hwy_network_lyr, hwy_network_csv, hwy_network_attr)
    hwy_abb_2 = MHN.make_attribute_dict(hwy_network_lyr, 'ABB', attr_list=[])

    hwy_anodes = [abb.split('-')[0] for abb in hwy_abb_2]
    hwy_bnodes = [abb.split('-')[1] for abb in hwy_abb_2]
    hwy_nodes_list = list(set(hwy_anodes).union(set(hwy_bnodes)))
    hwy_nodes_attr = ['NODE','POINT_X','POINT_Y','Zone09','CapacityZone09']
    hwy_nodes_query = '"NODE" IN ({0})'.format(','.join(hwy_nodes_list))
    hwy_nodes_view = MHN.make_skinny_table_view(MHN.node, 'hwy_nodes_view', hwy_nodes_attr, hwy_nodes_query)
    MHN.write_attribute_csv(hwy_nodes_view, hwy_nodes_csv, hwy_nodes_attr)
    arcpy.Delete_management(hwy_nodes_view)

    # Process attribute tables with generate_highway_files_2.sas.
    sas2_sas = ''.join((MHN.prog_dir, '/', sas2_name, '.sas'))
    sas2_args = [hwy_path, scen, str(MHN.max_poe), str(MHN.base_year)]
    MHN.submit_sas(sas2_sas, sas2_log, sas2_lst, sas2_args)
    if not os.path.exists(sas2_log):
        MHN.die(sas2_sas + ' did not run!')
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

    # Create linkshape.in.
    def generate_linkshape(arcs, output_dir):
        linkshape = output_dir.rstrip('/') + '/highway.linkshape'
        w = open(linkshape, 'w')
        w.write('c HIGHWAY LINK SHAPE FILE FOR SCENARIO {0}\n'.format(scen))
        w.write('c {0}\n'.format(MHN.timestamp('%d%b%y').upper()))
        w.write('t linkvertices\n')

        def write_vertices(fc, writer, reversed=False):
            with arcpy.da.SearchCursor(fc, ['SHAPE@','ANODE','BNODE']) as cursor:
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
                        vertex = part.next()
                        while vertex:
                            n += 1
                            writer.write(' '.join(['a', fnode, tnode, str(n), str(vertex.X), str(vertex.Y)]) + '\n')
                            vertex = part.next()
                            if not vertex:
                                vertex = part.next()
            return None

        arcs_mem = MHN.mem + '/arcs'
        arcpy.CopyFeatures_management(arcs, arcs_mem)
        write_vertices(arcs_mem, w)

        arcs_mem_flipped = MHN.mem + '/arcs_flipped'
        arcs_2dir_lyr = 'arcs_2dir'
        arcpy.MakeFeatureLayer_management(arcs_mem, arcs_2dir_lyr, '"DIRECTIONS" <> \'1\'')
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
