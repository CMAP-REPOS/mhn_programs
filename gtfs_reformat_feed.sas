/*
   gtfs_reformat_feed.sas
   authors: cheither & npeterson
   revised: 4/29/13
   ----------------------------------------------------------------------------
   Program reformats unloaded itinerary data for python.

*/
options noxwait;

%let progdir=%scan(&sysparm,1,$);
%let busrte=%scan(&sysparm,2,$);   *** bus route header CSV;
%let busitin=%scan(&sysparm,3,$);  *** bus itinerary CSV;
%let oneline=%scan(&sysparm,4,$);  *** one-line itineraries, passed to gtfs_collapse_routes.py;
%let feedgrp=%scan(&sysparm,5,$);  *** grouped bus routes, passed back from gtfs_collapse_routes.py;
%let runs=%scan(&sysparm,6,$);     *** final output CSV of this program;
%let tod=%scan(&sysparm,7,$);      *** TOD period;

*~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~*;
filename in1 "&busitin";
filename in2 "&busrte";
filename in3 "&feedgrp";
filename out1 "&oneline";
filename out2 "&runs";
*~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~*;

data sec; infile in1 dsd missover firstobs=2;
 length id $13.;
  input line $ itina itinb order layover dwcode zfare ltime ttf;
   id=compress(itina||"-"||itinb||"-"||dwcode);
  proc sort; by line order;

data rat; infile in2 dsd missover firstobs=2;
 length desc $20.; format start timeampm.;
  input line $ desc $ mode $ vtype headway speed rteid $ start;
   moderte=compress(substr(line,1,1)||rteid);
    proc sort; by line;


 *-------------------------------------------------------------------------------;
       **** Format data to analyze runs ***;
 *-------------------------------------------------------------------------------;
data s; merge sec rat; by line;

 *** -- Remove Pace Special Event Service -- ***;
data s; set s;
  if mode='Q' & rteid in ('222','237','282','284','387','475','476','768','769','773','774','775','776','779') then delete;

 *** Write out 1 line for each Route ***;
data s; set s; by line order;
 file out1 dsd lrecl=32767;
  if first.line then do;
    if last.line then put moderte line id;               ** needed to correctly handle routes with only 1 segment **;
    else put moderte line id @;
  end;
  else if last.line then put id;
  else put id @;


 *-------------------------------------------------------------------------------;
       **** Run python script to collapse runs into TOD routes ***;
 *-------------------------------------------------------------------------------;
data _null_;
  command="if exist pypath.txt (del pypath.txt /Q)"; call system(command);
  command="ftype Python.File >> pypath.txt"; call system(command); run;

data null; infile "pypath.txt" length=reclen;
  input location $varying254. reclen;
  loc=scan(location,2,'='); goodloc=substr(loc,1,index(loc,'.exe"')+4);
  call symput('runpython',trim(goodloc));
  run;

%macro runpy;
  data _null_;
    command="%bquote(&runpython) &progdir.\gtfs_collapse_routes.py &oneline &feedgrp"; call system(command);
    command="if exist pypath.txt (del pypath.txt /Q)"; call system(command); run;
%mend runpy;
%runpy
/* end of macro */


 *-------------------------------------------------------------------------------;
       **** Create TOD routes ***;
 *-------------------------------------------------------------------------------;
data groups; infile in3 dsd missover;
  input line $ group;
   proc sort; by line;

 *** - IDENTIFY REPRESENTATIVE RUN: Longest (most segments), then starts earliest - ***;
data sec1; merge sec groups(in=hit); by line; if hit;
proc summary nway; class line; id group; var order; output out=segcount max=segs;

data segcount(keep=line group segs start); merge segcount(in=hit) rat; by line; if hit;
 proc sort; by group descending segs start;

data rep(keep=line group); set segcount; by group descending segs start;
  if first.group;    *** group representative for AM Peak network ***;

 *** - CALCULATE AVERAGE HEADWAY & NUMBER OF RUNS REPRESENTED - ***;
proc summary nway data=segcount; class group; output out=cnt;
data hdwy(rename=(_freq_=runs)); merge segcount cnt; by group;

%macro headway;
  %if &tod=1 %then %do;
     data hdwy; set hdwy;
       ap=put(start,timeampm2.);
       if ap='PM' then priority=1; else priority=2;
       shr=hour(start);
         proc sort; by group priority shr start;
  %end;
  %else %do;
     proc sort data=hdwy; by group start;
  %end;
%mend headway;
%headway
run;

*****proc print data=hdwy;

data hdwy; set hdwy;
  format st timeampm.;
  st=lag(start); gp=lag(group);
  if runs>1 then do; if group ne gp then delete; end;

  if &tod=1 then maxtime=600;
  else if &tod=2 or &tod=4 then maxtime=60;
  else if &tod=5 then maxtime=240;
  else maxtime=120;

  if runs=1 then hdwy=maxtime;
  else hdwy=abs(start-st)/60;
  if hdwy>maxtime then hdwy=1440-hdwy;       ***adjust to calculate overnight times correctly if SAS assumes times cross days ***;
  if hdwy=0 then hdwy=maxtime;

  drop _type_;
***proc print;
proc summary nway; class group; var hdwy runs; output out=hdcnt mean=;

data final(drop=_type_ _freq_); merge rep hdcnt; by group;
 hdwy=round(hdwy,0.1);
 format hdwy d5.1;
 file out2 dsd;
  if _n_ = 1 then
    put 'TRANSIT_LINE,FEED_GROUP,GROUP_HEADWAY,GROUP_RUNS';
  put line group hdwy runs;

run;
