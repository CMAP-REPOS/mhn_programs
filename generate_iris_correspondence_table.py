#!/usr/bin/env python
'''
    generate_iris_correspondence_table.py
    Author: npeterson
    Revised: 1/16/2014
    ---------------------------------------------------------------------------
    Generate an "mhn2iris" correspondence table from the current MHN. Useful
    after extensive geometric updates or network expansion.

'''
import os
import sys
import arcpy
import MHN

arcpy.AddWarning('\nCurrently updating {0}.'.format(MHN.gdb))

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
iris_fc = arcpy.GetParameterAsText(0)  # Full path to IRIS shapefile
iris_id_field = arcpy.GetParameterAsText(1)  # IRIS field containing unique ID
out_workspace = arcpy.GetParameterAsText(2).replace('\\','/').rstrip('/') + '/'  # Output directory
table_name = 'mhn2iris_{0}'.format(MHN.timestamp('%Y%m%d'))

densify_distance = 30  # Minimum distance (ft) between road vertices
near_distance = 50  # Maximum distance (ft) between MHN/IRIS vertices to consider match
min_match_count = 5  # Minimum number of vertex matches to consider line match


# -----------------------------------------------------------------------------
#  Create temporary (dense) road features and points of their vertices.
# -----------------------------------------------------------------------------
temp_gdb = MHN.temp_dir + '/iris_temp.gdb'
MHN.delete_if_exists(temp_gdb)
arcpy.CreateFileGDB_management(MHN.break_path(temp_gdb)['dir'], MHN.break_path(temp_gdb)['name'], 'CURRENT')

arcpy.AddMessage('\nGenerating dense MHN vertices...')
mhn_arts_fc = temp_gdb + '/mhn_arts'
mhn_arts_vertices_fc = temp_gdb + '/mhn_arts_vertices'
mhn_arts_fields = ['ABB', 'ROADNAME']
mhn_arts_query = ''' "TYPE1" = '1' '''
mhn_arts_lyr = MHN.make_skinny_feature_layer(MHN.arc, 'mhn_arts_lyr', mhn_arts_fields, mhn_arts_query)
arcpy.CopyFeatures_management(mhn_arts_lyr, mhn_arts_fc)
arcpy.Densify_edit(mhn_arts_fc, distance=densify_distance)
arcpy.FeatureVerticesToPoints_management(mhn_arts_fc, mhn_arts_vertices_fc, 'ALL')

arcpy.AddMessage('\nGenerating dense IRIS vertices...')
iris_arts_fc = temp_gdb + '/iris_arts'
iris_arts_vertices_fc = temp_gdb + '/iris_arts_vertices'
iris_arts_fields = [iris_id_field, 'ROAD_NAME', 'MARKED_RT']
iris_arts_query = ''' "FCNAME" NOT IN ('Freeway and Expressway','Interstate') AND "COUNTY_NAM" IN ('Boone','Cook','DeKalb','DuPage','Grundy','Kane','Kankakee','Kendall','LaSalle','Lake','Lee','McHenry','Ogle','Will','Winnebago') '''
iris_arts_lyr = MHN.make_skinny_feature_layer(iris_fc, 'iris_arts_lyr', iris_arts_fields, iris_arts_query)
arcpy.CopyFeatures_management(iris_arts_lyr, iris_arts_fc)
arcpy.Densify_edit(iris_arts_fc, distance=densify_distance)
arcpy.FeatureVerticesToPoints_management(iris_arts_fc, iris_arts_vertices_fc, 'ALL')


# -----------------------------------------------------------------------------
#  Generate near table of closest IRIS vertex to each MHN vertex, and then find
#  the most-matched IRIS link for each MHN link.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nGenerating MHN-IRIS vertex near table...')
mhn_near_iris_table = temp_gdb + '/mhn_near_iris'
arcpy.GenerateNearTable_analysis(mhn_arts_vertices_fc, iris_arts_vertices_fc, mhn_near_iris_table, near_distance)

arcpy.AddMessage('\nIdentifying most-matched IRIS link for each MHN link...')
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

mhn_near_iris_freq_table = temp_gdb + '/mhn_near_iris_freq'
arcpy.Frequency_analysis(mhn_near_iris_table, mhn_near_iris_freq_table, [near_mhn_field, near_iris_field])
arcpy.Delete_management(mhn_near_iris_table)
del mhn_near_iris_table, mhn_vertices_abb_dict, iris_vertices_oid_dict

match_dict = {}
with arcpy.da.SearchCursor(mhn_near_iris_freq_table, [near_mhn_field, near_iris_field, 'FREQUENCY']) as cursor:
    for row in cursor:
        mhn_id = row[0]
        iris_id = row[1]
        freq = row[2]
        if mhn_id not in match_dict and freq > min_match_count:
            match_dict[mhn_id] = (iris_id, freq)
        elif mhn_id in match_dict and freq > match_dict[mhn_id][1]:
            match_dict[mhn_id] = (iris_id, freq)

# -----------------------------------------------------------------------------
#  Perform QC tests to filter out unlikely matches.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nRunning QC tests on potential matches...')

