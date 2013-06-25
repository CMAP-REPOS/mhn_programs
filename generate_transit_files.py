#!/usr/bin/env python
'''
    generate_transit_files.py
    Author: npeterson
    Revised: 6/25/13
    ---------------------------------------------------------------------------
    This program creates the Emme transit batchin files needed to model a
    scenario network. The scenario, output path and CT-RAMP flag are passed to
    the script as arguments from the ArcGIS tool.

'''
import os
import sys
import arcpy
import MHN  # Custom library for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
arcpy.env.qualifiedFieldNames = False  # Joined attributes will not have fc name prefix

scen_code = arcpy.GetParameterAsText(0)                                # String, default = '100'
root_path = arcpy.GetParameterAsText(1).replace('\\','/').rstrip('/')  # String, no default
ct_ramp = arcpy.GetParameter(2)                                        # Boolean, default = False

if not os.path.exists(root_path):
    MHN.die("{0} doesn't exist!".format(root_path))
hwy_path = ''.join((root_path, '/highway'))
if not os.path.exists(hwy_path):
    MHN.die('{0} contains no highway folder! Please run the Generate Highway Files tool first.'.format(root_path))
tran_path = ''.join((root_path, '/transit'))
if not os.path.exists(tran_path):
    MHN.die("{0} contains no transit folder! Please run the Master Rail Network's Create Emme Scenario Files tool first.".format(root_path))

sas1_name = 'gtfs_reformat_feed'
sas2_name = 'generate_transit_files_2'
sas3_name = 'generate_transit_files_3'
sas4_name = 'generate_transit_files_4'


# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
sas1_log = ''.join((MHN.temp_dir, '/', sas1_name, '.log'))
sas1_lst = ''.join((MHN.temp_dir, '/', sas1_name, '.lst'))
sas2_log = ''.join((MHN.temp_dir, '/', sas2_name, '.log'))
sas2_lst = ''.join((MHN.temp_dir, '/', sas2_name, '.lst'))
sas3_log = ''.join((MHN.temp_dir, '/', sas3_name, '.log'))
sas3_lst = ''.join((MHN.temp_dir, '/', sas3_name, '.lst'))
sas4_log = ''.join((MHN.temp_dir, '/', sas4_name, '.log'))
sas4_lst = ''.join((MHN.temp_dir, '/', sas4_name, '.lst'))
bus_route_csv = ''.join((MHN.temp_dir, '/bus_route.csv'))
bus_itin_csv = ''.join((MHN.temp_dir, '/bus_itin.csv'))
oneline_itin_txt = ''.join((MHN.temp_dir, '/oneline_itin.txt'))  # gtfs_collapse_routes.py input file (called by gtfs_reformat_feed.sas)
feed_groups_txt = ''.join((MHN.temp_dir, '/feed_groups.txt'))    # gtfs_collapse_routes.py output file
missing_links_csv = ''.join((MHN.out_dir, '/missing_bus_links.csv'))
link_dict_txt = ''.join((MHN.out_dir, '/link_dictionary.txt'))  # shortest_path.py input file (called by generate_transit_files_2.sas)
short_path_txt = ''.join((MHN.out_dir, '/short_path.txt'))      # shortest_path.py output file
path_errors_txt = ''.join((MHN.temp_dir, '/path_errors.txt'))


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(sas1_log)
MHN.delete_if_exists(sas1_lst)
MHN.delete_if_exists(sas2_log)
MHN.delete_if_exists(sas2_lst)
MHN.delete_if_exists(sas3_log)
MHN.delete_if_exists(sas3_lst)
MHN.delete_if_exists(sas4_log)
MHN.delete_if_exists(sas4_lst)
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
centroid_fc = ''.join((MHN.mem, '/centroid_fc'))
arcpy.CopyFeatures_management(centroid_lyr, centroid_fc)

zone_lyr = MHN.make_skinny_feature_layer(MHN.zone, 'zone_lyr', [MHN.zone_attr])


