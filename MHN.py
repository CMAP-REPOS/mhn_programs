#!/usr/bin/env python
'''
    MHN.py
    Author: npeterson
    Revised: 1/21/22
    ---------------------------------------------------------------------------
    A class for importing into MHN processing scripts, containing frequently
    used methods and variables.

'''
import os
import sys
import arcpy

class MasterHighwayNetwork(object):
    ''' An object containing properties and methods relating to the MHN processing
        scripts and a specified MHN geodatabase. '''

    # -----------------------------------------------------------------------------
    #  SET GDB-AGNOSTIC VARIABLES
    # -----------------------------------------------------------------------------
    base_year = 2015  # BASELINK=1 network year, not necessarily scenario 100 (i.e. base_year was recently 2009, while scenario 100 was 2010)

    bus_years = {
        'base':    2015,
        'current': 2016
    }

    centroid_ranges = {
        'CBD':     range(   1,   48),  # NB. range(i,j) includes i & excludes j
        'Chicago': range(   1,  718),
        'Cook':    range(   1, 1733),
        'McHenry': range(2584, 2703),
        'Lake':    range(2326, 2584),
        'Kane':    range(2112, 2305),
        'DuPage':  range(1733, 2112),
        'Will':    range(2703, 2927),
        'Kendall': range(2305, 2326),
        'MHN':     range(   1, 3650),
        'POE':     range(3633, 3650),
        'CMAP': {
            '7_Counties':  range(   1, 2927),
            'Grundy_Part': range(2949, 2950),
            'DeKalb_Part': range(2977, 2978)
        }

        # ## zones09 (C18Q3 and earlier)
        # 'CBD':     range(   1,   48),  # NB. range(i,j) includes i & excludes j
        # 'Chicago': range(   1,  310),
        # 'Cook':    range(   1,  855),
        # 'McHenry': range( 855,  959),
        # 'Lake':    range( 959, 1134),
        # 'Kane':    range(1134, 1279),
        # 'DuPage':  range(1279, 1503),
        # 'Will':    range(1503, 1691),
        # 'Kendall': range(1691, 1712),
        # 'CMAP':    range(   1, 1712),
        # 'MHN':     range(   1, 1962),
        # 'POE':     range(1945, 1962)
    }

    min_node_id =  5001  # 1-5000 reserved for zone centroids/POEs
    max_node_id = 29999  # 30000+ reserved for MRN nodes

    min_poe = min(centroid_ranges['POE'])
    max_poe = max(centroid_ranges['POE'])

    scenario_years = {
        '100': 2019,  # WARNING: commenting-out 100 will adversely affect transit file generation for later scenarios
        '200': 2025,
        '300': 2030,
        '400': 2035,
        '500': 2040,
        '600': 2045,  # UrbanSim only
        '700': 2050

        ### Old codes (C17Q2-C21Q4)
        # '100': 2015,  # WARNING: commenting-out 100 will adversely affect transit file generation for later scenarios
        # '200': 2020,
        # '300': 2025,
        # '400': 2030,
        # '500': 2035,  # Not currently used
        # '600': 2040,
        # '700': 2050

        ### Old codes (C17Q1 and earlier):
        # '100': 2010,  # WARNING: commenting-out 100 will adversely affect transit file generation for later scenarios
        # '200': 2015,
        # '300': 2020,
        # '400': 2025,
        # '500': 2030,
        # '600': 2040
    }

    min_year = min(year for scen, year in scenario_years.items())
    max_year = max(year for scen, year in scenario_years.items())

    tod_periods = {
        '1':  ('8PM-6AM',                                   # 1: overnight
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
               '"AM_SHARE" >= 0.5')
    }

    ampm_tods = {
        '1': ('1', '2', '3', '4', '5', '6', '7', '8', 'am'),  # All periods
        '2': ('2', '3', '4', '5', 'am'),                      # AM periods
        '3': ('1', '6', '7', '8'),                            # PM periods
        '4': ('1', '5')                                       # Off-peak periods
    }

    rsps = {
        3:   "McHenry-Lake Corridor",
        6:   "IL 31/Front St",
        10:  "IL 60",
        11:  "IL 62/Algonquin Rd",
        13:  "IL 83/Barron Blvd",
        14:  "IL 131/Greenbay Rd",
        15:  "IL 173/Rosecrans Rd",
        20:  "Elgin O'Hare Western Access",
        21:  "I-290/IL 53 Interchange Improvement",
        22:  "I-294/I-57 Interchange Addition",
        23:  "I-294 Central Tri-State Mobility Improvements",
        24:  "I-290/I-88/I-294 Interchange Improvement",
        25:  "Central Lake County Corridor: IL 53 North & IL 120",
        29:  "I-55 Managed Lane",
        30:  "I-290 Eisenhower Reconstruction & Managed Lane",
        31:  "Illiana Corridor",
        32:  "I-190 Access Improvements",
        33:  "Jane Byrne Interchange Reconstruction",
        34:  "I-55 Add Lanes & Reconstruction",
        35:  "I-57 Add Lanes",
        36:  "I-80 Reconstruction & Managed Lanes",
        37:  "I-80 Managed Lanes",
        38:  "I-80 to I-55 Connector",
        46:  "Randall Rd",
        51:  "North Algonquin Fox River Crossing",
        53:  "Caton Farm-Bruce Rd Corridor",
        55:  "Laraway Rd",
        56:  "Wilmington-Peotone Rd",
        57:  "Red Line Extension (South)",
        58:  "(58A/B) Red Purple Modernization",
        59:  "Blue Line West Extension",
        60:  "Brown Line Extension",
        61:  "Circle Line South (Phase II)",
        62:  "Circle Line North (Phase III)",
        63:  "Orange Line Extension",
        64:  "Yellow Line Enhancements & Extension",
        66:  "UP Northwest Extension",
        67:  "SouthWest Service Improvements / 75th St Corridor Improvement Program Elements",
        68:  "UP North Improvements",
        69:  "UP West Improvements",
        70:  "Rock Island Improvements",
        71:  "BNSF Extension-Oswego/Plano",
        72:  "BNSF Improvements",
        73:  "Heritage Corridor Improvements",
        74:  "Metra Electric Improvements",
        75:  "Metra Electric Extension",
        76:  "Milwaukee District North Extension-Wadsworth",
        77:  "Milwaukee District North Improvements",
        78:  "Milwaukee District West Extension-Marengo",
        79:  "Milwaukee District West Improvements",
        80:  "North Central Service Improvements",
        81:  "Rock Island Extension",
        82:  "SouthEast Service",
        83:  "SouthWest Extension",
        84:  "STAR Line",
        85:  "West Loop Transportation Center Phase I",
        87:  "Mid-City Transitway",
        88:  "West Loop Transportation Center Phase II",
        89:  "North Lake Shore Drive Improvements",
        93:  "Blue Line Forest Park Branch Reconstruction",
        94:  "Brown Line Capacity Expansion",
        98:  "A-2 Crossing Rebuild",
        102: "(102A) Pulse-ART Expansion",
        103: "River North-Streeterville Transit Improvements",
        104: "South Lakefront-Museum Campus Access Improvement",
        105: "Express Bus Expansion",
        106: "Ashland Ave BRT",
        107: "Green Line Extension",
        108: "South Halsted BRT",
        109: "IL 43/Harlem Ave",
        110: "IL 47",
        111: "IL 83/Kingery Hwy",
        112: "US 12/95th St",
        113: "US 20/Lake St",
        114: "US 45/Olde Half Day Rd",
        115: "BNSF Extension-Sugar Grove",
        116: "Heritage Corridor Extension",
        117: "Milwaukee District North Extension-Richmond",
        118: "Milwaukee District West Extension-Hampshire",
        119: "STAR Line Eastern Segment",
        120: "STAR Line Northern Segment",
        121: "Rock Island RER Service",
        122: "UP North RER Service",
        123: "UP Northwest RER Service",
        124: "CrossRail Chicago",
        125: "North Lakefront Light Rail Line",
        126: "South Lakefront Light Rail Line",
        127: "Superloop Light Rail Line",
        128: "Madison Street & Jackson Street Light Rail Lines",
        129: "Clark Street Light Rail Line",
        130: "Downtown Ring Light Rail Line",
        131: "The Burnham Ring Light Rail Line",
        132: "Milwaukee Avenue Streetcar & O'Hare Blue Line Express",
        134: "Cross-Town Tollway & CTA Route",
        135: "I-94 Bishop Ford Expressway",
        136: "I-90/1-94 Kennedy & Dan Ryan Expressways",
        137: "I-55 Stevenson Expressway",
        138: "I-90 Kennedy Expressway",
        139: "I-94 Edens Expressway",
        140: "I-90/I-94 Kennedy Expressway",
        141: "I-290/IL-53",
        142: "I-57",
        143: "Modern Metra Electric",
        144: "S.M.A.R.T. - Suburban Metropolitan Area Rapid Transit",
        145: "Vollmer Rd",
        146: "I-55 Dual Managed Lane",
        147: "Blue Line Capacity",
        151: "CREATE GS-02",
        152: "Elston-Armitage-Ahsland-Cortland Intersection",
        153: "Ashland-Ogden Metra Infill Station",
        154: "South Halsted Bus Enhancements",
        155: "I-294 BRT Stations",
        156: "Milwaukee Corridor/O'Hare Improvements",
        158: "US 6",
        159: "US 30",
        160: "US 45 & Milburn Bypass",
        161: "IL 7/143rd St",
        162: "IL 47",
        163: "IL 56",
        164: "IL 60",
        9901: "(A1) O'Hare Express Service",
        9902: "(A2) South Lakefront Improvements",
        9903: "(A3) I-55 Reconstruction & IL 126 Interchange Reconfiguration",
        9904: "(A4) I-55/IL 59 Interchange",
    }


    def __init__(self, mhn_gdb_path, zone_gdb_path=None):
        arcpy.env.overwriteOutput = True

        # -----------------------------------------------------------------------------
        #  SET GDB-SPECIFIC VARIABLES
        # -----------------------------------------------------------------------------
        self.gdb = mhn_gdb_path

        # Directories
        self.root_dir = os.path.dirname(self.gdb)
        self.imp_dir = self.ensure_dir(os.path.join(self.root_dir, 'import'))
        self.out_dir = self.ensure_dir(os.path.join(self.root_dir, 'output'))
        self.temp_dir = self.ensure_dir(os.path.join(self.root_dir, 'temp'))
        self.script_dir = sys.path[0]  # Directory containing this module
        if os.path.basename(self.script_dir) == 'utilities':
            self.prog_dir = os.path.dirname(self.script_dir)
            self.util_dir = self.script_dir
        else:
            self.prog_dir = self.script_dir
            self.util_dir = os.path.join(self.prog_dir, 'utilities')
        self.mem = 'in_memory'

        # MHN geodatabase structure, projection
        self.hwynet_name = 'hwynet'
        self.hwynet = os.path.join(self.gdb, self.hwynet_name)
        self.arc_name = 'hwynet_arc'
        self.arc = os.path.join(self.hwynet, self.arc_name)
        self.node_name = 'hwynet_node'
        self.node = os.path.join(self.hwynet, self.node_name)
        self.hwyproj = os.path.join(self.hwynet, 'hwyproj')
        self.bus_base = os.path.join(self.hwynet, 'bus_base')
        self.bus_current = os.path.join(self.hwynet, 'bus_current')
        self.bus_future = os.path.join(self.hwynet, 'bus_future')
        self.route_systems = {
            self.hwyproj: (os.path.join(self.gdb, 'hwyproj_coding'), 'TIPID', None, None),
            self.bus_base: (os.path.join(self.gdb, 'bus_base_itin'), 'TRANSIT_LINE', 'ITIN_ORDER', 0),
            self.bus_current: (os.path.join(self.gdb, 'bus_current_itin'), 'TRANSIT_LINE', 'ITIN_ORDER', 50000),
            self.bus_future: (os.path.join(self.gdb, 'bus_future_itin'), 'TRANSIT_LINE', 'ITIN_ORDER', 99000)
        }
        self.pnr_name = 'parknride'
        self.pnr = os.path.join(self.gdb, self.pnr_name)
        self.projection = arcpy.Describe(self.arc).spatialReference

        # Zone geodatabase structure (default to zone_systems.gdb in same dir as MHN gdb)
        if zone_gdb_path:
            self.zone_gdb = zone_gdb_path
        else:
            self.zone_gdb = os.path.join(self.root_dir, 'zone_systems.gdb')
        # self.zone = os.path.join(self.zone_gdb, 'zonesys09', 'zones09')
        # self.zone_attr = 'Zone09'
        # self.subzone = os.path.join(self.zone_gdb, 'zonesys09', 'subzones09')
        # self.subzone_attr = 'Subzone09'
        # self.capzone = os.path.join(self.zone_gdb, 'zonesys09', 'capzones09')
        # self.capzone_attr = 'CapacityZone09'
        self.zone = os.path.join(self.zone_gdb, 'zonesys17', 'zones17')
        self.zone_attr = 'zone17'
        self.subzone = os.path.join(self.zone_gdb, 'zonesys17', 'subzones17')
        self.subzone_attr = 'subzone17'
        self.capzone = os.path.join(self.zone_gdb, 'zonesys17', 'capzones17')
        self.capzone_attr = 'capzone17'
        self.imarea = os.path.join(self.zone_gdb, 'imarea18')
        self.imarea_attr = 'IMArea'

        # Misc.
        self.mhn2iris_name = 'mhn2iris'
        self.mhn2iris = os.path.join(self.gdb, self.mhn2iris_name)

        ### End MasterHighwayNetwork.__init__() def ###
        return None


    # -----------------------------------------------------------------------------
    #  DEFINE METHODS
    # -----------------------------------------------------------------------------
    @staticmethod
    def break_path(fullpath):
        ''' Splits a full-path string into a dictionary, containing 'dir', 'name'
            and 'ext' values. '''
        split1 = os.path.split(fullpath)
        directory = split1[0]
        filename_ext = split1[1]
        split2 = os.path.splitext(split1[1])
        filename = split2[0]
        extension = split2[1]
        return {'dir': directory, 'name': filename, 'ext': extension, 'name_ext': filename_ext}


    @staticmethod
    def build_geometry_dict(lyr, key_field):
        ''' For an input layer and a key field, returns a dictionary whose values
            are the arcpy geometry objects for the corresponding key. These objects
            can then be fetched by key and strung into a new array -- much faster
            than querying-and-dissolving if creating a large number of features,
            but some time is lost in the creation of this dict, so there is a
            definite trade-off. '''
        geom_dict = {}
        with arcpy.da.SearchCursor(lyr, [key_field, 'SHAPE@']) as cursor:
            for row in cursor:
                key = row[0]
                geom = row[1]
                geom_dict[key] = arcpy.Array()
                for part in geom:
                    for point in part:
                        geom_dict[key].add(point)
        return geom_dict


    def calculate_itin_measures(self, itin_table):
        ''' Calculates the F_MEAS and T_MEAS values for each row in an itin table,
            based on the MILES values of the corresponding MHN arc. '''
        abb_miles_dict = self.make_attribute_dict(self.arc, 'ABB', attr_list=['MILES'])
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
        sql = (None, 'ORDER BY TRANSIT_LINE, ITIN_ORDER')
        with arcpy.da.UpdateCursor(itin_table, ['TRANSIT_LINE', 'ITIN_ORDER', 'ABB', 'F_MEAS', 'T_MEAS'], sql_clause=sql) as cursor:
            order_tracker = 0
            cumulative_percent = 0
            for row in cursor:
                route = row[0]
                row_order = row[1]
                abb = row[2]
                if row_order == 1:  # Beginning of new route
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


    @staticmethod
    def check_edit_session(lyr):
        ''' Check for an active edit session on a specified layer by trying to
            open two cursors simultaneously. '''
        edit_session = True
        try:
            OID = arcpy.Describe(lyr).OIDFieldName
            with arcpy.da.UpdateCursor(lyr, OID) as rows:
                row = next(rows)
                with arcpy.da.UpdateCursor(lyr, OID) as rows2:
                    row2 = next(rows2)
        except RuntimeError as e:
            if str(e) == "workspace already in transaction mode":
                edit_session = False  # No active edit session
            else:
                raise  # Some other RuntimeError
        return edit_session


    @staticmethod
    def check_selection(lyr):
        ''' Check whether specified layer has a selection. '''
        try:
            if len(arcpy.Describe(lyr).FIDSet) == 0:
                return False
            else:
                return True
        except AttributeError:
            # `lyr` is not a feature layer or table view
            return False


    @staticmethod
    def delete_if_exists(filepath):
        ''' Check if a file exists, and delete it if so. '''
        if arcpy.Exists(filepath):
            arcpy.Delete_management(filepath)
            message = '{} successfully deleted.'.format(filepath)
        else:
            message = '{} does not exist.'.format(filepath)
        return message


    @staticmethod
    def determine_arc_bearing(line_geom):
        ''' Determines the cardinal direction of a single arc, determined from its
            two endpoints. The angle is determined by the atan2() function, and
            after some numeric manipulation is then used to select the correct
            cardinal direction from an ordered list of possibilities. '''
        from math import atan2, degrees, floor
        x1 = line_geom.firstPoint.X
        y1 = line_geom.firstPoint.Y
        x2 = line_geom.lastPoint.X
        y2 = line_geom.lastPoint.Y
        xdiff = x2 - x1
        ydiff = y2 - y1
        angle = degrees(atan2(ydiff, xdiff))
        index = int(floor(((angle + 22.5) % 360) / 45))
        cardinal_dirs = ('E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE')  # Order here is critical
        bearing = cardinal_dirs[index]
        return bearing


    @staticmethod
    def determine_OID_fieldname(fc):
        ''' Determines the Object ID fieldname for the specified fc/table. '''
        return arcpy.Describe(fc).OIDFieldName


    @staticmethod
    def determine_tolltype(vdf, cost):
        ''' Automatically determine TOLLTYPE code, based on link's VDF and
            toll cost. '''
        if cost > 0:
            if vdf == '7':
                tolltype = '1'  # Fixed cost toll (i.e. toll plaza)
            else:
                tolltype = '2'  # Per-mile rate (i.e. distance-based tolling)
        else:
            tolltype = '0'  # N/A (not tolled)
        return tolltype


    @staticmethod
    def die(error_message=''):
        ''' End processing prematurely. '''
        arcpy.AddError('\n{}\n'.format(error_message))
        sys.exit()
        return None


    @staticmethod
    def ensure_dir(directory):
        ''' Checks for the existence of a directory, creating it if it doesn't
            exist yet. '''
        if not os.path.exists(directory):
            os.makedirs(directory)
        return directory


    @staticmethod
    def find_shortest_path(graph, start, end):
        ''' Recursive function written by Chris Laffra to find shortest path
            between 2 nodes in a graph; implementation of Dijkstra's algorithm.
            Based on <http://code.activestate.com/recipes/119466/#c6>.

            Example graph dictionary (sub-dicts contain distances):

                {'a': {'w': 14, 'x': 7, 'y': 9},
                 'b': {'w': 9, 'z': 6},
                 'w': {'a': 14, 'b': 9, 'y': 2},
                 'x': {'a': 7, 'y': 10, 'z': 15},
                 'y': {'a': 9, 'w': 2, 'x': 10, 'z': 11},
                 'z': {'b': 6, 'x': 15, 'y': 11}}
        '''
        import heapq
        queue = [(0, start, [])]
        seen = set()
        while True:
            (p_cost, node, path) = heapq.heappop(queue)
            if node not in seen:
                path = path + [node]
                seen.add(node)
                if node == end:
                    return p_cost, path
                if node in graph.keys():
                    for (b_node, b_cost) in graph[node].items():
                        heapq.heappush(queue, (p_cost + b_cost, b_node, path))


    def get_yearless_hwyproj(self):
        ''' Check hwyproj completion years and return list of invalid projects'
            TIPIDs. '''
        common_id_field = self.route_systems[self.hwyproj][1]
        invalid_year_query = "{0} = 0 OR {0} IS NULL".format('COMPLETION_YEAR')
        invalid_year_lyr = self.make_skinny_table_view(self.hwyproj, 'invalid_year_lyr', ['COMPLETION_YEAR', common_id_field], invalid_year_query)
        invalid_year_count = int(arcpy.GetCount_management(invalid_year_lyr).getOutput(0))
        if invalid_year_count > 0:
            return [row[0] for row in arcpy.da.SearchCursor(invalid_year_lyr, [common_id_field])]
        else:
            return []


    @staticmethod
    def is_tipid(in_str):
        ''' Check whether a string is a properly formatted TIPID. '''
        is_tipid = False
        try:
            if len(in_str) == 10:
                pt1, pt2, pt3 = (int(pt) for pt in in_str.split('-'))
                if (0 <= pt1 <= 99) and (0 <= pt2 <= 99) and (0 <= pt3 <= 9999):
                    return True
        except:
            pass
        return is_tipid


    @staticmethod
    def make_attribute_dict(fc, key_field, attr_list=['*']):
        ''' Create a dictionary of feature class/table attributes, using OID as the
            key. Default of ['*'] for attr_list (instead of actual attribute names)
            will create a dictionary of all attributes.
            - NOTE 1: when key_field is the OID field, the OID attribute name can
              be fetched by MHN.determine_OID_fieldname(fc).
            - NOTE 2: using attr_list=[] will essentially build a list of unique
              key_field values. '''
        attr_dict = {}
        fc_fields = [f.name for f in arcpy.ListFields(fc) if f.type != 'Geometry']
        if attr_list == ['*']:
            valid_fields = fc_fields
        else:
            valid_fields = [f for f in attr_list if f in fc_fields]
        # Ensure that key_field is always the first field in the field list
        cursor_fields = [key_field] + list(set(valid_fields) - set([key_field]))
        with arcpy.da.SearchCursor(fc, cursor_fields) as cursor:
            for row in cursor:
                attr_dict[row[0]] = dict(zip(cursor.fields, row))
        return attr_dict


    @staticmethod
    def make_path(directory, filename, extension=''):
        ''' Combines a directory, name and optional extension to create a full-path
            string for a file. '''
        fullpath = os.path.join(directory, filename)
        if extension != '':
            fullpath += '.' + extension.lstrip('.')  # Guarantee 1 (and only 1) '.' in front of extension
        return fullpath


    @staticmethod
    def make_skinny(is_geo, in_obj, out_obj, keep_fields_list=None, where_clause=None):
        ''' Make an ArcGIS Feature Layer or Table View, containing only the fields
            specified in keep_fields_list, using an optional SQL query. Default
            will create a layer/view with NO fields. '''
        field_info_str = ''
        input_fields = arcpy.ListFields(in_obj)
        if not keep_fields_list:
            keep_fields_list = []
        for field in input_fields:
            if field.name in keep_fields_list:
                field_info_str += '{0} {0} VISIBLE;'.format(field.name)
            else:
                field_info_str += '{0} {0} HIDDEN;'.format(field.name)
        field_info_str.rstrip(';')  # Remove trailing semicolon
        if is_geo:
            arcpy.MakeFeatureLayer_management(in_obj, out_obj, where_clause, field_info=field_info_str)
        else:
            arcpy.MakeTableView_management(in_obj, out_obj, where_clause, field_info=field_info_str)
        return out_obj

    # Wrapper functions for make_skinny()
    def make_skinny_feature_layer(self, fc, lyr, keep_fields_list=None, where_clause=None):
        return self.make_skinny(True, fc, lyr, keep_fields_list, where_clause)
    def make_skinny_table_view(self, table, view, keep_fields_list=None, where_clause=None):
        return self.make_skinny(False, table, view, keep_fields_list, where_clause)


    @staticmethod
    def set_nulls(value, fc, fields):
        ''' Recalculate all null values in a list of specified fields to a
            specified replacement value. '''
        if type(value) is str:
            valid_types = ['String']
        else:
            valid_types = ['String', 'SmallInteger', 'Integer', 'Single', 'Double']
        matched_fields = [f for f in arcpy.ListFields(fc) if f.name in fields and f.type in valid_types]
        for field in matched_fields:
            if field.type == 'String':
                expression = "'{}'".format(value)
                if value == 0:
                    null_sql = "{0} IS NULL OR {0} IN ('', ' ')".format(field.name)  # Replace blanks, too
                else:
                    null_sql = "{} IS NULL".format(field.name)
            else:
                expression = "{}".format(value)
                null_sql = "{} IS NULL".format(field.name)
            null_view = 'null_view'
            arcpy.MakeTableView_management(fc, null_view, null_sql)
            if int(arcpy.GetCount_management(null_view).getOutput(0)) > 0:
                arcpy.CalculateField_management(null_view, field.name, expression, 'PYTHON')
            arcpy.Delete_management(null_view)
        return fc

    # Wrapper functions for set_nulls()
    def set_nulls_to_space(self, fc, fields):
        return self.set_nulls(' ', fc, fields)
    def set_nulls_to_zero(self, fc, fields):
        return self.set_nulls(0, fc, fields)


    def submit_sas(self, sas_file, sas_log, sas_lst, arg_list=None):
        ''' Calls a specified SAS program with optional arguments specified in a
            $-separated string. '''
        import subprocess
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        if not arg_list:
            arg_str = ''
        else:
            arg_str = '$'.join(str(arg) for arg in arg_list)
        bat = os.path.join(self.prog_dir, 'sasrun.bat')
        cmd = [bat, sas_file, arg_str, sas_log, sas_lst]
        return subprocess.check_call(cmd, startupinfo=startupinfo)


    @staticmethod
    def timestamp(ts_format='%Y%m%d%H%M%S'):
        ''' Creates a timestamp string, defaulting to the form YYYYMMDDHHMMSS, but
            any standard date formatting is accepted. See docs for details:
            <http://docs.python.org/2/library/datetime.html#strftime-strptime-behavior>.

            %a day of week, using locale's abbreviated weekday names
            %A day of week, using locale's full weekday names
            %b,%h month, using locale's abbreviated month names
            %B month, using locale's full month names #%c date and time as %x %X
            %d day of month (01-31)
            %H hour (00-23)
            %I hour (00-12)
            %j day number of year (001-366)
            %m month number (01-12)
            %M minute (00-59)
            %p locale's equivalent of AM or PM, whichever is appropriate
            %r time as %I:%M:%S %p
            %S seconds (00-59)
            %U week number of year (01-52), Sunday is the first day of the week
            %w day of week; Sunday is day 0
            %W week number of year (01-52), Monday is the first
            %x date, using locale's date format
            %X time, using locale's time format
            %y year within century (00-99)
            %Y year, including century (for example, 1994)
            %Z time zone abbreviation
        '''
        from datetime import datetime
        ts = datetime.now().strftime(ts_format)
        return ts


    def tipid_from_int(self, n):
        ''' Format an integer < 100,000,000 as a TIPID string. '''
        try:
            n_str = str(int(n)).zfill(8)
            tipid = '-'.join([n_str[:2], n_str[2:4], n_str[4:]])
        except:
            return None
        return tipid if self.is_tipid(tipid) else None


    def tipid_to_int(self, tipid):
        ''' Convert a TIPID string to an integer. '''
        if self.is_tipid(tipid):
            n_str = tipid.replace('-', '')
            return int(n_str)
        else:
            return None


    def validate_itin_times(self, itin_table):
        ''' Perform some auto QC on the DEP_TIME, ARR_TIME & LINE_SERV_TIME
            values for each row in an itin table, based on the MILES values
            of the corresponding MHN arc and the original DEP_TIME/ARR_TIME
            values themselves. Any segments where ARR_TIME = DEP_TIME will
            have travel time estimated by distance of link, at 30mph. '''
        abb_miles_dict = self.make_attribute_dict(self.arc, 'ABB', attr_list=['MILES'])

        # Loop to update times for each row, as appropriate
        sql = (None, 'ORDER BY TRANSIT_LINE, ITIN_ORDER')
        cursor_fields = ['TRANSIT_LINE', 'ITIN_ORDER', 'ABB', 'DEP_TIME', 'ARR_TIME', 'LINE_SERV_TIME']
        with arcpy.da.UpdateCursor(itin_table, cursor_fields, sql_clause=sql) as cursor:
            prev_arr_time = 0
            for row in cursor:
                route = row[0]
                row_order = row[1]
                abb = row[2]
                dep_time = row[3]
                arr_time = row[4]
                ltime = row[5]

                # Adjust dep_time & arr_time to accommodate changes to last segment
                if row_order > 1 and dep_time < prev_arr_time:
                    discrep_d = prev_arr_time - dep_time
                    dep_time += discrep_d
                    if arr_time < dep_time:
                        discrep_a = dep_time - arr_time  # Likely = discrep_d, but may be lower
                        arr_time += discrep_a

                # Re-estimate segment travel time (@ 30mph) when dep_time = arr_time
                if dep_time == arr_time:
                    segment_length = abb_miles_dict[abb]['MILES']
                    time_est = int(round(segment_length / 30 * 60 * 60))  # Seconds
                    arr_time += time_est
                    ltime = max(round(time_est / 60., 1), 0.1)  # Minutes (1 d.p.)

                # Update row with adjusted values and update prev_arr_time
                row[3:6] = [dep_time, arr_time, ltime]
                cursor.updateRow(row)
                prev_arr_time = arr_time

        return itin_table


    def write_arc_flag_file(self, flag_file, flag_query, csv_mode=False):
        ''' Create a file containing l=anode,bnode rows for all directional links
            meeting a specified criterion. '''
        self.delete_if_exists(flag_file)
        flag_lyr = 'flag_lyr'
        arcpy.MakeFeatureLayer_management(self.arc, flag_lyr, flag_query)
        with open(flag_file, 'w') as w:
            if csv_mode:
                row_prefix = ''
                w.write('ANODE,BNODE\n')
            else:
                row_prefix = 'l='
                w.write('~# {} links\n'.format(flag_query.strip()))
            with arcpy.da.SearchCursor(flag_lyr, ['ANODE', 'BNODE', 'DIRECTIONS']) as cursor:
                for row in cursor:
                    anode = row[0]
                    bnode = row[1]
                    directions = int(row[2])
                    w.write('{0}{1},{2}\n'.format(row_prefix, anode, bnode))
                    if directions > 1:
                        w.write('{0}{2},{1}\n'.format(row_prefix, anode, bnode))
        arcpy.Delete_management(flag_lyr)
        return flag_file


    @staticmethod
    def write_attribute_csv(in_obj, textfile, field_list=None, include_headers=True):
        ''' Write attributes of a feature class/table to a specified text file.
            Input field_list allows output field order to be specified. Defaults to
            all non-shape fields. '''
        valid_field_names = [f.name for f in arcpy.ListFields(in_obj) if f.name != '' and f.type != 'Geometry']
        if not field_list:
            fields = valid_field_names
        else:
            fields = [f for f in field_list if f in valid_field_names]
        csv = open(textfile,'w')
        if include_headers:
            csv.write(','.join(fields) + '\n')
        with arcpy.da.SearchCursor(in_obj, fields) as cursor:
            for row in cursor:
                csv.write(','.join(map(str, row)) + '\n')
        csv.close()
        return textfile
