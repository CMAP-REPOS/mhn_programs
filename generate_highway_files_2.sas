/*
    generate_highway_files_2.sas
    Authors: cheither, npeterson, nferguson & tschmidt
    Revised: 1/19/22
    ---------------------------------------------------------------------------
    Program uses base conditions and project data from the MHN to build Emme
    scenario highway networks. Emme batchin files are the output of this
    program. Called by generate_highway_files.py.

*/

options pagesize=50 linesize=125;

%let dir = %scan(&sysparm, 1, $);
%let scen = %scan(&sysparm, 2, $);
%let maxz = %scan(&sysparm, 3, $);
%let baseyr = %scan(&sysparm, 4, $);
%let abm = %scan(&sysparm, 5, $);

/* ------------------------------------------------------------------------------ */
*** INPUT FILES ***;
filename in1 "&dir.\&scen.\network.csv";
filename in2 "&dir.\&scen.\transact.csv";
filename in3 "&dir.\&scen.\year.csv";
filename in4 "&dir.\&scen.\nodes.csv";

*** OUTPUT FILES ***;
*** [output files defined in macro %output] ***;
/* ------------------------------------------------------------------------------ */

%macro main;

    *----------------------------------------------;
    ** READ IN MASTER HIGHWAY NETWORK ARC TABLE **;
    *----------------------------------------------;
    data network; infile in1 dlm=',' dsd firstobs=2;
        length abb $ 13;
        input anode
              bnode
              abb $
              directn
              type1
              type2
              ampm1
              ampm2
              posted1
              posted2
              thruln1
              thruln2
              thruft1
              thruft2
              parkln1
              parkln2
              parkres1 $
              parkres2 $
              sigic
              cltl
              rrcross
              toll
              modes
              blvd
              trkres
              vertclrn
              miles;
        if parkres1 ^= '' then resln1 = thruln1 + 1;  *** -- increased through lanes due to parking restriction (hold for later use) **;
        if parkres2 ^= '' then do;
            if directn = 2 then resln2 = thruln1 + 1;
            if directn = 3 then resln2 = thruln2 + 1;
        end;
        proc sort; by abb;
    data network; set network;
        miles = round(miles, 0.01);
        toll = round(toll, 0.01);

    *-----------------------------;
      ** READ IN SECTION TABLE **;
    *-----------------------------;
    data temp; infile in2 dlm=',' dsd firstobs=2;
        length abb $ 13;
        input tipid
              action
              directn
              type1
              type2
              ampm1
              ampm2
              posted1
              posted2
              thruln1
              thruln2
              thruft1
              thruft2
              aparkln1
              aparkln2
              sigic
              acltl
              arrcross
              toll
              modes
              tod
              abb $
              repanode
              repbnode;


    *-----------------------------------;
      ** FORMAT VARIABLES FOR UPDATE **;
    *-----------------------------------;
     data temp(drop=i); set temp;
         array fixmiss{16} type1 type2 sigic thruft1 thruln1 posted1 repanode
               repbnode thruft2 thruln2 posted2 toll directn ampm1 ampm2 modes;
         do i = 1 to 16;
            if fixmiss{i} = 0 then fixmiss{i} = '.';
         end;
         proc sort; by tipid;


    *---------------------------;
      ** READ IN ROUTE TABLE **;
    *---------------------------;
    data year; infile in3 dlm=',' dsd firstobs=2;
        input tipid compyear;
        proc sort; by tipid;


    *---------------------------------------------;
      ** MERGE SECTION TABLE WITH PROJECT YEAR **;
    *---------------------------------------------;
    data temp; merge temp year; by tipid;
        proc sort; by abb compyear;

    * - - - - - - - - - - - - - - - - - - - - - - - - - - *;
    **VERIFY THAT ALL SCENARIO PROJECTS ARE PRESENT**;
    data check; set temp;
        if compyear = '.' or action = '.';
        proc print noobs; var tipid action compyear;
        title "NETWORK PROJECT YEAR PROBLEM";
    * - - - - - - - - - - - - - - - - - - - - - - - - - - *;


    *-------------------------------------------------;
      ** PROCESS PARKING, CLTL & GRADE SEPARATIONS **;
    *-------------------------------------------------;
    data calc; set network;
        keep abb parkln1 parkln2 cltl rrcross;

    data temp; merge temp (in=hit) calc; by abb;
        if hit;
        **** these values cannot be negative ****;
        parkln1 = max(parkln1 + aparkln1, 0);
        parkln2 = max(parkln2 + aparkln2, 0);
        cltl = max(cltl + acltl, 0);
        rrcross = max(rrcross + arrcross, 0);
        drop aparkln1 aparkln2 acltl arrcross;


    *-------------------------------------------;
      ** SEPARATE SECTION TABLE INTO ACTIONS **;
    *-------------------------------------------;
    **** sep tod here, attach dir to it, process in output macro, CMH 8-04-08;
    data period temp(drop=tod); set temp;
        if tod > 0 then output period; else output temp;

    proc sort data=period; by abb;
    data n(keep=abb anode bnode directn); set network;
    data period; merge period (in=hit) n; by abb; if hit;
        tp = put(tod, 7.0);
        output;
        if directn = 2 then do;
            cn = anode; anode = bnode; bnode = cn;
            output;
        end;
        if directn = 3 then do;
            cn = anode; anode = bnode; bnode = cn;
            type1 = type2;
            ampm1 = ampm2;
            posted1 = posted2;
            thruln1 = thruln2;
            parkln1 = parkln2;
            thruft1 = thruft2;
            output;
        end;
        drop cn ampm2 posted2 thruln2 parkln2 thruft2 type2;
        proc sort; by anode bnode;

    data modify; set temp;
        if action = 1;

    data replace(keep=repanode repbnode abb); set temp;
        if action = 2;
        proc sort; by repanode repbnode;

    * - - - - - - - - - - - - - - - - - - - - - - - - - - - - - *;
      ** VERIFY THAT REPLACE NODES HAVE A CORRESPONDING LINK **;
    data junk1; set network;
        keep anode bnode miles; proc sort; by anode bnode;
    data junk2; set replace;
        anode = repanode; bnode = repbnode;
        proc sort; by anode bnode;
    data check; merge junk1 junk2; by anode bnode;
        if miles = '.';
        proc print noobs; var repanode repbnode;
        title "NETWORK REPLACE NODES WITHOUT A CORRESPONDING LINK";
    * - - - - - - - - - - - - - - - - - - - - - - - - - - - - - *;

    data delete; set temp;
        if action = 3;

    data add; set temp;
        if action = 4;


    *------------------------------------------------------------------;
      ** CREATE A 'CORRUPT' NETWORK WHERE BASE LINK CHARACTERISTICS **;
      ** ARE MODIFIED TO THEIR FINAL CONDITION IN scenario 'X' (1)  **;
    *------------------------------------------------------------------;
    data tempnet; update network modify; by abb;
        repanode = anode; repbnode = bnode;
        drop anode bnode compyear action miles abb;
        proc sort; by repanode repbnode;


    *-------------------------------------------------------------------------------;
      ** SUBSTITUTE VALUES FROM CORRUPT NETWORK INTO REPLACE DATASET (ACTION=2). **;
      ** LINKS NOT IN REPLACE DATASET ARE DROPPED. (2)  STEPS 1 & 2 ENSURE THAT  **;
      ** SKELETON LINKS WHICH OBTAIN THEIR ATTRIBUTES FROM OTHER LINKS RECEIVE   **;
      ** FINAL CHARACTERISTICS APPROPRIATE FOR scenario 'X'                      **;
    *-------------------------------------------------------------------------------;
    data replace; merge replace (in=hit) tempnet; by repanode repbnode;
        if hit;


    *---------------------------------------------;
      ** UPDATE MASTER LINKS WITH TRANSACTIONS **;
    *---------------------------------------------;
    data newdata; set add modify replace;
        proc sort; by abb compyear descending action;

    data network; update network newdata; by abb;

    data network; update network delete; by abb;
        if action = 3 then delete;

    data network; set network;
        if tipid = '.' then tipid = 0;
        proc sort; by anode bnode;

