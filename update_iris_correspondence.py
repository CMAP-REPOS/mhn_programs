#!/usr/bin/env python
'''
    update_iris_correspondence.py
    Author: npeterson
    Revised: 12/09/2013
    ---------------------------------------------------------------------------
    Re-generate the MHN2IRIS table with updated correspondences between
    arterial roads. Useful after extensive geometric updates or network
    expansion.

'''
import os
import sys
import arcpy
import MHN

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
iris_fc = arcpy.GetParameterAsText(0)  # Full path to IRIS shapefile
iris_id_field = arcpy.GetParameterAsText(1)  # IRIS field containing unique ID

densify_distance = 30  # Minimum distance (ft) between road vertices
near_distance = 50  # Maximum distance (ft) between MHN/IRIS vertices to consider match
min_match_count = 5  # Minimum number of vertex matches to consider line match


# -----------------------------------------------------------------------------
#  Create temporary (dense) road features and points of their vertices.
# -----------------------------------------------------------------------------
arcpy.AddMessage('\nGenerating dense MHN vertices...')
mhn_arts_fc = MHN.mem + '/mhn_arts'
mhn_arts_vertices_fc = MHN.mem + '/mhn_arts_vertices'
mhn_arts_fields = ['ABB', 'ROADNAME']
mhn_arts_query = ''' "TYPE1" = '1' '''
mhn_arts_lyr = MHN.make_skinny_feature_layer(MHN.arc, 'mhn_arts_lyr', mhn_arts_fields, mhn_arts_query)
arcpy.CopyFeatures_management(mhn_arts_lyr, mhn_arts_fc)
arcpy.Densify_edit(mhn_arts_fc, distance=densify_distance)
arcpy.FeatureVerticesToPoints_management(mhn_arts_fc, mhn_arts_vertices_fc, 'ALL')

arcpy.AddMessage('\nGenerating dense IRIS vertices...')
iris_arts_fc = MHN.mem + '/iris_arts'
iris_arts_vertices_fc = MHN.mem + '/iris_arts_vertices'
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
mhn_near_iris_table = MHN.mem + '/mhn_near_iris'
arcpy.GenerateNearTable_analysis(mhn_arts_vertices_fc, iris_arts_vertices_fc, mhn_near_iris_table, near_distance)

arcpy.AddMessage('\nIdentifying most-matched IRIS link for each MHN link...')
near_mhn_field = 'MHN_ABB'
near_iris_field = 'IRIS_{0}'.format(iris_id_field)

arcpy.AddField_management(mhn_near_iris_table, near_mhn_field, 'TEXT', field_length=13)
arcpy.AddField_management(mhn_near_iris_table, near_iris_field, 'LONG')

mhn_vertices_abb_dict = MHN.make_attribute_dict(mhn_arts_vertices_fc, MHN.determine_OID_fieldname(mhn_arts_vertices_fc), ['ABB'])
iris_vertices_oid_dict = MHN.make_attribute_dict(iris_arts_vertices_fc, MHN.determine_OID_fieldname(iris_arts_vertices_fc), [iris_id_field])

with arcpy.da.UpdateCursor(mhn_near_iris_freq_table, ['IN_FID', 'NEAR_FID', near_mhn_field, near_iris_field]) as cursor:
    for row in cursor:
        mhn_id = row[0]
        iris_id = row[1]
        cursor.updateRow([mhn_id, iris_id, mhn_vertices_abb_dict[mhn_id]['ABB'], iris_vertices_oid_dict[iris_id][iris_id_field]])

mhn_near_iris_freq_table = MHN.mem + '/mhn_near_iris_freq'
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
# Create dictionaries of attributes (road name, rte number) for any matched MHN
# and IRIS links.
matched_mhn_ids = (str(mhn_id) for mhn_id in match_dict)
arcpy.SelectLayerByAttribute_management(mhn_arts_lyr, 'SUBSET_SELECTION', ''' "ABB" IN ('{0}') '''.format("','".join(matched_mhn_ids))
mhn_attr_dict = MHN.make_attribute_dict(mhn_arts_lyr, 'ABB', ['ROADNAME'])

matched_iris_ids = (str(match_dict[mhn_id]) for mhn_id in match_dict)
arcpy.SelectLayerByAttribute_management(iris_arts_lyr, 'SUBSET_SELECTION', ''' "{0}" IN ({1}) '''.format(iris_id_field, ','.join(matched_iris_ids))
iris_attr_dict = MHN.make_attribute_dict(iris_arts_lyr, iris_id_field, ['ROAD_NAME', 'MARKED_RT'])

# Iterate through all potential matches and apply QC tests before writing
# successful matches to a list.
qc_matches = []
for mhn_id in match_dict:
    iris_id = match_dict[mhn_id]
    mhn_name = mhn_attr_dict[mhn_id]['ROADNAME']
    iris_name = iris_attr_dict[iris_id]['ROAD_NAME']
    iris_rte = iris_attr_dict[iris_id]['MARKED_RT']


# -----------------------------------------------------------------------------
#  Write final table to MHN geodatabase.
# -----------------------------------------------------------------------------
