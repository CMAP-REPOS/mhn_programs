/* read_path_output.sas
   Craig Heither, 09/30/2011

-------------                                                             -------------
   This SAS program reads the shortest path data written by find_shortest_path.py
   and inserts it into the transit itineraries.  
-------------                                                             -------------    */
options linesize=120;

 *** RE-FORMAT PATH DATA AS ITINERARY SEGMENTS ***;
data read(keep=newb set i); infile in4 length=reclen lrecl=1000;
  input alldata $varying1000. reclen;
   set=_n_; 
   alldata=compress(alldata,"[] ()");
   c=count(alldata,",");
      *** format itinerary segments ***;
   do i=1 to c;
      newb=input(scan(alldata,i+1,","),best5.); output;
   end;
  proc sort; by set i;

data first; set read; by set i;
 if first.set then itinerary_a=newb;
 if last.set then itinerary_b=newb;
   proc summary nway; class set; var itinerary_a itinerary_b; output out=ends max=;

data read(drop=_type_ _freq_ grp); merge read ends; by set;
  newa=lag(newb); grp=lag(set); impute=1;
  if set=grp;
   proc sort; by newa newb;


 *** DETERMINE SEGMENT LENGTH AND TOTAL DISTANCE FOR EACH SET ***;
data len(keep=newa newb linkmi); set mhn; rename itinerary_a=newa itinerary_b=newb mhnmi=linkmi;
data read; merge read (in=hit) len; by newa newb; if hit;
  proc summary nway; class set; var linkmi; output out=totlen sum=totmi;
proc sort data=read; by set;
data read(drop=_type_ _freq_); merge read totlen; by set;



 *** MERGE NEW SEGMENTS INTO TRANSIT RUN ITINERARIES ***;
proc sql noprint;
  create table newitin as
      select verify.*,
             read.newa,newb,set,i,impute,linkmi,totmi
      from verify left join read
      on verify.itinerary_a=read.itinerary_a & verify.itinerary_b=read.itinerary_b
      order by newline,order,i;


%macro checkds(dsn);
  %if %sysfunc(exist(&dsn)) %then %do;
      *** -- if dwadj exists: process to Attach Pnode1 to Links so the Correct Dwell Code can be Assigned (highway links only) -- ***;
        proc sql noprint;
          create table newitin2 as
              select newitin.*,
                     dwadj.pnode1
              from newitin left join dwadj
              on newitin.newline=dwadj.newline & newitin.newb=dwadj.newb      
              order by newline,order,i;
        data newitin2(drop=pnode1); set newitin2;
        run;
  %end;
  %else %do;
      *** -- otherwise: set up newitin2 for next step (rail links only) -- ***;
    data newitin2; set newitin;
    run;
  %end;
%mend checkds;

%checkds(work.dwadj)
 /* end macro */


data newitin(drop=newa newb set impute totmi i linkmi); set newitin2; by newline order i;
  if first.newline & i>1 then group=group;         ** ensures order is correct when recalculated **;
  else if i>1 then group=line;
   *** Update Attributes for New Segments ***;
  if impute=1 then do;
     itinerary_a=newa; itinerary_b=newb;   
     ltime=round((arr_time-dep_time)/60*linkmi/totmi,0.1);
     imputed=impute;
     if i>2 then do;
        zfare=0;              ** if there is a zone fare - only apply it to the first segment in the set **;
     end;
     if substr(newline,1,1) in ('e','q','c','m') then dwcode=1;                    ** flag imputed nodes as non-stops on rail or express bus runs **;
  end;
  if last.order & impute=1 then dwcode=0;


 *** RECALCULATE DEPARTURE AND ARRIVAL TIMES ON IMPUTED SEGMENTS ***;
data newitin; set newitin;
  rank=_n_; i=lag(imputed); group=lag(line); dt=lag(dep_time);
  proc sort; by rank;
data newitin; set newitin;
  retain d 0; 
   if imputed ne i or line ne group or dep_time ne dt then d+1;
   output;
  proc sort; by d rank;
data newitin; set newitin; by d rank;
  retain ar 0; 
   ar=ar+(ltime*60);
   if first.d then ar=ltime*60;
   output;
data value(keep=d origd); set newitin(where=(imputed=1)); by d rank;
  if first.d; rename dep_time=origd;
data newitin; merge newitin value; by d;
  if imputed=1 then arr_time=dep_time+ar-(dep_time-origd);              ** adjustment for fixed times on imputed links split by shortest path **;
  dp=lag(arr_time);
  if imputed=1 & not first.d then dep_time=dp;
  if first.d & i>imputed & dp & order>1 then dep_time=dp;               ** adjustment for link following imputed one in itinerary to update departure time **;
  proc sort; by rank;

data newitin(drop=rank i d ar origd dp); set newitin;

run;