%mend main;
%main


*============================================================================*;
  ** CREATE BATCHIN FILES FOR SCENARIO NETWORK TEMPLATE.  ALL TIME-OF-DAY **;
  ** NETWORKS FOR A SCENARIO WILL BE CONSTRUCTED BY REMOVING LINKS FROM   **;
  ** THIS TEMPLATE.                                                       **;
*============================================================================*;

*---------------------------------------;
  ** FORMAT LINKS FOR EMME LINK FILE **;
*---------------------------------------;
data network; set network;
    output;
    if directn = 3 then do;
        cn = anode; anode = bnode; bnode = cn;
        type1 = type2;
        ampm1 = ampm2;
        posted1 = posted2;
        thruln1 = thruln2;
        parkln1 = parkln2;
        thruft1 = thruft2;
        parkres1 = parkres2;
        resln1 = resln2;
        output;
    end;
    drop cn ampm2 posted2 thruln2 parkln2 thruft2 type2;
    proc sort; by anode bnode;

data emme2; set network;

* - - - - - - - - - - - - - - - - - - - - - - - - - - *;
** VERIFY THAT EACH LINK HAS A MODE **;
data check; set network;
    if modes = 0;
    proc print; var anode bnode modes;
    title "NETWORK LINKS WITHOUT A CODED MODE";

