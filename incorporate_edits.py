#!/usr/bin/env python
'''
    incorporate_edits.py
    Author: npeterson
    Revised: 5/4/17
    ---------------------------------------------------------------------------
    This script should be run after any geometric edits have been made to the
    Master Highway Network. It will:
      - Verify that all arcs have values for all necessary attributes;
      - Move existing nodes to correct location after arc ends have been moved;
      - Create new nodes where links have been split or new arcs have been
        added; and,
      - Ensure that all nodes have a unique ID (maintaining existing IDs
        whenever possible) and that no nodes overlap each other.

    Requires an ArcGIS for Desktop 10.1+ Advanced license!

'''
import os
import sys
import arcpy
from MHN import MasterHighwayNetwork  # Custom class for MHN processing functionality

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
mhn_gdb_path = arcpy.GetParameterAsText(0)  # MHN geodatabase
MHN = MasterHighwayNetwork(mhn_gdb_path)

#arcpy.AddWarning('\nCurrently updating {0}.'.format(MHN.gdb))

# -----------------------------------------------------------------------------
#  Set diagnostic output locations.
# -----------------------------------------------------------------------------
bad_arcs_shp = os.path.join(MHN.temp_dir, 'bad_arcs.shp')
duplicate_nodes_shp = os.path.join(MHN.temp_dir, 'duplicate_nodes.shp')
overlapping_nodes_shp = os.path.join(MHN.temp_dir, 'overlapping_nodes.shp')


# -----------------------------------------------------------------------------
#  Clean up old temp files, if necessary.
# -----------------------------------------------------------------------------
MHN.delete_if_exists(bad_arcs_shp)
MHN.delete_if_exists(duplicate_nodes_shp)
MHN.delete_if_exists(overlapping_nodes_shp)


# -----------------------------------------------------------------------------
#  Check arcs for all required attributes.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nValidating edits:')

# Make a copy of the unmodified arcs.
temp_arcs = os.path.join(MHN.mem, 'temp_arcs')
arcpy.CopyFeatures_management(MHN.arc, temp_arcs)

# Set null values to 0 or a space.
MHN.set_nulls_to_zero(temp_arcs, ['ANODE','BNODE','DIRECTIONS','TYPE1','TYPE2','THRULANES1','THRULANES2',
                                  'THRULANEWIDTH1','THRULANEWIDTH2','AMPM1','AMPM2','MODES','POSTEDSPEED1',
                                  'POSTEDSPEED2','PARKLANES1','PARKLANES2','SIGIC','CLTL','RRGRADECROSS',
                                  'TOLLSYS','TOLLDOLLARS','NHSIC','CHIBLVD','TRUCKRTE','TRUCKRES','VCLEARANCE','MESO'])
MHN.set_nulls_to_space(temp_arcs, ['BASELINK','ROADNAME','PARKRES1','PARKRES2','SRA','TRUCKRES_UPDATED'])

# Update existing ABB values.
# -- Arcs with ANODE, BNODE and BASELINK:
arcs_with_ABB_lyr = 'arcs_with_ABB_lyr'
arcpy.MakeFeatureLayer_management(temp_arcs, arcs_with_ABB_lyr, ''' "ANODE" <> 0 AND "BNODE" <> 0 AND "BASELINK" <> ' ' ''')
arcpy.CalculateField_management(arcs_with_ABB_lyr, 'ABB', '"{0}-{1}-{2}".format(!ANODE!, !BNODE!, !BASELINK!)', 'PYTHON')
arcpy.Delete_management(arcs_with_ABB_lyr)
# -- Arcs missing ANODE, BNODE or BASELINK:
arcs_without_ABB_lyr = 'arcs_without_ABB_lyr'
arcpy.MakeFeatureLayer_management(temp_arcs, arcs_without_ABB_lyr, ''' "ANODE" = 0 OR "BNODE" = 0 OR "BASELINK" = ' ' ''')
arcpy.CalculateField_management(arcs_without_ABB_lyr, 'ABB', "' '", 'PYTHON')
arcpy.Delete_management(arcs_without_ABB_lyr)

# Check for problems with other fields.
bad_arcs_lyr = 'bad_arcs_lyr'
bad_arcs_query = (
    ''' "BASELINK" = ' ' OR "DIRECTIONS" = '0' '''
    ''' OR ("BASELINK" = '1' AND ("DIRECTIONS" = '0' OR "TYPE1" = '0' OR "THRULANES1" = 0 OR "THRULANEWIDTH1" = 0 OR "AMPM1" = '0' OR "MODES" = '0')) '''
    ''' OR ("BASELINK" = '1' AND "TYPE1" <> '7' AND "POSTEDSPEED1" = 0) '''
    ''' OR ("BASELINK" = '1' AND "DIRECTIONS" = '3' AND ("TYPE2" = '0' OR "THRULANES2" = 0 OR "THRULANEWIDTH2" = 0 OR "AMPM2" = '0')) '''
    ''' OR ("BASELINK" = '1' AND "DIRECTIONS" = '3' AND "TYPE2" <> '7' AND "POSTEDSPEED2" = 0) '''
)
arcpy.MakeFeatureLayer_management(temp_arcs, bad_arcs_lyr, bad_arcs_query)
bad_arcs_count = int(arcpy.GetCount_management(bad_arcs_lyr).getOutput(0))
if bad_arcs_count > 0:
    arcpy.CopyFeatures_management(bad_arcs_lyr, bad_arcs_shp)
    MHN.die('Some arcs are missing required attributes. Check {0} for specific arcs.'.format(bad_arcs_shp))
    raise arcpy.ExecuteError