# -----------------------------------------------------------------------------
#  Identify representative runs from GTFS bus itineraries.
# -----------------------------------------------------------------------------
rep_runs_dict = {}
bus_fc_dict = {MHN.bus_base: 'base',
               MHN.bus_current: 'current'}

# Remove base or current from bus_fc_dict, if not used for specified scenario.
if scen_code == 'ALL':
    pass
elif MHN.scenario_years[scen_code] <= MHN.bus_years['base']:
    del bus_fc_dict[MHN.bus_current]
else:
    del bus_fc_dict[MHN.bus_base]

# Identify representative runs for bus_base and/or bus_current, as relevant.
for bus_fc in bus_fc_dict:
    arcpy.AddMessage('\nIdentifying representative runs from {0}...'.format(bus_fc))

    which_bus = bus_fc_dict[bus_fc]

    rep_runs_dict[which_bus] = {}
    for tod in sorted(MHN.tod_periods.keys()):
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
        bus_itin_query = '"{0}" IN (\'{1}\')'.format(bus_id_field, "','".join((bus_id for bus_id in selected_bus_routes)))
        bus_itin_view = MHN.make_skinny_table_view(MHN.route_systems[bus_fc][0], 'bus_itin_view', bus_itin_attr, bus_itin_query)
        MHN.write_attribute_csv(bus_itin_view, bus_itin_csv, bus_itin_attr)
        arcpy.Delete_management(bus_itin_view)

        # Process exported route & itin tables with gtfs_reformat_feed.sas.
        sas1_sas = ''.join((MHN.prog_dir, '/', sas1_name, '.sas'))
        sas1_output = ''.join((MHN.temp_dir, '/bus_', which_bus, '_runs_', tod, '.csv'))
        sas1_args = [MHN.prog_dir, bus_route_csv, bus_itin_csv, oneline_itin_txt, feed_groups_txt, sas1_output, tod]
        MHN.delete_if_exists(sas1_output)
        MHN.submit_sas(sas1_sas, sas1_log, sas1_lst, sas1_args)
        if not os.path.exists(sas1_log):
            MHN.die('{0} did not run!'.format(sas1_sas))
        elif not os.path.exists(feed_groups_txt):
            MHN.die('{0}/gtfs_collapse_routes.py did not run! (Called by {1}.)'.format(MHN.prog_dir, sas1_sas))
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
    all_runs_itin_miles = MHN.mem + '/all_runs_itin_miles_' + which_bus
    arcpy.CopyRows_management(all_runs_itin_view, all_runs_itin_miles)
    arcpy.RemoveJoin_management(all_runs_itin_view)
    arcpy.Delete_management(all_runs_itin_view)
    all_runs_itin_miles_dict[which_bus] = all_runs_itin_miles

# Generate future itinerary joined with MILES, if necessary.
if scen_code != '100':
    arcpy.AddMessage('-- bus_future_itin + MILES')
    future_runs_itin_view = 'future_runs_itin_view'
    arcpy.MakeTableView_management(MHN.route_systems[MHN.bus_future][0], future_runs_itin_view)
    arcpy.AddJoin_management(future_runs_itin_view, 'ABB', arc_miles_view, 'ABB', 'KEEP_ALL')
    future_runs_itin_miles = MHN.mem + '/all_runs_itin_miles_future'
    arcpy.CopyRows_management(future_runs_itin_view, future_runs_itin_miles)
    arcpy.RemoveJoin_management(future_runs_itin_view)
    arcpy.Delete_management(future_runs_itin_view)
    all_runs_itin_miles_dict['future'] = future_runs_itin_miles
    arcpy.Delete_management(arc_miles_view)


# -----------------------------------------------------------------------------
#  Iterate through scenarios, if more than one requested.
# -----------------------------------------------------------------------------
if scen_code == 'ALL':
    scen_list = sorted(MHN.scenario_years.keys())
else:
    scen_list = [scen_code]