** VERIFY THAT EACH LINK HAS AMPM CODED **;
data check; set network;
    if ampm1 = 0;
    proc print; var anode bnode ampm1;
    title "NETWORK LINKS WITHOUT AMPM CODED";

** VERIFY THAT EACH LINK HAS A TYPE **;
data check; set emme2;
    if type1 = 0;
    proc print; var anode bnode type1;
    title "NETWORK LINKS WITHOUT A CODED TYPE";

** VERIFY THAT EACH LINK HAS LANES **;
data check; set emme2;
    if thruln1 = 0;
    proc print; var anode bnode thruln1;
    title "NETWORK LINKS WITHOUT CODED LANES";

** VERIFY THAT EACH LINK HAS LANE WIDTHS **;
data check; set emme2;
    if thruft1 = 0;
    proc print; var anode bnode thruft1;
    title "NETWORK LINKS WITHOUT CODED LANE WIDTHS";

** VERIFY THAT EACH NON-TOLL LINK HAS A SPEED **;
data check; set emme2;
    if posted1 = 0 and type1 ^= 7;
    proc print; var anode bnode posted1;
    title "NETWORK LINKS WITHOUT CODED SPEEDS";

** VERIFY THAT EACH TOLL LINK HAS A TOLL AMOUNT **;
data check; set emme2;
    if type1 = 7 and toll = 0;
    proc print; var anode bnode type1 toll;
    title "SUSPICIOUS TOLL CHARGES";

** VERIFY THAT EACH LINK HAS A LENGTH **;
data check; set emme2;
    if miles = 0;
    proc print; var anode bnode miles;
    title "NETWORK LINKS WITHOUT A CODED LENGTH";
* - - - - - - - - - - - - - - - - - - - - - - - - - - *;


*--------------------------------------------------;
  ** FORMAT LINKS FOR EMME EXTRA ATTRIBUTE FILE **;
*--------------------------------------------------;
data network2(drop=cn); set network;
    output;
    if directn = 2 then do;
        cn = anode; anode = bnode; bnode = cn;
        parkres1 = parkres2;
        resln1 = resln2;
        output;
    end;
    proc sort; by anode bnode;

data links; set network2;


*-------------------------------------------------;
  ** ATTACH X & Y COORDINATES TO NETWORK NODES **;
