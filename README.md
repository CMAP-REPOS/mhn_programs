GOTO2040/mhn_programs
=====================
The MHN Programs repository is a collection of (mostly) Python scripts used to administer the Chicago Metropolitan Agency for Planning (CMAP)'s Master Highway Network geodatabase. This geodatabase is used, in conjunction with the Master Rail Network, to generate travel demand modeling networks, which we use for all of our modeling needs, including transportation conformity.

The MHN itself contains information about all of the major roads within the 21-county CMAP modeling area, as well as all major road construction projects scheduled between now and 2040, all current CTA and Pace bus routes, and planned future bus routes (like CTA's Ashland BRT).

The scripts in this repository are used to import new GTFS bus data and road construction project details, maintain the integrity of the network after geometric edits have been made, and export data in a format suitable for input into Emme modeling networks. They are intended to be loaded into an ArcGIS toolbox and run from within the ArcMap or ArcCatalog GUI.

ArcGIS Toolbox Configuration
----------------------------
There are currently 7 main scripts, each of which corresponds to an ArcGIS tool. These main scripts all import the MHN.py module, and most of them call subsequent SAS and/or Python scripts, which do not need to be configured as ArcGIS tools. The main ones should be added to an ArcGIS Toolbox (right-click -> Add -> Script...) with the following configurations (parameter order _is_ important):

* **generate_highway_files.py**
  * Parameters:
    1. Scenario Code (string; input; default=100)
    2. Root Folder for Batchin Files (folder; input)

* **generate_transit_files.py**
  * Parameters:
    1. Scenario Code (string; input; default=100)
    2. Root Folder for Batchin Files (folder; input)
    3. CT-RAMP Output (boolean; input; default=false)

* **import_future_bus_routes.py**
  * Parameters:
    1. Future Bus Route Coding XLS (file; input)

* **import_gtfs_bus_routes.py**
  * Parameters:
    1. Bus Route Header CSV (file; input)
    2. Bus Route Itinerary CSV (file; input)
    3. Bus Route System to Import Into (string; input; default=current)

* **import_highway_projects.py**
  * Parameters:
    1. Highway Project Coding XLS (file; input)

* **incorporate_edits.py**
  * Parameters: _N/A_

* **update_highway_project_years.py**
  * Parameters:
    1. Project Years CSV (file; input)
    2. Uncodable Projects CSV (file; input)
    3. MRN Geodatabase (workspace; input)

### Optional Utilities Toolset
This repository also includes a "Util" folder, containing scripts that perform various utilitarian functions relating to the MHN. If you wish to use any of them, you can create a new Toolset within your Toolbox (right-click -> New -> Toolset) and add the scripts to it in the same way as you added the main ones. The configurations are as follows:

* **generate_directional_links.py**
  * Parameters:
    1. Input Arc Feature Class (feature class; input)
    2. Output Feature Class (feature class; output)