else:
    arcpy.Delete_management(bad_arcs_lyr)
    arcpy.AddMessage('-- All arcs have all required attributes')


# -----------------------------------------------------------------------------
#  Generate nodes from arcs, to check for changes and errors.
# -----------------------------------------------------------------------------
# Generate ANODES, including a copy with no BNODE field.
anodes = os.path.join(MHN.mem, 'anodes')
anodes_copy = os.path.join(MHN.mem, 'anodes_copy')
arcpy.FeatureVerticesToPoints_management(temp_arcs, anodes, 'START')
arcpy.CopyFeatures_management(anodes, anodes_copy)
arcpy.DeleteField_management(anodes_copy, ['BNODE'])

# Generate BNODES, including a copy with no ANODE field.
bnodes = os.path.join(MHN.mem, 'bnodes')
bnodes_copy = os.path.join(MHN.mem, 'bnodes_copy')
arcpy.FeatureVerticesToPoints_management(temp_arcs, bnodes, 'END')
arcpy.CopyFeatures_management(bnodes, bnodes_copy)
arcpy.DeleteField_management(bnodes_copy, ['ANODE'])


# -----------------------------------------------------------------------------
#  Merge ANODES and BNODES, dissolving to create two sets of points: one with
#  unique ABB values and another with unique NODE values.
# -----------------------------------------------------------------------------
merged_copies = os.path.join(MHN.mem, 'merged_copies')
ab_map = ('NODE "NODE" true true false 4 Long 0 0 ,First,#,{0},ANODE,-1,-1,{1},BNODE,-1,-1;'
          'ABB "ABB" true true false 21 Text 0 0 ,First,#,{0},ABB,-1,-1,{1},ABB,-1,-1').format(anodes_copy, bnodes_copy)
arcpy.Merge_management([anodes_copy, bnodes_copy], merged_copies, ab_map)
arcpy.Delete_management(anodes_copy)
arcpy.Delete_management(bnodes_copy)

# Create unique ABB nodes.
new_nodes_ABB = os.path.join(MHN.mem, 'new_nodes_ABB')
new_nodes_ABB_lyr = 'new_nodes_ABB_lyr'
arcpy.Dissolve_management(merged_copies, new_nodes_ABB, ['ABB'], multi_part=False)
arcpy.AddXY_management(new_nodes_ABB)
arcpy.MakeFeatureLayer_management(new_nodes_ABB, new_nodes_ABB_lyr)

# Create unique NODE nodes.
new_nodes_NODE = os.path.join(MHN.mem, 'new_nodes_NODE')
new_nodes_NODE_lyr = 'new_nodes_NODE_lyr'
arcpy.Dissolve_management(merged_copies, new_nodes_NODE, ['NODE'], multi_part=False)
arcpy.AddXY_management(new_nodes_NODE)
arcpy.MakeFeatureLayer_management(new_nodes_NODE, new_nodes_NODE_lyr)


# -----------------------------------------------------------------------------
#  Determine the current highest NODE value.
# -----------------------------------------------------------------------------
valid_node_ids = set(range(MHN.min_node_id, MHN.max_node_id + 1))
taken_node_ids = set(r[0] for r in arcpy.da.SearchCursor(new_nodes_NODE, ['NODE']))
available_node_ids = sorted(valid_node_ids - taken_node_ids)
if len(available_node_ids) == 0:
    arcpy.AddWarning('\nWARNING: All valid node IDs ({0}-{1}) are currently in use. No new nodes can be added.\n'.format(MHN.min_node_id, MHN.max_node_id))
elif len(available_node_ids) < 100:
    arcpy.AddWarning('\nWARNING: Only {0} valid node IDs ({1}-{2}) are still available.\n'.format(len(available_node_ids), MHN.min_node_id, MHN.max_node_id))


# -----------------------------------------------------------------------------
#  Identify arcs that have been split, and assign a new NODE value to the
#  split-point(s).
# -----------------------------------------------------------------------------
abb_freq_table = os.path.join(MHN.mem, 'abb_freq')
abb_freq_view = 'abb_freq_view'
split_arc_nodes_view = 'split_arc_nodes_view'
split_dict = {}
arcpy.MakeTableView_management(new_nodes_ABB, split_arc_nodes_view, ''' "ABB" <> ' ' ''')
arcpy.Frequency_analysis(split_arc_nodes_view, abb_freq_table, ['ABB'])
arcpy.MakeTableView_management(abb_freq_table, abb_freq_view, '"FREQUENCY" > 2')
split_count = int(arcpy.GetCount_management(abb_freq_view).getOutput(0))
if split_count == 0:
    arcpy.Delete_management(abb_freq_view)
    arcpy.Delete_management(abb_freq_table)
    arcpy.Delete_management(new_nodes_ABB)
    arcpy.AddMessage('-- No existing arcs were split')
