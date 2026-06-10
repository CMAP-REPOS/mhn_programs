# MHN User Guide
This file contains information about the day-to-day maintenance of CMAP's Master Highway Netowrk (MHN) and all the processing tools. For information about the database's structure, see the [tool description](tool_description.md).

# Workspace Setup 
The primary Master Highway Network geodatabase resides in a restricted folder of the Data Depot at "V:\Secure\Master_Highway\mhn.gdb." There are currently (as of June 2026) efforts to bring the MHN to ArcGIS Enterprise. 

Regardless, for MHN processing, it is strongly recommended that updates be made and tested on a local (C:\ drive) copy/replica before updating the official version. This allows the work to be done faster and more reliably than trying to read/write data over the network— especially if connected via VPN. 

To create a local environment for managing the MHN, do the following:

1.	Ensure that you have SAS and ArcGIS Pro installed on your computer. (Until all SAS scripts are translated to Python.)
2.	Create a new folder on your local drive where you have full read/write access (e.g., "C:\Users\username\Documents\MHN").
3.	Clone this git repository from GitHub into your MHN folder.
4.  Copy "mhn.gdb" and "zone_systems.gdb" from "V:\Secure\Master_Highway" into your MHN folder.
5.  If you wish to use a pre-made template, there is an ArcGIS Pro project file on the V drive that you can copy to your C drive, as well. (When first opening, ensure filepaths are updated to your current setup.)

# Editing the MHN
Historically, virtually all MHN editing has been processed within the "mhn_editor" map of the "master_highway" ArcGIS Pro project. The way the MHN geodatabase and the processing tools are set up, you will almost never need to edit any feature classes or tables, other than `hwynet_arc`. 

This feature class contains the network links, which form the building blocks for the rest of the datasets. 

For example, `hwynet_node` contains network nodes, but these are automatically generated from the endpoints of `hwynet_arc` whenever the "Incorporate Edit"s tool is run. The highway project features in `hwyproj` derive their geometries directly from the links referenced in the `hwyproj_coding` table and are automatically updated by the "Incorporate Edits" and "Import Highway Projects" tools. 

The bus routes in `bus_base`/`bus_current`/`bus_future` are generated in the same way as highway projects. The highway project coding and bus itinerary tables are imported from external spreadsheets with the various "Import" tools and are generally much easier to update by importing new spreadsheets rather than trying to modify the geodatabase tables directly.

Below are instructions for handling some common modifications. Consider familiarizing yourself with ArcGIS Pro's editing functionality. Make sure you enable snapping so that your link endpoints align correctly, and ensure editing sessions terminate properly before any tools are run. (Otherwise, errors can occur.)

- _**Splitting a link.**_ If an existing link needs to be split (e.g., to add an intersection with a new link), begin an edit session, select the link to be split, split it with ArcGIS’s split tool, saving your edits and ending the edit session, then running the "Incorporate Edits" tool. A new node will automatically be generated at the location of the split, and the `ANODE`, `BNODE`, and `ABB` attributes of the parts will be automatically updated. A link can be split multiple times, if needed, before running "Incorporate Edits". However, **DO NOT** manually modify the `ANODE` or `BNODE` attributes of the split links prior to running "Incorporate Edits"— the only way the script knows an existing link has been split is that it sees multiple links with identical `ANODE`-`BNODE`-`ABB` values. If you split a link with highway project coding or bus route coding on it, the coding will automatically be updated to reference the new links.
- _**Adding a new skeleton link**_. Skeleton links include any links that are not part of the base year network, but are needed to code highway projects that build new roads (or realign existing ones). To add a skeleton link, begin an edit session on `hwynet_arc` and create a new line feature. Skeleton links must have `BASELINK` == 0 as well as a non-zero `DIRECTIONS` value. Optional attributes that may be set on skeleton links, if applicable, are: `TOLLSYS`, `NHSIC`, `SRA`, `CHIBLVD`, `TRUCKRTE`, `TRUCKRES`, `TRUCKRES_UPDATED` and  `VCLEARANCE`. (See [data-structure.md](data-structure.md) for details about what these represent.) Other than that, all attributes should be blank, including `ANODE`, `BNODE`, and `ABB`, which are some of the attributes that are assigned automatically when you run "Incorporate Edits".
- _**Adding a new baselink**_. Baselinks are the links representing the base year network (currently 2015, which is different than Scenario 100, currently 2019). The process for adding these is the same as adding a skeleton link, except you must set `BASELINK`==1 and supply values for all of the following attributes: `DIRECTIONS`, `MODES`, `TYPE1`, `THRULANES1`, `THRULANEWIDTH1`, `POSTEDSPEED1`, and `AMPM1`. Additionally, if `DIRECTIONS`=3, you must supply `TYPE2`, `THRULANES2`, `THRULANEWIDTH2`, `POSTEDSPEED2` and `AMPM2`.
- _**Deleting a link**_. In an edit session, select a link and press the Delete key on your keyboard, or Right-click + Delete, then save your edits. **IMPORTANT**: relationship classes in the MHN are configured so that when a link is deleted, any records in the `hwyproj_coding` and `bus_itin` tables that reference that link will *also be deleted*, leaving gaps in bus itineraries and potentially incomplete highway project coding. Before deleting a link, carefully consider the cascading effects it may have on these other datasets. (If a gap exists in a bus itinerary, the "Generate Transit Files" tool will attempt to fill that gap using a shortest-path algorithm on the nearby links, so you will likely still be able to generate Emme transaction files.) Converting a baselink to a skeleton link or vice versa (by changing the value of the `BASELINK` attribute) will have the same practical effect on these datasets as deleting a link, since the relationships are configured to reference `ABB` values, which change when `BASELINK` does.

