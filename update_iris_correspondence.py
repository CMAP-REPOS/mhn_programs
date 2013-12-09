#!/usr/bin/env python
'''
    update_iris_correspondence.py
    Author: npeterson
    Revised: 12/09/2013
    ---------------------------------------------------------------------------
    Re-generate the MHN2IRIS table with updated correspondences. Useful after
    extensive geometric updates or network expansion.

'''
import os
import sys
import arcpy
import MHN

# -----------------------------------------------------------------------------
#  Set parameters.
# -----------------------------------------------------------------------------
