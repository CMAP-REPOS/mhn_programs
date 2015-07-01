#!/usr/bin/env python
'''
    generate_transit_files.py
    Author: npeterson
    Revised: 6/30/15
    ---------------------------------------------------------------------------
    This program creates the Emme transit batchin files needed to model a
    scenario network. The scenario, output path and CT-RAMP flag are passed to
    the script as arguments from the tool. Creates access.network,
    bus.itinerary, bus.network, and busnode.extatt files for all TOD periods.

    Rail batchin files (generated from the Master Rail Network) must already
    exist in a folder called 'transit' contained within the root folder
    specified by this tool.

    Additionally, this tool will merge the separate highway and rail linkshape
    files for the specified scenario(s) into a new one, located in
    {root folder}/linkshape. This file will allow correct link geometry to be
    viewed in Emme, after the scenario has been initialized.

'''
import os
import sys
import arcpy
from MHN import MasterHighwayNetwork  # Custom class for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
arcpy.env.qualifiedFieldNames = False  # Joined attributes will not have fc name prefix

mhn_gdb_path = arcpy.GetParameterAsText(0)          # MHN geodatabase
MHN = MasterHighwayNetwork(mhn_gdb_path)
scen_list = arcpy.GetParameterAsText(1).split(';')  # Semicolon-delimited string, e.g. '100;200'
root_path = arcpy.GetParameterAsText(2)             # String, no default
ct_ramp = arcpy.GetParameter(3)                     # Boolean, default = False

out_tod_periods = sorted(MHN.tod_periods.keys())

if not os.path.exists(root_path):
    MHN.die("{0} doesn't exist!".format(root_path))
hwy_path = os.path.join(root_path, 'highway')
if not os.path.exists(hwy_path):
    MHN.die('{0} contains no highway folder! Please run the Generate Highway Files tool first.'.format(root_path))
tran_path = os.path.join(root_path, 'transit')
if not os.path.exists(tran_path):
    MHN.die("{0} contains no transit folder! Please run the Master Rail Network's Create Emme Scenario Files tool first.".format(root_path))

sas1_name = 'gtfs_reformat_feed'
sas2_name = 'generate_transit_files_2'
sas3_name = 'generate_transit_files_3'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = os.path.join(MHN.temp_dir, '{0}.log'.format(sas1_name))
sas1_lst = os.path.join(MHN.temp_dir, '{0}.lst'.format(sas1_name))
sas2_log = os.path.join(MHN.temp_dir, '{0}.log'.format(sas2_name))
sas2_lst = os.path.join(MHN.temp_dir, '{0}.lst'.format(sas2_name))
sas3_log = os.path.join(MHN.temp_dir, '{0}.log'.format(sas3_name))
sas3_lst = os.path.join(MHN.temp_dir, '{0}.lst'.format(sas3_name))
bus_route_csv = os.path.join(MHN.temp_dir, 'bus_route.csv')
bus_itin_csv = os.path.join(MHN.temp_dir, 'bus_itin.csv')
oneline_itin_txt = os.path.join(MHN.temp_dir, 'oneline_itin.txt')  # gtfs_collapse_routes.py input file (called by gtfs_reformat_feed.sas)
feed_groups_txt = os.path.join(MHN.temp_dir, 'feed_groups.txt')    # gtfs_collapse_routes.py output file
missing_links_csv = os.path.join(MHN.out_dir, 'missing_bus_links.csv')
link_dict_txt = os.path.join(MHN.out_dir, 'link_dictionary.txt')  # shortest_path.py input file (called by generate_transit_files_2.sas)
short_path_txt = os.path.join(MHN.out_dir, 'short_path.txt')      # shortest_path.py output file
path_errors_txt = os.path.join(MHN.temp_dir, 'path_errors.txt')


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(sas2_log)
MHN.delete_if_exists(sas2_lst)
MHN.delete_if_exists(sas3_log)
MHN.delete_if_exists(sas3_lst)
MHN.delete_if_exists(bus_route_csv)
MHN.delete_if_exists(bus_itin_csv)
MHN.delete_if_exists(oneline_itin_txt)
MHN.delete_if_exists(feed_groups_txt)
MHN.delete_if_exists(missing_links_csv)
MHN.delete_if_exists(link_dict_txt)
MHN.delete_if_exists(short_path_txt)
MHN.delete_if_exists(path_errors_txt)


# -----------------------------------------------------------------------------
#  Create features/layers that will be same for all scenarios & TODs.
# -----------------------------------------------------------------------------
arc_miles_view = 'arc_miles_view'
MHN.make_skinny_table_view(MHN.arc, arc_miles_view, ['ABB', 'MILES'])

node_oid_field = MHN.determine_OID_fieldname(MHN.node)
centroid_lyr = MHN.make_skinny_feature_layer(MHN.node, 'centroid_lyr', [node_oid_field, 'NODE'], '"NODE" <= {0}'.format(max(MHN.centroid_ranges['MHN'])))
centroid_fc = os.path.join(MHN.mem, 'centroid_fc')
arcpy.CopyFeatures_management(centroid_lyr, centroid_fc)

zone_lyr = MHN.make_skinny_feature_layer(MHN.zone, 'zone_lyr', [MHN.zone_attr])


# -----------------------------------------------------------------------------
#  Identify representative runs from GTFS bus itineraries.
# -----------------------------------------------------------------------------
rep_runs_dict = {}
bus_fc_dict = {MHN.bus_base: 'base',
               MHN.bus_current: 'current'}

# Remove base or current from bus_fc_dict, if not used for specified scenarios.
if not any(MHN.scenario_years[scen] <= MHN.bus_years['base'] for scen in scen_list):
    del bus_fc_dict[MHN.bus_base]
if not any(MHN.scenario_years[scen] > MHN.bus_years['base'] for scen in scen_list):
    del bus_fc_dict[MHN.bus_current]