*-------------------------------------------------;
data coord; infile in4 dlm=',' dsd firstobs=2;
    length area $20.;
    input node
          x
          y
          zone
          areatype
          imarea;

    ** Zone09 area definitions **;
    if 1 <= zone <= 854 then area = '01. Cook Co.';
    else if 855 <= zone <= 958 then area = '06. McHenry Co.';
    else if 959 <= zone <= 1133 then area = '05. Lake Co.';
    else if 1134 <= zone <= 1278 then area = '03. Kane Co.';
    else if 1279 <= zone <= 1502 then area = '02. DuPage Co.';
    else if 1503 <= zone <= 1690 then area = '07. Will Co.';
    else if 1691 <= zone <= 1711 then area = '04. Kendall Co.';
    else if 1712 <= zone <= 1723 then area = '08. Grundy Co.';
    else if 1724 <= zone <= 1731 then area = '09. Boone Co.';
    else if 1732 <= zone <= 1752 then area = '10. DeKalb Co.';
    else if 1753 <= zone <= 1774 then area = '11. Kankakee Co.';
    else if 1775 <= zone <= 1811 then area = '12. Winnebago Co.';
    else if 1812 <= zone <= 1817 then area = '13. Ogle Co. (part)';
    else if 1818 <= zone <= 1823 then area = '14. Lee Co. (part)';
    else if 1824 <= zone <= 1835 then area = '15. LaSalle Co. (part)';
    else if 1836 <= zone <= 1882 then area = '16. Lake, IN';
    else if 1883 <= zone <= 1897 then area = '17. Porter, IN';
    else if 1898 <= zone <= 1909 then area = '18. LaPorte, IN';
    else if 1910 <= zone <= 1925 then area = '19. Kenosha, WI';
    else if 1926 <= zone <= 1938 then area = '20. Racine, WI';
    else if 1939 <= zone <= 1944 then area = '21. Walworth, WI';
    else area = '22. POEs / Outside';
    proc sort; by node;

    * - - - - - - - - - - - - - - - - - - - - - - - - - - *;
    ** VERIFY THAT EACH NODE HAS A UNIQUE NUMBER **;
    proc summary; by node; output out=check;
    data check; set check;
        if _freq_ > 1;
        proc print noobs; var node _freq_;
        title "NETWORK NODES WITH DUPLICATE NUMBERS";
    * - - - - - - - - - - - - - - - - - - - - - - - - - - *;

*------------------------------------------------------------;
 ** MACRO ATTACHES COORDINATES TO NODES & GENERATES       **;
 ** OUTPUT FILES FOR EMME.                                **;