else:
    with arcpy.da.SearchCursor(abb_freq_view, ['ABB']) as split_arcs_cursor:
        for split_arc in split_arcs_cursor:
            ABB = split_arc[0]
            anode = int(ABB.split('-')[0])
            bnode = int(ABB.split('-')[1])
            baselink = int(ABB.split('-')[2])
            individual_ABB_lyr = 'individual_ABB_lyr'
            ABB_intersect = os.path.join(MHN.mem, 'ABB_intersect')
            ABB_int_buffer = os.path.join(MHN.mem, 'ABB_int_buffer')
            arcpy.MakeFeatureLayer_management(merged_copies, individual_ABB_lyr, ''' "ABB" = '{0}' '''.format(ABB))
            arcpy.Intersect_analysis([individual_ABB_lyr], ABB_intersect, join_attributes='ONLY_FID')
            arcpy.Delete_management(individual_ABB_lyr)
            # Select By Location against the now-selected point doesn't seem to work reliably, so create a 1-ft. buffer of split-nodes instead:
            arcpy.Buffer_analysis(ABB_intersect, ABB_int_buffer, 0.25)
            arcpy.Delete_management(ABB_intersect)
            arcpy.SelectLayerByLocation_management(new_nodes_NODE_lyr, 'INTERSECT', ABB_int_buffer, selection_type='NEW_SELECTION')
            arcpy.Delete_management(ABB_int_buffer)
            with arcpy.da.UpdateCursor(new_nodes_NODE_lyr, ['NODE','SHAPE@XY']) as new_nodes_NODE_cursor:
                new_node_id_dict = {}
                for new_node_NODE in new_nodes_NODE_cursor:
                    # Assign all nodes in same location the same ID:
                    xy = new_node_NODE[1]
                    if xy not in new_node_id_dict:
                        try:
                            next_avail_id = available_node_ids.pop(0)
                        except IndexError:
                            MHN.die('ERROR: All valid node IDs ({0}-{1}) are already in use! New node(s) cannot be assigned an ID!'.format(MHN.min_node_id, MHN.max_node_id))
                        new_node_id_dict[xy] = next_avail_id
                        if (anode,bnode,baselink) in split_dict:
                            split_dict[(anode,bnode,baselink)].append(next_avail_id)
                        else:
                            split_dict[(anode,bnode,baselink)] = [next_avail_id]
                    new_node_NODE[0] = new_node_id_dict[xy]
                    new_nodes_NODE_cursor.updateRow(new_node_NODE)

    arcpy.Delete_management(abb_freq_view)
    arcpy.Delete_management(abb_freq_table)
    arcpy.Delete_management(new_nodes_ABB)
    arcpy.AddMessage('-- New node values have been assigned for split arcs')


# -----------------------------------------------------------------------------
#  Dissolve arc-generated nodes by NODE field only, to eliminate duplicates.
# -----------------------------------------------------------------------------
new_nodes = os.path.join(MHN.mem, 'new_nodes')
new_nodes_lyr = 'new_nodes_lyr'
arcpy.Dissolve_management(new_nodes_NODE, new_nodes, ['NODE'], multi_part=False)
arcpy.AddXY_management(new_nodes)
arcpy.MakeFeatureLayer_management(new_nodes, new_nodes_lyr)
arcpy.Delete_management(new_nodes_NODE)


# -----------------------------------------------------------------------------
#  Check for duplicate node IDs.
# -----------------------------------------------------------------------------
new_nodes_view = 'new_nodes_view'
id_freq_table = os.path.join(MHN.mem, 'id_freq')
id_freq_view = 'id_freq_view'
arcpy.MakeTableView_management(new_nodes, new_nodes_view, '"NODE" <> 0') #'"NODE" IS NOT NULL AND "NODE" <> 0'
arcpy.Frequency_analysis(new_nodes_view, id_freq_table, ['NODE'])
arcpy.MakeTableView_management(id_freq_table, id_freq_view, '"FREQUENCY" > 1')
duplicate_count = int(arcpy.GetCount_management(id_freq_view).getOutput(0))
if duplicate_count == 0:
    arcpy.Delete_management(id_freq_view)
    arcpy.Delete_management(id_freq_table)
    arcpy.AddMessage('-- No nodes have duplicate IDs')
else:
    duplicates = [duplicate[0] for duplicate in arcpy.da.SearchCursor(id_freq_view, ['NODE'])]
    duplicate_query = ' OR '.join(['"NODE" = {0}'.format(id) for id in duplicates])
    arcpy.SelectLayerByAttribute_management(new_nodes_lyr, 'NEW_SELECTION', duplicate_query)
    duplicate_nodes_temp = os.path.join(MHN.mem, 'duplicate_nodes')
    arcpy.CopyFeatures_management(new_nodes_lyr, duplicate_nodes_temp)
    arcpy.Dissolve_management(duplicate_nodes_temp, duplicate_nodes_shp, ['NODE'], multi_part=True)
    arcpy.Delete_management(duplicate_nodes_temp)
    MHN.die('Some unconnected arcs incorrectly share node values. Check {0} for specific arc endpoints.'.format(duplicate_nodes_shp))
    raise arcpy.ExecuteError


# -----------------------------------------------------------------------------
#  Check for overlapping nodes.
# -----------------------------------------------------------------------------
xy_freq_table = os.path.join(MHN.mem, 'xy_freq')
xy_freq_view = 'xy_freq_view'
arcpy.Frequency_analysis(new_nodes_view, xy_freq_table, ['POINT_X', 'POINT_Y'])
arcpy.MakeTableView_management(xy_freq_table, xy_freq_view, '"FREQUENCY" > 1')
overlap_count = int(arcpy.GetCount_management(xy_freq_view).getOutput(0))
if overlap_count == 0:
    arcpy.Delete_management(xy_freq_view)
    arcpy.Delete_management(xy_freq_table)
    arcpy.AddMessage('-- No nodes overlap each other')
