/*
   export_future_network_2.sas
   Authors: cheither & npeterson
   Revised: 7/25/13
   ----------------------------------------------------------------------------
   Program updates network to specified year environment for GTFS processing.
   Also, identifies intersections where a freeway ramp intersects one arterial.
   These will be removed from the ARTERIAL=1 category in the MHN and flagged as
   RAMP=1. Ghost intersections are also identified: an intersection comprised
   of two segments of the same road and (either no cross-streets or a centroid
   connector). These will be removed from the ARTERIAL=1 category and flagged
   as GHOST=1.

*/

options pagesize=50 linesize=125;

%let netwkcsv=%scan(&sysparm,1,$);
%let transcsv=%scan(&sysparm,2,$);
%let yearcsv=%scan(&sysparm,3,$);
%let updatelk=%scan(&sysparm,4,$);
%let flagnode=%scan(&sysparm,5,$);
%let buildyr=%scan(&sysparm,6,$);
%let maxz=%scan(&sysparm,7,$);
%let baseyr=%scan(&sysparm,8,$);

/* ------------------------------------------------------------------------------ */
                              *** INPUT FILES ***;
  filename in1 "&netwkcsv";
  filename in2 "&transcsv";
  filename in3 "&yearcsv";
                              *** OUTPUT FILES ***;
  filename out1 "&updatelk";
  filename out2 "&flagnode";
 /* ------------------------------------------------------------------------------ */
%macro main;

               *-----------------------------------------------;
                ** READ IN MASTER HIGHWAY NETWORK ARC TABLE **;
               *-----------------------------------------------;
  data network; infile in1 dlm=',' firstobs=2;
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
         baselink
         sigic
         cltl
         rrcross
         toll
         modes
         miles;
    proc sort; by abb;

*- - - - - - - - - - - - - - - - - -*;
   %if &buildyr=&baseyr %then %goto skip;
*- - - - - - - - - - - - - - - - - -*;

                      *-------------------------------;
                         ** READ IN SECTION TABLE **;
                      *-------------------------------;
  data temp; infile in2 dlm=','firstobs=2;
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

              *---------------------------------;
               ** FORMAT VARIABLES FOR UPDATE **;
              *---------------------------------;
 data temp(drop=i); set temp;
     array fixmiss{16} type1 type2 sigic thruft1 thruln1 posted1 repanode
               repbnode thruft2 thruln2 posted2 toll directn ampm1 ampm2 modes;
          do i=1 to 16;
             if fixmiss{i}=0 then fixmiss{i}='.';
          end;
            proc sort; by tipid;


              *-------------------------------;
                ** READ IN ROUTE TABLE **;
              *-------------------------------;
  data year; infile in3 dlm=',' firstobs=2;
    input tipid compyear;
    proc sort; by tipid;

           *----------------------------------------------;
             ** MERGE SECTION TABLE WITH PROJECT YEAR **;
           *----------------------------------------------;
  data temp; merge temp year; by tipid;
            proc sort; by abb compyear;

       * - - - - - - - - - - - - - - - - - - - - - - - - - - *;
       **VERIFY THAT ALL SCENARIO PROJECTS ARE PRESENT**;
       data check; set temp;
          if compyear='.' or action='.';
        proc print noobs; var tipid action compyear;
        title "NETWORK PROJECT YEAR PROBLEM";
       * - - - - - - - - - - - - - - - - - - - - - - - - - - *;


      *----------------------------------------------------;
          ** PROCESS PARKING, CLTL & GRADE SEPARATIONS **;
      *----------------------------------------------------;
 data calc; set network;
    keep abb parkln1 parkln2 cltl rrcross;

 data temp; merge temp (in=hit) calc; by abb;
   if hit;
    **** these values cannot be negative ****;
     parkln1=max(parkln1+aparkln1,0);
     parkln2=max(parkln2+aparkln2,0);
     cltl=max(cltl+acltl,0);
     rrcross=max(rrcross+arrcross,0);
       drop aparkln1 aparkln2 acltl arrcross;


        *--------------------------------------------;
          ** SEPARATE SECTION TABLE INTO ACTIONS **;
        *--------------------------------------------;

 **** sep tod here, attach dir to it, process in output macro, CMH 8-04-08;
 data period temp(drop=tod); set temp;
   if tod>0 then output period; else output temp;

   proc sort data=period; by abb;
   data n(keep=abb anode bnode directn); set network;
   data period; merge period (in=hit) n; by abb; if hit;
     tp=put(tod,7.0);
     output;
      if directn=2 then do;
         cn=anode; anode=bnode; bnode=cn;
        output;
      end;
      if directn=3 then do;
         cn=anode;  anode=bnode;  bnode=cn;
         type1=type2;
         ampm1=ampm2;
         posted1=posted2;
         thruln1=thruln2;
         parkln1=parkln2;
         thruft1=thruft2;
       output;
      end;
       drop cn ampm2 posted2 thruln2 parkln2 thruft2 type2;
       proc sort; by anode bnode;


 data modify; set temp(where=(action=1));

 data replace(keep=repanode repbnode abb action); set temp(where=(action=2));
        proc sort; by repanode repbnode;

       * - - - - - - - - - - - - - - - - - - - - - - - - - - *;
       **VERIFY THAT REPLACE NODES HAVE A CORRESPONDING LINK**;
       data junk1; set network;
           keep anode bnode miles; proc sort; by anode bnode;
       data junk2; set replace;
           anode=repanode; bnode=repbnode;
            proc sort; by anode bnode;
       data check; merge junk1 junk2; by anode bnode;
          if miles='.';
        proc print noobs; var repanode repbnode;
        title "NETWORK REPLACE NODES WITHOUT A CORRESPONDING LINK";
       * - - - - - - - - - - - - - - - - - - - - - - - - - - *;

 data delete; set temp(where=(action=3));

 data add; set temp(where=(action=4));


      *------------------------------------------------------------------;
        ** CREATE A 'CORRUPT' NETWORK WHERE BASE LINK CHARACTERISTICS **;
        ** ARE MODIFIED TO THEIR FINAL CONDITION IN scenario 'X' (1)   **;
      *------------------------------------------------------------------;
  data tempnet; update network modify; by abb;
      repanode=anode; repbnode=bnode;
        drop anode bnode compyear action miles abb;
         proc sort; by repanode repbnode;


 *-------------------------------------------------------------------------------;
   ** SUBSTITUTE VALUES FROM CORRUPT NETWORK INTO REPLACE DATASET (ACTION=2). **;
   ** LINKS NOT IN REPLACE DATASET ARE DROPPED. (2)  STEPS 1 & 2 ENSURE THAT  **;
   ** SKELETON LINKS WHICH OBTAIN THEIR ATTRIBUTES FROM OTHER LINKS RECEIVE   **;
   ** FINAL CHARACTERISTICS APPROPRIATE FOR scenario 'X'                      **;
 *-------------------------------------------------------------------------------;
  data replace; merge replace (in=hit) tempnet; by repanode repbnode; if hit;


       *-----------------------------------------------;
          ** UPDATE MASTER LINKS WITH TRANSACTIONS **;
       *-----------------------------------------------;
  data newdata; set add modify replace;
      proc sort; by abb compyear descending action;

  data network; update network newdata; by abb;

  data network; update network delete; by abb;


