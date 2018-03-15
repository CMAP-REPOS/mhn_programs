/*
   import_future_bus_routes_2.sas
   authors: cheither & npeterson
   revised: 3/15/18
   ----------------------------------------------------------------------------
   Program is called by import_future_bus_routes.py and formats bus itineraries
   to build with arcpy.

*/

%let codexls=%scan(&sysparm,1,$);
*%let excel=%scan(&codexls,-1,.);  *gets coding spreadsheet extension: XLS or XLSX;
%let dir=%scan(&sysparm,2,$);
%let itincsv=%scan(&sysparm,3,$);
%let routecsv=%scan(&sysparm,4,$);
%let maxzn=%scan(&sysparm,5,$);
%let lst=%scan(&sysparm,6,$);


/*-------------------------------------------------------------*/
* INPUT FILES *;
filename inbus "&codexls";
filename in1 "&dir./network.csv";
filename in2 "&dir./transact.csv";
filename in3 "&dir./year.csv";
* OUTPUT FILES *;
filename out1 "&routecsv";
filename out2 "&itincsv";
/*-------------------------------------------------------------*/

%macro getdata;
  %if %sysfunc(fexist(inbus)) %then %do;
    ** READ IN CODING FOR BUS ITINERARIES **;
    *proc import out=section datafile="&codexls" dbms=&excel replace;
    proc import out=section datafile="&codexls" dbms=excel replace;
    sheet="itinerary"; getnames=yes; mixed=yes; guessingrows=1000;
    proc sort data=section; by tr_line order;
    %end;
  %else %do;
    data null; file "&lst";
    put "File not found: &codexls";
    %end;
  %mend getdata;
%getdata
/* end macro */


data section; set section(where=(tr_line is not null));
  tr_line=lowcase(tr_line);
  if layover='.' or layover='' then layover=0;
  if dw_code='.' or dw_code='' then dw_code=0;
  if zn_fare='.' or zn_fare='' then zn_fare=0;
  if ttf='.' or ttf='' then ttf=0;
  trv_time=round(trv_time,.1);
  group=lag(tr_line);

data chk; set section(where=(trv_time in (.,0))); proc print; title "Link Travel Time Must be Coded";
data verify; set section; proc sort; by itin_a itin_b;


             ** READ IN ROUTE TABLE CODING **;
proc import out=rte datafile="&codexls" dbms=&excel replace; sheet="header"; getnames=yes; mixed=yes; guessingrows=1000;
data rte; set rte(where=(tr_line is not null));
 length des $22. nt $32.;
  tr_line=lowcase(tr_line);
  if replace='' then replace='X';
  if notes='' then notes='X';
  description=upcase(description);
  d=compress(description,"'");
  d=substr(d,1,20);
  des=trim(d);
  nt=trim(notes);

      proc sort nodupkey; by tr_line;

data chk; set rte(where=(scenario in (.,0))); proc print; title "Scenario Values Must be Coded";


    ** Replace File for ARC **;
data rte; set rte (keep=tr_line des mode veh_type headway speed scenario replace tod nt ct_veh);
  label tr_line='TRANSIT_LINE'
        des='DESCRIPTION'
        mode='MODE'
        veh_type='VEHICLE_TYPE'
        headway='HEADWAY'
        speed='SPEED'
        scenario='SCENARIO'
        replace='REPLACE'
        tod='TOD'
        nt='NOTES'
        ct_veh='CT_VEH';
   proc sort; by tr_line;
   proc export outfile=out1 dbms=csv label replace;

 *** VERIFY ITINERARIES HAVE HEADERS AND VICE-VERSA ***;
data r(drop=tr_line); set rte; length trln $6.; trln=tr_line; rte=1; proc sort nodupkey; by trln;
data s; set section; length trln $6.; trln=tr_line; itn=1; proc sort nodupkey; by trln;
data s; merge s r; by trln;
data check; set s; if rte=1 & itn=.; proc print; title "Route with no Itinerary";
data check; set s; if itn=1 & rte=.; proc print; title "Itinerary with no Header";


