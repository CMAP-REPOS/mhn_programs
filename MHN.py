#!/usr/bin/env python
'''
    MHN.py
    Author: npeterson
    Revised: 5/21/13
    ---------------------------------------------------------------------------
    A library for importing into MHN processing scripts, containing frequently
    used methods and variables.

    Contents:
      1. Directories & Files
      2. Miscellaneous Parameters
      3. Methods

'''
import os
import sys
import arcpy
arcpy.env.OverwriteOutput = True

# -----------------------------------------------------------------------------
#  1. DIRECTORIES & FILES
# -----------------------------------------------------------------------------
mem = 'in_memory'
default_gdb = 'C:/MHN/mhn.gdb'
#root_dir = 'V:/Secure/Master_Highway'
root_dir = 'C:/MHN'
out_dir = root_dir + '/Output'
prog_dir = root_dir + '/Programs'
temp_dir = root_dir + '/Temp'
#gdb = root_dir + '/mhn.gdb'
gdb = root_dir + '/mhn_test.gdb'
#gdb = root_dir + '/sandbox.gdb'
hwynet_name = 'hwynet'
hwynet = gdb + '/' + hwynet_name
arc_name = 'hwynet_arc'
arc = hwynet + '/' + arc_name
node_name = 'hwynet_node'
node = hwynet + '/' + node_name
hwyproj = hwynet + '/hwyproj'
bus_base = hwynet + '/bus_base'
bus_current = hwynet + '/bus_current'
bus_future = hwynet + '/bus_future'
route_systems = {
                 hwyproj: (gdb + '/hwyproj_coding', 'TIPID', ''),
                 bus_base: (gdb + '/bus_base_itin', 'TRANSIT_LINE', 'ITIN_ORDER'),
                 bus_current: (gdb + '/bus_current_itin', 'TRANSIT_LINE', 'ITIN_ORDER'),
                 bus_future: (gdb + '/bus_future_itin', 'TRANSIT_LINE', 'ITIN_ORDER')
                }
zone_gdb = root_dir + '/zone_systems.gdb'
zone = zone_gdb + '/Zones09'
zone_attr = 'Zone09'
subzone = zone_gdb + '/Subzones09'
subzone_attr = 'Subzone09'
capzone = zone_gdb + '/CapacityZones09'
capzone_attr = 'CapacityZone09'

arcpy.Delete_management(mem)  # Clear memory doing anything else


# -----------------------------------------------------------------------------
#  3. MISCELLANEOUS PARAMETERS
# -----------------------------------------------------------------------------
base_year = 2010  # BASELINK=1 network year, not necessarily scenario 100 (i.e. base_year was recently 2009, while scenario 100 was 2010)

bus_years = {'base': 2010,
             'current': 2012}

centroid_ranges = {'CBD'     : xrange(   1,   48),  # NB. xrange(i,j) is INCLUSIVE of i, EXCLUSIVE of j
                   'Chicago' : xrange(   1,  310),
                   'Cook'    : xrange(   1,  855),
                   'McHenry' : xrange( 855,  959),
                   'Lake'    : xrange( 959, 1134),
                   'Kane'    : xrange(1134, 1279),
                   'DuPage'  : xrange(1279, 1503),
                   'Will'    : xrange(1503, 1691),
                   'Kendall' : xrange(1691, 1712),
                   'CMAP'    : xrange(   1, 1712),
                   'MHN'     : xrange(   1, 1962),
                   'POE'     : xrange(1945, 1962)}

min_poe = min(centroid_ranges['POE'])
max_poe = max(centroid_ranges['POE'])

projection = arcpy.Describe(hwynet).spatialReference

scenario_years = {'100': 2010,
                  '200': 2015,
                  '300': 2020,
                  '400': 2025,
                  '500': 2030,
                  '600': 2040}

min_year = min((year for scen, year in scenario_years.iteritems()))
max_year = max((year for scen, year in scenario_years.iteritems()))

tod_periods = {'1':  ('8PM-6AM',                                   # 1: overnight
                      '"STARTHOUR" >= 20 OR "STARTHOUR" <= 5'),
               '2':  ('6AM-7AM',                                   # 2: AM shoulder 1
                      '"STARTHOUR" = 6'),
               '3':  ('7AM-9AM',                                   # 3: AM peak
                      '"STARTHOUR" IN (7, 8)'),
               '4':  ('9AM-10AM',                                  # 4: AM shoulder 2
                      '"STARTHOUR" = 9'),
               '5':  ('10AM-2PM',                                  # 5: midday
                      '"STARTHOUR" >= 10 AND "STARTHOUR" <= 13'),
               '6':  ('2PM-4PM',                                   # 6: PM shoulder 1
                      '"STARTHOUR" IN (14, 15)'),
               '7':  ('4PM-6PM',                                   # 7: PM peak
                      '"STARTHOUR" IN (16, 17)'),
               '8':  ('6PM-8PM',                                   # 8: PM shoulder 2
                      '"STARTHOUR" IN (18, 19)'),
               'am': ('7AM-9AM',                                   # am: Same as TOD 3, but for buses w/ >50% service in period
                      '"AM_SHARE" >= 0.5')}


