#!/usr/bin/env python
'''
    generate_iris_correspondence_table.py
    Author: npeterson
    Revised: 7/22/2014
    ---------------------------------------------------------------------------
    Generate an "mhn2iris" correspondence table from the current MHN. Useful
    after extensive geometric updates or network expansion.

    Requires the fuzzywuzzy module! <https://github.com/seatgeek/fuzzywuzzy>

'''
import os
import sys
import math
import arcpy
from fuzzywuzzy import fuzz  # Fuzzy string matching <https://github.com/seatgeek/fuzzywuzzy>

sys.path.append(os.path.abspath(os.path.join(sys.path[0], '..')))  # Add mhn_programs dir to path, so MHN.py can be imported
import MHN  # Custom library for MHN processing functionality

arcpy.AddWarning('\nCurrently generating IRIS correspondence for {0}.'.format(MHN.gdb))

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
iris_fc = arcpy.GetParameterAsText(0)  # Full path to IRIS shapefile
iris_id_field = arcpy.GetParameterAsText(1)  # IRIS field containing unique ID
out_workspace = arcpy.GetParameterAsText(2)  # Output directory
table_name = 'mhn2iris_{0}.dbf'  # Format with timestamp at time of creation

densify_distance = 25  # Minimum distance (ft) between road vertices
near_distance = 75  # Maximum distance (ft) between MHN/IRIS vertices to consider match
min_match_count = 5  # Minimum number of vertex matches to consider line match
min_fuzz_score = 50  # Minimum fuzzy string match score for MHN/IRIS names to consider line match

if near_distance < densify_distance * 2:
    arcpy.AddWarning(('\nWARNING: near_distance parameter is less than 2x densify_distance,'
                      ' which may lead to unexpected matches. For best results,'
                      ' set near_distance to at least 2x densify_distance.'))


# -----------------------------------------------------------------------------
#  Create temporary (dense) road features and points of their vertices.
# -----------------------------------------------------------------------------
temp_gdb = os.path.join(MHN.temp_dir, 'iris_temp.gdb')
MHN.delete_if_exists(temp_gdb)
arcpy.CreateFileGDB_management(MHN.break_path(temp_gdb)['dir'], MHN.break_path(temp_gdb)['name'], 'CURRENT')

# Create a layer of the modeled extent of Illinois, for clipping the MHN and IRIS links:
illinois_lyr = MHN.make_skinny_feature_layer(MHN.zone, 'illinois_lyr', where_clause=''' "COUNTY" LIKE '17%' ''')

arcpy.AddMessage('\nGenerating dense MHN vertices...')
mhn_clipped = os.path.join(MHN.mem, 'mhn_clipped')
arcpy.Clip_analysis(MHN.arc, illinois_lyr, mhn_clipped)
mhn_arts_fc = os.path.join(temp_gdb, 'mhn_arts')
mhn_arts_vertices_fc = os.path.join(temp_gdb, 'mhn_arts_vertices')
mhn_arts_fields = ['ABB', 'ROADNAME']
mhn_arts_query = ''' "TYPE1" = '1' '''
mhn_arts_lyr = MHN.make_skinny_feature_layer(mhn_clipped, 'mhn_arts_lyr', mhn_arts_fields, mhn_arts_query)
arcpy.CopyFeatures_management(mhn_arts_lyr, mhn_arts_fc)
arcpy.Densify_edit(mhn_arts_fc, distance=densify_distance)
arcpy.FeatureVerticesToPoints_management(mhn_arts_fc, mhn_arts_vertices_fc, 'ALL')