**IMPORTANT**: Run the "Incorporate Edits" tool after making any of the changes described above.

# Using the Highway and Transit Coding Spreadsheets
Highway project coding is stored in an Excel spreadsheet and is imported into the MHN geodatabase by running the "Import Highway Projects" tool. Using the spreadsheet to store the coding allows multiple people to work on highway project coding simultaneously. There is no limit on the amount of project coding that may be imported at one time. The tool used to import highway coding into the database **will delete an already existing project** from the route system to prepare for new coding. Therefore, **coding for an entire project must be imported when a change is made to it**. To export current project coding for an extensive highway project, consider using the "Export Highway Project Coding" tool.

The tool that imports the coding into the MHN geodatabase directly accesses the spreadsheet data, therefore:
- Highway project coding must be stored in the "template" sheet of the workbook.
- The "template" name for the worksheet must not be changed.
- The column names in "template" must not be changed.

## Spreadsheet Variables
The table below lists the coding spreadsheet variables and their descriptions. Comments are included in the spreadsheet to assist the analyst in coding the variables. Variables ending in "1" apply to the "from-to" direction (anode-to-bnode), and those ending in "2" apply to the "to-from" direction (bnode-to-anode). 

### Table 1. Coding Spreadsheet Columns and Descriptions
| Coding Template Variable | Description |
|---|---|
| `TIPID` | TIP project identification number (with or without dashes). |
| `ANODE` | MHN link a-node number. |
| `BNODE` | MHN link b-node number. |
| `ACTION` | Network processing action code:<br>- `1` = modify<br>- `2` = replace<br>- `3` = delete<br>- `4` = add |
| `TYPE1` & `TYPE2` | New facility type code:<br>- `1` = arterial<br>- `2` = freeway<br>- `3` = freeway-arterial ramp<br>- `4` = expressway<br>- `5` = freeway-freeway ramp<br>- `6` = centroid connector<br>- `7` = toll facility<br>- `8` = metered freeway entrance ramp |
| `SIGIC` | Add signal interconnect to link (code = `1` to add, code = `-1` to remove). |
| `FEET1` & `FEET2` | New average driving lane width. |
| `LANES1` & `LANES2` | New number of driving lanes. |
| `SPEED1` & `SPEED2` | New speed limit. |
| `REP_ANODE` & `REP_BNODE` | Node numbers of link providing attributes, *only* for `ACTION = 2`. |
| `TOLLDOLLARS` | New toll amount. |
| `DIRECTIONS` | New directions code:<br>- `1` = one way<br>- `2` = two way (attributes in both directions identical)<br>- `3` = two way (at least one attribute different in opposing direction) |
| `PARKLANES1` & `PARKLANES2` | Add/remove parking lanes: coded number will be added to parking lanes number currently coded on link in MHN to calculate final lanes (code positive to add, negative to remove). |
| `CLTL` | Add/remove continuous left turn lane (code = `1` to add, code = `-1` to remove). |
| `AMPM1` & `AMPM2` | New time period restrictions code:<br>- `1` = open all time periods<br>- `2` = open AM periods only<br>- `3` = open PM periods only<br>- `4` = open off-peak periods only |
| `MODES` | New modes permitted code:<br>- `1` = all vehicles<br>- `2` = autos only<br>- `3` = trucks only<br>- `4` = transit only (only called for transit networks) |
| `RR_GRADE_SEP` | Add/remove at-grade railroad crossing (code = `1` to add, code = `-1` to remove). |
| `TOD` | Time-of-day code indicating specific time periods when changes are applied. Default of blank or `0` means changes applied to all periods. Code is text string of affected time periods:<br>- `1` = 8 PM – 6 AM<br>- `2` = 6 AM – 7 AM<br>- `3` = 7 AM – 9 AM<br>- `4` = 9 AM – 10 AM<br>- `5` = 10 AM – 2 PM<br>- `6` = 2 PM – 4 PM<br>- `7` = 4 PM – 6 PM<br>- `8` = 6 PM – 8 PM |