******************************;
          *-----------------------------------*;
                   ** VERIFY CODING **;
          *-----------------------------------*;
  ** Update MHN links - Just Need to Know if it will be in network in future **;
data network; infile in1 dlm=',' firstobs=2;
   length abb $ 13;
   input anode bnode baselink abb directn type1 type2 ampm1 ampm2 posted1 posted2 thruln1 thruln2
       thruft1 thruft2 parkln1 parkln2 sigic cltl rrcross toll modes miles;
    proc sort; by abb;

data temp; infile in2 dlm=',' firstobs=2;
   length abb $ 13;
   input tipid abb action directn;
    if directn=0 then directn=.;
     proc sort; by tipid;

data year; infile in3 dlm=',' firstobs=2;
   input tipid compyear; proc sort; by tipid;

data temp; merge temp year; by tipid; proc sort; by abb compyear;

data delete; set temp(where=(action=3));
data other; set temp(where=(action in (1,2,4)));
data network; update network other; by abb;
data network; update network delete; by abb;
  if action=3 then delete;

data mhn(rename=(anode=itin_a bnode=itin_b));
  set network;
  match=1;
  output;
  if directn>1 then do;
    c=anode;
    anode=bnode;
    bnode=c;
    output;
  end;
  drop c;
  proc sort; by itin_a itin_b;

data check; merge verify (in=hit) mhn; by itin_a itin_b; if hit;
  if match=1 then delete;
   proc print; var abb itin_a itin_b directn tr_line order;
    title "MIS-CODED ANODE-BNODE OR DIRECTIONAL PROBLEM ON THESE LINKS";

** Ensure Transit Not Coded on Centroid Links **;
data bad; set verify;
  if itin_a le &maxzn or itin_b le &maxzn;
     proc print; var itin_a itin_b tr_line order;
     title "TRANSIT CODING ON CENTROID CONNECTORS";
******************************;

          *-----------------------------------*;
              ** FORMAT ITINERARY DATASET **;
          *-----------------------------------*;
data section(drop=order); set section;
   retain ordnew 1;
      ordnew+1;
      if tr_line ne group then ordnew=1;
     output;
  proc sort; by itin_a itin_b;

  ** Find True Arc Direction in MHN **;
data section; merge section (in=hit) mhn; by itin_a itin_b;
   if hit;
      proc sort; by tr_line ordnew;

     *---------------------------------*;
        ** WRITE ITINERARY FILE **
     *---------------------------------*;
data writeout; set section (keep=tr_line itin_a itin_b abb ordnew layover dw_code zn_fare trv_time ttf);
  label tr_line='TRANSIT_LINE'
        itin_a='ITIN_A'
        itin_b='ITIN_B'
        abb='ABB'
        ordnew='ITIN_ORDER'
        layover='LAYOVER'
        dw_code='DWELL_CODE'
        zn_fare='ZONE_FARE'
        trv_time='LINE_SERV_TIME'
        ttf='TTF';
   proc sort; by tr_line ordnew;
   proc export outfile=out2 dbms=csv label replace;

       * - - - - - - - - - - - - - - - - - *;
            **REPORT ITINERARY GAPS**;
   **THESE ARE MIS-CODED LINKS OR SKELETONS THAT NEED CODING**;
         data check; set section;
           z=lag(itin_b);
            if itin_a ne z and ordnew>1 then output;
            proc print; var tr_line ordnew itin_a itin_b z;
            title 'Itinerary Gaps';
       * - - - - - - - - - - - - - - - - - *;

       * - - - - - - - - - - - - - - - - - *;
            **REPORT LAYOVER PROBLEMS**;
   **A MAXIMUM OF TWO LAYOVERS ARE ALLOWED PER TRANSIT LINE **;
         data check; set section; if layover>0;
            proc freq; tables tr_line / noprint out=check;
         data check; set check;
            if count>2;
            proc print; var tr_line count;
            title 'Too Many Layovers Coded';
       * - - - - - - - - - - - - - - - - - *;


run;
