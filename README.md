# CMAP-REPOS/mhn_programs

The MHN Programs repository is a collection of (mostly) Python scripts used to administer the [Chicago Metropolitan Agency for Planning (CMAP)](http://www.cmap.illinois.gov)'s Master Highway Network [geodatabase](http://www.esri.com/software/arcgis/geodatabase). This geodatabase is used, in conjunction with the Master Rail Network, to generate travel demand modeling networks, which we use for all of our modeling needs, including [transportation conformity](http://www.cmap.illinois.gov/conformity-analysis).

The MHN itself contains information about all of the major roads within the 21-county CMAP modeling area, as well as all major road construction projects scheduled between now and 2050, all current CTA and Pace bus routes, and planned future bus routes.

The scripts in this repository are used to import new GTFS bus data and road construction project details, maintain the integrity of the network after geometric edits have been made, and export data in a format suitable for input into [Emme](http://www.inrosoftware.com/en/products/emme) modeling networks. This repository includes an ArcGIS Toolbox (mhn_tools.tbx), which has been configured such that each of the main scripts can (and should!) be run within the ArcMap/ArcCatalog/ArcGIS Pro GUI out of the box!

## Getting Started
See the [wiki](https://github.com/CMAP-REPOS/mhn_programs/wiki/Getting-Set-Up).