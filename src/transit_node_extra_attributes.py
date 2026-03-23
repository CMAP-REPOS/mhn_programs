#!/usr/bin/env python
'''
    transit_node_extra_attributes.py
    Author: npeterson
    Revised: 9/9/15
    ---------------------------------------------------------------------------
    Generate two CSVs:

    1.  bus_node_extra_attributes.csv -- contains @bstyp, @bsinf, @timbo for
        each bus stop

    2.  rail_node_extra_attributes.csv -- contains @rspac, @rpcos, @rstyp,
        @rsinf, @timbo for each rail station

    Bus data relies on stop-level information provided by CTA, as well as a
    manually-created text file listing the MHN that are to be modeled as bus
    plazas, for CTA and Pace.

'''
import os
import sys
import arcpy

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
# Input files
#SCENARIO = 200
#RAIL_NODE = r'M:\proj1\nrf\Development\Activity-Based Model\2019 Scenario\data\input\mrn-c20q4-zone_fares.gdb\railnet\railnet_node'
#BATCHIN_DIR = r'M:\proj1\nrf\Development\Activity-Based Model\2019 Scenario\data\output\transit\200'
#CTA_BUS_SHP = r'M:\proj1\nrf\Development\Activity-Based Model\2019 Scenario\data\input\CTABusStops_CTA_201908.shp'
CTA_MATCH = os.path.join(MHN.in_dir, 'cta_stops_match_20161206.csv')
PACE_MATCH = os.path.join(MHN.in_dir, 'pace_stops_match_20161206.csv')
BUS_PLAZA = os.path.join(MHN.in_dir, 'Bus_Plaza_Nodes_C15Q3.txt')
RAIL_TERMINAL = os.path.join(MHN.in_dir, 'Rail_Terminal_Nodes_C15Q3.txt')

# Output files
OUT_BUS_CSV = os.path.join(tran_path, 'bus_node_extra_attributes.csv')
OUT_RAIL_CSV = os.path.join(tran_path, 'rail_node_extra_attributes.csv')

# Boarding time in minutes, by stop type
TIMBO_BY_TYPE = {
    1: 0.5,  # Pole
    2: 0.5,  # Shelter
    3: 1.0,  # Bus plaza
    4: 1.5,  # Rail station
    5: 3.5,  # Rail terminal
}


# -----------------------------------------------------------------------------
#  Identify all nodes in the bus and rail networks.
# -----------------------------------------------------------------------------
# def get_nodes_from_batchin(batchin):
#     ''' Parse a network batchin file to obtain transit stop nodes. '''
#     nodes = set()
#     with open(batchin, 'r') as r:
#         for line in r:
#             # Stop reading when links are reached
#             if line.startswith('t links'):
#                 break
#             # Nodes are defined by "a" (not centroid "a*") lines
#             elif line.startswith('a '):
#                 attr = line.strip().split()
#                 node = int(attr[1].replace("'", ""))
#                 nodes.add(node)
#     return nodes

# def get_scen_nodes(bus_or_rail):
#     ''' Read each of the time-of-day bus & rail network files to identify every
#         node present in the scenario. '''
#     nodes = set()
#     for tod in range(1, 9):
#         batchin = os.path.join(BATCHIN_DIR, '{0}.network_{1}'.format(bus_or_rail, tod))
#         nodes.update(get_nodes_from_batchin(batchin))
#     return nodes

def get_nodes_from_batchin(batchin):
    ''' Parse a network batchin file to obtain transit stop nodes. '''
    nodes = set()
    with open(batchin, 'r') as r:
        for line in r:
            # Stop reading when links are reached
            if line.startswith('t links'):
                break
            # Nodes are defined by "a" (not centroid "a*") lines
            elif line.startswith('a '):
                attr = line.strip().split()
                node = int(attr[1].replace("'", ""))
                nodes.add(node)
    return nodes

def get_scen_nodes(bus_or_rail):
    ''' Read each of the time-of-day bus & rail network files to identify every
        node present in all scenarios. '''
    rsp = rsp_eval
    if rsp == True:
        scen_labels = [horiz_scen]
    else:
        scen_labels=scen_list
    nodes = set()
    for scen in scen_labels:
        scen_tran_path = os.path.join(tran_path, scen)
        for tod in out_tod_periods:
            batchin = os.path.join(scen_tran_path, f'{bus_or_rail}.network_{tod}')
            nodes.update(get_nodes_from_batchin(batchin))
    return nodes

bus_nodes = get_scen_nodes('bus')
rail_nodes = get_scen_nodes('rail')


# -----------------------------------------------------------------------------
#  Read in bus stop data.
# -----------------------------------------------------------------------------
cta_matched_stops = set()
cta_stop_match = {}
with arcpy.da.SearchCursor(CTA_MATCH, ['stop_id', 'node']) as c:
    for r in c:
        stop_id = int(r[0])
        node_id = int(r[1])
        cta_matched_stops.add(stop_id)
        if node_id in cta_stop_match:
            cta_stop_match[node_id].add(stop_id)
        else:
            cta_stop_match[node_id] = set([stop_id])

pace_matched_stops = set()
pace_stop_match = {}
with arcpy.da.SearchCursor(PACE_MATCH, ['stop_id', 'node']) as c:
    for r in c:
        stop_id = r[0]
        node_id = int(r[1])
        pace_matched_stops.add(stop_id)
        if node_id not in cta_stop_match:
            if node_id in pace_stop_match:
                pace_stop_match[node_id].add(stop_id)
            else:
                pace_stop_match[node_id] = set([stop_id])