# -----------------------------------------------------------------------------
#  2. METHODS
# -----------------------------------------------------------------------------
def break_path(fullpath):
    ''' Splits a full-path string into a dictionary, containing 'dir', 'name'
        and 'ext' values. '''
    split1 = fullpath.rsplit('/', 1)
    directory = split1[0]
    if '.' in split1[1]:
        split2 = split1[1].rsplit('.', 1)
        filename = split2[0]
        extension = '.' + split2[1]
        filename_extension = '.'.join((filename, extension))
    else:
        filename = split1[1]
        extension = ''
        filename_extension = filename
    return {'dir': directory, 'name': filename, 'ext': extension, 'name_ext': filename_extension}


def calculate_itin_measures(itin_table):
    ''' Calculates the F_MEAS and T_MEAS values for each row in an itin table,
        based on the MILES values of the corresponding MHN arc. '''
    abb_miles_dict = make_attribute_dict(arc, 'ABB', attr_list=['MILES'])
    route_miles_dict = {}
    # 1st loop to determine total route lengths.
    with arcpy.da.SearchCursor(itin_table, ['TRANSIT_LINE', 'ABB']) as cursor:
        for row in cursor:
            route = row[0]
            abb = row[1]
            if route in route_miles_dict:
                 route_miles_dict[route] += abb_miles_dict[abb]['MILES']
            else:
                 route_miles_dict[route] = abb_miles_dict[abb]['MILES']
    # 2nd loop to calculate F_MEAS and T_MEAS for each row.
    with arcpy.da.UpdateCursor(itin_table, ['TRANSIT_LINE', 'ITIN_ORDER', 'ABB', 'F_MEAS', 'T_MEAS']) as cursor:
        order_tracker = 0
        cumulative_percent = 0
        for row in cursor:
            route = row[0]
            row_order = row[1]
            abb = row[2]
            if row_order < order_tracker:
                cumulative_percent = 0
            segment_length = abb_miles_dict[abb]['MILES']
            segment_percent = segment_length / route_miles_dict[route] * 100
            row[3] = cumulative_percent
            new_cumulative_percent = cumulative_percent + segment_percent
            row[4] = new_cumulative_percent
            cursor.updateRow(row)
            order_tracker = row_order
            cumulative_percent = new_cumulative_percent
    return itin_table


def delete_if_exists(filepath):
    ''' Check if a file exists, and delete it if so. '''
    if arcpy.Exists(filepath):
        arcpy.Delete_management(filepath)
        message = filepath + ' successfully deleted.'
    else:
        message = filepath + ' does not exist.'
    return message


def determine_arc_bearing(arc):
    ''' Determines the cardinal direction of a single arc, determined from its
        two endpoints. The angle is determined by the atan2() function, and
        after some numeric manipulation is then used to select the correct
        cardinal direction from an ordered list of possibilities. '''
    from math import atan2, degrees, floor
    x1 = arc.firstPoint.X
    y1 = arc.firstPoint.Y
    x2 = arc.lastPoint.X
    y2 = arc.lastPoint.Y
    xdiff = x2 - x1
    ydiff = y2 - y1
    angle = degrees(atan2(ydiff, xdiff))
    index = int(floor(((angle + 22.5) % 360) / 45))
    cardinal_dirs = ('E','NE','N','NW','W','SW','S','SE')  # Order here is critical
    bearing = cardinal_dirs[index]
    return bearing


def determine_OID_fieldname(fc):
    ''' Determines the Object ID fieldname for the specified fc/table. '''
    describe = arcpy.Describe(fc)
    OID_name = describe.OIDFieldName
    return OID_name


def die(error_message):
    ''' End processing prematurely. '''
    arcpy.AddError('\n' + error_message + '\n')
    from sys import exit
    exit()


def ensure_dir(directory):
    ''' Checks for the existence of a directory, creating it if it doesn't
        exist yet. '''
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


def get_yearless_hwyproj():
    ''' Check hwyproj completion years and return list of invalid projects'
        TIPIDs. '''
    common_id_field = route_systems[hwyproj][1]
    invalid_year_query = '"{0}" = 0 OR "{0}" IS NULL'.format('COMPLETION_YEAR')
    invalid_year_lyr = make_skinny_table_view(hwyproj, 'invalid_year_lyr', ['COMPLETION_YEAR', common_id_field], invalid_year_query)
    invalid_year_count = int(arcpy.GetCount_management(invalid_year_lyr).getOutput(0))
    if invalid_year_count > 0:
        return [row[0] for row in arcpy.da.SearchCursor(invalid_year_lyr, [common_id_field])]
    else:
        return []