# Create dictionaries of attributes (road name, rte number) for any matched MHN
# and IRIS links.
matched_mhn_ids = (str(mhn_id) for mhn_id in match_dict)
arcpy.SelectLayerByAttribute_management(mhn_arts_lyr, 'NEW_SELECTION', ''' "ABB" IN ('{0}') '''.format("','".join(matched_mhn_ids)))
mhn_attr_dict = MHN.make_attribute_dict(mhn_arts_lyr, 'ABB', ['ROADNAME'])

matched_iris_ids = (str(match_dict[mhn_id][0]) for mhn_id in match_dict)
arcpy.SelectLayerByAttribute_management(iris_arts_lyr, 'NEW_SELECTION', ''' "{0}" IN ({1}) '''.format(iris_id_field, ','.join(matched_iris_ids)))
iris_attr_dict = MHN.make_attribute_dict(iris_arts_lyr, iris_id_field, ['ROAD_NAME', 'MARKED_RT'])

# Define some cleaning functions for MHN/IRIS road names & rte numbers.
def clean_name(in_name):
    ''' Remove punctuation, cardinal directions, and suffixes '''
    out_name = in_name.upper()
    # Ignore ramps (mostly in IRIS):
    if ' TO ' not in out_name:
        # Replace punctuation and misc. keywords:
        for string, rep in [('-', ' '), ('/', ' '), ('(', ''), (')', ''), ('.', ''), ("'", ""), ('MARTIN LUTHER KING', 'MLK')]:
            out_name = out_name.replace(string, rep)
        # Remove cardinal directions:
        for cdir in ('N', 'S', 'E', 'W'):
            if out_name.startswith(cdir + ' '):
                out_name = out_name[len(cdir):].strip()
            if out_name.endswith(' ' + cdir):
                out_name = out_name[:-len(cdir)].strip()
        # Remove suffixes (road types):
        for suf in ('AVE', 'AV', 'BLVD', 'CT', 'DR', 'EXPY', 'HWY', 'LN', 'PKWY', 'PKY', 'PL', 'RD', 'ST', 'TR', 'WAY'):
            if out_name.endswith(' ' + suf):
                out_name = out_name[:-len(suf)].strip()
        # Find longest remaining "word":
        out_name = max(out_name.split(' '), key=len)
    else:
        out_name = None
    return out_name

def clean_rte(in_rte):
    ''' Convert IRIS format into probable MHN format '''
    if in_rte.startswith('S'):
        out_rte = 'IL {0}'.format(in_rte[1:].lstrip('0'))
    elif in_rte.startswith('U'):
        out_rte = 'US {0}'.format(in_rte[1:].lstrip('0'))
    else:
        out_rte = None
    return out_rte


# Iterate through all potential matches and apply QC tests before writing
# successful matches to a list.
qc_matches = []
for mhn_id in match_dict:
    iris_id = match_dict[mhn_id][0]
    mhn_name = mhn_attr_dict[mhn_id]['ROADNAME']
    mhn_name_base = clean_name(mhn_name)
    iris_name = iris_attr_dict[iris_id]['ROAD_NAME']
    iris_name_base = clean_name(iris_name)
    iris_rte = clean_rte(iris_attr_dict[iris_id]['MARKED_RT'])

    match = False  # Assume no match

    # Compare names/route numbers for match:
    if mhn_name_base:
        if iris_name_base:
            if mhn_name_base == iris_name_base:
                match = True
            elif iris_name_base in mhn_name:
                match = True
            elif mhn_name_base in iris_name:
                match = True
        elif iris_rte and iris_rte in mhn_name:
            match = True

    # Exclude any mistakenly matched 'upper'/'lower' roads:
    if match:
        if 'LOWER' in mhn_name and 'LOWER' not in iris_name:
            match = False
        elif 'LOWER' not in mhn_name and 'LOWER' in iris_name:
            match = False
        elif 'UPPER' in mhn_name and 'UPPER' not in iris_name:
            match = False
        elif 'UPPER' not in mhn_name and 'UPPER' in iris_name:
            match = False

    # If matched, add to list:
    if match:
        qc_matches.append((mhn_id, iris_id))


# -----------------------------------------------------------------------------
#  Create final table in memory and then write it to MHN geodatabase.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nWriting match table...')
match_table = temp_gdb + '/mhn_iris_match'
match_mhn_field = near_mhn_field
match_iris_field = near_iris_field

arcpy.CreateTable_management(MHN.break_path(match_table)['dir'], MHN.break_path(match_table)['name'])
arcpy.AddField_management(match_table, match_mhn_field, 'TEXT', field_length=13)
arcpy.AddField_management(match_table, match_iris_field, 'LONG')
with arcpy.da.InsertCursor(match_table, [match_mhn_field, match_iris_field]) as cursor:
    for mhn_id, iris_id in qc_matches:
        cursor.insertRow([mhn_id, iris_id])

output_table = arcpy.TableToTable_conversion(match_table, out_workspace, table_name)


# -----------------------------------------------------------------------------
#  Clean up.
# -----------------------------------------------------------------------------
arcpy.Delete_management(temp_gdb)
arcpy.AddMessage('\nAll done! Correspondence table successfully written to {0}\n'.format(output_table))