Four "action codes" control link processing. Action codes are defined below. For all action code values, the variables `TIPID`, `ANODE`, `BNODE`, and `ACTION` must be filled with a non-zero number. The remaining variables are coded based on the following rules:
- Action code `1` modifies the coded attributes on links with existing attributes.
    - Only attributes that are changing must be coded— the rest may be left blank, or filled with "0"
- Action code `2` (named "replace") copies attributes from one link to another, and is primarily used in conjunction with a "delete" function to delete the link it copied (hence, "replace").
    - Only `REP_ANODE` and `REP_BNODE` (denoting the link to copy from) need coding
- Action code `3` deletes a link.
    - No attributes need coding
- Action code `4` is applied to a skeleton link to add it to the network.
    - all final attributes must be coded (including `AMPM1`, `AMPM2`, and `MODES`)

During network processing, current MHN link attributes are updated with highway project coding entries to represent conditions after the project is implemented. Only the attributes changing due to project implementation need to be coded in the spreadsheet; unchanged attributes should be left blank or coded with a zero.

Highway project coding rules for parking lanes (`NEWPARKLN1` and `2`), continuous left turn lanes (`CLTL`) and railroad grade separations (`NEWRRGRADECROSS1` and `2`) are slightly different.  Values for these attributes are added to (or subtracted from) current MHN link values to yield the final result.  This allows for these attributes to be increased, decreased or removed.  This is necessary because there is no way to determine if a "zero" coded for these variables represents no change or the removal of an attribute.

Highway projects are coded to work independently of one another.  Stand-alone coding allows network attributes to be processed correctly, regardless of the specific mix of projects in the final network.  Thus, modifications (`ACTION_CODE`=1) should always be coded to a base link, even if coding for another project leads to the replacement (`ACTION_CODE`=2) of that specific link.  The network processing program ensures the appropriate attributes are carried forward.

There is no limit on the number of projects that can reference the same link; however each link should only be referenced once in the coding for a particular project.  If a link is modified in one project and replaced in a different project, it will appear once in the coding for each.  Its attributes are updated in the first project (`ACTION_CODE`==1) and it is deleted (`ACTION_CODE`==3) in the second project when its attributes are given to the new links (`ACTION_CODE`==2).  If the update and replacement occur within the same project, the base link is deleted and the new links are coded with `ACTION_CODE`==4 to ensure that all final attributes are coded.  Otherwise the base link would require two coding entries to modify and delete it within this project.

The only time a link may be referenced more than once within the coding for a specific project is when the tod variable is used.  This variable identifies specific time-of-day periods when the coded changes will be applied (only the changes being applied during the time periods may be coded with the tod value).  For instance, if a project is adding a signal interconnect, widening lanes and closing one driving lane during the peak periods for a particular link, two coding entries for that link will be needed in the project.  One will update the sigic and feet1 values, and the other will use tod to change lanes1 during the peak periods.  

Finally, the most restrictive capacity is always coded for add-lanes projects.  If implementation of a project will not result in an additional through lane along the entire length of the MHN link, the additional lane is not coded.  If an add-lanes project is being applied to part of an MHN link and the additional lane already exists on the remaining portion, the add-lanes should be coded. 