# Identify representative runs for bus_base and/or bus_current, as relevant.
for bus_fc in bus_fc_dict:
    arcpy.AddMessage('\nIdentifying representative runs from {0}...'.format(bus_fc))

    which_bus = bus_fc_dict[bus_fc]

    rep_runs_dict[which_bus] = {}
    for tod in out_tod_periods:
        arcpy.AddMessage('-- TOD {0}...'.format(tod.upper()))

        # Export header info of bus routes in current TOD.
        bus_id_field = MHN.route_systems[bus_fc][1]
        bus_route_attr = [bus_id_field, 'DESCRIPTION', 'MODE', 'VEHICLE_TYPE', 'HEADWAY', 'SPEED', 'ROUTE_ID', 'START']
        bus_route_query = MHN.tod_periods[tod][1]
        bus_route_view = MHN.make_skinny_table_view(bus_fc, 'bus_route_view', bus_route_attr, bus_route_query)
        MHN.write_attribute_csv(bus_route_view, bus_route_csv, bus_route_attr)
        selected_bus_routes = MHN.make_attribute_dict(bus_route_view, bus_id_field, attr_list=[])
        arcpy.Delete_management(bus_route_view)

        # Export itineraries for selected runs.
        bus_order_field = MHN.route_systems[bus_fc][2]
        bus_itin_attr = [bus_id_field, 'ITIN_A', 'ITIN_B', bus_order_field, 'LAYOVER', 'DWELL_CODE', 'ZONE_FARE', 'LINE_SERV_TIME', 'TTF']
        bus_itin_query = ''' "{0}" IN ('{1}') '''.format(bus_id_field, "','".join((bus_id for bus_id in selected_bus_routes)))
        bus_itin_view = MHN.make_skinny_table_view(MHN.route_systems[bus_fc][0], 'bus_itin_view', bus_itin_attr, bus_itin_query)
        MHN.write_attribute_csv(bus_itin_view, bus_itin_csv, bus_itin_attr)
        arcpy.Delete_management(bus_itin_view)

        # Process exported route & itin tables with gtfs_reformat_feed.sas.
        sas1_sas = os.path.join(MHN.prog_dir, '{0}.sas'.format(sas1_name))
        sas1_output = os.path.join(MHN.temp_dir, 'bus_{0}_runs_{1}.csv'.format(which_bus, tod))
        sas1_args = [MHN.prog_dir, bus_route_csv, bus_itin_csv, oneline_itin_txt, feed_groups_txt, sas1_output, tod]
        MHN.delete_if_exists(sas1_output)
        MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
        if not os.path.exists(sas1_log):
            MHN.die('{0} did not run!'.format(sas1_sas))
        elif not os.path.exists(feed_groups_txt):
            MHN.die('{0} did not run! (Called by {1}.)'.format(os.path.join(MHN.prog_dir, 'gtfs_collapse_routes.py'), sas1_sas))
        elif os.path.exists(sas1_lst) or not os.path.exists(sas1_output):
            MHN.die('{0} did not run successfully. Please review {1}.'.format(sas1_sas, sas1_log))
        else:
            os.remove(sas1_log)
            os.remove(bus_route_csv)
            os.remove(bus_itin_csv)
            os.remove(oneline_itin_txt)
            os.remove(feed_groups_txt)

        rep_runs_dict[which_bus][tod] = sas1_output


# -----------------------------------------------------------------------------
#  Generate large itinerary tables joined with MILES attribute.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nCreating temporary itinerary datasets...')
all_runs_itin_miles_dict = {}

for bus_fc in bus_fc_dict:
    which_bus = bus_fc_dict[bus_fc]
    arcpy.AddMessage('-- bus_{0}_itin + MILES'.format(which_bus))
    all_runs_itin_view = 'all_runs_itin_view'
    arcpy.MakeTableView_management(MHN.route_systems[bus_fc][0], all_runs_itin_view)
    arcpy.AddJoin_management(all_runs_itin_view, 'ABB', arc_miles_view, 'ABB', 'KEEP_ALL')
    all_runs_itin_miles = os.path.join(MHN.mem, 'all_runs_itin_miles_{0}'.format(which_bus))
    arcpy.CopyRows_management(all_runs_itin_view, all_runs_itin_miles)
    arcpy.RemoveJoin_management(all_runs_itin_view)
    arcpy.Delete_management(all_runs_itin_view)
    all_runs_itin_miles_dict[which_bus] = all_runs_itin_miles

# Generate future itinerary joined with MILES, if necessary.
if any(MHN.scenario_years[scen] > MHN.base_year for scen in scen_list):
    arcpy.AddMessage('-- bus_future_itin + MILES')
    future_runs_itin_view = 'future_runs_itin_view'
    arcpy.MakeTableView_management(MHN.route_systems[MHN.bus_future][0], future_runs_itin_view)
    arcpy.AddJoin_management(future_runs_itin_view, 'ABB', arc_miles_view, 'ABB', 'KEEP_ALL')
    future_runs_itin_miles = os.path.join(MHN.mem, 'all_runs_itin_miles_future')
    arcpy.CopyRows_management(future_runs_itin_view, future_runs_itin_miles)
    arcpy.RemoveJoin_management(future_runs_itin_view)
    arcpy.Delete_management(future_runs_itin_view)
    all_runs_itin_miles_dict['future'] = future_runs_itin_miles
    arcpy.Delete_management(arc_miles_view)


