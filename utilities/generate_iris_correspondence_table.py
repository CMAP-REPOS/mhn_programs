#!/usr/bin/env python
'''
    generate_iris_correspondence_table.py
    Author: npeterson
    Revised: 8/4/2014
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

# ---------------------------------------------------------------------
#  Set parameters.
# ---------------------------------------------------------------------
iris_fc = arcpy.GetParameterAsText(0)        # Full path to IRIS shapefile
iris_id_field = arcpy.GetParameterAsText(1)  # IRIS unique ID field
mhn_id_field = 'ABB'                         # MHN unique ID field
out_workspace = arcpy.GetParameterAsText(2)  # Output directory
table_name = 'mhn2iris_{0}.dbf'              # Output match table; format with timestamp at time of creation

mhn_buffer_dist = 150  # Only match IRIS links coming within this distance (ft) of a HERE link
densify_distance = 25  # Minimum distance (ft) between road vertices
near_distance = 75     # Maximum distance (ft) between IRIS/HERE vertices to consider match
min_match_count = 5    # Minimum number of vertex matches to consider line match
min_fuzz_score = 60    # Minimum fuzzy string match score for IRIS/HERE names to consider line match

if near_distance < densify_distance * 2:
    arcpy.AddMessage((
        'WARNING: near_distance parameter is less than 2x densify_distance, '
        'which may lead to less effective matching. For best results, set '
        'near_distance to at least double densify_distance.'
    ))


# ---------------------------------------------------------------------
#  Define functions.
# ---------------------------------------------------------------------
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


def make_oid_dict(fc, value_field):
    ''' Create a dictionary of feature class/table attributes, using OID as the
        key and another specified field as the value. '''
    return {r[0]: r[1] for r in arcpy.da.SearchCursor(fc, ['OID@', value_field])}

## An alternative to make_oid_dict(), if background processing is disabled.
## Uses array module: <https://docs.python.org/2/library/array.html>.
#def make_oid_array(fc, value_field):
#    import array
#    oid_array = array.array('L')  # 'L' = unsigned long integer
#    key_field = arcpy.Describe(fc).OIDFieldName
#    with arcpy.da.SearchCursor(fc, ['OID@', value_field]) as c:
#        for r in c:
#            oid, value = r
#            if oid > len(oid_array) - 1:
#                oid_array.extend((0 for x in xrange(oid + 1 - len(oid_array))))
#            oid_array[oid] = int(value)
#    return oid_array


# ---------------------------------------------------------------------
#  Create temporary (dense) road features and points of their vertices.
# ---------------------------------------------------------------------
arcpy.AddMessage('\nInitializing geodatabase...')
temp_gdb_name = 'mhn_iris_temp'
temp_gdb = os.path.join(MHN.temp_dir, temp_gdb_name + '.gdb')
if arcpy.Exists(temp_gdb):
    arcpy.Delete_management(temp_gdb)
arcpy.CreateFileGDB_management(os.path.dirname(temp_gdb), os.path.basename(temp_gdb), 'CURRENT')

# Create a layer of the modeled extent of Illinois, for clipping the MHN and IRIS links:
il_zones_sql = ''' "COUNTY" >= 17000 AND "COUNTY" < 18000 '''
illinois_lyr = MHN.make_skinny_feature_layer(MHN.zone, 'illinois_lyr', il_zones_sql)

# Select IRIS links intersecting Illinois zones
arcpy.AddMessage('Selecting IRIS links in Illinois modeling zones...')
iris_mem_fc = os.path.join(MHN.mem, 'iris')
iris_keep_fields = [iris_id_field, 'ROAD_NAME', 'MARKED_RT', 'MARKED_RT2', 'FCNAME']
iris_lyr = MHN.make_skinny_feature_layer(iris_fc, 'iris_lyr', iris_keep_fields)
arcpy.CopyFeatures_management(iris_lyr, iris_mem_fc)
iris_mem_lyr = 'iris_mem_lyr'
arcpy.MakeFeatureLayer_management(iris_mem_fc, iris_mem_lyr)
arcpy.SelectLayerByLocation_management(iris_mem_lyr, 'INTERSECT', illinois_lyr)

# Copy IRIS & MHN links into temp GDB, projecting IRIS to match MHN projection
arcpy.AddMessage('Copying IRIS & HERE links to geodatabase...')
mhn_fc = os.path.join(temp_gdb, 'mhn')
mhn_keep_fields = [mhn_id_field, 'ROADNAME', 'TYPE1']
base_mhn_sql = ''' "BASELINK" = '1' AND "TYPE1" <> '6' '''
mhn_lyr = MHN.make_skinny_feature_layer(MHN.arc, 'mhn_lyr', mhn_keep_fields, base_mhn_sql)
arcpy.SelectLayerByLocation_management(mhn_lyr, 'INTERSECT', illinois_lyr, selection_type='SUBSET_SELECTION')
arcpy.CopyFeatures_management(mhn_lyr, mhn_fc)

iris_fc = os.path.join(temp_gdb, 'iris')
arcpy.Project_management(iris_mem_lyr, iris_fc, MHN.projection)
arcpy.Delete_management(iris_mem_fc)

# Buffer MHN links
arcpy.AddMessage('Buffering MHN links by {0} feet...'.format(mhn_buffer_dist))
mhn_buffer_fc = os.path.join(temp_gdb, 'mhn_buffer')
arcpy.Buffer_analysis(mhn_fc, mhn_buffer_fc, mhn_buffer_dist)

# Subset IRIS links
arcpy.AddMessage('Subsetting IRIS links...')
iris_subset_lyr = 'iris_subset_lyr'
arcpy.MakeFeatureLayer_management(iris_fc, iris_subset_lyr)
arcpy.SelectLayerByLocation_management(iris_subset_lyr, 'INTERSECT', mhn_buffer_fc)
iris_subset_fc = os.path.join(temp_gdb, 'iris_subset')
arcpy.CopyFeatures_management(iris_subset_lyr, iris_subset_fc)

# Densify IRIS & MHN links and create vertices from dense lines
arcpy.AddMessage('Densifying links and generating vertices...')
arcpy.Densify_edit(mhn_fc, distance=densify_distance)
mhn_vertices_fc = os.path.join(temp_gdb, 'mhn_vertices')
arcpy.FeatureVerticesToPoints_management(mhn_fc, mhn_vertices_fc, 'ALL')

arcpy.Densify_edit(iris_subset_fc, distance=densify_distance)
iris_vertices_fc = os.path.join(temp_gdb, 'iris_vertices')
arcpy.FeatureVerticesToPoints_management(iris_subset_fc, iris_vertices_fc, 'ALL')


# ---------------------------------------------------------------------
#  Define a function to perform link matching.
# ---------------------------------------------------------------------
near_mhn_field = 'MHN_{0}'.format(mhn_id_field)
near_iris_field = 'IRIS_{0}'.format(iris_id_field)

def match_subset_of_links(mhn_vertices_lyr, iris_vertices_lyr, ignore_names=False, subset_near_distance=None):
    ''' For two feature layers (subsets of the IRIS and MHN vertices feature
        classes) return a dictionary of matched links. '''

    if not subset_near_distance:
        subset_near_distance = near_distance

    ###  GENERATE NEAR FREQUENCY TABLE AND ATTACH ID_FIELD VALUES ###
    arcpy.AddMessage('-- Generating vertex OID dictionaries...')
    mhn_vertices_id_dict = make_oid_dict(mhn_vertices_lyr, mhn_id_field)
    iris_vertices_id_dict = make_oid_dict(iris_vertices_lyr, iris_id_field)

    arcpy.AddMessage('-- Generating near-table...')
    near_table = os.path.join(temp_gdb, 'mhn_near_iris')
    arcpy.GenerateNearTable_analysis(mhn_vertices_lyr, iris_vertices_lyr, near_table, subset_near_distance)

    arcpy.AddMessage('-- Calculating frequencies of match candidates...')
    arcpy.AddField_management(near_table, near_mhn_field, 'TEXT', field_length=13)
    arcpy.AddField_management(near_table, near_iris_field, 'LONG')

    with arcpy.da.UpdateCursor(near_table, ['IN_FID', 'NEAR_FID', near_mhn_field, near_iris_field]) as cursor:
        for row in cursor:
            mhn_id = row[0]
            iris_id = row[1]
            cursor.updateRow([mhn_id, iris_id, mhn_vertices_id_dict[mhn_id], iris_vertices_id_dict[iris_id]])

    near_freq_table = os.path.join(temp_gdb, 'mhn_near_iris_freq')
    arcpy.Frequency_analysis(near_table, near_freq_table, [near_mhn_field, near_iris_field])
    arcpy.Delete_management(near_table)
    del mhn_vertices_id_dict, iris_vertices_id_dict

    ###  PERFORM QC TESTS TO FIND LIKELY MATCHES ###
    arcpy.AddMessage('-- Running QC tests to find matches...')

    # Create dictionaries of attributes (road name, rte number) for near table's
    # IRIS and MHN links, as well as link length for MHN links.
    matched_mhn_ids = set([str(row[0]) for row in arcpy.da.SearchCursor(near_freq_table, [near_mhn_field])])
    arcpy.SelectLayerByAttribute_management(mhn_lyr, 'NEW_SELECTION', ''' "{0}" IN ('{1}') '''.format(mhn_id_field, "','".join(matched_mhn_ids)))
    mhn_attr_dict = MHN.make_attribute_dict(mhn_lyr, mhn_id_field, ['ROADNAME'])
    with arcpy.da.SearchCursor(mhn_lyr, [mhn_id_field, 'SHAPE@LENGTH']) as cursor:
        for row in cursor:
            mhn_attr_dict[row[0]]['LENGTH'] = row[1]

    matched_iris_ids = set([str(row[0]) for row in arcpy.da.SearchCursor(near_freq_table, [near_iris_field])])
    iris_clip_lyr = MHN.make_skinny_feature_layer(iris_subset_fc, 'iris_clip_lyr', ['ROAD_NAME', 'MARKED_RT', 'MARKED_RT2'])
    arcpy.SelectLayerByAttribute_management(iris_clip_lyr, 'NEW_SELECTION', ''' "{0}" IN ({1}) '''.format(iris_id_field, ','.join(matched_iris_ids)))
    iris_attr_dict = MHN.make_attribute_dict(iris_clip_lyr, iris_id_field, ['ROAD_NAME', 'MARKED_RT', 'MARKED_RT2'])

    # Create the match dictionary
    match_dict = {}
    with arcpy.da.SearchCursor(near_freq_table, [near_mhn_field, near_iris_field, 'FREQUENCY']) as cursor:
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
            if 'LOWER' not in mhn_name.split() and 'LOWER' in iris_name.split():
                fuzz_score = 0
            elif 'LOWER' in mhn_name.split() and 'LOWER' not in iris_name.split():
                fuzz_score = 0
            else:
                fuzz_score = fuzz.token_set_ratio(mhn_name, iris_combo)  # 0-100: How similar are the names?

            # If MHN link is too short for a match to be possible (or unlikely), reduce match count threshold
            mhn_length = mhn_attr_dict[mhn_id]['LENGTH']
            max_possible_matches = math.floor(mhn_length / densify_distance)
            max_likely_matches = math.ceil(0.6 * max_possible_matches)
            arc_min_freq = min(min_match_count, max_likely_matches)

            # Make initial match if min match count and fuzz_score are okay
            if mhn_id not in match_dict:
                if freq >= arc_min_freq:

                    # Give the benefit of the doubt when ignoring names or either is unnamed
                    if ignore_names or not (mhn_name and iris_combo):
                        match_dict[mhn_id] = (iris_id, freq, fuzz_score, mhn_name, iris_combo)

                    # Otherwise only match if fuzz_score is above minimum threshold
                    elif fuzz_score > min_fuzz_score:
                        match_dict[mhn_id] = (iris_id, freq, fuzz_score, mhn_name, iris_combo)

            # Consider replacing match if new match count is at least as high
            elif freq > match_dict[mhn_id][1]:

                # Give the benefit of the doubt when ignoring names or either is unnamed
                if ignore_names or not (iris_combo and mhn_name):
                    match_dict[mhn_id] = (iris_id, freq, fuzz_score, mhn_name, iris_combo)

                # Otherwise only match if fuzz_score is better (and above minimum threshold)
                elif fuzz_score > max(min_fuzz_score, match_dict[mhn_id][2]):
                    match_dict[mhn_id] = (iris_id, freq, fuzz_score, mhn_name, iris_combo)

            elif freq == match_dict[mhn_id][1]:
                if fuzz_score > max(min_fuzz_score, match_dict[mhn_id][2]):
                    match_dict[mhn_id] = (iris_id, freq, fuzz_score, mhn_name, iris_combo)

    return match_dict


# ---------------------------------------------------------------------
#  Define SQL queries to stratify links into types that may require
#  unique matching procedures.
# ---------------------------------------------------------------------

# -- MHN --
mhn_ramp_qry = ''' "TYPE1" IN ('3', '5') '''

mhn_expy_qry = ''' "TYPE1" IN ('2', '4') '''

mhn_blvd_qry = (
    ''' "TYPE1" = '1' AND ("ROADNAME" LIKE '%WACKER DR%' OR '''
    ''' "ROADNAME" IN ('DREXEL BLVD','DOUGLAS BLVD','GARFIELD BLVD', '''
    ''' 'INDEPENDENCE BLVD')) '''
)

mhn_arts_qry = (
    ''' "TYPE1" = '1' AND NOT ({0}) '''
).format(mhn_blvd_qry)

# -- IRIS --
iris_ramp_qry = ''' UPPER("ROAD_NAME") LIKE '% TO %' '''

iris_expy_qry = (
    ''' ("FCNAME" IN ('Freeway and Expressway', 'Interstate') OR '''
    ''' (UPPER("ROAD_NAME") LIKE '%LAKE SHORE%' AND "MARKED_RT" = 'U041')) '''
    ''' AND NOT ({0}) '''
).format(iris_ramp_qry)

iris_arts_qry = (
    ''' NOT ({0}) AND NOT ({1}) '''
).format(iris_expy_qry, iris_ramp_qry)


# -----------------------------------------------------------------------------
#  Create match dictionaries for each link type.
# -----------------------------------------------------------------------------

# -- BOULEVARDS / DIVIDED ARTERIALS --
arcpy.AddMessage('\nMatching IRIS arterials to MHN divided arterials/boulevards...')

mhn_blvd_vertices_lyr = 'mhn_blvd_vertices_lyr'
arcpy.MakeFeatureLayer_management(mhn_vertices_fc, mhn_blvd_vertices_lyr, mhn_blvd_qry)

iris_arts_vertices_lyr = 'iris_arts_vertices_lyr'
arcpy.MakeFeatureLayer_management(iris_vertices_fc, iris_arts_vertices_lyr, iris_arts_qry)

blvd_near_distance = max(near_distance, 200)
blvd_match_dict = match_subset_of_links(mhn_blvd_vertices_lyr, iris_arts_vertices_lyr, subset_near_distance=blvd_near_distance)


# -- REMAINING ARTERIALS --
arcpy.AddMessage('\nMatching IRIS arterials to remaining MHN arterials...')

mhn_arts_vertices_lyr = 'mhn_arts_vertices_lyr'
arcpy.MakeFeatureLayer_management(mhn_vertices_fc, mhn_arts_vertices_lyr, mhn_arts_qry)

arts_match_dict = match_subset_of_links(mhn_arts_vertices_lyr, iris_arts_vertices_lyr)


# -- RAMPS --
arcpy.AddMessage('\nMatching IRIS ramps to MHN ramps (geometry only)...')

mhn_ramp_vertices_lyr = 'mhn_ramp_vertices_lyr'
arcpy.MakeFeatureLayer_management(mhn_vertices_fc, mhn_ramp_vertices_lyr, mhn_ramp_qry)

iris_ramp_vertices_lyr = 'iris_ramp_vertices_lyr'
arcpy.MakeFeatureLayer_management(iris_vertices_fc, iris_ramp_vertices_lyr, iris_ramp_qry)

ramp_match_dict = match_subset_of_links(mhn_ramp_vertices_lyr, iris_ramp_vertices_lyr, ignore_names=True)


# -- EXPRESSWAYS --
arcpy.AddMessage('\nMatching IRIS expressways to MHN expressways (geometry only)...')

mhn_expy_vertices_lyr = 'mhn_expy_vertices_lyr'
arcpy.MakeFeatureLayer_management(mhn_vertices_fc, mhn_expy_vertices_lyr, mhn_expy_qry)

iris_expy_vertices_lyr = 'iris_expy_vertices_lyr'
arcpy.MakeFeatureLayer_management(iris_vertices_fc, iris_expy_vertices_lyr, iris_expy_qry)

expy_near_distance = max(near_distance, 200)
expy_match_dict = match_subset_of_links(mhn_expy_vertices_lyr, iris_expy_vertices_lyr, ignore_names=True, subset_near_distance=expy_near_distance)


# -----------------------------------------------------------------------------
#  Create final table in memory and then write it to output location.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nWriting match table...')
match_table = os.path.join(temp_gdb, 'mhn_iris_match')
match_mhn_field = near_mhn_field
match_iris_field = near_iris_field

arcpy.CreateTable_management(os.path.dirname(match_table), os.path.basename(match_table))
arcpy.AddField_management(match_table, match_mhn_field, 'TEXT', field_length=13)
arcpy.AddField_management(match_table, match_iris_field, 'LONG')
arcpy.AddField_management(match_table, 'FREQUENCY', 'LONG')
arcpy.AddField_management(match_table, 'FUZZ_SCORE', 'LONG')
arcpy.AddField_management(match_table, 'MHN_NAME', 'TEXT', field_length=50)
arcpy.AddField_management(match_table, 'IRIS_NAME', 'TEXT', field_length=50)

# Insert matches from each dict into table.
with arcpy.da.InsertCursor(match_table, [match_mhn_field, match_iris_field, 'FREQUENCY', 'FUZZ_SCORE', 'MHN_NAME', 'IRIS_NAME']) as cursor:

    # 1. Insert boulevard/divided arterial matches:
    for mhn_id in blvd_match_dict.keys():
        cursor.insertRow([mhn_id] + list(blvd_match_dict[mhn_id]))

    # 2. Insert other arterial matches:
    for mhn_id in arts_match_dict.keys():
        cursor.insertRow([mhn_id] + list(arts_match_dict[mhn_id]))

    # 3. Insert ramp matches:
    for mhn_id in ramp_match_dict.keys():
        cursor.insertRow([mhn_id] + list(ramp_match_dict[mhn_id]))

    # 4. Insert expressway matches:
    for mhn_id in expy_match_dict.keys():
        cursor.insertRow([mhn_id] + list(expy_match_dict[mhn_id]))

table_name = table_name.format(MHN.timestamp('%Y%m%d'))
output_table = arcpy.TableToTable_conversion(match_table, out_workspace, table_name)


# ---------------------------------------------------------------------
#  Wrap up.
# ---------------------------------------------------------------------
arcpy.AddMessage('Cleaning up...')
arcpy.Delete_management(MHN.mem)
arcpy.AddMessage('All done! Correspondence table successfully written to {0}.\n'.format(output_table))
