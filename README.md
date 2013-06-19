mhn_programs
============
The MHN Programs repository is a collection of (mostly) Python scripts used to administer the Chicago Metropolitan Agency for Planning (CMAP)'s Master Highway Network geodatabase. This geodatabase is used, in conjunction with the Master Rail Network, to generate travel demand modeling networks, which we use for all of our modeling needs, including transportation conformity.

The MHN itself contains information about all of the major roads within the 21-county CMAP modeling area, as well as all major road construction projects scheduled between now and 2040, all current CTA and Pace bus routes, and planned future bus routes (like CTA's Ashland BRT).

The scripts in this repository are used to import new GTFS bus data and road construction project details, maintain the integrity of the network after geometric edits have been made, and export data in a format suitable for input into Emme modeling networks. They are intended to be loaded into an ArcGIS toolbox and run from within the ArcMap or ArcCatalog GUI.