# -----------------------------------------------------------------------------
#  Iterate through scenarios, if more than one requested.
# -----------------------------------------------------------------------------
for scen in scen_list:
    # Set scenario-specific parameters.
    scen_year = MHN.scenario_years[scen]
    if scen_year <= MHN.bus_years['base']:
        bus_fc = MHN.bus_base
        which_bus = 'base'
    else:
        bus_fc = MHN.bus_current
        which_bus = 'current'

    scen_hwy_path = os.path.join(hwy_path, scen)
    if not os.path.exists(scen_hwy_path):
        MHN.die('{0} contains no {1} folder! Please run the Generate Highway Files tool for this scenario first.'.format(hwy_path, scen))
    scen_tran_path = os.path.join(tran_path, scen)
    if not os.path.exists(scen_tran_path):
        MHN.die("{0} contains no {1} folder! Please run the Master Rail Network's Create Emme Scenario Files tool for this scenario first.".format(tran_path, scen))

    # -------------------------------------------------------------------------
    # Iterate through scenario's TOD periods and write transit batchin files.
    # -------------------------------------------------------------------------
    arcpy.AddMessage('\nGenerating Scenario {0} ({1}) transit files...'.format(scen, str(scen_year)))

    for tod in out_tod_periods:
        arcpy.AddMessage('-- TOD {0}...'.format(tod.upper()))

        rail_itin = os.path.join(scen_tran_path, 'rail.itinerary_{0}'.format(tod))
        rail_net = os.path.join(scen_tran_path, 'rail.network_{0}'.format(tod))
        rail_node = os.path.join(scen_tran_path, 'railnode.extatt_{0}'.format(tod))
        bus_itin = os.path.join(scen_tran_path, 'bus.itinerary_{0}'.format(tod))
        bus_net = os.path.join(scen_tran_path, 'bus.network_{0}'.format(tod))
        bus_node = os.path.join(scen_tran_path, 'busnode.extatt_{0}'.format(tod))
        bus_stop = os.path.join(scen_tran_path, 'busstop.pnt')
        cta_bus = os.path.join(scen_tran_path, 'ctabus.pnt')
        pace_bus = os.path.join(scen_tran_path, 'pacebus.pnt')
        cta_stop = os.path.join(scen_tran_path, 'ctastop.pnt')
        metra_stop = os.path.join(scen_tran_path, 'metrastop.pnt')
        itin_final = os.path.join(scen_tran_path, 'itin.final')

        if tod == 'am':  # Use TOD 3 highways for AM transit
            hwy_l1 = os.path.join(scen_hwy_path, '{0}03.l1'.format(scen))
            hwy_n1 = os.path.join(scen_hwy_path, '{0}03.n1'.format(scen))
            hwy_n2 = os.path.join(scen_hwy_path, '{0}03.n2'.format(scen))
        else:
            hwy_l1 = os.path.join(scen_hwy_path, '{0}0{1}.l1'.format(scen, tod))
            hwy_n1 = os.path.join(scen_hwy_path, '{0}0{1}.n1'.format(scen, tod))
            hwy_n2 = os.path.join(scen_hwy_path, '{0}0{1}.n2'.format(scen, tod))

        if not (os.path.exists(rail_itin) and os.path.exists(rail_net) and os.path.exists(rail_node)):
            MHN.die("{0} doesn't contain all required rail batchin files! Please run the Master Rail Network's Create Emme Scenario Files tool for this scenario first.".format(scen_tran_path))
        elif not (os.path.exists(hwy_l1) and os.path.exists(hwy_n1) and os.path.exists(hwy_n2)):
            MHN.die("{0} doesn't contain all required highway batchin files! Please run the Generate Highway Files tool for this scenario first.".format(scen_hwy_path))

        # Export table of Park-n-Ride nodes
        pnr_view = 'pnr_view'
        MHN.make_skinny_table_view(MHN.pnr, pnr_view, ['NODE', 'COST', 'SPACES'])
        pnr_csv = os.path.join(scen_tran_path, 'pnr.csv')
        MHN.write_attribute_csv(pnr_view, pnr_csv)

        # Create a temporary table of TOD's representative runs' header attributes
        bus_lyr = 'bus_lyr'
        arcpy.MakeFeatureLayer_management(bus_fc, bus_lyr)
        bus_id_field = MHN.route_systems[bus_fc][1]
        rep_runs = rep_runs_dict[which_bus][tod]
        arcpy.AddJoin_management(bus_lyr, bus_id_field, rep_runs, 'TRANSIT_LINE', 'KEEP_COMMON')  # 'KEEP_COMMON' excludes unmatched routes
        rep_runs_table = os.path.join(MHN.mem, 'rep_runs')
        arcpy.CopyRows_management(bus_lyr, rep_runs_table)
        arcpy.RemoveJoin_management(bus_lyr)
        arcpy.Delete_management(bus_lyr)

        # Export header info of representative bus runs in current TOD.
        if ct_ramp:
            rep_runs_attr = [bus_id_field, 'DESCRIPTION', 'MODE', 'CT_VEH', 'SPEED', 'GROUP_HEADWAY']  # CT_VEH instead of VEHICLE_TYPE
        else:
            rep_runs_attr = [bus_id_field, 'DESCRIPTION', 'MODE', 'VEHICLE_TYPE', 'SPEED', 'GROUP_HEADWAY']
        rep_runs_query = MHN.tod_periods[tod][1]
        rep_runs_view = MHN.make_skinny_table_view(rep_runs_table, 'rep_runs_view', rep_runs_attr, rep_runs_query)
        rep_runs_csv = os.path.join(scen_tran_path, 'rep_runs.csv')
        MHN.write_attribute_csv(rep_runs_view, rep_runs_csv, rep_runs_attr)
        selected_runs = MHN.make_attribute_dict(rep_runs_view, bus_id_field, attr_list=[])
        arcpy.Delete_management(rep_runs_view)
        arcpy.Delete_management(rep_runs_table)

        # Export itineraries for selected runs.
        bus_order_field = MHN.route_systems[bus_fc][2]
        rep_runs_itin_attr = [bus_id_field, 'ITIN_A', 'ITIN_B', bus_order_field, 'LAYOVER', 'DWELL_CODE', 'ZONE_FARE', 'LINE_SERV_TIME', 'TTF', 'F_MEAS', 'T_MEAS', 'MILES']
        rep_runs_itin_query = ''' "{0}" IN ('{1}') '''.format(bus_id_field, "','".join((bus_id for bus_id in selected_runs)))
        rep_runs_itin_view = MHN.make_skinny_table_view(all_runs_itin_miles_dict[which_bus], 'rep_runs_itin_view', rep_runs_itin_attr, rep_runs_itin_query)
        rep_runs_itin_csv = os.path.join(scen_tran_path, 'rep_runs_itin.csv')
        MHN.write_attribute_csv(rep_runs_itin_view, rep_runs_itin_csv, rep_runs_itin_attr)
        arcpy.Delete_management(rep_runs_itin_view)

        # Export future coding as necessary.
        replace_csv = os.path.join(scen_tran_path, 'replace.csv')
        if scen != '100':
            # Header data first.
            bus_future_lyr = 'future_lyr'
            arcpy.MakeFeatureLayer_management(MHN.bus_future, bus_future_lyr)
            bus_future_id_field = MHN.route_systems[MHN.bus_future][1]
            bus_future_attr = [bus_future_id_field, 'DESCRIPTION', 'MODE', 'VEHICLE_TYPE', 'SPEED', 'HEADWAY']
            bus_future_query = ''' "SCENARIO" LIKE '%{0}%' '''.format(scen[0])  # SCENARIO field contains first character of applicable scenario codes
            bus_future_view = MHN.make_skinny_table_view(bus_future_lyr, 'bus_future_view', bus_future_attr, bus_future_query)
            bus_future_csv = os.path.join(scen_tran_path, 'bus_future.csv')
            MHN.write_attribute_csv(bus_future_view, bus_future_csv, bus_future_attr, include_headers=False)  # Skip headers for easier appending
            selected_future_runs = MHN.make_attribute_dict(bus_future_view, bus_future_id_field, attr_list=[])

            # Another header set for route replacement data.
            replace_attr = [bus_future_id_field, 'REPLACE', 'TOD']
            replace_view = MHN.make_skinny_table_view(bus_future_lyr, 'replace_view', replace_attr, bus_future_query)
            MHN.write_attribute_csv(replace_view, replace_csv, replace_attr)
            arcpy.Delete_management(replace_view)

            # Corresponding itineraries.
            bus_future_order_field = MHN.route_systems[MHN.bus_future][2]
            bus_future_itin_attr = [bus_future_id_field, 'ITIN_A', 'ITIN_B', bus_future_order_field, 'LAYOVER', 'DWELL_CODE', 'ZONE_FARE', 'LINE_SERV_TIME', 'TTF', 'F_MEAS', 'T_MEAS', 'MILES']
            bus_future_itin_query = ''' "{0}" IN ('{1}') '''.format(bus_future_id_field, "','".join((bus_future_id for bus_future_id in selected_future_runs)))
            bus_future_itin_view = MHN.make_skinny_table_view(all_runs_itin_miles_dict['future'], 'bus_future_itin_view', bus_future_itin_attr, bus_future_itin_query)
            bus_future_itin_csv = os.path.join(scen_tran_path, 'bus_future_itin.csv')
            MHN.write_attribute_csv(bus_future_itin_view, bus_future_itin_csv, bus_future_itin_attr, include_headers=False)  # Skip headers for easier appending
            arcpy.Delete_management(bus_future_itin_view)

            # Append future header/itin data to base/current header/itin files.
            with open(rep_runs_csv, 'a') as writer:
                with open(bus_future_csv, 'r') as reader:
                    for line in reader:
                        writer.write(line)
            os.remove(bus_future_csv)
            with open(rep_runs_itin_csv, 'a') as writer:
                with open(bus_future_itin_csv, 'r') as reader:
                    for line in reader:
                        writer.write(line)
            os.remove(bus_future_itin_csv)

        # Identify any missing itinerary endpoints (1st itin_a/last itin_b).
        scen_nodes = set()
        with open(hwy_n1, 'r') as n1:
            for row in n1:
                attr = row.split()
                if attr[0] == 'a':  # ignore comments and 'a*', which are centroids
                    scen_nodes.add(attr[1])

        itin_endpoints = set()
        with open(rep_runs_itin_csv, 'r') as itin:
            itina_index = rep_runs_itin_attr.index('ITIN_A')
            itinb_index = rep_runs_itin_attr.index('ITIN_B')
            fmeas_index = rep_runs_itin_attr.index('F_MEAS')
            tmeas_index = rep_runs_itin_attr.index('T_MEAS')
            first_line = True
            for row in itin:
                if first_line:
                    first_line = False
                    continue
                attr = row.strip().split(',')
                fmeas = float(attr[fmeas_index])
                tmeas = float(attr[tmeas_index])
                itina = attr[itina_index]
                itinb = attr[itinb_index]
                if fmeas == 0:
                    itin_endpoints.add(itina)
                if tmeas == 100:
                    itin_endpoints.add(itinb)

        missing_endpoints = itin_endpoints - scen_nodes

        # Identify any missing PNR nodes.
        pnr_nodes = set()
        with open(pnr_csv, 'r') as csv_r:
            first_line = True
            for row in csv_r:
                if first_line:
                    first_line = False
                    continue
                attr = row.strip().split(',')
                node = attr[0]
                pnr_nodes.add(node)

        missing_pnr_nodes = pnr_nodes - scen_nodes

        # Replace any missing itinerary endpoints with closest existing node.
        if missing_endpoints:
            replacements = {}
            node_oid_field = MHN.determine_OID_fieldname(MHN.node)
            scen_nodes_query = ''' "NODE" IN ({0}) '''.format(','.join(scen_nodes))
            scen_nodes_lyr = MHN.make_skinny_feature_layer(MHN.node, 'scen_nodes_lyr', [node_oid_field, 'NODE'], scen_nodes_query)
            for node in missing_endpoints:
                missing_node_lyr = MHN.make_skinny_feature_layer(MHN.node, 'missing_node_lyr', [node_oid_field, 'NODE'], '"NODE" = {0}'.format(node))
                closest_node_table = '/'.join((MHN.mem, 'closest_node_table'))
                arcpy.GenerateNearTable_analysis(missing_node_lyr, scen_nodes_lyr, closest_node_table)  # Defaults to single closest feature
                with arcpy.da.SearchCursor(closest_node_table, ['NEAR_FID']) as cursor:
                    for row in cursor:
                        closest_node_query = '"{0}" = {1}'.format(node_oid_field, row[0])
                        closest_node_layer = arcpy.MakeFeatureLayer_management(MHN.node, 'closest_node_lyr', closest_node_query)
                        replacements[node] = [str(row[0]) for row in arcpy.da.SearchCursor(closest_node_layer, ['NODE'])][0]
                arcpy.Delete_management(closest_node_table)

            rep_runs_itin_fixed_csv = rep_runs_itin_csv.replace('.csv', '_fixed.csv')
            with open(rep_runs_itin_fixed_csv, 'w') as new_itin:
                with open(rep_runs_itin_csv, 'r') as old_itin:
                    itina_index = rep_runs_itin_attr.index('ITIN_A')
                    itinb_index = rep_runs_itin_attr.index('ITIN_B')
                    fmeas_index = rep_runs_itin_attr.index('F_MEAS')
                    tmeas_index = rep_runs_itin_attr.index('T_MEAS')
                    first_line = True
                    for row in old_itin:
                        if first_line:
                            new_itin.write(row)
                            first_line = False
                            continue
                        attr = row.strip().split(',')
                        fmeas = float(attr[fmeas_index])
                        tmeas = float(attr[tmeas_index])
                        itina = attr[itina_index]
                        itinb = attr[itinb_index]
                        if fmeas == 0 and itina in missing_endpoints:
                            row = row.replace(itina, replacements[itina])
                        if tmeas == 100 and itinb in missing_endpoints:
                            row = row.replace(itinb, replacements[itinb])
                        new_itin.write(row)

            os.remove(rep_runs_itin_csv)
            rep_runs_itin_csv = rep_runs_itin_fixed_csv

        # Replace any missing PNR nodes with closest existing node *in same zone*.
        if missing_pnr_nodes:
            scen_node_zones = {str(r[0]): r[1] for r in arcpy.da.SearchCursor(MHN.node, ['NODE', MHN.zone_attr])}
            replacements = {}
            node_oid_field = MHN.determine_OID_fieldname(MHN.node)
            for node in missing_pnr_nodes:
                scen_zone_nodes_query = ''' "NODE" IN ({0}) AND "{1}" = {2} '''.format(','.join(scen_nodes), MHN.zone_attr, scen_node_zones[node])
                scen_zone_nodes_lyr = MHN.make_skinny_feature_layer(MHN.node, 'scen_nodes_lyr', [node_oid_field, 'NODE'], scen_zone_nodes_query)
                missing_node_lyr = MHN.make_skinny_feature_layer(MHN.node, 'missing_node_lyr', [node_oid_field, 'NODE'], '"NODE" = {0}'.format(node))
                closest_node_table = '/'.join((MHN.mem, 'closest_node_table'))
                arcpy.GenerateNearTable_analysis(missing_node_lyr, scen_zone_nodes_lyr, closest_node_table)  # Defaults to single closest feature
                with arcpy.da.SearchCursor(closest_node_table, ['NEAR_FID']) as cursor:
                    for row in cursor:
                        closest_node_query = '"{0}" = {1}'.format(node_oid_field, row[0])
                        closest_node_layer = arcpy.MakeFeatureLayer_management(MHN.node, 'closest_node_lyr', closest_node_query)
                        replacements[node] = [str(row[0]) for row in arcpy.da.SearchCursor(closest_node_layer, ['NODE'])][0]
                arcpy.Delete_management(closest_node_table)

            pnr_fixed_csv = pnr_csv.replace('.csv', '_fixed.csv')
            with open(pnr_fixed_csv, 'w') as new_pnr:
                with open(pnr_csv, 'r') as old_pnr:
                    first_line = True
                    for row in old_pnr:
                        if first_line:
                            new_pnr.write(row)
                            first_line = False
                            continue
                        attr = row.strip().split(',')
                        node = attr[0]
                        if node in missing_pnr_nodes:
                            row = row.replace(node, replacements[node])
                        new_pnr.write(row)

            os.remove(pnr_csv)
            pnr_csv = pnr_fixed_csv

        # Call generate_transit_files_2.sas -- creates bus batchin files.
        sas2_sas = os.path.join(MHN.prog_dir, '{0}.sas'.format(sas2_name))
        sas2_output = os.path.join(tran_path, '{0}_{1}.txt'.format(sas2_name, scen))
        sas2_args = (scen_tran_path, scen_hwy_path, rep_runs_csv, rep_runs_itin_csv, replace_csv, pnr_csv,
                     scen, tod, str(min(MHN.centroid_ranges['CBD'])), str(max(MHN.centroid_ranges['CBD'])),
                     str(MHN.max_poe), min(MHN.scenario_years.keys()), MHN.prog_dir, missing_links_csv,
                     link_dict_txt, short_path_txt, path_errors_txt, sas2_output)
        if tod == out_tod_periods[0] and os.path.exists(sas2_output):
            os.remove(sas2_output)  # Delete this before first iteration, or else old version will be appended to.
        MHN.submit_sas(sas2_sas, sas2_log, sas2_lst, sas2_args)
        if not os.path.exists(sas2_log):
            MHN.die('{0} did not run!'.format(sas2_sas))
        elif os.path.exists(sas2_lst) or not os.path.exists(sas2_output):
            MHN.die('{0} did not run successfully. Please review {1}.'.format(sas2_sas, sas2_log))
        elif os.path.exists(path_errors_txt):
            MHN.die('Path errors were encountered. Please review {0}.'.format(path_errors_txt))
        else:
            os.remove(sas2_log)
            os.remove(rep_runs_csv)
            os.remove(rep_runs_itin_csv)
            os.remove(pnr_csv)
            MHN.delete_if_exists(replace_csv)


        # ---------------------------------------------------------------------
        # Generate rail stop data from rail batchin files.
        # ---------------------------------------------------------------------
        def generate_rail_pnt_files(itin_batchin, ntwk_batchin, cta_pnt, metra_pnt):

            # Read in rail network node coordinates
            node_coords = {}

            with open(ntwk_batchin, 'rb') as network:
                section = ''

                for line in network:
                    attr = line.strip().split()
                    if len(attr) == 0:
                        continue

                    # Track section to only process nodes (not lines)
                    elif attr[0] == 't':
                        section = attr[1].lower()

                    # Store all node coords in dict
                    elif section == 'nodes' and attr[0] == 'a':
                        node = int(attr[1])
                        x = float(attr[2])
                        y = float(attr[3])
                        node_coords[node] = (x, y)

            # Determine rail network nodes that serve as stops for CTA/Metra
            cta_stops = set()
            metra_stops = set()

            with open(itin_batchin, 'rb') as itin:
                vtype = ''
                is_stop = True  # First node in file will be a stop

                for line in itin:
                    attr = line.strip().split()
                    if len(attr) == 0 or attr[0] in ('c', 't', 'path=no'):
                        continue

                    # Set mode and first is_stop for header lines
                    elif attr[0].startswith('a'):
                        mode_index = 2 if attr[0] == 'a' else 1  # Allow for space/no space after "a"
                        mode = attr[mode_index].lower()  # 'c' (CTA) or 'm' (Metra)
                        is_stop = True  # First node in itin will be a stop

                    # Add stop nodes to CTA/Metra stop dicts
                    else:
                        if attr[0].startswith('dwt='):
                            anode = int(attr[1])
                        else:
                            anode = int(attr[0])

                        # If stops allowed, add to appropriate stop dict
                        if is_stop:
                            if mode == 'c':
                                cta_stops.add(anode)
                            elif mode == 'm':
                                metra_stops.add(anode)

                        # Update is_stop for *next* anode (dwt applies to bnodes)
                        is_stop = False if 'dwt=#' in line else True

                # Write CTA .pnt file
                cta_w = open(cta_pnt, 'wb')
                for node in sorted(cta_stops):
                    if node in node_coords:
                        cta_w.write('{0},{1},{2}\n'.format(node, node_coords[node][0], node_coords[node][1]))
                cta_w.write('END\n')
                cta_w.close()

                # Write Metra .pnt file
                metra_w = open(metra_pnt, 'wb')
                for node in sorted(metra_stops):
                    if node in node_coords:
                        metra_w.write('{0},{1},{2}\n'.format(node, node_coords[node][0], node_coords[node][1]))
                metra_w.write('END\n')
                metra_w.close()

            return None

        generate_rail_pnt_files(rail_itin, rail_net, cta_stop, metra_stop)


        # ---------------------------------------------------------------------
        # Create transit network links with modes c, m, u, v, w, x, y and z.
        # ---------------------------------------------------------------------
        # Convert PNT files to temporary point feature classes.
        def pnt_file_to_fc(pnt_file, fc_path, fc_name):
            ''' Convert a textfile of coordinates (with additional ID field in
                front) to points. '''
            arcpy.CreateFeatureclass_management(fc_path, fc_name, 'POINT')
            fc = os.sep.join((fc_path, fc_name))
            pnt_id_field = '_'.join((fc_name, 'PNT_ID'))
            arcpy.AddField_management(fc, pnt_id_field, 'LONG')
            with arcpy.da.InsertCursor(fc, [pnt_id_field, 'SHAPE@XY']) as cursor:
                with open(pnt_file, 'r') as in_pts:
                    for row in in_pts:
                        row_list = row.strip().split(',')
                        if len(row_list) == 3:
                            id_num = row_list[0]
                            x_coord = float(row_list[1])
                            y_coord = float(row_list[2])
                            xy = (x_coord, y_coord)
                            cursor.insertRow([id_num, xy])
            return fc

        bus_stop_xy = pnt_file_to_fc(bus_stop, MHN.mem, 'bus_stop_xy')
        cta_bus_xy = pnt_file_to_fc(cta_bus, MHN.mem, 'cta_bus_xy')
        pace_bus_xy = pnt_file_to_fc(pace_bus, MHN.mem, 'pace_bus_xy')
        cta_stop_xy = pnt_file_to_fc(cta_stop, MHN.mem, 'cta_stop_xy')
        metra_stop_xy = pnt_file_to_fc(metra_stop, MHN.mem, 'metra_stop_xy')
        os.remove(bus_stop)
        os.remove(cta_bus)
        os.remove(pace_bus)
        os.remove(cta_stop)
        os.remove(metra_stop)

        # Intersect CTA rail, Metra, and bus stop points with zones.
        zone_suffix = '_z'
        cta_stop_xy_z = os.path.join(MHN.mem, 'cta_stop_xy{0}'.format(zone_suffix))
        metra_stop_xy_z = os.path.join(MHN.mem, 'metra_stop_xy{0}'.format(zone_suffix))
        bus_stop_xy_z = os.path.join(MHN.mem, 'bus_stop_xy{0}'.format(zone_suffix))
        arcpy.Intersect_analysis([cta_stop_xy, zone_lyr], cta_stop_xy_z, 'NO_FID')
        arcpy.Intersect_analysis([metra_stop_xy, zone_lyr], metra_stop_xy_z, 'NO_FID')
        arcpy.Intersect_analysis([bus_stop_xy, zone_lyr], bus_stop_xy_z, 'NO_FID')
        arcpy.Delete_management(cta_stop_xy)
        arcpy.Delete_management(metra_stop_xy)
        arcpy.Delete_management(bus_stop_xy)

        # Create CBD and non-CBD layers for CTA (rail) stops and bus stops.
        cbd_query = '"{0}" >= {1} AND "{0}" <= {2}'.format(MHN.zone_attr, min(MHN.centroid_ranges['CBD']), max(MHN.centroid_ranges['CBD']))
        noncbd_query = '"{0}" < {1} OR "{0}" > {2}'.format(MHN.zone_attr, min(MHN.centroid_ranges['CBD']), max(MHN.centroid_ranges['CBD']))

        cta_cbd_lyr = 'cta_cbd_lyr'
        arcpy.MakeFeatureLayer_management(cta_stop_xy_z, cta_cbd_lyr, cbd_query)
        cta_cbd_fc = os.path.join(MHN.mem, 'cta_cbd_fc')
        arcpy.CopyFeatures_management(cta_cbd_lyr, cta_cbd_fc)

        cta_noncbd_lyr = 'cta_noncdb_lyr'
        arcpy.MakeFeatureLayer_management(cta_stop_xy_z, cta_noncbd_lyr, noncbd_query)
        cta_noncbd_fc = os.path.join(MHN.mem, 'cta_noncbd_fc')
        arcpy.CopyFeatures_management(cta_noncbd_lyr, cta_noncbd_fc)

        bus_cbd_lyr = 'bus_cbd_lyr'
        arcpy.MakeFeatureLayer_management(bus_stop_xy_z, bus_cbd_lyr, cbd_query)
        bus_cbd_fc = os.path.join(MHN.mem, 'bus_cbd_fc')
        arcpy.CopyFeatures_management(bus_cbd_lyr, bus_cbd_fc)

        bus_noncbd_lyr = 'bus_noncdb_lyr'
        arcpy.MakeFeatureLayer_management(bus_stop_xy_z, bus_noncbd_lyr, noncbd_query)
        bus_noncbd_fc = os.path.join(MHN.mem, 'bus_noncbd_fc')
        arcpy.CopyFeatures_management(bus_noncbd_lyr, bus_noncbd_fc)

        # Perform distance calculations
        def calculate_distances(pts_1, pts_1_field, pts_2, pts_2_field, dist_limit, out_csv):
            ''' Create a CSV of all pairs of points in pts_1 & pts_2 within dist_limit
                feet of each other. Inputs cannot be layers; must be FCs. '''
            near_table = os.path.join(MHN.mem, 'near_table')
            arcpy.GenerateNearTable_analysis(pts_1, pts_2, near_table, dist_limit, closest='ALL')
            near_view = 'near_view'
            arcpy.MakeTableView_management(near_table, near_view)

            pts_1_oid_field = MHN.determine_OID_fieldname(pts_1)
            pts_1_view = 'pts_1_view'
            arcpy.MakeTableView_management(pts_1, pts_1_view)
            arcpy.AddJoin_management(near_view, 'IN_FID', pts_1_view, pts_1_oid_field)

            pts_2_oid_field = MHN.determine_OID_fieldname(pts_2)
            pts_2_view = 'pts_2_view'
            arcpy.MakeTableView_management(pts_2, pts_2_view)
            arcpy.AddJoin_management(near_view, 'NEAR_FID', pts_2_view, pts_2_oid_field)

            near_joined = os.sep.join((MHN.mem, 'near_joined'))
            arcpy.CopyRows_management(near_view, near_joined)
            MHN.write_attribute_csv(near_joined, out_csv, [pts_1_field, pts_2_field, 'NEAR_DIST'], include_headers=False)

            arcpy.RemoveJoin_management(near_view)
            arcpy.Delete_management(pts_1_view)
            arcpy.Delete_management(pts_2_view)
            arcpy.Delete_management(near_table)
            arcpy.Delete_management(near_joined)

            return out_csv

        def distance_to_zone_centroid(pts_fc, pts_node_field, pts_zone_field, centroids_fc, centroids_node_field, out_csv):
            ''' Create a CSV of each point in pts_fc, the zone it's in, and the
                distance to that zone's centroid. '''
            centroid_sr = arcpy.Describe(centroids_fc).spatialReference
            centroid_geom = {r[0]: r[1].projectAs(centroid_sr) for r in arcpy.da.SearchCursor(centroids_fc, [centroids_node_field, 'SHAPE@'])}
            w = open(out_csv, 'wb')
            with arcpy.da.SearchCursor(pts_fc, [pts_node_field, pts_zone_field, 'SHAPE@']) as c:
                for node, zone, pt_geom in c:
                    distance = pt_geom.projectAs(centroid_sr).distanceTo(centroid_geom[zone])
                    w.write('{0},{1},{2}\n'.format(node, zone, distance))
            w.close()
            del centroid_geom
            return out_csv


        # -- Mode c: 1/8 mile inside CBD; 1/2 mile outside CBD.
        cbddist_txt = calculate_distances(bus_stop_xy_z, 'bus_stop_xy_PNT_ID', cta_cbd_lyr, 'cta_stop_xy_PNT_ID', 660, os.path.join(scen_tran_path, 'cbddist.txt'))
        ctadist_txt = calculate_distances(bus_stop_xy_z, 'bus_stop_xy_PNT_ID', cta_noncbd_lyr, 'cta_stop_xy_PNT_ID', 2640, os.path.join(scen_tran_path, 'ctadist.txt'))

        # -- Mode m: 1/4 mile from modes B,E; 0.55 miles from modes P,L,Q.
        metracta_txt = calculate_distances(cta_bus_xy, 'cta_bus_xy_PNT_ID', metra_stop_xy_z, 'metra_stop_xy_PNT_ID', 1320, os.path.join(scen_tran_path, 'metracta.txt'))
        metrapace_txt = calculate_distances(pace_bus_xy, 'pace_bus_xy_PNT_ID', metra_stop_xy_z, 'metra_stop_xy_PNT_ID', 2904, os.path.join(scen_tran_path, 'metrapace.txt'))

        # -- Modes u, v, w, x, y & z.
        busz_txt = calculate_distances(bus_cbd_fc, 'bus_stop_xy_PNT_ID', centroid_fc, 'NODE', 7920, os.path.join(scen_tran_path, 'busz.txt'))  # Large search distance; results will be heavily trimmed
        busz2_txt = calculate_distances(bus_noncbd_fc, 'bus_stop_xy_PNT_ID', centroid_fc, 'NODE', 26400, os.path.join(scen_tran_path, 'busz2.txt'))  # Large search distance; results will be heavily trimmed
        ctaz_txt = calculate_distances(cta_cbd_fc, 'cta_stop_xy_PNT_ID', centroid_fc, 'NODE', 2904, os.path.join(scen_tran_path, 'ctaz.txt'))
        ctaz2_txt = calculate_distances(cta_noncbd_fc, 'cta_stop_xy_PNT_ID', centroid_fc, 'NODE', 2904, os.path.join(scen_tran_path, 'ctaz2.txt'))
        metraz_txt = calculate_distances(metra_stop_xy_z, 'metra_stop_xy_PNT_ID', centroid_fc, 'NODE', 2904, os.path.join(scen_tran_path, 'metraz.txt'))

        bcent_txt = distance_to_zone_centroid(bus_stop_xy_z, 'bus_stop_xy_PNT_ID', MHN.zone_attr, centroid_fc, 'NODE', os.path.join(scen_tran_path, 'buscentroids.txt'))

        c1z_txt = MHN.write_attribute_csv(cta_cbd_fc, os.path.join(scen_tran_path, 'c1z.txt'), ['cta_stop_xy_PNT_ID', MHN.zone_attr], include_headers=False)
        c2z_txt = MHN.write_attribute_csv(cta_noncbd_fc, os.path.join(scen_tran_path, 'c2z.txt'), ['cta_stop_xy_PNT_ID', MHN.zone_attr], include_headers=False)
        mz_txt = MHN.write_attribute_csv(metra_stop_xy_z, os.path.join(scen_tran_path, 'mz.txt'), ['metra_stop_xy_PNT_ID', MHN.zone_attr], include_headers=False)

        # Clean up temp point features/layers.
        for fc in (cta_stop_xy_z, metra_stop_xy_z, bus_stop_xy_z, cta_bus_xy, pace_bus_xy, cta_cbd_fc, cta_noncbd_fc, bus_cbd_fc, bus_noncbd_fc):
            arcpy.Delete_management(fc)

        # Call generate_transit_files_3.sas -- writes access.network file.
        sas3_sas = os.path.join(MHN.prog_dir, '{0}.sas'.format(sas3_name))
        sas3_output = os.path.join(scen_tran_path, 'access.network_{0}'.format(tod))
        sas3_args = [scen_tran_path, scen, str(min(MHN.centroid_ranges['CBD'])), str(max(MHN.centroid_ranges['CBD'])), tod]
        MHN.submit_sas(sas3_sas, sas3_log, sas3_lst, sas3_args)
        if not os.path.exists(sas3_log):
            MHN.die('{0} did not run!'.format(sas3_sas))
        elif os.path.exists(sas3_lst) or not os.path.exists(sas3_output):
            MHN.die('{0} did not run successfully. Please review {1}.'.format(sas3_sas, sas3_log))
        else:
            os.remove(sas3_log)
            os.remove(cbddist_txt)
            os.remove(ctadist_txt)
            os.remove(metracta_txt)
            os.remove(metrapace_txt)
            os.remove(busz_txt)
            os.remove(busz2_txt)
            os.remove(ctaz_txt)
            os.remove(ctaz2_txt)
            os.remove(metraz_txt)
            os.remove(bcent_txt)
            os.remove(c1z_txt)
            os.remove(c2z_txt)
            os.remove(mz_txt)
            os.remove(itin_final)

        ### End of TOD loop ###

    # -------------------------------------------------------------------------
    # Merge scenario highway and rail linkshape files into linkshape_X00.in.
    # -------------------------------------------------------------------------
    arcpy.AddMessage('\nMerging Scenario {0} ({1}) highway & rail linkshape files...'.format(scen, str(scen_year)))

    linkshape_hwy = os.path.join(scen_hwy_path, 'highway.linkshape')
    linkshape_rail = os.path.join(scen_tran_path, 'rail.linkshape')
    linkshape_dir = MHN.ensure_dir(os.path.join(root_path, 'linkshape'))
    linkshape_in = os.path.join(linkshape_dir, 'linkshape_{0}.in'.format(scen))

    w = open(linkshape_in, 'w')
    w.write('c HIGHWAY & RAIL LINK SHAPE FILE FOR SCENARIO {0}\n'.format(scen))
    w.write('c {0}\n'.format(MHN.timestamp('%d%b%y').upper()))
    w.write('t linkvertices\n')

    with open(linkshape_hwy, 'r') as r:
        for line in r:
            if line.startswith('a ') or line.startswith('r '):
                w.write(line)

    with open(linkshape_rail, 'r') as r:
        for line in r:
            if line.startswith('a ') or line.startswith('r '):
                w.write(line)

    w.close()

    ### End of scenario loop ###

# -----------------------------------------------------------------------------
#  Clean up script-level data.
# -----------------------------------------------------------------------------
for bus_fc in bus_fc_dict:
    which_bus = bus_fc_dict[bus_fc]
    for tod in out_tod_periods:
        MHN.delete_if_exists(rep_runs_dict[which_bus][tod])
arcpy.Delete_management(MHN.mem)
arcpy.AddMessage('\nAll done!\n')