cta_stop_attr = {stop_id: {'SHELTER': 0, 'INFO': 0} for stop_id in cta_matched_stops}
#with arcpy.da.SearchCursor(CTA_BUS_SHP, ['SYSTEMSTOP', 'SHELTER', 'BTSIGN']) as c:
#    for r in c:
#        stop_id = int(r[0])
#        if stop_id in cta_matched_stops:
#            cta_stop_attr[stop_id]['SHELTER'] = 1 if r[1] > 0 else 0
#            cta_stop_attr[stop_id]['INFO'] = 1 if r[2] > 0 else 0

bus_plazas = set()
with open(BUS_PLAZA, 'r') as r:
    for line in r:
        if line.strip() and not line.startswith('c'):
            node_id = int(line.strip().split(',')[0])
            bus_plazas.add(node_id)


# -----------------------------------------------------------------------------
#  Create master bus stop attribute dictionary.
# -----------------------------------------------------------------------------
bus_node_attr = {node_id: {'TYPE': 1, 'INFO': 1} for node_id in bus_nodes}

for node_id in bus_node_attr:

    # Determine which CTA stations have shelters and/or real-time info
    if node_id in cta_stop_match:
        child_stops = float(len(cta_stop_match[node_id]))

        pct_shelter = sum(cta_stop_attr[stop_id]['SHELTER'] for stop_id in cta_stop_match[node_id]) / child_stops
        if pct_shelter >= 0.5:
            bus_node_attr[node_id]['TYPE'] = 2

        pct_real = sum(cta_stop_attr[stop_id]['INFO'] for stop_id in cta_stop_match[node_id]) / child_stops
        if pct_real >= 0.5:
            bus_node_attr[node_id]['INFO'] = 2

    # Change type for bus plazas
    if node_id in bus_plazas:
        bus_node_attr[node_id]['TYPE'] = 3

    # Set @timbo (boarding time), derived from stop type
    stop_type = bus_node_attr[node_id]['TYPE']
    bus_node_attr[node_id]['TIMBO'] = TIMBO_BY_TYPE[stop_type]


# -----------------------------------------------------------------------------
#  Read in rail station data.
# -----------------------------------------------------------------------------
# mrn_attr = {}
# with arcpy.da.SearchCursor(RAIL_NODE, ['NODE', 'PSPACE', 'PCOST', 'FTR_PSPACE', 'FTR_PCOST']) as c:
#     for r in c:
#         node_id = r[0]
#         space = r[1]
#         cost = r[2]

#         # Check scenario against FTR_PSPACE
#         if ':' in r[3]:
#             ftr_scen, ftr_space = r[3].split(':')
#             ftr_scen = int(ftr_scen) * 100
#             ftr_space = int(ftr_space)
#             if ftr_scen <= SCENARIO:
#                 space = ftr_space

#         # Check scenario against FTR_PCOST
#         if ':' in r[4]:
#             ftr_scen, ftr_cost = r[4].split(':')
#             ftr_scen = int(ftr_scen) * 100
#             ftr_cost = int(ftr_cost)
#             if ftr_scen <= SCENARIO:
#                 cost = ftr_cost

#         mrn_attr[node_id] = {'SPACE': space, 'COST': cost}

rail_terminals = set()
with open(RAIL_TERMINAL, 'r') as r:
    for line in r:
        if line.strip() and not line.startswith('c'):
            node_id = int(line.strip().split(',')[0])
            rail_terminals.add(node_id)


# -----------------------------------------------------------------------------
#  Create master rail station attribute dictionary.
# -----------------------------------------------------------------------------
#rail_node_attr = {node_id: {'TYPE': 4, 'INFO': 2, 'SPACE': 0, 'COST': 0} for node_id in rail_nodes}
rail_node_attr = {node_id: {'TYPE': 4, 'INFO': 2} for node_id in rail_nodes}

for node_id in rail_node_attr:

    # Add parking spaces and cost from MRN where applicable
    # if node_id in mrn_attr:
    #     rail_node_attr[node_id]['SPACE'] = mrn_attr[node_id]['SPACE']
    #     rail_node_attr[node_id]['COST'] = mrn_attr[node_id]['COST']

    # Change type for major downtown terminals
    if node_id in rail_terminals:
        rail_node_attr[node_id]['TYPE'] = 5

    # Set @timbo (boarding time), derived from stop type
    stop_type = rail_node_attr[node_id]['TYPE']
    rail_node_attr[node_id]['TIMBO'] = TIMBO_BY_TYPE[stop_type]


# -----------------------------------------------------------------------------
#  Write output files.
# -----------------------------------------------------------------------------
with open(OUT_BUS_CSV, 'w') as w:
    w.write('node,@bstyp,@bsinf,@timbo\n')
    for node_id in sorted(bus_node_attr.keys()):
        bstyp = bus_node_attr[node_id]['TYPE']
        bsinf = bus_node_attr[node_id]['INFO']
        timbo = bus_node_attr[node_id]['TIMBO']
        w.write('{0},{1},{2},{3}\n'.format(node_id, bstyp, bsinf, timbo))

with open(OUT_RAIL_CSV, 'w') as w:
    #w.write('node,@rspac,@rpcos,@rstyp,@rsinf,@timbo\n')
    w.write('node,@rstyp,@rsinf,@timbo\n')
    for node_id in sorted(rail_node_attr.keys()):
        #rspac = rail_node_attr[node_id]['SPACE']
        #rpcos = rail_node_attr[node_id]['COST']
        rstyp = rail_node_attr[node_id]['TYPE']
        rsinf = rail_node_attr[node_id]['INFO']
        timbo = rail_node_attr[node_id]['TIMBO']
        #w.write('{0},{1},{2},{3},{4},{5}\n'.format(node_id, rspac, rpcos, rstyp, rsinf, timbo))
        w.write('{0},{1},{2},{3}\n'.format(node_id, rstyp, rsinf, timbo))