*------------------------------------------------------------;
%macro output(tod);

    %global tot;
    %let tot = 0;

    *** OUTPUT FILES cont. ***;
    filename out2 "&dir.\&scen.\&scen.0&tod..l1";
    filename out3 "&dir.\&scen.\&scen.0&tod..l2";
    filename out4 "&dir.\&scen.\&scen.0&tod..n1";
    filename out5 "&dir.\&scen.\&scen.0&tod..n2";

    ** IDENTIFY ANY TOD-SPECIFIC ATTRIBUTE CHANGES **;
    data per; set period(where=(tp ? "&tod"));
    data temp; set per nobs=totobs; call symput('tot', left(put(totobs, 8.))); run;
        %if &tot > 0 %then %do;
            data links&tod; update links per; by anode bnode;
        %end;
        %else %do;
            data links&tod; set links;
        %end;

    ** FINAL RESOLUTION OF THROUGH-LANES DUE TO PEAK PERIOD PARKING RESTRICTIONS **;
    data links&tod; set links&tod;
        if count(parkres1, "&tod") > 0 then do;
            thruln1 = max(thruln1, resln1);  **-- max. value of (original lanes+1) or value after project coding processed--**;
            parkln1 = 0;                     **-- obviously no parking is available -**;
        end;

    ** SET EMME MODES (based on modes, trkres, blvd, vertclrn & tod) **;
    data links&tod; set links&tod;
        if modes = 1 then mode = 'ASHThmlb';       ** all modes;
        else if modes = 2 then mode = 'ASHThmlb';  ** all modes (unless modified below by trkres);
        else if modes = 3 then mode = 'AThmlb';    ** truck only;
        else if modes = 4 then delete;             ** transit only;
        else if modes = 5 then mode = 'AH';        ** HOV only;

        ** UPDATE TRUCK RESTRICTIONS **;
        ** Edit by TSchmidt & NPeterson 5/21/14 **;
        if modes = 2 then do;
            if trkres in (1, 18) then mode = 'ASH';  ** No trucks;
            else if trkres in (2:4, 9:11, 13, 25, 35, 37) then mode = 'ASHTb';  ** No trucks except B-plates;
            else if trkres in (7:8, 14, 16:17, 19, 27, 29, 31, 34, 38:44, 46:47, 49) then mode = 'ASHTlb';  ** No medium or heavy trucks;
            else if trkres in (5, 30, 45, 48) then mode = 'ASHTmlb';  ** No heavy trucks;
            /*else if trkres in (6, 15, 20, 22:24, 26, 28, 32:33, 36) then mode = 'ASHThmlb'; */ ** Already set implicitly by modes=2 **;
            if blvd = 1 then mode = 'ASH';  ** No trucks. Trumps trkres codes;
        end;

        ** Vertical clearance restrictions added 9/9/15 by NFerguson **;
        if 0 < vertclrn < 162 then mode = compress(mode, 'h'); ** Minimum 13'6" clearance for heavy trucks;
        if 0 < vertclrn < 150 then mode = compress(mode, 'm'); ** Minimum 12'6" clearance for medium trucks;
        if 0 < vertclrn < 138 then mode = compress(mode, 'l'); ** Minimum 11'6" clearance for light trucks;

        ** Time-of-day truck restrictions added 9/12/14 by TSchmidt **;
        if &tod = 1 then do;    **-- Currently only overnight restrictions --**;
            if trkres in (21) then mode = 'ASH';  ** No trucks;
            else if trkres in (12) then mode = 'ASHTb';  ** No trucks except B-plates;
        end;

    ** UPDATE TOLL COST FOR DISTANCE-BASED TOLL LINKS **;
    ** Edit by NPeterson 5/4/2017 **;
    data links&tod; set links&tod;
        if toll > 0 and type1 ^= 7 then do;
            toll = toll * miles;
            toll = round(toll, 0.01);
        end;

    ** ATTACH COORDINATES TO NETWORK NODES **;
    data nodes1(keep=node); set emme2;
        node = anode; output;
        node = bnode; output;
        proc sort; by node;
    data nodes1; set nodes1; by node;
        if last.node then output;
    data netnodes; merge nodes1 (in=hit) coord; by node; if hit;
        anode = node;
    data links&tod; merge links&tod (in=hit) netnodes; by anode; if hit;

    ** FORMAT ANODES FOR NODE ATTRIBUTE FILE **;
    data anodes(keep=node); set links&tod;
        node = anode;
        proc sort; by node;
    data anodes; set anodes; by node;
        if last.node then output;

    data anodes; merge anodes (in=hit) coord; by node; if hit;

    **WRITE OUT EMME LINK FILE**;
    data out; set links&tod;
        flag = 'a ';
        file out2;
        if _n_ = 1 then do;
            put 'c a,i-node,j-node,length,modes,type,lanes,vdf' /
                't links init';
        end;
        put
        @1 flag $2.
           anode 6.
           bnode 7. +1
           miles
           mode $8. +1
           '1 '
           thruln1 +1
           type1;

    **WRITE OUT EMME EXTRA ATTRIBUTE FILE**;
    data out2; set links&tod;
        file out3;
        if _n_ = 1 then put 'c i-node,j-node,@speed,@width,@parkl,@cltl,@toll,@sigic,@rrx,@tipid';
        put
        @1 anode 6.
           bnode 7. +1
           posted1 +1
           thruft1 +1
           parkln1 +1
           cltl +1
           toll +1
           sigic +1
           rrcross +1
           tipid;

    ** WRITE OUT NODE FILE FOR EMME **;
    data out3; set netnodes;
        if node <= &maxz then flag = 'a*'; else flag = 'a ';
        file out4;
        if _n_ = 1 then do;
            put 'c a,node,x,y' /
                't nodes init';
        end;
        put
        @1 flag $2.
           node 6. +1
           x
           y;

    ** WRITE OUT NODE ATTRIBUTE FILE FOR EMME **;
    data out4; set anodes;
        file out5;
        if _n_= 1 then put 'c i-node,@zone,@atype,@imarea';
        put
        @1 node 6. +1
           zone +1
           areatype +1
           imarea;