### Common Coding Errors
Highway project coding errors generally fall into three categories:
- **Wrong nodes** - The anode-bnode combination does not match a link in the MHN. This error is flagged before project coding is imported. 
- **Missing variables for `ACTION_CODE`== 4** - All final attributes must be coded, including `AMPM1` (and `AMPM2` if necessary) and `MODES`. This error is flagged before project coding is imported.
- **Incorrectly coding `ADD_` variables** - Values for parking lanes (`PARKLN`), continuous left turn lanes (`CLTL`) and at-grade crossings (`RRGRADECROSS`) are added to existing `hwynet_arc` values.  These variables are best verified by checking final link attributes in an analysis network.


# Using the Processing Tools
- **Incorporate Edits** – Enforces network topology after modifying any of the links in hwynet_arc. Specifically, it regenerates all of the node, bus route and highway project feature classes, and also updates several attributes of the hwynet_arc feature class. Run this any time you have modified the geometry of links in hwynet_arc.
- **Import Highway Projects** – Imports a highway project coding spreadsheet into the MHN (specifically the hwyproj_coding table and the hwyproj feature class). Run this whenever you are adding a new highway project or updating outdated coding for an existing project. Coding for multiple projects can be contained in a single spreadsheet. The highway project coding template is stored in V:\Secure\Master_Highway\import\coding_templates. IMPORTANT: the highway project coding template does not currently include a column for specifying each project’s completion year. After importing highway projects, you can either set the hwyproj COMPLETION_YEAR attribute manually, or run Update Highway Project Years. If you need to add coding for a project that does not have a TIPID, you should use the format 99-99-XXXX, where XXXX is incremented from the already-existing “pseudo-projects”; importing any coding for an existing TIPID (real or not) will overwrite the existing coding.
- **Import Future Bus Routes** – Imports a future bus coding spreadsheet into the MHN (specifically the bus_future_itin table and bus_future feature class). Run this whenever you are adding or updating coding for future bus routes (i.e., proposed routes that are part of the TIP). Coding for multiple routes can be contained in a single spreadsheet. The future bus coding template is stored in V:\Secure\Master_Highway\import\coding_templates.
- **Import GTFS Bus Routes** – Imports updated existing bus schedules into the MHN (specifically the bus_base and/or bus_current feature classes and their associated itinerary tables). The input CSV files for this tool are generated from raw GTFS data through a separate process, which Nick Ferguson is responsible for. The latest base/current CSVs should be stored in V:\Secure\Master_Highway\import\gtfs_bus_data. IMPORTANT: update mhn_programs\MHN.py after running this tool to ensure that the values in the bus_years dictionary correctly represent the new data.
- **Update Highway Project Years** – Compares the projects present in the hwyproj and bus_future feature classes (as well as the MRN) against the contents of 3 separate CSV files (which Craig Heither generally prepares for each conformity analysis), stored in V:\Secure\Master_Highway\import:
    - "year.csv" contains the completion years for each conformed project in the TIP
    - "required.csv" contains the completion years for exempt projects that have MHN coding  
    - "no_code.csv" contains a list of conformed TIP projects that cannot be coded in the MHN
    
    This tool should always be run prior to generating Emme batchin files for a conformity analysis to ensure that the correct projects are built for each modeled year. The tool will alert the user to any projects listed in year.csv or required.csv that do not have any coding in the MHN/MRN (in which case they should be coded if possible, or else added to no_code.csv), as well as any projects that are coded in the MHN/MRN with a valid completion year (≤2050) that are not listed in year.csv or required.csv (in which case they should be added to one of the CSVs if they are valid, or else have their completion year set to 9999). If no warnings arise, the tool will update the COMPLETION_YEARS field in hwyproj to match the CSV contents and the MHN is ready to generate Emme batchin files for conformity. This is typically an iterative process that requires looking up many projects in the TIP to determine how they should be handled.
- **Generate Highway Files** – Generates the highway batchin files for one or more Emme scenario networks. If generating conformity networks, only run this after Update Highway Project Years has successfully been run with no warnings.
- **Generate Transit Files** – Generates the non-rail transit batchin files for one or more Emme scenario networks. This tool can only be run after Generate Highway Files has been run for the same scenarios, and after the rail batchin files have been exported from the MRN via the MRN processing tools.