arcpy.AddMessage('\nGenerating dense IRIS vertices...')
iris_clipped = os.path.join(MHN.mem, 'iris_clipped')
arcpy.Clip_analysis(iris_fc, illinois_lyr, iris_clipped)
iris_arts_fc = os.path.join(temp_gdb, 'iris_arts')
iris_arts_vertices_fc = os.path.join(temp_gdb, 'iris_arts_vertices')
iris_arts_fields = [iris_id_field, 'ROAD_NAME', 'MARKED_RT', 'MARKED_RT2']
iris_arts_query = ''' "FCNAME" NOT IN ('Freeway and Expressway','Interstate') '''  # Exclude freeways
iris_arts_query += ''' AND "ROAD_NAME" NOT LIKE '% TO %' '''                       # Exclude ramps
iris_arts_lyr = MHN.make_skinny_feature_layer(iris_clipped, 'iris_arts_lyr', iris_arts_fields, iris_arts_query)
arcpy.CopyFeatures_management(iris_arts_lyr, iris_arts_fc)
arcpy.Densify_edit(iris_arts_fc, distance=densify_distance)
arcpy.FeatureVerticesToPoints_management(iris_arts_fc, iris_arts_vertices_fc, 'ALL')


# -----------------------------------------------------------------------------
#  Generate near table of closest IRIS vertex to each MHN vertex, and then find
#  the most-matched IRIS link for each MHN link.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nGenerating MHN-IRIS vertex near table...')

# Enforce large minimum near_distance for specific boulevards, because IRIS only digitized one side...
blvd_near_distance = max(near_distance, 200)
mhn_blvd_vertices_lyr = 'mhn_blvd_vertices_lyr'
mhn_blvd_query = (''' "ROADNAME" IN ('DREXEL BLVD','DOUGLAS BLVD','GARFIELD BLVD','INDEPENDENCE BLVD') '''
                  ''' OR "ROADNAME" LIKE '%WACKER DR%' ''')
mhn_blvd_near_iris_table = os.path.join(temp_gdb, 'mhn_blvd_near_iris')
arcpy.MakeFeatureLayer_management(mhn_arts_vertices_fc, mhn_blvd_vertices_lyr, mhn_blvd_query)
arcpy.GenerateNearTable_analysis(mhn_blvd_vertices_lyr, iris_arts_vertices_fc, mhn_blvd_near_iris_table, blvd_near_distance)
arcpy.Delete_management(mhn_blvd_vertices_lyr)

# ... then use normal near_distance for most MHN arterials and append blvd table
mhn_arts_vertices_lyr = 'mhn_arts_vertices_lyr'
mhn_arts_query = ''' NOT ({0}) '''.format(mhn_blvd_query.strip())
mhn_near_iris_table = os.path.join(temp_gdb, 'mhn_near_iris')
arcpy.MakeFeatureLayer_management(mhn_arts_vertices_fc, mhn_arts_vertices_lyr, mhn_arts_query)
arcpy.GenerateNearTable_analysis(mhn_arts_vertices_lyr, iris_arts_vertices_fc, mhn_near_iris_table, near_distance)
arcpy.Delete_management(mhn_arts_vertices_lyr)
arcpy.Append_management(mhn_blvd_near_iris_table, mhn_near_iris_table)

# Identify vertex match frequencies for each matched pair of links
arcpy.AddMessage('\nCalculating frequencies of match candidates...')
near_mhn_field = 'MHN_ABB'
near_iris_field = 'IRIS_{0}'.format(iris_id_field)

arcpy.AddField_management(mhn_near_iris_table, near_mhn_field, 'TEXT', field_length=13)
arcpy.AddField_management(mhn_near_iris_table, near_iris_field, 'LONG')

mhn_vertices_abb_dict = MHN.make_attribute_dict(mhn_arts_vertices_fc, MHN.determine_OID_fieldname(mhn_arts_vertices_fc), ['ABB'])
iris_vertices_oid_dict = MHN.make_attribute_dict(iris_arts_vertices_fc, MHN.determine_OID_fieldname(iris_arts_vertices_fc), [iris_id_field])

with arcpy.da.UpdateCursor(mhn_near_iris_table, ['IN_FID', 'NEAR_FID', near_mhn_field, near_iris_field]) as cursor:
    for row in cursor:
        mhn_id = row[0]
        iris_id = row[1]
        cursor.updateRow([mhn_id, iris_id, mhn_vertices_abb_dict[mhn_id]['ABB'], iris_vertices_oid_dict[iris_id][iris_id_field]])

