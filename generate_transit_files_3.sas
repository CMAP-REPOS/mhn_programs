/*
   generate_transit_files_3.sas
   authors: cheither & npeterson
   revised: 8/8/14
   ----------------------------------------------------------------------------
   Program reads batchout of rail transit lines (modes c and m) and formats
   file of stops to be used in arc to create bus-rail links. Emme rail batchin
   files must be in final directory.

*/
options pagesize=64 linesize=80;

%let railitin=%scan(&sysparm,1,$);
%let railnet=%scan(&sysparm,2,$);
%let ctapnt=%scan(&sysparm,3,$);
%let metrapnt=%scan(&sysparm,4,$);

/*-------------------------------------------------------------*/
                  *** INPUT FILES ***;
   filename in1 "&railitin";
   filename in2 "&railnet";
                  *** OUTPUT FILES ***;
   filename out1 "&ctapnt";
   filename out2 "&metrapnt";
/*-------------------------------------------------------------*/

          *------------------------------------*;
            ** READ IN & FORMAT ITINERARIES **;
          *------------------------------------*;
data lines itins;
  infile in1 truncover;
  retain count 0; retain type;
  input @1 first $1. @;
  if first in ('c','t') then delete;
  else if first='a' then do;
    count+1;
    input name $ type $;
    name = dequote(name);
    output lines;
  end;
  else do;
    input @1 path= $ @;
    if path='no' then delete;
    else do;
      if find(_infile_, "dwt=") > 0 then do;
        input @1 dwt= $20. ttf= us1= us2= us3= lay=;
        anode=input(scan(dwt,2,' '), best.);
        dwt=scan(dwt,1,' ');
		if substr(dwt,1,1) in ('#','>','<','+','*') then dwflag = substr(dwt,1,1);
        output itins;
      end;
      else do;
        input @1 anode lay=;
        output itins;
      end;
    end;
  end;

 /*GET CODE AND BNODE ON SAME LINE*/
data itins(keep=node code type); set itins;
  node=anode;
  if dwflag='#' then dwcode=1;
  else if dwflag='>' then dwcode=2;
  else if dwflag='<' then dwcode=3;
  else if dwflag='+' then dwcode=4;
  else if dwflag='*' then dwcode=5;
  else dwcode=0;
  code=lag(dwcode);
  counter=lag(count);
  if count ne counter then code=0;
     proc sort; by node code;

 /*SEPARATE INTO CTA AND METRA (STOPS ONLY)*/
data cta; set itins(where=(type='C' & code ne 1));

data cta; set cta; by node code;
  if first.node then output;
    proc sort; by node;

data metra; set itins(where=(type='M' & code ne 1));

data metra; set metra; by node code;
  if first.node then output;
    proc sort; by node;

          *------------------------------------*;
              ** READ IN NODE COORDINATES **;
          *------------------------------------*;
data coord(keep=node x y); infile in2 missover;
 length recid $ 1;
 retain section 0;
 input recid @;
   if recid='c' then delete;
   if recid=' ' then delete;
   if recid='t' then do;
      section+1;
       delete;
   end;
   if recid='a' and section=1 then do;
      input node x y;
      output coord;
   end;

 *----------------------------------------------------*;
    ** ATTACH COORDINATES TO STOPS AND WRITE FILES **;
 *----------------------------------------------------*;
data cta; merge cta (in=hit) coord; by node;
  if hit;

data print1; set cta end=eof;
 file out1 dlm=',';
  put node x y;
 if eof=1 then do;
   put 'END';
 end;

data metra; merge metra (in=hit) coord; by node;
  if hit;

data print2; set metra end=eof;
 file out2 dlm=',';
  put node x y;
 if eof=1 then do;
   put 'END';
 end;

run;