else:
    # Create PointGeometry array containing overlaps, buffer by 3" and select overlapping nodes for export to shapefile.
    overlaps = []
    with arcpy.da.SearchCursor(xy_freq_view, ['POINT_X','POINT_Y']) as overlap_cursor:
        for overlap in overlap_cursor:
            overlap_xy = (overlap[0],overlap[1])
            overlaps.append(overlap_xy)
    point = arcpy.Point()
    overlap_points = []
    for coord_pair in overlaps:
        point.X = coord_pair[0]
        point.Y = coord_pair[1]
        overlap_point = arcpy.PointGeometry(point)
        overlap_points.append(overlap_point)
    overlap_points_buffer = os.path.join(MHN.mem, 'overlap_points_buffer')
    arcpy.Buffer_analysis(overlap_points, overlap_points_buffer, 0.25)
    arcpy.SelectLayerByLocation_management(new_nodes_lyr, 'INTERSECT', overlap_points_buffer, selection_type='NEW_SELECTION')
    arcpy.CopyFeatures_management(new_nodes_lyr, overlapping_nodes_shp)
    MHN.die('Some connected arcs have conflicting ANODE and/or BNODE values. Check {0} for specific arc endpoints.'.format(overlapping_nodes_shp))
    raise arcpy.ExecuteError


# -----------------------------------------------------------------------------
#  Eliminate NULL nodes that are coincident with existing nodes, and assign a
#  new NODE value to those that are not.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nUpdating features (in memory):')
with arcpy.da.UpdateCursor(new_nodes, ['OID@','SHAPE@','NODE'], '"NODE" IS NULL OR "NODE" = 0') as null_nodes_cursor:
    for null_node in null_nodes_cursor:
        OID_att = MHN.determine_OID_fieldname(new_nodes)
        OID = null_node[0]
        null_point = null_node[1]
        non_null_nodes_lyr = 'non_null_nodes_lyr'
        arcpy.MakeFeatureLayer_management(new_nodes, non_null_nodes_lyr, '"{0}" <> {1} AND ("NODE" IS NOT NULL AND "NODE" <> 0)'.format(OID_att, OID))
        # Select By Location against the now-selected point doesn't seem to work reliably, so create a 3" buffer of it instead:
        null_point_buffer = os.path.join(MHN.mem, 'null_point_buffer')
        arcpy.Buffer_analysis(null_point, null_point_buffer, 0.25)
        arcpy.SelectLayerByLocation_management(non_null_nodes_lyr, 'INTERSECT', null_point_buffer, selection_type='NEW_SELECTION')
        arcpy.Delete_management(null_point_buffer)
        intersect_count = int(arcpy.GetCount_management(non_null_nodes_lyr).getOutput(0))
        if intersect_count > 0:
            null_nodes_cursor.deleteRow()
        else:
            try:
                next_avail_id = available_node_ids.pop(0)
            except IndexError:
                MHN.die('ERROR: All valid node IDs ({0}-{1}) are already in use! New node(s) cannot be assigned an ID!'.format(MHN.min_node_id, MHN.max_node_id))
            null_node[2] = next_avail_id
            null_nodes_cursor.updateRow(null_node)
arcpy.AddMessage('-- New NODE values assigned')


# Verify that all Park-n-Ride nodes still exist.
node_ids = set((r[0] for r in arcpy.da.SearchCursor(new_nodes, ['NODE'])))
non_centroid_ids = set((i for i in node_ids if i > MHN.max_poe))
pnr_nodes = set((r[0] for r in arcpy.da.SearchCursor(MHN.pnr, ['NODE'])))
bad_pnr_nodes = pnr_nodes - non_centroid_ids
if bad_pnr_nodes:
    bad_pnr_node_str = ', '.join((str(n) for n in sorted(bad_pnr_nodes)))
    MHN.die(
        '''The following nodes are referenced in {0}, but no longer exist '''
        '''in the network or are zone centroids: {1}. Please update the '''
        '''table to reference only existing, non-centroid nodes.'''
        ''.format(MHN.pnr, bad_pnr_node_str)
    )
else:
    arcpy.AddMessage('-- Park-n-Ride NODE values verified')


# -----------------------------------------------------------------------------
#  Update node/arc attributes.
# -----------------------------------------------------------------------------
# Calculate node ZONE and AREATYPE using Identity tool.
new_nodes_CZ = os.path.join(MHN.mem, 'new_nodes_CZ')
subzone_lyr = MHN.make_skinny_feature_layer(MHN.subzone, 'subzone_lyr', [MHN.zone_attr, MHN.subzone_attr, MHN.capzone_attr])
arcpy.Identity_analysis(new_nodes, subzone_lyr, new_nodes_CZ, 'NO_FID')