*- - - - - - - - - - -*;
 %skip: ;
*- - - - - - - - - - -*;

%mend main;
%main
/* end of macro */


data attr;
 set network (keep=abb type1 type2 toll ampm1 ampm2 sigic posted1 posted2 thruln1 thruln2
                   parkln1 parkln2 cltl thruft1 thruft2 directn modes action);
 action=max(action,0);
 label abb='ABB'
       type1='TYPE1'
       type2='TYPE2'
       toll='TOLLDOLLARS'
       ampm1='AMPM1'
       ampm2='AMPM2'
       sigic='SIGIC'
       posted1='POSTEDSPEED1'
       posted2='POSTEDSPEED2'
       thruln1='THRULANES1'
       thruln2='THRULANES2'
       parkln1='PARKLANES1'
       parkln2='PARKLANES2'
       cltl='CLTL'
       thruft1='THRULANEWIDTH1'
       thruft2='THRULANEWIDTH2'
       directn='DIRECTIONS'
       modes='MODES'
       action='ACTION_CODE';
   proc sort; by abb;
   proc export outfile=out1 dbms=csv label replace;


      *------------------------------------------------------------------;
        ** CATEGORIZE ARTERIAL INTERSECTIONS: ARTERIAL, RAMP, GHOST **;
      *------------------------------------------------------------------;

*** CREATE SET OF AVAILABLE LINKS ***;
data ntwk; set network;
  if action in (1,2,4) then baselink=1;
  if baselink=0 or action=3 then delete;

data nd; set ntwk;
  node=anode; output;
  node=bnode; output;
   proc sort nodupkey; by node;
data nd; set nd(where=(node>&maxz));

*** SUMMARIZE NUMBER OF LINKS (BY TYPE) USING INTERSECTION ***;
data arterial; set ntwk(where=(type1=1));
  node=anode; output;
  node=bnode; output;
    proc summary nway; class node; output out=artsum;
data artsum(drop=_type_); set artsum; arterial=1; rename _freq_=arterials;

data ramp; set ntwk(where=(type1 in (3,8)));   *** remember, these flags are for arterial intersections ***;
  node=anode; output;
  node=bnode; output;
    proc summary nway; class node; output out=rampsum;
data rampsum(drop=_type_); set rampsum; rename _freq_=ramps;

data cent; set ntwk(where=(type1=6));
  node=anode; output;
  node=bnode; output;
    proc summary nway; class node; output out=centsum;
data centsum(drop=_type_); set centsum; rename _freq_=cntrd;

data other; set ntwk(where=(type1 in (2,4,5,7)));
  node=anode; output;
  node=bnode; output;
    proc summary nway; class node; output out=othrsum;
data othrsum(drop=_type_); set othrsum; rename _freq_=other;


*** --- Identify Ramp Intersections --- ***;
data nd(keep=node arterials arterial ramps); merge nd(in=hit) artsum rampsum; by node; if hit;
    array zero(*) _numeric_;
      do i=1 to dim(zero);
       if zero(i)=. then zero(i)=0;
      end;

data nd; set nd;
  if ramps>0 & arterials<3 then do;       ** exclude ramps attached directly to intersections (old coding short-cut);
    ramp=1; arterial=0;                   ** ensure mutually exclusive;
  end;
  else ramp=0;

*** --- Identify Ghost Intersections --- ***;
**(remove ramp intersections because categories are mutually exclusive)**;
data nd; merge nd(in=hit) centsum othrsum; by node; if hit;
  if cntrd=. then cntrd=0; if other=. then other=0;

data nd; set nd;
  if ramp=0 & arterials<3 & other=0 then do;      ** ensure mutually exclusive;
     ghost=1; arterial=0;
  end;
  else ghost=0;
data nd; set nd(where=(arterial>0 or ramp>0 or ghost>0));

 ** Write File of Updated Attributes **;
data nd; set nd (keep=node arterial ramp ghost);
  label node='NODE'
        arterial='ARTERIAL'
        ramp='RAMP'
        ghost='GHOST';
   proc sort; by node;
   proc export outfile=out2 dbms=csv label replace;

run;