mhn_near_iris_freq_table = os.path.join(temp_gdb, 'mhn_near_iris_freq')
arcpy.Frequency_analysis(mhn_near_iris_table, mhn_near_iris_freq_table, [near_mhn_field, near_iris_field])
del mhn_vertices_abb_dict, iris_vertices_oid_dict


# -----------------------------------------------------------------------------
#  Perform QC tests to find likely matches.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nRunning QC tests on potential matches...')

# Create dictionaries of attributes (road name, rte number) for any matched MHN
# and IRIS links, as well as link length for MHN arcs.
matched_mhn_ids = set([row[0] for row in arcpy.da.SearchCursor(mhn_near_iris_freq_table, [near_mhn_field])])
arcpy.SelectLayerByAttribute_management(mhn_arts_lyr, 'NEW_SELECTION', ''' "ABB" IN ('{0}') '''.format("','".join(matched_mhn_ids)))
mhn_attr_dict = MHN.make_attribute_dict(mhn_arts_lyr, 'ABB', ['ROADNAME'])
with arcpy.da.SearchCursor(mhn_arts_lyr, ['ABB', 'SHAPE@LENGTH']) as cursor:
    for row in cursor:
        mhn_attr_dict[row[0]]['LENGTH'] = row[1]

matched_iris_ids = set([str(row[0]) for row in arcpy.da.SearchCursor(mhn_near_iris_freq_table, [near_iris_field])])
arcpy.SelectLayerByAttribute_management(iris_arts_lyr, 'NEW_SELECTION', ''' "{0}" IN ({1}) '''.format(iris_id_field, ','.join(matched_iris_ids)))
iris_attr_dict = MHN.make_attribute_dict(iris_arts_lyr, iris_id_field, ['ROAD_NAME', 'MARKED_RT', 'MARKED_RT2'])

# Define some cleaning functions for MHN/IRIS road names & rte numbers.
def clean_name(in_name):
    ''' Remove punctuation, cardinal directions, and suffixes '''
    out_name = in_name.upper()
    # Ignore ramps (mostly in IRIS):
    if ' TO ' not in out_name and out_name.strip() != 'UNMARKED':
        # Replace punctuation and misc. keywords:
        for string, rep in [('-',' '),('/',' '),('&',''),('(',''),(')',''),('.',''),("'",""),('MARTIN LUTHER KING ','MLK '),('ML KING ','MLK '),('FRT ','FRONTAGE ')]:
            out_name = out_name.replace(string, rep)
        # Remove cardinal directions:
        for cdir in ('N','S','E','W'):
            if out_name.startswith(cdir + ' '):
                out_name = out_name[len(cdir):].strip()
            if out_name.endswith(' ' + cdir):
                out_name = out_name[:-len(cdir)].strip()
        # Remove suffixes (road types and directions):
        for suf in ('NB','SB','EB','WB','AVE','AV','BLVD','CT','DR','EXPY','FWY','HWY','LN','PKWY','PKY','PL','RD','SQ','ST','TR','WAY'):
            if out_name.endswith(' ' + suf) or ' ' + suf + ' ' in out_name:
                out_name = out_name.replace(' ' + suf, '')
    else:
        out_name = ''
    return out_name

def clean_rte(in_rte):
    ''' Convert IRIS format into probable MHN format '''
    if in_rte.startswith('S'):
        out_rte = 'IL {0}'.format(in_rte[1:].lstrip('0'))
    elif in_rte.startswith('U'):
        out_rte = 'US {0}'.format(in_rte[1:].lstrip('0'))
    else:
        out_rte = ''
    return out_rte