arcpy.DeleteIdentical_management(new_nodes_CZ, ['Shape', 'NODE'])  # Delete (arbitrarily) duplicates created from nodes lying exactly on border of 2+ zones/capzones
with arcpy.da.UpdateCursor(new_nodes_CZ, ['NODE', MHN.zone_attr, MHN.subzone_attr, MHN.capzone_attr]) as zoned_nodes_cursor:
    for zoned_node in zoned_nodes_cursor:
        node = zoned_node[0]
        zone = zoned_node[1]
        subzone = zoned_node[2]
        capzone = zoned_node[3]
        if MHN.min_poe <= node <= MHN.max_poe and zone > 0:
            MHN.die('POE {0} is in zone {1}! Please move it outside of the modeling area.'.format(str(node), str(zone)))
            raise arcpy.ExecuteError
        # Set appropriate POE values
        elif MHN.min_poe <= node <= MHN.max_poe and zone == 0:
            zoned_node[1] = node  # POE "zone" = node ID
            zoned_node[3] = 99
            zoned_nodes_cursor.updateRow(zoned_node)
        # Set appropriate external values
        elif node > MHN.max_poe and zone == 0:
            zoned_node[1] = 9999
            zoned_node[3] = 11
            zoned_nodes_cursor.updateRow(zoned_node)
        elif node < MHN.min_poe and node != zone:
            arcpy.AddWarning('-- WARNING: Zone ' + str(node) + ' centroid is in zone ' + str(zone) + '! Please verify that this is intentional.')
        else:
            pass
arcpy.AddMessage('-- Node {0}, {1} & {2} fields recalculated'.format(MHN.zone_attr, MHN.subzone_attr, MHN.capzone_attr))

# Calculate arc ANODE and BNODE values.
anodes_id = os.path.join(MHN.mem, 'anodes_id')
bnodes_id = os.path.join(MHN.mem, 'bnodes_id')
arcpy.Identity_analysis(anodes, new_nodes, anodes_id)
arcpy.Identity_analysis(bnodes, new_nodes, bnodes_id)
anodes_id_dict = MHN.make_attribute_dict(anodes_id, 'ORIG_FID', ['NODE'])
bnodes_id_dict = MHN.make_attribute_dict(bnodes_id, 'ORIG_FID', ['NODE'])
with arcpy.da.UpdateCursor(temp_arcs, ['OID@','ANODE','BNODE']) as arcs_cursor:
    for arc in arcs_cursor:
        OID = arc[0]
        old_a = arc[1]
        old_b = arc[2]
        new_a = anodes_id_dict[OID]['NODE']
        new_b = bnodes_id_dict[OID]['NODE']
        if new_a != old_a or new_b != old_b:
            arc[1] = new_a
            arc[2] = new_b
            arcs_cursor.updateRow(arc)
arcpy.Delete_management(anodes)
arcpy.Delete_management(anodes_id)
arcpy.Delete_management(bnodes)
arcpy.Delete_management(bnodes_id)
arcpy.AddMessage('-- Arc ANODE & BNODE fields recalculated')

# Calculate arc ABB values.
arcpy.CalculateField_management(temp_arcs, 'ABB', '"{0}-{1}-{2}".format(!ANODE!, !BNODE!, !BASELINK!)', 'PYTHON')
arcpy.AddMessage('-- Arc ABB field recalculated')

# Calculate arc MILES values.
miles_update_lyr = 'miles_update_lyr'
arcpy.MakeFeatureLayer_management(temp_arcs, miles_update_lyr, ''' "TYPE1" NOT IN ('6','7') OR "MILES" IS NULL OR "MILES" = 0 ''')
arcpy.CalculateField_management(miles_update_lyr, 'MILES', '!shape.length@miles!', 'PYTHON')
arcpy.AddMessage('-- Arc MILES field recalculated')

# Calculate arc BEARING values.
with arcpy.da.UpdateCursor(temp_arcs, ['SHAPE@','BEARING']) as bearing_cursor:
    for arc in bearing_cursor:
        old_bearing = arc[1]
        new_bearing = MHN.determine_arc_bearing(line_geom=arc[0])
        if new_bearing != old_bearing:
            arc[1] = new_bearing
            bearing_cursor.updateRow(arc)
arcpy.AddMessage('-- Arc BEARING field recalculated')

# Calculate arc TOLLTYPE values.
with arcpy.da.UpdateCursor(temp_arcs, ['TOLLTYPE', 'TYPE1', 'TOLLDOLLARS']) as tolltype_cursor:
    for arc in tolltype_cursor:
        old_tolltype = arc[0]
        new_tolltype = MHN.determine_tolltype(vdf=arc[1], cost=arc[2])
        if new_tolltype != old_tolltype:
            arc[0] = new_tolltype
            tolltype_cursor.updateRow(arc)
arcpy.AddMessage('-- Arc TOLLTYPE field recalculated')


# -----------------------------------------------------------------------------
#  Build dictionary of split links' ABB values, from dict of split-node IDs.
# -----------------------------------------------------------------------------
# Get a dictionary of all new ABB values, with MILES values.
new_ABB_values = MHN.make_attribute_dict(temp_arcs, 'ABB', ['MILES'])