- There are also several additional tools in the **Utilities** toolset that do not play critical roles in the day-to-day management of the MHN, but are occasionally useful:
    - **Export Future Network** – Builds MHN links and nodes to a specified year (incorporating all highway projects with completion years up to that year) and saves the results in a user-specified geodatabase. It runs very quickly and is useful for verifying that a scenario will include the right projects – and that they will be represented correctly – prior to creating Emme batchin files.

    - **Export Highway Project Coding** – Saves a CSV containing the current highway project coding for any hwyproj features that are selected in ArcMap. The CSV is formatted to match the highway project coding template spreadsheet, so if you are adjusting the coding for an existing project this tool provides you with a great starting point, rather than having to code the entire project from scratch or dig up the original coding spreadsheet.

    - **Update MHN Base Year** – It doesn’t happen very often, but when the MHN base year needs to be updated, this tool is designed to do the hard work. It uses the same functionality behind Export Future Network to build the nodes and links to a specific year, but it also keeps the rest of the MHN (highway projects still in the future from the new base year, bus routes, etc.) intact. Results are saved in a new geodatabase. Since this tool has been used so infrequently, you would be well advised to inspect the output VERY CAREFULLY before replacing the current MHN. IMPORTANT: this tool does not modify the SCENARIO values in bus_future or parknride – these will need to be updated manually if the scenario codes are changing to represent different years (or, even better, these fields should be replaced with START_YEAR fields, like COMPLETION_YEAR in hwyproj).

    - **Straighten Selected Links** – Removes all vertices other than the endpoints from the link(s) currently selected in ArcMap. Useful when making extensive geometrical edits. Incorporate Edits must be run after using this tool.

    - **Generate Directional Links** – Generates a new line feature class based on hwynet_arc, but with each link only representing a single direction (like Emme) rather than the MHN’s bidirectional representation. Can be useful for QC or calculations of things like lane-miles.

    - **Generate IRIS Correspondence Table** – A legacy tool that should probably not be used anymore. Aaron Brown has developed better procedures for matching MHN links to IRIS links.

