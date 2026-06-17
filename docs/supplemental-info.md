# Master Highway Network Supplemental Information
The following details additional information or codes that are used during MHN coding/processing.

## Truck Restriction Codes
Truck restriction codes are in the `TRUCKRES` field of the `hwynet_arc` feature class. These values are manually coded into base links as well as skeleton links, and do not get incorporated into highway project coding processing. (See [Issue #164](https://github.com/CMAP-REPOS/mhn_programs/issues/164) on GitHub.)
| Restriction No. | Type | Rule | Emme Mode |
|---|---|---|---|
| 39 | Per Axle Weight Restrictions | Maximum 2 axles | ASHTlb |
| 13 | Per Axle Weight Restrictions | 2 tons (4,000 lbs) per axle; GVW 10 tons (20,000 lbs) | ASHTb |
| 37 | Per Axle Weight Restrictions | 3 tons (6,000 lbs) per axle | ASHTb |
| 7 | Per Axle Weight Restrictions | 5 tons (10,000 lbs) per axle | ASHTlb |
| 38 | Per Axle Weight Restrictions | 6 tons (12,000 lbs) per axle | ASHTlb |
| 40 | Per Axle Weight Restrictions | 6 tons (12,000 lbs) per axle; maximum 2 axles | ASHTlb |
| 16 | Per Axle Weight Restrictions | 6 tons (12,000 lbs) per axle; GVW 18 tons (36,000 lbs) | ASHTlb |
| 30 | Per Axle Weight Restrictions | 6 tons (12,000 lbs) per axle; GVW 25 tons (50,000 lbs) | ASHTmlb |
| 32 | Per Axle Weight Restrictions | 8 tons (16,000 lbs) per axle | ASHThmlb |
| 22 | Per Axle Weight Restrictions | 9 tons (18,000 lbs) per single-axle; 16 tons (32,000 lbs) per tandem-axle; GVW 73,280 lbs | ASHThmlb |
| 23 | Per Axle Weight Restrictions | 10 tons (20,000 lbs) per axle | ASHThmlb |
| 33 | Per Axle Weight Restrictions | 10 tons (20,000 lbs) per single-axle; 17 tons (34,000 lbs) per tandem-axle | ASHThmlb |
| 26 | Per Axle Weight Restrictions | 10 tons (20,000 lbs) per axle; GVW 40 tons (80,000 lbs) | ASHThmlb |
| 1 | Total Weight Restrictions | No trucks | ASH |
| 3 | Total Weight Restrictions | No trucks except B plates (GVW 4 tons/8,000 lbs) | ASHTb |
| 18 | Total Weight Restrictions | GVW 2.5 tons (5,000 lbs) | ASH |
| 4 | Total Weight Restrictions | GVW 3 tons (6,000 lbs) | ASHTb |
| 9 | Total Weight Restrictions | GVW 3.5 tons (7,000 lbs) | ASHTb |
| 2 | Total Weight Restrictions | GVW 5 tons (10,000 lbs) | ASHTb |
| 11 | Total Weight Restrictions | GVW 6 tons (12,000 lbs) | ASHTb |
| 35 | Total Weight Restrictions | GVW 7 tons (14,000 lbs) | ASHTb |
| 10 | Total Weight Restrictions | GVW 8 tons (16,000 lbs) | ASHTb |
| 25 | Total Weight Restrictions | GVW 9 tons (18,000 lbs) | ASHTb |
| 8 | Total Weight Restrictions | GVW 10 tons (20,000 lbs) | ASHTlb |
| 17 | Total Weight Restrictions | GVW 12 tons (24,000 lbs) | ASHTlb |
| 34 | Total Weight Restrictions | GVW 14 tons (28,000 lbs) | ASHTlb |
| 19 | Total Weight Restrictions | GVW 15 tons (30,000 lbs) | ASHTlb |
| 29 | Total Weight Restrictions | GVW 16 tons (32,000 lbs) | ASHTlb |
| 27 | Total Weight Restrictions | GVW 20 tons (40,000 lbs) | ASHTlb |
| 41 | Total Weight Restrictions | GVW 21 tons (42,000 lbs) | ASHTlb |
| 5 | Total Weight Restrictions | GVW 25 tons (50,000 lbs) | ASHTmlb |
| 48 | Total Weight Restrictions | GVW 25 tons (50,000 lbs); SU only | ASHTmlb |
| 28 | Total Weight Restrictions | GVW 36 tons (72,000 lbs) | ASHThmlb |
| 24 | Total Weight Restrictions | GVW 73,280 lbs | ASHThmlb |
| 20 | Total Weight Restrictions | GVW 74,880 lbs | ASHThmlb |
| 6 | Total Weight Restrictions | GVW 40 tons (80,000 lbs) | ASHThmlb |
| 31 | Total Weight Restrictions | GVW: 10 tons (20,000 lbs) SU; 22 tons (44,000 lbs) 3-4 axles; 36 tons (72,000 lbs) 5+ axles; 30 tons (60,000 lbs) tag trailers | ASHTlb |
| 44 | Total Weight Restrictions | GVW: 11 tons (22,000 lbs) SU; 14 tons (28,000 lbs) 3-4 axles; 17 tons (34,000 lbs) 5+ axles | ASHTlb |
| 43 | Total Weight Restrictions | GVW: 11 tons (22,000 lbs) SU; 16 tons (32,000 lbs) 3-4 axles; 19 tons (38,000 lbs) 5+ axles | ASHTlb |
| 49 | Total Weight Restrictions | GVW: 12 tons (24,000 lbs) SU; 14 tons (28,000 lbs) 3-4 axles; 16 tons (32,000 lbs) 5+ axles | ASHTlb |
| 14 | Total Weight Restrictions | GVW: 13 tons (26,000 lbs) SU; 25 tons (50,000 lbs) 3-4 axles; 29 tons (58,000 lbs) 5+ axles | ASHTlb |
| 47 | Total Weight Restrictions | GVW: 14 tons (28,000 lbs) SU; 15 tons (30,000 lbs) 3-4 axles; 16 tons (32,000 lbs) 5+ axles | ASHTlb |
| 42 | Total Weight Restrictions | GVW: 18 tons (36,000 lbs) SU; 21 tons (42,000 lbs) 3-4 axles; 23 tons (46,000 lbs) 5+ axles | ASHTlb |
| 46 | Total Weight Restrictions | GVW: 19 tons (38,000 lbs) SU; 23 tons (46,000 lbs) 3-4 axles; 26 tons (52,000 lbs) 5+ axles | ASHTlb |
| 45 | Total Weight Restrictions | GVW: 22 tons (44,000 lbs) SU; 28 tons (56,000 lbs) 3-4 axles; 31 tons (62,000 lbs) 5+ axles | ASHTmlb |
| 36 | Total Weight Restrictions | GVW: 22 tons (44,000 lbs) SU; 29 tons (58,000 lbs) 3-4 axles; 36 tons (72,000 lbs) 5+ axles | ASHThmlb |
| 21 | Time and Date Restrictions | GVW 2.5 tons (5,000 lbs); restriction 12:00 AM to 5:00 AM | ASH |
| 12 | Time and Date Restrictions | GVW 6 tons (12,000 lbs); restriction 11:00 PM to 6:00 AM | ASHTb |
| 15 | Time and Date Restrictions | No trucks except B plates (GVW 4 tons/8,000 lbs); restriction 4/15 through 6/13 | ASHThmlb |