# Initialize and build split_dict_ABB.
split_dict_ABB = {}
for ABB_tuple in split_dict:
    anode = ABB_tuple[0]
    bnode = ABB_tuple[1]
    baselink = ABB_tuple[2]
    split_nodes = split_dict[ABB_tuple]
    available_anodes = [anode] + split_nodes
    available_bnodes = split_nodes + [bnode]
    required_ABB_count = len(available_anodes)  # Each ANODE (or BNODE) must be used once and only once; assumes no flipping
    unordered_ABBs = {}
    while len(available_anodes) > 0:
        test_anode = available_anodes[0]
        failed_attempts = 0
        for test_bnode in available_bnodes:
            ABB_synth = '{0}-{1}-{2}'.format(test_anode, test_bnode, baselink)
            if ABB_synth in new_ABB_values:
                split_miles = new_ABB_values[ABB_synth]['MILES']
                unordered_ABBs[test_anode] = [test_bnode, baselink, split_miles]
                available_anodes.remove(test_anode)
                available_bnodes.remove(test_bnode)
                break
            else:
                failed_attempts += 1
                if failed_attempts == len(available_bnodes):
                    MHN.die('Problem identifying split arc ABB values between ANODE {0} and BNODE {1}! Were any of them flipped?'.format(anode, bnode))
                    raise arcpy.ExecuteError
    total_miles = sum([unordered_ABBs[split_ABB][2] for split_ABB in unordered_ABBs])
    for split_ABB in unordered_ABBs:
        unordered_ABBs[split_ABB][2] /= total_miles  # Convert raw length into share of total
    def order_ABBs(dict, anode_seed, list=[]):
        ''' A recursive function to order ABB values based on key:value pairs
            in the unordered_ABBs dictionary '''
        if len(list) == len(dict):
            return list
        else:
            anode = anode_seed
            bnode = dict[anode_seed][0]
            baselink = dict[anode_seed][1]
            length_ratio = dict[anode_seed][2]
            ABB = '{0}-{1}-{2}'.format(anode, bnode, baselink)
            list.append([ABB, length_ratio])
            return order_ABBs(dict, bnode, list)
    ordered_ABBs = order_ABBs(unordered_ABBs, anode)  # A list of tuples: (ABB, length_ratio)
    for ABB_list in ordered_ABBs:
        index = ordered_ABBs.index(ABB_list)
        start_ratio = sum([ordered_ABBs[i][1] for i in range(index)])
        ABB_list.append(start_ratio)  # Append start_ratio to track "how far along" each segment begins...
    for ABB, length_ratio, start_ratio in ordered_ABBs:
        index = ordered_ABBs.index([ABB, length_ratio, start_ratio])
        if ABB_tuple in split_dict_ABB:  # Check if key exists yet or not
            split_dict_ABB[ABB_tuple].append((ABB, index, start_ratio, length_ratio))
        else:
            split_dict_ABB[ABB_tuple] = [(ABB, index, start_ratio, length_ratio)]


# -----------------------------------------------------------------------------
#  Update route systems.
# -----------------------------------------------------------------------------
# Build dict to store all arc geometries for mix-and-match route-building.
vertices_comprising = MHN.build_geometry_dict(temp_arcs, 'ABB')

arcpy.AddMessage('\nRebuilding route systems (in memory):')