def make_attribute_dict(fc, key_field, attr_list=['*']):
    ''' Create a dictionary of feature class/table attributes, using OID as the
        key. Default of ['*'] for attr_list (instead of actual attribute names)
        will create a dictionary of all attributes.
        - NOTE 1: when key_field is the OID field, the OID attribute name can
          be fetched by MHN.determine_OID_fieldname(fc).
        - NOTE 2: using attr_list=[] will essentially build a list of unique
          key_field values. '''
    attr_dict = {}
    fc_field_objects = arcpy.ListFields(fc)
    fc_fields = [field.name for field in fc_field_objects if field.type != 'Geometry']
    if attr_list == ['*']:
        valid_fields = fc_fields
    else:
        valid_fields = [field for field in attr_list if field in fc_fields]
    # Ensure that key_field is always the first field in the field list
    cursor_fields = [key_field] + list(set(valid_fields) - set([key_field]))
    with arcpy.da.SearchCursor(fc, cursor_fields) as cursor:
        for row in cursor:
            attr_dict[row[0]] = dict(zip(cursor.fields,row))
    return attr_dict


def make_path(directory, filename, extension=''):
    ''' Combines a directory, name and optional extension to create a full-path
        string for a file. '''
    fullpath = directory.rstrip('/') + '/' + filename
    if extension != '':
        fullpath += '.' + extension.lstrip('.')  # Guarantee 1 (and only 1) '.' in front of extension
    return fullpath


def make_skinny(is_geo, in_obj, out_obj, keep_fields_list=None, where_clause=''):
    ''' Make an ArcGIS Feature Layer or Table View, containing only the fields
        specified in keep_fields_list, using an optional SQL query. Default
        will create a layer/view with NO fields. '''
    field_info_str = ''
    input_fields = arcpy.ListFields(in_obj)
    if not keep_fields_list:
        keep_fields_list = []
    for field in input_fields:
        if field.name in keep_fields_list:
            field_info_str += field.name + ' ' + field.name + ' VISIBLE;'
        else:
            field_info_str += field.name + ' ' + field.name + ' HIDDEN;'
    field_info_str.rstrip(';')  # Remove trailing semicolon
    if is_geo:
        arcpy.MakeFeatureLayer_management(in_obj, out_obj, where_clause, field_info=field_info_str)
    else:
        arcpy.MakeTableView_management(in_obj, out_obj, where_clause, field_info=field_info_str)
    return out_obj

# Wrapper functions for make_skinny()
def make_skinny_feature_layer(fc, lyr, keep_fields_list=None, where_clause=''):
    return make_skinny(True, fc, lyr, keep_fields_list, where_clause)
def make_skinny_table_view(table, view, keep_fields_list=None, where_clause=''):
    return make_skinny(False, table, view, keep_fields_list, where_clause)


def set_nulls(value, fc, fields):
    ''' Recaluclate all null values in a list of specified fields to a
        specified replacement value. '''
    if type(value) is str:
        valid_types = ['String']
    else:
        valid_types = ['String','SmallInteger','Integer','Single','Double']
    matched_fields = [field for field in arcpy.ListFields(fc) if field.name in fields and field.type in valid_types]
    for field in matched_fields:
        if field.type == 'String':
            expression = "'" + str(value) + "'"
        else:
            expression = str(value)
        null_view = 'null_view'
        arcpy.MakeTableView_management(fc, null_view, '"' + field.name + '" IS NULL')
        if int(arcpy.GetCount_management(null_view).getOutput(0)) > 0:
            arcpy.CalculateField_management(null_view, field.name, expression, 'PYTHON_9.3')
        arcpy.Delete_management(null_view)
    return fc

# Wrapper functions for set_nulls()
def set_nulls_to_space(fc, fields):
    return set_nulls(' ', fc, fields)
def set_nulls_to_zero(fc, fields):
    return set_nulls(0, fc, fields)


def submit_sas(sas_file, sas_log, sas_lst, arg_list=None):
    ''' Calls a specified SAS program with optional arguments specified in a
        $-separated string. '''
    if not arg_list:
        arg_str = ''
    else:
        arg_str = '$'.join(arg_list)
    from subprocess import call
    bat = prog_dir + '/sasrun_gdb.bat'
    cmd = [bat, sas_file, arg_str, sas_log, sas_lst]
    return call(cmd)


def timestamp(format='%Y%m%d%H%M%S'):
    ''' Creates a timestamp string, defaulting to the form YYYYMMDDHHMMSS, but
        any standard date formatting is accepted. See docs for details:
        <http://docs.python.org/2/library/datetime.html#strftime-strptime-behavior>. '''
    from datetime import datetime
    timestamp = datetime.now().strftime(format)
    return timestamp


def write_attribute_csv(in_obj, textfile, field_list=None, include_headers=True):
    ''' Write attributes of a feature class/table to a specified text file.
        Input field_list allows output field order to be specified. Defaults to
        all non-shape fields. '''
    all_field_objects = arcpy.ListFields(in_obj)
    valid_field_names = [field.name for field in all_field_objects if field.name != '' and field.type != 'Geometry']
    if not field_list:
        fields = valid_field_names
    else:
        fields = [field for field in field_list if field in valid_field_names]
    csv = open(textfile,'w')
    if include_headers:
        csv.write(','.join(fields) + '\n')
    with arcpy.da.SearchCursor(in_obj, fields) as cursor:
        for row in cursor:
            csv.write(','.join(map(str,row)) + '\n')
    csv.close()
    return textfile
