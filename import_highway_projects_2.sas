/*
   import_highway_projects_2.sas
   authors: cheither & npeterson
   revised: 7/18/14
   ----------------------------------------------------------------------------
   This program reads highway project coding and assigns an observation number
   to each line of coding, dependent upon the number of times a link (anode-
   bnode combination) appears in the file.  This is a way to separate the data,
   as a link may be used only once during a run of import_highway_projects.py.
   Program also verifies project coding links have a match in the MHN.

*/
option missing=0;  **this is only a mask: the true value is still .;

%let xls=%scan(&sysparm,1,$);
%let excel=%scan(&xls,-1,.);
%let mhnlinks=%scan(&sysparm,2,$);
%let projcsv=%scan(&sysparm,3,$);
%let lst=%scan(&sysparm,4,$);

******************************;
 filename in0 "&xls";
 filename in1 "&mhnlinks";
 filename out1 "&projcsv";
******************************;

%macro getdata;
  %if %sysfunc(fexist(in0)) %then %do;
        ** READ IN HIGHWAY PROJECT CODING **;
       proc import out=coding datafile="&xls" dbms=&excel replace; sheet="template"; getnames=yes; mixed=yes;
  %end;
  %else %do;
   data null;
    file "&lst";
     put "File not found: &xls";
  %end;
%mend getdata;
%getdata
  /* end macro */


data coding; set coding(where=(tipid>0));
   abnode=anode*100000+bnode;
    proc sort; by abnode tipid;


  ** OUTPUT DATA (COLUMNS WITH NO VALUES WERE READ AS TEXT DURING IMPORT) **;
data out; set coding;
 file out1 dsd;
    put tipid anode bnode action rep_anode rep_bnode type1 type2 feet1 feet2 lanes1 lanes2 speed1 speed2
        ampm1 ampm2 modes tolldollars directions parklanes1 parklanes2 sigic cltl rr_grade_sep tod abnode;

  ** READ DATA BACK IN TO REPLACE BLANKS WITH ZEROES **;
data coding; infile out1 missover dsd;
    input tipid anode bnode action rep_anode rep_bnode type1 type2 feet1 feet2 lanes1 lanes2 speed1 speed2
          ampm1 ampm2 modes tolldollars directions parklanes1 parklanes2 sigic cltl rr_grade_sep tod abnode;


data coding1; set coding;
 check=lag(abnode);

data coding1; set coding1;
 retain observ 1;

 if abnode ne check then observ=1;
  output;
  observ+1;


** Verify Coding **;
data coding2(keep=anode bnode tipid action); set coding;
   proc sort; by anode bnode;

data check; set coding2;
 if tipid>0 and anode>0 and bnode>0 and action>0 then delete;
   proc print; title 'FIX MISSING VALUES ON THESE LINKS';

data mhn; infile in1 missover dlm=',' firstobs=2;
  input anode bnode baselink;
    match=1;
   proc sort; by anode bnode;

data coding2; merge coding2 (in=hit) mhn; by anode bnode;
  if hit;

data check; set coding2;
   if match=1 then delete;
     proc print; title 'FIX ANODE-BNODE CODING ON THESE LINKS';

data check2; set coding2;
   if baselink=1 then delete;
   if action=2 or action=4 then delete;
   *if tipid=1020020 then delete;
     proc print; title 'BAD SKELETON LINK CODING ON THESE LINKS';

** Check for Duplicates within Project **;
data junk; set coding;
  ab2=lag(abnode);
   tip2=lag(tipid);
   if tod>0 then delete;
   if abnode=ab2 and tipid=tip2 then output;
     proc print; title 'DUPLICATE ANODE-BNODE CODING WITHIN A PROJECT';

** Verify Coding for Action=4 Links **;
data check; set coding(where=(action=4));
  if type1>0 and lanes1>0 and feet1>0 and speed1>0 and ampm1>0 and modes>0 then delete;
  if type1=7 and (speed1=0 or speed1='.') then delete;
     proc print; var tipid anode bnode action type1 lanes1 feet1 speed1 ampm1 modes;
      title 'FIX MISSING VALUES ON THESE LINKS';

** Verify Coding for Action=2 Links **;
data check; set coding(where=(action=2));
  if rep_anode>0 and rep_bnode>0 then delete;
     proc print; var tipid anode bnode action rep_anode rep_bnode;
      title 'REPLACE NODE VALUES ARE REQUIRED ON THESE LINKS';

data replaced; set coding(where=(action=2));
  proc sort; by rep_anode rep_bnode;
data baselinks; set mhn(where=(baselink=1));
  rep_anode=anode; rep_bnode=bnode;
  keep rep_anode rep_bnode match;
  proc sort; by rep_anode rep_bnode;
data check; merge replaced baselinks; by rep_anode rep_bnode;
  if match=1 then delete;
     proc print; var tipid anode bnode action rep_anode rep_bnode;
      title 'REPLACED BASELINKS DO NOT EXIST FOR THESE LINKS';

data check; set coding(where=(action=2));
  if max(type1,type2,sigic,feet1,lanes1,speed1,feet2,lanes2,speed2,tolldollars,directions,parklanes1,parklanes2,cltl,ampm1,ampm2,modes,tod)>0;
   proc print;
     var tipid anode bnode action type1 type2 feet1 feet2 lanes1 lanes2 speed1 speed2
         ampm1 ampm2 modes tolldollars directions parklanes1 parklanes2 sigic cltl tod;
     title 'NON-USABLE VALUES CODED ON THESE LINKS';

proc sort data=coding1; by anode bnode;
data coding1; merge coding1(in=hit) mhn; by anode bnode; if hit;
  abb=catx('-', anode, bnode, baselink);

data out;
  set coding1 (keep=tipid abb action rep_anode rep_bnode type1 type2 feet1 feet2 lanes1 lanes2 speed1 speed2
                    ampm1 ampm2 modes tolldollars directions parklanes1 parklanes2 sigic cltl rr_grade_sep tod);
  label tipid='TIPID'
        abb='ABB'
        action='ACTION_CODE'
        rep_anode='REP_ANODE'
        rep_bnode='REP_BNODE'
        type1='NEW_TYPE1'
        type2='NEW_TYPE2'
        feet1='NEW_THRULANEWIDTH1'
        feet2='NEW_THRULANEWIDTH2'
        lanes1='NEW_THRULANES1'
        lanes2='NEW_THRULANES2'
        speed1='NEW_POSTEDSPEED1'
        speed2='NEW_POSTEDSPEED2'
        ampm1='NEW_AMPM1'
        ampm2='NEW_AMPM2'
        modes='NEW_MODES'
        tolldollars='NEW_TOLLDOLLARS'
        directions='NEW_DIRECTIONS'
        parklanes1='ADD_PARKLANES1'
        parklanes2='ADD_PARKLANES2'
        sigic='ADD_SIGIC'
        cltl='ADD_CLTL'
        rr_grade_sep='ADD_RRGRADECROSS'
        tod='TOD';
   proc sort; by tipid action;
   proc export outfile=out1 dbms=csv label replace;

run;