def update_route_system(header, itin, vertices_comprising, split_dict_ABB, new_ABB_values, common_id_field, order_field=None):
    ''' A method for updating any of the MHN's route systems: hwyproj,
        bus_base, bus_current, and bus_future. order_field argument allows for
        separate treatment of hwyproj and the bus routes. '''

    # Copy itinerary table to memory for non-destructive editing
    header_name = MHN.break_path(header)['name']
    itin_name = MHN.break_path(itin)['name']
    arcpy.AddMessage('-- ' + header_name + '...')
    itin_copy_path = MHN.mem
    itin_copy_name = itin_name + '_copy'
    itin_copy = os.path.join(itin_copy_path, itin_copy_name)
    arcpy.CreateTable_management(itin_copy_path, itin_copy_name, itin)

    itin_OID_field = MHN.determine_OID_fieldname(itin)
    itin_dict = MHN.make_attribute_dict(itin, itin_OID_field)

    # Check validity of ABB value on each line, adjusting the itinerary when
    # invalidity is due to a split
    max_itin_OID = max([OID for OID in itin_dict])
    split_itin_dict = {}
    all_itin_OIDs = list(itin_dict.keys())
    all_itin_OIDs.sort()  # For processing in itinerary order, rather than in the dict's pseudo-random order
    bad_itin_OIDs = []
    if order_field:
        order_bump = 0
    for OID in all_itin_OIDs:
        common_id = itin_dict[OID][common_id_field]
        if order_field:
            order = itin_dict[OID][order_field]
            if order == 1:
                order_bump = 0
        ABB = itin_dict[OID]['ABB']
        if ABB != None:
            anode = int(ABB.split('-')[0])
            bnode = int(ABB.split('-')[1])
            baselink = int(ABB.split('-')[2])
        else:
            anode = 0
            bnode = 0
            baselink = 0
        if ABB not in new_ABB_values:
            if not order_field:  # For hwyproj, all deleted links should be removed from coding. Split links will be replaced.
                bad_itin_OIDs.append(OID)
            if (anode,bnode,baselink) in split_dict_ABB:  # If ABB is invalid because it was split, find new ABB values
                ordered_segments = split_dict_ABB[(anode,bnode,baselink)]
                if order_field:
                    bad_itin_OIDs.append(OID)  # For bus routes, only split links should be removed (and replaced).
                    itin_a = itin_dict[OID]['ITIN_A']
                    itin_b = itin_dict[OID]['ITIN_B']
                    if itin_b == anode or itin_a == bnode:
                        backwards = True
                        ordered_segments = ordered_segments[::-1]  # Make a reversed copy of the ordered segments
                    else:
                        backwards = False
                for split_ABB in ordered_segments:
                    split_anode = int(split_ABB[0].split('-')[0])
                    split_bnode = int(split_ABB[0].split('-')[1])
                    split_baselink = int(split_ABB[0].split('-')[2])
                    split_length_ratio = split_ABB[3]
                    max_itin_OID += 1
                    split_itin_dict[max_itin_OID] = itin_dict[OID].copy()
                    split_itin_dict[max_itin_OID]['ABB'] = split_ABB[0]

                    if order_field:
                        if backwards:
                            split_itin_a = split_bnode
                            split_itin_b = split_anode
                            split_start_ratio = 1 - (split_ABB[2] + split_length_ratio)
                        else:
                            split_itin_a = split_anode
                            split_itin_b = split_bnode
                            split_start_ratio = split_ABB[2]

                        # Adjust itinerary nodes and order:
                        split_itin_dict[max_itin_OID]['ITIN_A'] = split_itin_a
                        split_itin_dict[max_itin_OID]['ITIN_B'] = split_itin_b
                        if split_itin_a != itin_a:  # First split segment receives the same order as the original
                            order_bump += 1
                        split_itin_dict[max_itin_OID][order_field] += order_bump

                        # Adjust variables that only apply to original link's itin_b:
                        if split_itin_dict[max_itin_OID]['LAYOVER'] > 0 and split_itin_b != itin_b:
                            split_itin_dict[max_itin_OID]['LAYOVER'] = 0

                        # Apportion length-dependent variables:
                        split_itin_dict[max_itin_OID]['LINE_SERV_TIME'] *= split_length_ratio
                        F_MEAS = split_itin_dict[max_itin_OID]['F_MEAS']
                        T_MEAS = split_itin_dict[max_itin_OID]['T_MEAS']
                        meas_diff = T_MEAS - F_MEAS
                        if header_name == 'bus_future':
                            future = True
                        else:
                            future = False
                        if not future:  # bus_future has no DEP_TIME or ARR_TIME
                            DEP_TIME = split_itin_dict[max_itin_OID]['DEP_TIME']
                            ARR_TIME = split_itin_dict[max_itin_OID]['ARR_TIME']
                            time_diff = ARR_TIME - DEP_TIME
                        if split_itin_a != itin_a:
                            split_itin_dict[max_itin_OID]['F_MEAS'] += meas_diff * split_start_ratio
                            if not future:
                                split_itin_dict[max_itin_OID]['DEP_TIME'] += time_diff * split_start_ratio
                        else:
                            pass  # F_MEAS & DEP_TIME are already correct for itin_a
                        if split_itin_b != itin_b:
                            split_itin_dict[max_itin_OID]['T_MEAS'] = F_MEAS + meas_diff * (split_start_ratio + split_length_ratio)
                            if not future:
                                split_itin_dict[max_itin_OID]['ARR_TIME'] = DEP_TIME + time_diff * (split_start_ratio + split_length_ratio)
                        else:
                            pass  # T_MEAS & ARR_TIME are already correct for itin_b
        else:
            if order_field:
                itin_dict[OID][order_field] += order_bump

    for OID in bad_itin_OIDs:
        del itin_dict[OID]  # Remove invalid ABB records after accounting for splits

    # Combine itinerary dicts, adjust ITIN_ORDER and report new gaps and write
    # updated records to table in memory.
    itin_dict.update(split_itin_dict)
    itin_fields = [field.name for field in arcpy.ListFields(itin_copy) if field.type != 'OID']
    with arcpy.da.InsertCursor(itin_copy, itin_fields) as coding_cursor:
        for OID in itin_dict:
            coding_cursor.insertRow([itin_dict[OID][field] for field in itin_fields])

    # Sort records into a second table in memory.
    itin_updated = os.path.join(MHN.mem, '{0}_itin_updated'.format(header_name))
    if order_field:
        arcpy.Sort_management(itin_copy, itin_updated, [[common_id_field,'ASCENDING'], [order_field,'ASCENDING']])
    else:
        arcpy.Sort_management(itin_copy, itin_updated, [[common_id_field,'ASCENDING']])
    arcpy.Delete_management(itin_copy)

    # Re-build line features.
    header_updated_path = MHN.mem
    header_updated_name = '{0}_updated'.format(header_name)
    header_updated = os.path.join(header_updated_path, header_updated_name)
    arcs_traversed_by = {}
    field_list = ['ABB', common_id_field]
    with arcpy.da.SearchCursor(itin_updated, field_list) as itin_cursor:
        for row in itin_cursor:
            abb = row[0]
            common_id = row[1]
            if common_id in arcs_traversed_by:
                arcs_traversed_by[common_id].append(abb)
            else:
                arcs_traversed_by[common_id] = [abb]

    common_id_list = [row[0] for row in arcpy.da.SearchCursor(header, [common_id_field])]
    arcpy.CreateFeatureclass_management(header_updated_path, header_updated_name, 'POLYLINE', header)
    with arcpy.da.InsertCursor(header_updated, ['SHAPE@', common_id_field]) as routes_cursor:
        for common_id in common_id_list:
            route_vertices = arcpy.Array([vertices_comprising[abb] for abb in arcs_traversed_by[common_id] if abb in vertices_comprising])
            try:
                route = arcpy.Polyline(route_vertices)
                routes_cursor.insertRow([route, common_id])
            except:
                itin_delete_query = ''' "{0}" = '{1}' '''.format(common_id_field, common_id)
                with arcpy.da.UpdateCursor(itin_updated, ['OID@'], itin_delete_query) as itin_delete_cursor:
                    for row in itin_delete_cursor:
                        itin_delete_cursor.deleteRow()
                arcpy.AddWarning(
                    '   - {0} = {1} cannot be rebuilt because the arcs comprising '
                    'it no longer exist (or have new ABB). It cannot be rebuilt '
                    'and is being deleted. Please re-import it if necessary.'.format(common_id_field, common_id)
                )

    # Append the header file attribute values from a search cursor of the original.
    attributes = MHN.make_attribute_dict(header, common_id_field)
    update_fields = [field.name for field in arcpy.ListFields(header) if field.type not in ['OID','Geometry'] and field.name.upper() != 'SHAPE_LENGTH']
    with arcpy.da.UpdateCursor(header_updated, update_fields) as attribute_cursor:
        for row in attribute_cursor:
            common_id = row[update_fields.index(common_id_field)]
            for field in [field for field in update_fields if field != common_id_field]:
                row[update_fields.index(field)] = attributes[common_id][field]
            attribute_cursor.updateRow(row)

    return ((header, header_updated), (itin, itin_updated))


