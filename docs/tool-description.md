# Master Highway Network Tool Descriptions
The following is a description of tools in the Master Highway Network (MHN) suite of processing programs.

For a guide on how to update highway project coding, see the [how-to guide](how-to.md).

# Primary Tools
A set of Python scripts has been developed to perform the data handling and processing needs of maintaining the MHN geodatabase. These are stored along with an ArcGIS toolbox `mhn_tools.tbx` in this repository.

## Generate Highway Files
```
generate_highway_files.py
|--- sasrun.bat
|--- coding_overlap.sas
|--- generate_highway_files_2.sas
```

### Parameters 
- MHN Geodatabase - filepath to MHN geodatabase
- Scenario Code - scenario years to generate (ignored if "RSP Evaluation" is checked)
- Root Folder for Emme Batchin Files - folder in which emme transaction files will be generated
- Create Scenario-Indepenedent TOLLSYS.FLAG file - If checked, will generate tollsys.flag file in highway folder, can be read into Emme to specify links where TOLLSYS=1.
- ABM Output - If checked, will generate ABM outputs (deprecated)
- RSP Evaluation - If checked, will generate a highway network using the following additional parameters:
    - RSP Column - column in hwyproj containing RSP number
    - RSP Number - the RSP number denoting the project you wish to output (left blank if not a roadway project)
    - RSP No-Build TIPID CSV - a csv containing the TIPIDs of all projects considered part of a "no-build" scenario. These projects, along with the project specified in the "RSP Number" parameter, will be outputted.
    - RSP Horizon Year - essentially nonfunctional, but the script will output transaction files into a folder named as the year's associated scenario code (e.g., "2026" will name output folder "200", as of June 2026.)

### Description 
For a specified set of scenarios and an output directory, this tool exports all necessary information out of the MHN into scenario-specific network highway "transaction files," which can then be imported into Emme for travel demand modeling. 

## Generate Transit Files
```
generate_transit_files.py
|--- sasrun.bat
|--- gtfs_reformat_feed.sas
|--- gtfs_collapse_routes.py
|--- generate_transit_files_2.sas
|--- generate_transit_files_3.sas
```
### Parameters
- MHN Geodatabase - filepath to MHN geodatabase
- Scenario Code - scenario years to generate (ignored if "RSP Evaluation" is checked)
- Root Folder for Emme Batchin Files - folder in which emme transaction files will be generated
- RSP Evaluation - If checked, will generate a transit network using the following additional parameters:
    - RSP Number - the bus RSP number denoting the project you wish to output (left blank if not a bus project)
    - RSP No-Build TIPID CSV - a csv containing the TIPIDs of all projects considered part of a "no-build" scenario. These projects, along with the project specified in the "RSP Number" parameter, will be outputted. 
    - RSP Horizon Year - essentially nonfunctional, but the script will output transaction files into a folder named as the year's associated scenario code (e.g., "2026" will name output folder "200", as of June 2026)


