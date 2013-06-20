/* coding_overlap.sas
   Craig Heither & Noel Peterson, last rev. 4/15/13

-------------                                          -------------
   Program checks for conflicting lanes coding on the same link.
   Called by generate_highway_files.py.
-------------                                          -------------              */
                                                                     
options pagesize=50 linesize=125;

/* ------------------------------------------------------------------------------ */
                              *** INPUT FILES ***;
  %let dir = &sysparm;
  filename in1 "&dir./overlap_network.csv";
  filename in2 "&dir./overlap_transact.csv";
  filename in3 "&dir./overlap_year.csv";
/* ------------------------------------------------------------------------------ */
               *-----------------------------------------------;
                ** READ IN MASTER HIGHWAY NETWORK ARC TABLE **;
               *-----------------------------------------------;
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
          sigic
          cltl
          rrcross
          toll
          modes
          miles;
    proc sort; by abb;

                      *-------------------------------;
                         ** READ IN SECTION TABLE **;
                      *-------------------------------;
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
          asigic
          acltl
          arrcross
          toll
          modes
          abb $
          repanode
          repbnode;

              *---------------------------------;
               ** FORMAT VARIABLES FOR UPDATE **;
              *---------------------------------;
 data temp(drop=i); set temp;
     array fixmiss{15} directn type1 type2 ampm1 ampm2 posted1 posted2 thruln1 thruln2
               thruft1 thruft2 toll modes repanode repbnode;
          do i=1 to 15;
             if fixmiss{i}=0 then fixmiss{i}='.';
          end;
            proc sort; by tipid;


              *-------------------------------;
                ** READ IN ROUTE TABLE **;
              *-------------------------------;
  data year(keep=tipid compyear); infile in3 dlm=',' dsd firstobs=2;
          input tipid
                compyear;
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
        title "NETWORK  PROJECT YEAR PROBLEM";
       * - - - - - - - - - - - - - - - - - - - - - - - - - - *;


      *----------------------------------------------------;
          ** PROCESS PARKING, CLTL & GRADE SEPARATIONS **;
      *----------------------------------------------------;
 data calc; set network;
    keep abb parkln1 parkln2 cltl rrcross sigic;

 data temp; merge temp (in=hit) calc; by abb;
   if hit;
     parkln1=parkln1+aparkln1;
     parkln2=parkln2+aparkln2;
     cltl=cltl+acltl;
     rrcross=rrcross+arrcross;
     sigic=sigic+asigic;
       drop aparkln1 aparkln2 acltl arrcross asigic;


        *--------------------------------------------;
          ** SEPARATE SECTION TABLE INTO ACTIONS **;
        *--------------------------------------------;
 data modify; set temp;
    if action=1;

 data replace(keep=repanode repbnode abb); set temp;
    if action=2;
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
        title "NETWORK  REPLACE NODES WITHOUT A CORRESPONDING LINK";
       * - - - - - - - - - - - - - - - - - - - - - - - - - - *;

 data add; set temp;
    if action=4;


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
  data replace; merge replace (in=hit) tempnet; by repanode repbnode;
    if hit;


       *-----------------------------------------------;
          ** LOOK FOR CONFLICTING CODING **;
       *-----------------------------------------------;
  data newdata; set add modify replace;
      proc sort; by abb descending compyear;
      
data nodes(keep=abb anode bnode lanes1 lanes2 typ1 typ2); set network;
  lanes1=thruln1; lanes2=thruln2;  typ1=type1; typ2=type2;
  
data new2; merge newdata (in=hit) nodes; by abb; if hit;
  **compare to base coding if project coding not changing lanes**;
      if lanes1>0 and thruln1>0 then thruln1=max(thruln1,lanes1);
      if lanes2>0 and thruln2>0 then thruln2=max(thruln2,lanes2);  

data new2; set new2;
  abb2=lag(abb);
  new_yr=lag(compyear);
  new_tip=lag(tipid);
  new_ln1=lag(thruln1);
  new_ln2=lag(thruln2);
 
  if abb=abb2 then do;
    if compyear=new_yr and ((thruln1>0 and new_ln1>0 and thruln1 ne new_ln1) or
       (thruln2>0 and new_ln2>0 and thruln2 ne new_ln2)) then output;
    if compyear<new_yr and ((thruln1>0 and new_ln1>0 and new_ln1<thruln1) or
       (thruln2>0 and new_ln2>0 and new_ln2<thruln2)) then output;
  end;

  proc print;
   var abb anode bnode tipid compyear thruln1 thruln2 new_tip new_yr new_ln1 new_ln2;
  title1 'Possible Conflicting Coding';
  title2 '(coding_overlap.sas)';