updated_route_systems_list = []
for route_system in MHN.route_systems:
    header = route_system
    itin = MHN.route_systems[route_system][0]
    common_id_field = MHN.route_systems[route_system][1]
    order_field = MHN.route_systems[route_system][2]
    updated_route_system = update_route_system(header, itin, vertices_comprising, split_dict_ABB, new_ABB_values, common_id_field, order_field)
    updated_route_systems_list.append(updated_route_system)


# -----------------------------------------------------------------------------
#  Commit the changes only after everything else has run successfully.
# -----------------------------------------------------------------------------
timestamp = MHN.timestamp()
backup_gdb = MHN.gdb[:-4] + '_' + timestamp + '.gdb'
arcpy.Copy_management(MHN.gdb, backup_gdb)
arcpy.AddWarning('\nGeodatabase temporarily backed up to {0}. (If update fails for any reason, replace {1} with this.)'.format(backup_gdb, MHN.gdb))

arcpy.AddMessage('\nSaving changes to disk...')

# Delete existing relationship classes
for dirpath, dirnames, filenames in arcpy.da.Walk(MHN.gdb, datatype='RelationshipClass'):
    for filename in filenames:
        rel_class = os.path.join(dirpath, filename)
        arcpy.Delete_management(rel_class)

# Replace old arcs.
arcpy.AddMessage('-- {0}...'.format(MHN.arc))
arcpy.TruncateTable_management(MHN.arc)
arcpy.Append_management(temp_arcs, MHN.arc, 'TEST')
arcpy.Delete_management(temp_arcs)

# Replace old nodes.
arcpy.AddMessage('-- {0}...'.format(MHN.node))
arcpy.TruncateTable_management(MHN.node)
arcpy.Append_management(new_nodes_CZ, MHN.node, 'TEST')
arcpy.Delete_management(new_nodes_CZ)

# Replace route system tables and line FCs.
for updated_route_system in updated_route_systems_list:

    # Header feature class:
    header = updated_route_system[0][0]
    header_updated = updated_route_system[0][1]
    arcpy.AddMessage('-- {0}...'.format(header))
    arcpy.TruncateTable_management(header)
    arcpy.Append_management(header_updated, header, 'TEST')
    arcpy.Delete_management(header_updated)

    # Itinerary table:
    itin = updated_route_system[1][0]
    itin_updated = updated_route_system[1][1]
    arcpy.AddMessage('-- {0}...'.format(itin))
    arcpy.TruncateTable_management(itin)
    arcpy.Append_management(itin_updated, itin, 'TEST')
    arcpy.Delete_management(itin_updated)

# Rebuild relationship classes.
arcpy.AddMessage('\nRebuilding relationship classes...')
for route_system in MHN.route_systems:
    header = route_system
    header_name = MHN.break_path(header)['name']
    itin = MHN.route_systems[route_system][0]
    itin_name = MHN.break_path(itin)['name']
    common_id_field = MHN.route_systems[route_system][1]
    rel_arcs = os.path.join(MHN.gdb, 'rel_arcs_to_{0}'.format(itin_name))
    rel_sys = os.path.join(MHN.gdb, 'rel_{0}_to_{1}'.format(itin_name.rsplit('_',1)[0], itin_name.rsplit('_',1)[1]))
    arcpy.CreateRelationshipClass_management(MHN.arc, itin, rel_arcs, 'SIMPLE', itin_name, MHN.arc_name, 'NONE', 'ONE_TO_MANY', 'NONE', 'ABB', 'ABB')
    arcpy.CreateRelationshipClass_management(header, itin, rel_sys, 'COMPOSITE', itin_name, header_name, 'FORWARD', 'ONE_TO_MANY', 'NONE', common_id_field, common_id_field)

rel_pnr = os.path.join(MHN.gdb, 'rel_nodes_to_{0}'.format(MHN.pnr_name))
arcpy.CreateRelationshipClass_management(MHN.node, MHN.pnr, rel_pnr, 'SIMPLE', MHN.pnr_name, MHN.node_name, 'NONE', 'ONE_TO_MANY', 'NONE', 'NODE', 'NODE')

# Clean up.
arcpy.Compact_management(MHN.gdb)
arcpy.Delete_management(MHN.mem)
arcpy.Delete_management(backup_gdb)
arcpy.AddMessage('\nChanges successfully applied!\n')

try:
    arcpy.RefreshActiveView()
except:
    # Must be using ArcGIS Pro...
    pass