# Updating Processing Tools
Most of these tools have existed largely in their current form [since 2013](https://github.com/CMAP-REPOS/mhn_programs/releases/tag/C13Q3), and have therefore been tested extensively. For that reason, it is rare that the code will require major changes in response to a bug (and most bugs have instead come from trying to implement new functionality). 

However, sometimes a bug is discovered, or a new feature is requested. The code is all maintained in the mhn_programs repository on GitHub, which tracks all changes made over time. It also allows users to create “branches” to test new code without overwriting the official version. I have generally worked with 2 branches: the "master" branch, which is the latest stable version of the code, and the "develop" branch, where new features are tested. Once I am happy with the changes I have made in "develop", I create a pull request to merge those changes into "master." If I am working on multiple unrelated new features simultaneously, I might create a new branch for each new feature and merge each one as it is finished.

If changes are made to the MHN base year, scenario years, GTFS bus years, the zone system, or the travel model’s time-of-day periods, the corresponding variables in MHN.py should be updated as well. In addition to these variables, MHN.py contains many functions that are used by multiple processing tools.

In general, the code in "V:\Secure\Master_Highway\mhn_programs" should always be kept on the "master" branch, while the clone stored on your local drive should be on the "develop" branch. Test new code locally and create a pull request when you’re satisfied. After approving a pull request from "develop" to "master" on GitHub, be sure to pull those changes to "V:\Secure\Master_Highway\mhn_programs" to keep it in sync with GitHub.

For more details about managing Git/GitHub repositories, see the [GitHub docs](https://docs.github.com/en/repositories).


# Tips for Successful Processing
Here are some general tips on running any of the MHN processing tools:

- Any edit session must be closed prior to running the scripts.

- Affected feature classes must not be active in ArcCatalog when a script is running in ArcMap, and vice versa.

- The *main* MHN geodatabase is stored at "V:\Secure\Master_Highway\mhn.gdb." (Currently working on moving it to ArcGIS Enterprise.) However, since processing can be extremely slow over the network, it is recommended that a copy of this geodatabase be placed on your C: drive for any editing and processing. Once processing is complete, the modified copy can then be moved to the network, to replace the original version.

## Editing
- If a new arc is digitized, only the following fields will be calculated automatically: `ANODE`, `BNODE`, `ABB`, `MILES`, `BEARING`. All links (including skeletons) must have `DIRECTIONS` and `BASELINK` coded manually. If `BASELINK` == 1, all other required attributes (depending on `DIRECTIONS`) must be coded, too.
- Do not manually specify `ANODE` or `BNODE` (or `ABB`) values. These will all be calculated automatically.

- If you split a link during editing, do not alter the `ANODE`, `BNODE` or `ABB` values: this is how the processing scripts determine which links have been split, and they will be reassigned automatically. Leaving these values intact will allow any highway project coding or bus itinerary segments to be maintained after incorporating the edits. Any other attributes of split links are fair game for changing.

- Run the "Incorporate Edits" tool after any geometric edits have been made (e.g. deleting links, digitizing new links, splitting existing links, moving the ends of links, adding/deleting link shape points).

- Relationship classes have been set up such that, if any of the line features are deleted from one of the route systems (`hwyproj`, `bus_base`, `bus_current`, or `bus_future`), the corresponding coding/itinerary will **also** be deleted from the corresponding coding/itinerary table. These deletions must be made during an editing session, however.

- Enable "snapping" whenever you are editing `hwynet_arc`. This will help to ensure that the endpoints of all links meeting at an intersection are at the exact same coordinates. If two links look like their endpoints meet, but they are actually a very small distance apart, "Incorporate Edits" will create two different nodes and the links will not actually be connected to each other in the travel model.

- If adding new skeleton links for a highway project for which IDOT, etc., have shared a detailed schematic, I recommend georeferencing a PNG or JPG version of it. (I frequently take screenshots of their PDF documents to manage this.) This removes the guesswork from digitizing new links and ensures that the MHN project will closely resemble the final build.

- Do not edit the geometry or attributes of `hwynet_node` – this feature class is rebuilt entirely from scratch based on `hwynet_arc`’s endpoints every time "Incorporate Edits" is run, and your edits will vanish.

- Do not manually edit the geometry of `hwyproj`, `bus_current`, `bus_base`, or `bus_future`. Instead, update the underlying links in `hwynet_arc` and run "Incorporate Edits". (If you are rerouting a bus or changing a highway project without modifying the link geometry, then import a new highway/bus coding spreadsheet.)

- Feel free to edit attributes of `hwyproj`, `bus_current`, `bus_base`, or `bus_future` (e.g., changing a highway project’s completion year or a bus route’s time-of-day periods), but if you are making changes more detailed than project- or route-level information you are strongly encouraged to make the changes in a highway/bus coding spreadsheet and import them instead of making the changes directly in the geodatabase.

- If a highway project or future bus route is no longer part of the TIP, consider changing the `COMPLETION_YEAR` to `9999` instead of deleting the project from the MHN. This way, they will be ignored when generating highway/transit files but, if they are resurrected in the TIP in the future, they will not need to be recoded from scratch.

- If you delete any links that have base/current bus route coding on them, it is recommended that you re-import the base/current GTFS data.

- Always make sure that centroid connectors maintain access to the network after links are deleted (either by literally deleting them from `hwynet_arc` or with `ACTION` == 3 as part of a highway project). If all links providing access/egress to a centroid connector must be deleted, consider moving that centroid connector to another intersection within the same zone.

- When creating skeleton links for a new highway project that involves realignment, be careful not to add a link with the same `ANODE` and `BNODE` as an existing baselink. While they will have different `ABB` values (`ANODE`-`BNODE`-`0` vs. `ANODE`-`BNODE`-`1`), it’s still a problem because the highway/bus coding spreadsheets only identify links by `ANODE` and `BNODE`. (See [this GitHub issue](https://github.com/CMAP-REPOS/mhn_programs/issues/44).)

- For massive, multi-year highway projects where significant portions will be completed and open to traffic before the official completion year for the entire project, I have coded the completed portions as separate projects (using "pseudo"-TIPIDs of the format `99-99-XXXX`) with their own completion years. This has the added benefit of allowing the already-completed portions of projects to be included in the no-build scenario for an RSP analysis, for example. Notable projects where this approach was used are the "Elgin-O’Hare Western Access" project (which has 2 pseudo-projects with 2016 & 2017 completion years), and the "I-190 Access Improvements" project (which has a pseudo-project with a 2016 completion year). Beginning in 2025, these pseudo-IDs can be documented in the `NOTES` field of the `hwyproj` feature class.

- The `RSP_ID` field in `hwyproj` is currently an integer field, because ON TO 2050 originally only used numeric IDs. With the plan update, however, some RSPs have alphanumeric IDs (e.g., A2, A3, A4). These have been given numeric IDs of the form `99XX`, where XX is the numeric portion of their actual ID (e.g., A3 = 9903). In the future, this field should probably be converted to text. Also, the `MCP_ID` field is leftover from the GO TO 2040 days and should probably be removed. The `RCP_ID` field is already text and contains RCP IDs for the 2026 long-range transportation plan.