%mend output;

*--------------------------------------------;
 ** MACRO CREATES NETWORK SUMMARY REPORT **;
*--------------------------------------------;
%macro report(timeper);

    data report; set links&timeper;
        lanemile = thruln1 * miles;
        cltlmi = cltl * miles;
        sigicmi = sigic * miles;
        parkmi = parkln1 * miles;
        if type1 = 7 then tollmi = miles; else tollmi = 0;
        if modes = 2 then trckmi = miles; else trckmi = 0;
        proc summary nway; var miles lanemile cltlmi sigicmi tollmi parkmi trckmi;
        class area; output out=junk sum=;

    data nodesum; set netnodes;
        proc summary nway; class area; output out=junk2;

    data junk; set junk; drop _type_;
    data junk2; set junk2; node = _freq_; keep area node;

    data last; merge junk junk2; by area;
        label _freq_='Directional Links'
              miles='Link Miles'
              lanemile='Lane Miles'
              node='Network Nodes'
              area='Area'
              cltlmi='CLTL Link Miles'
              sigicmi='Sigic Link Miles'
              tollmi='Toll Link Miles'
              parkmi='Parking Link Miles'
              trckmi='Truck Restrict Link Miles';

        proc print label noobs; var area node _freq_ miles lanemile cltlmi sigicmi tollmi parkmi trckmi;
            sum _freq_ miles lanemile node cltlmi sigicmi tollmi parkmi trckmi;
            format node _freq_ comma6. miles lanemile cltlmi sigicmi tollmi parkmi trckmi comma9.2;
            title "&dir SCENARIO &scen EMME SUMMARY: &scen.0&timeper";
            title2 "(hwy2.sas)";

%mend report;


*-----------------------------------------------------------------;
  ** FOLLOWING LINES WRITE OUT TEMPLATE NETWORK (0) AND CREATE **;
  ** SUMMARY REPORT.                                           **;
*-----------------------------------------------------------------;
%output(0)  ** all **;  run;
%report(0)  ** all **;  run;


*============================================================================*;
 ** CREATE BATCHIN FILES FOR SCENARIO OVERNIGHT. LINKS WITH AMPM1 OF 2 (AM **;
 ** ONLY) ARE DELETED FROM TEMPLATE.                                       **;
*============================================================================*;

*---------------------------------------;
  ** SELECT LINKS FOR EMME LINK FILE **;
*---------------------------------------;
data emme2; set network(where=(ampm1 not in (2)));

*--------------------------------------------------;
  ** FORMAT LINKS FOR EMME EXTRA ATTRIBUTE FILE **;
*--------------------------------------------------;
data links; set network2(where=(ampm1 not in (2)));

*----------------------------------------------------------------;
  ** FOLLOWING LINES WRITE OUT OVERNIGHT (1) FILES AND CREATE **;
  ** SUMMARY REPORT.                                          **;
*----------------------------------------------------------------;
%output(1)  ** overnight **;  run;
%report(1)  ** overnight **;  run;


*============================================================================*;
 ** CREATE BATCHIN FILES FOR SCENARIO AM PEAK (7AM-9AM), AND ITS BEGINNING **;
 ** (6AM-7AM) AND ENDING (9AM-10AM) SHOULDERS. LINKS WITH AMPM1 OF 3 (PM   **;
 ** ONLY) OR 4 (OFF-PEAK ONLY) ARE DELETED FROM TEMPLATE.                  **;