### Description
For a specified set of scenarios and output directory, this tool exports all necessary information out of the MHN into scenario-specific network transit "transaction files," which can then be imported into Emme for travel demand modeling. The "Generate Highway Files" tool must have already been run (as well as the Master Rail Network's "Create Emme Scenario Files" tool) for the same scenario(s) out output directory, as this tool builds transit networks using the highway and rail networks.

Before transit files are generated, all bus runs from the `bus_base` or `bus_current` feature classes are separated by time-of-day period into temporary feature classes. The selection for each period, except `AM`, is made using the `STARTHOUR` field. The `AM` period selects any runs for which `AM_SHARE` >= 0.5. The time-of-day-specific data is exported to temporary CSV files.

The program `gtfs_reformat_feed.sas` is called (via `sasrun.bat`) to reformat the time-of-day-specific bus itinerary data. The program subsequently calls `gtfs_collapse_routes.py` to determine, based on reformatted itinerary data, which runs are similar enough to combine into a single "representative run." When the SAS program resumes, it chooses these "representative runs" for each set that is to be combined and calculates their average headways.

For each included time-of-day period, the program `generate_transit_files_2.sas` is called (via `sasrun.bat`) to analyze the highway project coding to determine the appropriate highway links in the scenario that the buses should run on. It also creates bus-to-bus transfer links (coded as mode `b`) and three bus stop files (CTA stops, Pace stops, and all stops), which are used later to create additional types of auxiliary links. All but one of the final Emme transaction bus files are created by this program. The list file (`generate_transit_files_2_x00.lst`, in the `output/transit` folder) *must be reviewed* after the programs complete to ensure no coding errors were encountered. (These errors will not prevent the program from running.) This SAS program looks for the following coding issues: 
    - itinerary segment directional issues
    - itinerary gaps
    - too many layovers (more than 2) coded in an itinerary
Files of CTA rail and Metra stops are greated from MRN transaction files for auxiliary link processing.

The distances between sets of bus stops, rail stops, and zone centroids are calculated, and, after `generate_transit_files_3.sas`, the final Emme transit transaction file is written.

Once all transaction files have been generated for a given scenario, the highway and rail linkshape files (greated by the "Generate Highway Files" tool and MRN processing, respectively) are merged together into a single file ("linkshape_x00.in). This file is placed under the "linkshape" folder in the same root directory as the highway and transit files. It can be imported into Emme to display true network geometry instead of straight lines. 

## Import Future Bus Routes
```
import_future_bus_routes.py
|--- sasrun.bat
|--- import_future_bus_routes_2.sas
```
### Parameters
- MHN Geodatabase - filepath to MHN geodatabase
- Future Bus Route Coding Spreadsheet - filepath to the excel workbook in which bus "line" and "itinerary" information is located

### Description
This tool is used to import planned bus routes from a future bus coding spreadsheet into the MHN's `bus_future` feature class and corresponding itinerary table. The new route data will be appended to the feature class (unless routes with the same `TRANSIT_LINE` already exist— in which case, the old version will be overwritten).

The program `import_future_bus_routes_2.sas` is called (via `sasrun.bat`) to import the coding data directly from the spreadsheet, perform error checking, and reformat the data for import into `bus_future` amd `bus_future_itin`. The following errors are checked:
    - route data without corresponding itinerary data and vice-versa
    - unavailable `ANODE`-`BNODE` values or itinerary segment directional issues
    - coding applied to zone centroid connectors
    - itinerary gaps
    - too many layovers coded in an itinerary

If errors are encountered, they are written to `temp/import_future_bus_routes_2.lst`, all processing stops before any data are imported into the geodatabase, and the user is prompted to correct the issues before re-running the tool.

## Import Highway Projects
```
import_highway_projects.py
|--- sasrun.bat
|--- import_highway_projects_2.sas
```
### Parameters
MHN Geodatabase - filepath to MHN geodatabase
Highway Project Coding Spreadhseet - filepath to the excel workbook in which highway project coding is located

### Description
This tool builds polyline features of all coded projects contained within a highway project coding spreadsheet (specified as the tool's sole parameter), appends them to the `hwyproj` feature class (or replaces existing versions), and stores all spreadsheet coding for the project in the `hwyproj_coding` table.

The program `import_highway_projects_2.sas` is automatically called (via `sasrun.bat`) to import the coding data directly from the spreadsheet, perform some error checking, and reformat the data for import into the geodatabase. The tool checks for the following errors:
    - highway link coding missing any of the four required fields: `TIPID`, `ANODE`, `BNODE`, or `ACTION`
    - highway link coding using unavailable `ANODE`-`BNODE` combinations
    - incorrect action code applied to skeleton links
    - duplicate `ANODE`-`BNODE` coding within a single project
    - missing required attributes on new links (`ACTION`==4)
    - missing or invalid replace node values, or unusable attribute values on replace links (`ACTION`==2)

If errors are encountered, they are written to `temp/import_highway_projects_2.lst`, all processing stops before any data are imported to the geodatabase, and the user is prompted to correct the issues.

When updating the coding for an existing project, this process can be facilitated by exporting the existing coding with the "Export Highway Project Coding" utility, then modifying the coding in the output CSV and saving it in XLSX format before re-importing it.

Neither this tool nor the project coding spreadsheet provide a means of specifying a project's completion year. The `COMPLETION_YEAR` attribute in the `hwyproj` attribute table can be edited manually after a successful import. Alternatively, if the project is imported for use in a Conformity analysis, the `COMPLETION_YEAR` attribute will be adjusted automatically when the "Update Highway Project Years" tool is run.

## Incorporate Edits
```
incorporate_edits.py (no subscripts)
```
### Parameters
MHN Geodatabase - filepath to MHN geodatabase in which edits were made

### Description
This tool updates the topology of all MHN feature classes (nodes, bus routes and highway projects) after any geometric edits to roadway links, and automatically updates the values for a number of attributes (`ANODE`, `BNODE`, `ABB`, `MILES` & `BEARING` for links; `NODE`, `ZONE` & `AREATYPE` for nodes). Bus itinerary and highway project coding tables will also be altered, if any of the edits removed/split a link on which an itinerary/project relied.

Since all updates are based on roadway links, any other geometric changes in the network (e.g. moving nodes, reshaping bus route features, etc.) will be lost. For this reason, all editing should be done to links alone. (Changes to the attributes of other features, on the other hand, will remain after the updates.)

New links must have a valid value for the `BASELINK` and `DIRECTIONS` attributes. Additionally, if the link is set to be a base link (`BASELINK` = 1), then the tool will verify that all other required attributes have valid values. If not, the user will be alerted as to which links need changes. `ANODE`/`BNODE`/`ABB` values should always be left for the tool to calculate automatically: adjusting them manually can result in much more time spent troubleshooting if any errors are made.

This tool will also check for illegal geometric edits, and alert the user if any exist. Illegal edits specifically include:
    - duplicate node IDs: the same node is referenced by the `ANODE` or `BNODE` of two different links, even though the corresponding endpoints are not coincident
    - overlapping nodes: two coincident link endpoints have conflicting `ANODE`/`BNODE` values

The only parameter to specify before running this tool is the path to the edited MHN geodatabase.

## Update Highway Project Years
```
update_highway_project_years.py (no subscripts)
```
### Parameters
- MHN Geodatabase - filepath to MHN geodatabase
- MHN Geodatabase - filepath to MRN geodatabase
- Conformed Project Years CSV - filepath to a CSV file containing TIPIDs and completion years of projects considered "conformed" in the TIP (CSV typically named "year.csv")
- Coded Exempt Project Years CSV - filepath to a CSV file containing TIPIDs and completion years of projects considered "exempt" but still codeable in the TIP (CSV typically named "required.csv")
- Uncodeable Projects CSV - filepath to a CSV file containing TIPIDs and completion years of projects deemed uncodeable from the TIP (CSV typically named "nocode.csv")

### Description
This tool updates the completion years of projects to be included in Conformity analyses. The final completion year file is received from the TIP division after all project changes have been processed.

Parameters (pre-requisites for running this script):
- A CSV file containing TIPIDs & completion years of codable Conformed projects (default: import/year.csv)
- A CSV file containing TIPIDs & completion years of codable Exempt projects (default: import/required.csv)
- A CSV file containing TIPIDs of Conformed or Exempt projects deemed uncodable (default: import/no_code.csv)
- A current version of the Master Rail Network (MRN) geodatabase

Output files, if errors encountered:
- `output/early_transit_scenarios.csv`: projects whose completion years in year.csv or required.csv are later than one or more of the scenarios specified in the MHN bus_future, MRN future or MRN people_mover tables.
- `output/in_year_not_mhn.txt`: projects listed in year.csv or required.csv (excluding those in no_code.csv) that are either not coded in the hwyproj feature class or do not have a valid completion year
- `output/in_mhn_not_year.txt`: projects coded in the hwyproj feature class with valid completion years that are not listed in year.csv or required.csv

Finalizing the completion years is usually an iterative process.

# Secondary Tools/Utilities

## Export Future Network (Utilities)
```
export_future_network.py
```
### Parameters
- MHN Geodatabase - filepath to MHN geodatabase
- Build Year - the year to build the network to
- Folder Containing Output Geodatabase - filepath to a folder that will contain the output geodatabase
- Output Database Name - name for the output geodatabase

### Description
This tool will build the MHN to its coded state for a specified year, and save the modified links and nodes in a specified geodatabase. Within the geodatabase, it will create a year-specific feature dataset (if one doesn't already exist), into which the link and node feature classes will be saved. Temporary CSVs containing attribute data for MHN links and highway project coding to be implemented by the specified year are generated.

The program process_highway_coding.sas is automatically called (via sasrun.bat) to update network attributes, add new links and delete old ones according to the temporary highway project coding CSVs.

This tool was written specifically to facilitate the processing of up-to-date GTFS bus data that are newer than the MHN's base year (currently 2015), ensuring that the buses are routed on the roads in their current state.

It is also extremely useful for verifying that highway project coding does what it was intended to after running the "Import Highway Projects" tool: rather than selecting individual links that are affected by the coding and then viewing the raw coding related to it in the `hwyproj_coding` table, exporting a future network makes the coded changes immediately visible, and the updated attributes (e.g. `THRULANES1`) can be queried directly from the resultant links (or even symbolized by color/thickness/etc. in ArcMap) to quickly verify the accuracy of the coding.

## Export Highway Project Coding
```
utilities\export_hwyproj_coding.py
```
### Parameters
- MHN hwyproj layer - a layer of selected roadway projects from `hwyproj`
- Directory to save CSV - filepath to folder that will contain the output CSV
- Output CSV name - name for the output CSV

### Description
This tool will export the highway project coding stored in an MHN geodatabase's `hwyproj_coding` table into a CSV, formatted to match the highway project coding spreadsheet template required by the "Import Highway Projects" tool. As such, the tool facilitates the rapid modification and updating of existing highway project coding. (Note: that tool requires an Excel file as input, so the CSV should be saved in XLSX format prior to modification.)

The tool requires an MHN geodatabase's `hwyproj` feature class (or a layer of that feature class) as an input, and the coding will be exported from the `hwyproj_coding` table within the same geodatabase. If a layer with only a subset of highway projects selected is used, the output will be restricted to the coding for the selected project(s) only. Otherwise, the entire coding table will be exported.

## Generate Directional Links
```
utilities\generate_directional_links.py
```
### Parameters
- Input Roadway Feature Class - input bi-directional network feature class (e.g., `hwynet_arc`)
- Output Feature Class - output location for uni-directional feature class and with statistics fields

### Description
This tool takes a bi-directional network feature class (i.e. `hwynet_arc` in the MHN) and generates a directional one (in a user-specified location) based on the values in the `DIRECTIONS` field. Specifically, any link with `DIRECTIONS` == 2 OR `DIRECTIONS` == 3 will be duplicated, and the duplicate will be flipped so that it is digitized in the opposite direction. All direction-dependent attributes (e.g. `ABB`, `BEARING`, etc.) will be adjusted for the duplicates, and the no-longer-meaningful attributes (e.g. `AMPM2`, `THRULANES2`, etc., as well as `DIRECTIONS`) will be deleted for all links.

The resultant feature class is useful, in particular, for calculations of lane-miles (i.e. `THRULANES1` * `MILES`); without generating directional links, lane-miles would have to be calculated via a somewhat complicated function, like the following:

```python
def calc_lanemiles(directions, miles, lanes1, lanes2):
    ''' A method to calculate lane-miles for a given link. '''
    if directions == '1':
        lanemiles = miles * lanes1
    elif directions == '2':
        lanemiles = 2 * miles * lanes1
    elif directions == '3':
        lanemiles = miles * lanes1 + miles * lanes2
    return lanemiles
```

## Generate IRIS Correspondence Table
```
utilities\generate_iris_correspondence_table.py
```
### Parameters
- MHN Geodatabase - filepath to MHN geodatabase
- IRIS Feature Class - feature class containing IRIS roadway information
- IRIS Unique ID Field - field name in IRIS Feature Class corresponding to unique IDs
- Output Workspace - the output workspace in which the `mhn2iris` correspondence DBF file will be written

### Description
(NOTE: This tool is deprecated and needs a substantive update to be useful. Kept here for posterity.)

This tool compares MHN arterial links to IDOT's IRIS features and attempts find the best match for each. Matches, consisting of the MHN link's ABB value and the corresponding IRIS link's `OBJECTID` value, are saved in a timestamped DBF file in the MHN's output directory. This table is useful for joining IRIS data (such as the AADT counts used for travel demand model validation) to the MHN. This tool is mostly useful after extensive geometric updates or network expansion.

In order to find a suitable match, the script turns every MHN arterial link and IRIS match candidate into a series of points, spaced every x feet (default=25). For each MHN point, all IRIS points within y feet (default=60) are identified. For each link, the number of times each nearby IRIS link was matched is summed into a frequency table. The script then iterates over the frequency table, checking for the most likely match for each MHN link. A minimum of z matches (default=5) must have been made to a particular IRIS link for a match to even be considered, and the names of the two roads (using a combination of `ROAD_NAME` and the `MARKED_RT` fields in IRIS's case) are compared using the brilliant fuzzywuzzy module, which must be installed beforehand.

The final match for each MHN link (assuming any match was made) will be the IRIS link with the highest number of point-level matches that has an acceptable fuzzy string comparison score (or the best such score, if multiple IRIS links matched the same number of points).

This process is actually applied separately to four subsets of the MHN:

- Normal arterials
- Divided arterials/boulevards
- Expressways
- Ramps

Each of these uses slightly different distance parameters for the matching. For ramps and expressways, the road names are completely ignored; instead, a higher minimum number of point-matches (20) is required for a link-match to be considered.

## Straighten Selected Links
```
utilities\straighten_selected_links.py
```
### Parameters
- Layer Containing Selection of Line Features - input layer containing a selection of line layers to be straightened

### Description
This is a simple tool that will delete all non-endpoint vertices for links selected in ArcGIS Pro. It can be used for any line feature class, but if used on the MHN's `hwynet_arc` features, be sure to run the "Incorporate Edits" tool afterwards, just as you would after any other geometric updates.

## Update MHN Base Year
```
utilities\update_mhn_base_year.py
```
### Parameters
- MHN Geodatabase - filepath of MHN geodatabase
- Build Year - the year to build the network to
- Folder Containing Output Geodatabase - path to containing folder in which the output geodatabase will be written
- Output Geodatabase Name - name of output geodatabase, will overwrite if already exists

### Description
This tool will copy an MHN geodatabase and build it to its coded state for a new base year, leaving all bus routes and highway project coding (with completion years after the new base year) intact. Temporary CSVs containing attribute data for MHN links and highway project coding to be implemented by the specified year are generated.

After running this tool, The "Incorporate Edits" tool must also be run on the output geodatabase to rebuild all of the relationship classes and ensure nodes, highway project geometries, etc. are correct. It is also recommended that bus itineraries be imported from scratch into the new geodatabase with the "Import GTFS Bus Routes" tool.

The program `process_highway_coding.sas` is automatically called (via `sasrun.bat`) to update network attributes, add new links and delete old ones according to the temporary highway project coding CSVs.

It is important to note that, if a skeleton link (`BASELINK` == 0) is included in the coding for multiple highway projects, and if some but not all of those projects have a completion year after the new base year, the tool will run successfully but the output geodatabase will contain invalid highway project coding. 

The tool will automatically identify and report the specific projects (and specific links) with invalid coding. The coding for those projects should be exported from the input geodatabase (where it's still valid), modified to work with the updated network in the output geodatabase, and then imported into the output geodatabase.