match_dict = {}
with arcpy.da.SearchCursor(mhn_near_iris_freq_table, [near_mhn_field, near_iris_field, 'FREQUENCY']) as cursor:
    for row in cursor:
        mhn_id = row[0]
        iris_id = row[1]
        freq = row[2]

        mhn_name = clean_name(mhn_attr_dict[mhn_id]['ROADNAME'])
        iris_name = clean_name(iris_attr_dict[iris_id]['ROAD_NAME'])
        iris_rte = clean_rte(iris_attr_dict[iris_id]['MARKED_RT'])
        iris_rte2 = clean_rte(iris_attr_dict[iris_id]['MARKED_RT2'])
        iris_combo = '{0} {1} {2}'.format(iris_rte, iris_rte2, iris_name).strip()

        # Score names on similarity, ignoring non-"lower" matches (e.g. Lower Wacker Dr)
        if 'LOWER' in mhn_name.split() and 'LOWER' not in iris_name.split():
            fuzz_score = 0
        elif 'LOWER' not in mhn_name.split() and 'LOWER' in iris_name.split():
            fuzz_score = 0
        else:
            fuzz_score = fuzz.token_set_ratio(mhn_name, iris_combo)  # 0-100: How similar are the names?

        # Set tuple of values to save if matched
        match_tuple = (iris_id, freq, fuzz_score, mhn_name, iris_combo)

        # If MHN link is too short for a match to be possible (or likely), reduce match count threshold
        mhn_length = mhn_attr_dict[mhn_id]['LENGTH']
        max_possible_matches = math.floor(mhn_length / densify_distance)
        max_likely_matches = math.ceil(0.5 * max_possible_matches)  # Multiplier is somewhat arbitrary
        arc_min_freq = min(min_match_count, max_likely_matches)

        # Make initial match if min match count and fuzz_score are okay
        if mhn_id not in match_dict:
            if freq >= arc_min_freq:

                # Give the benefit of the doubt when either is unnamed
                if not (mhn_name and iris_combo):
                    match_dict[mhn_id] = match_tuple

                # Otherwise only match if fuzz_score is above minimum threshold
                elif fuzz_score > min_fuzz_score:
                    match_dict[mhn_id] = match_tuple

        # Consider replacing match if new match count is at least as high
        elif freq > match_dict[mhn_id][1]:

            # Give the benefit of the doubt when either is unnamed
            if not (mhn_name and iris_combo):
                match_dict[mhn_id] = match_tuple

            # Otherwise only match if fuzz_score is better (and above minimum threshold)
            elif fuzz_score > max(min_fuzz_score, match_dict[mhn_id][2]):
                match_dict[mhn_id] = match_tuple

        elif freq == match_dict[mhn_id][1]:
            if fuzz_score > max(min_fuzz_score, match_dict[mhn_id][2]):
                match_dict[mhn_id] = match_tuple


# -----------------------------------------------------------------------------
#  Create final table in memory and then write it to MHN geodatabase.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nWriting match table...')
match_table = os.path.join(temp_gdb, 'mhn_iris_match')
match_mhn_field = near_mhn_field
match_iris_field = near_iris_field

arcpy.CreateTable_management(MHN.break_path(match_table)['dir'], MHN.break_path(match_table)['name'])
arcpy.AddField_management(match_table, match_mhn_field, 'TEXT', field_length=13)
arcpy.AddField_management(match_table, match_iris_field, 'LONG')
arcpy.AddField_management(match_table, 'FREQUENCY', 'LONG')
arcpy.AddField_management(match_table, 'FUZZ_SCORE', 'LONG')
arcpy.AddField_management(match_table, 'MHN_NAME', 'TEXT', field_length=50)
arcpy.AddField_management(match_table, 'IRIS_NAME', 'TEXT', field_length=62)
with arcpy.da.InsertCursor(match_table, [match_mhn_field, match_iris_field, 'FREQUENCY', 'FUZZ_SCORE', 'MHN_NAME', 'IRIS_NAME']) as cursor:
    for mhn_id in match_dict.keys():
        cursor.insertRow([mhn_id] + list(match_dict[mhn_id]))

table_name = table_name.format(MHN.timestamp('%Y%m%d'))
output_table = arcpy.TableToTable_conversion(match_table, out_workspace, table_name)


# -----------------------------------------------------------------------------
#  Clean up.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nCleaning up...')
arcpy.Delete_management(MHN.mem)
arcpy.AddMessage('\nAll done! Correspondence table successfully written to {0}\n'.format(output_table))