*============================================================================*;

*--------------------------------------;
  ** SELECT LINKS FOR EMME LINK FILE **;
*--------------------------------------;
data emme2; set network(where=(ampm1 not in (3,4)));

*--------------------------------------------------;
  ** FORMAT LINKS FOR EMME EXTRA ATTRIBUTE FILE **;
*--------------------------------------------------;
data links; set network2(where=(ampm1 not in (3,4)));

*----------------------------------------------------------------;
  ** FOLLOWING LINES WRITE OUT AM PEAK (3) AND SHOULDER (2&4) **;
  ** FILES AND CREATE SUMMARY REPORT.                         **;
*----------------------------------------------------------------;
%output(2)  ** pre-shoulder **;   run;
%report(2)  ** pre-shoulder **;   run;
%output(3)  ** am peak **;        run;
%report(3)  ** am peak **;        run;
%output(4)  ** post-shoulder **;  run;
%report(4)  ** post-shoulder **;  run;


*===========================================================================*;
 ** CREATE BATCHIN FILES FOR SCENARIO MIDDAY (10AM-2PM). LINKS WITH AMPM1 **;
 ** OF 3 (PM ONLY) ARE DELETED FROM TEMPLATE.                             **;
*===========================================================================*;

*---------------------------------------;
  ** SELECT LINKS FOR EMME LINK FILE **;
*---------------------------------------;
data emme2; set network(where=(ampm1 not in (3)));

*--------------------------------------------------;
  ** FORMAT LINKS FOR EMME EXTRA ATTRIBUTE FILE **;
*--------------------------------------------------;
data links; set network2(where=(ampm1 not in (3)));

*-------------------------------------------------------------;
  ** FOLLOWING LINES WRITE OUT MIDDAY (5) FILES AND CREATE **;
  ** SUMMARY REPORT.                                       **;
*-------------------------------------------------------------;
%output(5)  ** midday **;  run;
%report(5)  ** midday **;  run;


*============================================================================*;
 ** CREATE BATCHIN FILES FOR SCENARIO PM PEAK (4PM-6PM), AND ITS BEGINNING **;
 ** (2PM-4PM) AND ENDING SHOULDERS (6PM-8PM). LINKS WITH AMPM1 OF 2 (AM    **;
 ** ONLY) OR 4 (OFF-PEAK ONLY) ARE DELETED FROM TEMPLATE.                  **;
*============================================================================*;

*---------------------------------------;
  ** SELECT LINKS FOR EMME LINK FILE **;
*---------------------------------------;
data emme2; set network(where=(ampm1 not in (2,4)));

*--------------------------------------------------;
  ** FORMAT LINKS FOR EMME EXTRA ATTRIBUTE FILE **;
*--------------------------------------------------;
data links; set network2(where=(ampm1 not in (2,4)));

*----------------------------------------------------------------;
  ** FOLLOWING LINES WRITE OUT PM PEAK (7) AND SHOULDER (6&8) **;
  ** FILES AND CREATE SUMMARY REPORT.                         **;
*----------------------------------------------------------------;
%output(6)  ** pre-shoulder **;   run;
%report(6)  ** pre-shoulder **;   run;
%output(7)  ** pm peak **;        run;
%report(7)  ** pm peak **;        run;
%output(8)  ** post-shoulder **;  run;
%report(8)  ** post-shoulder **;  run;

*--------------------------------------------------;
  ** WRITE ANY ABM FILES, IF DESIRED **;
*--------------------------------------------------;
%macro writeabm;
    %if &abm = 1 %then %do;

        * Generate toll file;
        filename out6 "&dir.\&scen.\toll";
        data toll (keep=anode bnode toll); set network;
            label anode='inode'
                  bnode='jnode'
                  toll='@toll';
            proc export outfile=out6 dbms=csv label replace;

        %end;
    %mend writeabm;
%writeabm

run;