for scen in scen_list:
    # Set scenario-specific parameters.
    scen_year = MHN.scenario_years[scen]
    if scen_year <= MHN.bus_years['base']:
        bus_fc = MHN.bus_base
        which_bus = 'base'
    else:
        bus_fc = MHN.bus_current
        which_bus = 'current'

    scen_hwy_path = '/'.join((hwy_path, scen))
    if not os.path.exists(scen_hwy_path):
        MHN.die('{0} contains no {1} folder! Please run the Generate Highway Files tool for this scenario first.'.format(hwy_path, scen))
    scen_tran_path = '/'.join((tran_path, scen))
    if not os.path.exists(scen_tran_path):
        MHN.die("{0} contains no {1} folder! Please run the Master Rail Network's Create Emme Scenario Files tool for this scenario first.".format(tran_path, scen))

    # -------------------------------------------------------------------------
    # Iterate through scenario's TOD periods and write transit batchin files.
    # -------------------------------------------------------------------------
    arcpy.AddMessage('\nGenerating Scenario {0} ({1}) transit files...'.format(scen, str(scen_year)))

    for tod in sorted(MHN.tod_periods.keys()):
        arcpy.AddMessage('-- TOD {0}...'.format(tod.upper()))

        rail_itin = ''.join((scen_tran_path, '/rail.itinerary_', tod))
        rail_net = ''.join((scen_tran_path, '/rail.network_', tod))
        rail_node = ''.join((scen_tran_path, '/railnode.extatt_', tod))
        bus_itin = ''.join((scen_tran_path, '/bus.itinerary_', tod))
        bus_net = ''.join((scen_tran_path, '/bus.network_', tod))
        bus_node = ''.join((scen_tran_path, '/busnode.extatt_', tod))
        bus_stop = ''.join((scen_tran_path, '/busstop.pnt'))
        cta_bus = ''.join((scen_tran_path, '/ctabus.pnt'))
        pace_bus = ''.join((scen_tran_path, '/pacebus.pnt'))
        cta_stop = ''.join((scen_tran_path, '/ctastop.pnt'))
        metra_stop = ''.join((scen_tran_path, '/metrastop.pnt'))
        itin_final = ''.join((scen_tran_path, '/itin.final'))

        if tod == 'am':  # Use TOD 3 highways for AM transit
            hwy_l1 = ''.join((scen_hwy_path, '/', scen, '03.l1'))
            hwy_n1 = ''.join((scen_hwy_path, '/', scen, '03.n1'))
            hwy_n2 = ''.join((scen_hwy_path, '/', scen, '03.n2'))
        else:
            hwy_l1 = ''.join((scen_hwy_path, '/', scen, '0', tod, '.l1'))
            hwy_n1 = ''.join((scen_hwy_path, '/', scen, '0', tod, '.n1'))
            hwy_n2 = ''.join((scen_hwy_path, '/', scen, '0', tod, '.n2'))

        if not (os.path.exists(rail_itin) and os.path.exists(rail_net) and os.path.exists(rail_node)):
            MHN.die("{0} doesn't contain all required rail batchin files! Please run the Master Rail Network's Create Emme Scenario Files tool for this scenario first.".format(scen_tran_path))
        elif not (os.path.exists(hwy_l1) and os.path.exists(hwy_n1) and os.path.exists(hwy_n2)):
            MHN.die("{0} doesn't contain all required highway batchin files! Please run the Generate Highway Files tool for this scenario first.".format(scen_hwy_path))

        # Create a temporary table of TOD's representative runs' header attributes
        bus_lyr = 'bus_lyr'
        arcpy.MakeFeatureLayer_management(bus_fc, bus_lyr)
        bus_id_field = MHN.route_systems[bus_fc][1]
        rep_runs = rep_runs_dict[which_bus][tod]
        arcpy.AddJoin_management(bus_lyr, bus_id_field, rep_runs, 'TRANSIT_LINE', 'KEEP_COMMON')  # 'KEEP_COMMON' excludes unmatched routes
        rep_runs_table = ''.join((MHN.mem, '/rep_runs'))
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
        rep_runs_csv = ''.join((scen_tran_path, '/rep_runs.csv'))
        MHN.write_attribute_csv(rep_runs_view, rep_runs_csv, rep_runs_attr)
        selected_runs = MHN.make_attribute_dict(rep_runs_view, bus_id_field, attr_list=[])
        arcpy.Delete_management(rep_runs_view)
        arcpy.Delete_management(rep_runs_table)

        # Export itineraries for selected runs.
        bus_order_field = MHN.route_systems[bus_fc][2]
        rep_runs_itin_attr = [bus_id_field, 'ITIN_A', 'ITIN_B', bus_order_field, 'LAYOVER', 'DWELL_CODE', 'ZONE_FARE', 'LINE_SERV_TIME', 'TTF', 'F_MEAS', 'T_MEAS', 'MILES']
        rep_runs_itin_query = '"{0}" IN (\'{1}\')'.format(bus_id_field, "','".join((bus_id for bus_id in selected_runs)))
        rep_runs_itin_view = MHN.make_skinny_table_view(all_runs_itin_miles_dict[which_bus], 'rep_runs_itin_view', rep_runs_itin_attr, rep_runs_itin_query)
        rep_runs_itin_csv = ''.join((scen_tran_path, '/rep_runs_itin.csv'))
        MHN.write_attribute_csv(rep_runs_itin_view, rep_runs_itin_csv, rep_runs_itin_attr)
        arcpy.Delete_management(rep_runs_itin_view)

        # Export future coding as necessary.
        replace_csv = ''.join((scen_tran_path, '/replace.csv'))
        if scen != '100':
            # Header data first.
            bus_future_lyr = 'future_lyr'
            arcpy.MakeFeatureLayer_management(MHN.bus_future, bus_future_lyr)
            bus_future_id_field = MHN.route_systems[MHN.bus_future][1]
            bus_future_attr = [bus_future_id_field, 'DESCRIPTION', 'MODE', 'VEHICLE_TYPE', 'SPEED', 'HEADWAY']
            bus_future_query = '"SCENARIO" LIKE \'%{0}%\''.format(scen[0])  # SCENARIO field contains first character of applicable scenario codes
            bus_future_view = MHN.make_skinny_table_view(bus_future_lyr, 'bus_future_view', bus_future_attr, bus_future_query)
            bus_future_csv = ''.join((scen_tran_path, '/bus_future.csv'))
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
            bus_future_itin_query = '"{0}" IN (\'{1}\')'.format(bus_future_id_field, "','".join((bus_future_id for bus_future_id in selected_future_runs)))
            bus_future_itin_view = MHN.make_skinny_table_view(all_runs_itin_miles_dict['future'], 'bus_future_itin_view', bus_future_itin_attr, bus_future_itin_query)
            bus_future_itin_csv = ''.join((scen_tran_path, '/bus_future_itin.csv'))
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


        # Call generate_transit_files_2.sas -- creates bus batchin files.
        sas2_sas = ''.join((MHN.prog_dir, '/', sas2_name, '.sas'))
        sas2_output = ''.join((tran_path, '/', sas2_name, '_', scen, '.txt'))
        sas2_args = (scen_tran_path, scen_hwy_path, rep_runs_csv, rep_runs_itin_csv, replace_csv, scen,
                     tod, str(min(MHN.centroid_ranges['CBD'])), str(max(MHN.centroid_ranges['CBD'])),
                     str(MHN.max_poe), min(MHN.scenario_years.keys()), MHN.prog_dir, missing_links_csv,
                     link_dict_txt, short_path_txt, path_errors_txt, sas2_output)
        if tod == sorted(MHN.tod_periods.keys())[0] and os.path.exists(sas2_output):
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
            MHN.delete_if_exists(replace_csv)

        # Call generate_transit_files_3.sas -- creates rail stop information.
        sas3_sas = ''.join((MHN.prog_dir, '/', sas3_name, '.sas'))
        sas3_args = [rail_itin, rail_net, cta_stop, metra_stop]
        MHN.submit_sas(sas3_sas, sas3_log, sas3_lst, sas3_args)
        if not os.path.exists(sas3_log):
            MHN.die('{0} did not run!'.format(sas3_sas))
        elif os.path.exists(sas3_lst) or not (os.path.exists(cta_stop) and os.path.exists(metra_stop)):
            MHN.die('{0} did not run successfully. Please review {1}.'.format(sas3_sas, sas3_log))
        else:
            arcpy.Delete_management(sas3_log)

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
        cta_stop_xy_z = ''.join((MHN.mem, os.sep, 'cta_stop_xy', zone_suffix))
        metra_stop_xy_z = ''.join((MHN.mem, os.sep, 'metra_stop_xy', zone_suffix))
        bus_stop_xy_z = ''.join((MHN.mem, os.sep, 'bus_stop_xy', zone_suffix))
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
        cta_cbd_fc = ''.join((MHN.mem, '/cta_cbd_fc'))
        arcpy.CopyFeatures_management(cta_cbd_lyr, cta_cbd_fc)

        cta_noncbd_lyr = 'cta_noncdb_lyr'
        arcpy.MakeFeatureLayer_management(cta_stop_xy_z, cta_noncbd_lyr, noncbd_query)
        cta_noncbd_fc = ''.join((MHN.mem, '/cta_noncbd_fc'))
        arcpy.CopyFeatures_management(cta_noncbd_lyr, cta_noncbd_fc)

        bus_cbd_lyr = 'bus_cbd_lyr'
        arcpy.MakeFeatureLayer_management(bus_stop_xy_z, bus_cbd_lyr, cbd_query)
        bus_cbd_fc = ''.join((MHN.mem, '/bus_cbd_fc'))
        arcpy.CopyFeatures_management(bus_cbd_lyr, bus_cbd_fc)

        bus_noncbd_lyr = 'bus_noncdb_lyr'
        arcpy.MakeFeatureLayer_management(bus_stop_xy_z, bus_noncbd_lyr, noncbd_query)
        bus_noncbd_fc = ''.join((MHN.mem, '/bus_noncbd_fc'))
        arcpy.CopyFeatures_management(bus_noncbd_lyr, bus_noncbd_fc)

        # Perform distance calculations
        def calculate_distances(pts_1, pts_1_field, pts_2, pts_2_field, dist_limit, out_csv):
            ''' Create a CSV of all pairs of points in pts_1 & pts_2 within dist_limit
                feet of each other. Inputs cannot be layers; must be FCs. '''
            near_table = os.sep.join((MHN.mem, 'near_table'))
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

        # -- Mode c: 1/8 mile inside CBD; 1/2 mile outside CBD.
        cbddist_txt = calculate_distances(bus_stop_xy_z, 'bus_stop_xy_PNT_ID', cta_cbd_lyr, 'cta_stop_xy_PNT_ID', 660, ''.join((scen_tran_path, '/cbddist.txt')))
        ctadist_txt = calculate_distances(bus_stop_xy_z, 'bus_stop_xy_PNT_ID', cta_noncbd_lyr, 'cta_stop_xy_PNT_ID', 2640, ''.join((scen_tran_path, '/ctadist.txt')))

        # -- Mode m: 1/4 mile from modes B,E; 0.55 miles from modes P,L,Q.
        metracta_txt = calculate_distances(cta_bus_xy, 'cta_bus_xy_PNT_ID', metra_stop_xy_z, 'metra_stop_xy_PNT_ID', 1320, ''.join((scen_tran_path, '/metracta.txt')))
        metrapace_txt = calculate_distances(pace_bus_xy, 'pace_bus_xy_PNT_ID', metra_stop_xy_z, 'metra_stop_xy_PNT_ID', 2904, ''.join((scen_tran_path, '/metrapace.txt')))

        # -- Modes u, v, w, x, y & z.
        busz_txt = calculate_distances(bus_cbd_fc, 'bus_stop_xy_PNT_ID', centroid_fc, 'NODE', 1320, ''.join((scen_tran_path, '/busz.txt')))
        busz2_txt = calculate_distances(bus_noncbd_fc, 'bus_stop_xy_PNT_ID', centroid_fc, 'NODE', 2904, ''.join((scen_tran_path, '/busz2.txt')))
        ctaz_txt = calculate_distances(cta_cbd_fc, 'cta_stop_xy_PNT_ID', centroid_fc, 'NODE', 2904, ''.join((scen_tran_path, '/ctaz.txt')))
        ctaz2_txt = calculate_distances(cta_noncbd_fc, 'cta_stop_xy_PNT_ID', centroid_fc, 'NODE', 2904, ''.join((scen_tran_path, '/ctaz2.txt')))
        metraz_txt = calculate_distances(metra_stop_xy_z, 'metra_stop_xy_PNT_ID', centroid_fc, 'NODE', 2904, ''.join((scen_tran_path, '/metraz.txt')))
        c1z_txt = MHN.write_attribute_csv(cta_cbd_fc, ''.join((scen_tran_path, '/c1z.txt')), ['cta_stop_xy_PNT_ID', MHN.zone_attr], include_headers=False)
        c2z_txt = MHN.write_attribute_csv(cta_noncbd_fc, ''.join((scen_tran_path, '/c2z.txt')), ['cta_stop_xy_PNT_ID', MHN.zone_attr], include_headers=False)
        mz_txt = MHN.write_attribute_csv(metra_stop_xy_z, ''.join((scen_tran_path, '/mz.txt')), ['metra_stop_xy_PNT_ID', MHN.zone_attr], include_headers=False)

        # Clean up temp point features/layers.
        for fc in (cta_stop_xy_z, metra_stop_xy_z, bus_stop_xy_z, cta_bus_xy, pace_bus_xy, cta_cbd_fc, cta_noncbd_fc, bus_cbd_fc, bus_noncbd_fc):
            arcpy.Delete_management(fc)

        # Call generate_transit_files_4.sas -- writes access.network file.
        sas4_sas = ''.join((MHN.prog_dir, '/', sas4_name, '.sas'))
        sas4_output = ''.join((scen_tran_path, '/access.network_', tod))
        sas4_args = [scen_tran_path, scen, str(min(MHN.centroid_ranges['CBD'])), str(max(MHN.centroid_ranges['CBD'])), tod]
        MHN.submit_sas(sas4_sas, sas4_log, sas4_lst, sas4_args)
        if not os.path.exists(sas4_log):
            MHN.die('{0} did not run!'.format(sas4_sas))
        elif os.path.exists(sas4_lst) or not os.path.exists(sas4_output):
            MHN.die('{0} did not run successfully. Please review {1}.'.format(sas4_sas, sas4_log))
        else:
            os.remove(sas4_log)
            os.remove(cbddist_txt)
            os.remove(ctadist_txt)
            os.remove(metracta_txt)
            os.remove(metrapace_txt)
            os.remove(busz_txt)
            os.remove(busz2_txt)
            os.remove(ctaz_txt)
            os.remove(ctaz2_txt)
            os.remove(metraz_txt)
            os.remove(c1z_txt)
            os.remove(c2z_txt)
            os.remove(mz_txt)
            os.remove(itin_final)

        ### End of TOD loop ###

    ### End of scenario loop ###

# -----------------------------------------------------------------------------
#  Clean up script-level data.
# -----------------------------------------------------------------------------
for bus_fc in bus_fc_dict:
    which_bus = bus_fc_dict[bus_fc]
    for tod in sorted(MHN.tod_periods.keys()):
        MHN.delete_if_exists(rep_runs_dict[which_bus][tod])
arcpy.Delete_management(MHN.mem)
arcpy.AddMessage('\nAll done!\n')
