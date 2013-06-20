/*
   generate_transit_files_3.sas
   authors: cheither & npeterson
   revised: 5/6/13
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
 infile in1 missover dlm="= ' # + < > *";
  retain count 0; retain type;
  input @1 check $1. @3 check2 $4. @13 check3 $1. @22 check4 $1. @;
    select;
       when (check in ('c','t')) delete;
       when (check='a') do; count+1;
              input @1 check $ name $6. type $;  output lines; end;
       when (check2='path') delete;
       when (check=' ' and check3=' ' and (check4 ne '#' and check4 ne '+' and check4 ne '<' and
                    check4 ne '>' and check4 ne '*')) delete;
       otherwise do;
             input @1 anode dwt=$ ttf= lay= us1= us2= us3=;
               output itins; end;
    end;

 /*GET CODE AND BNODE ON SAME LINE*/
data itins(keep=node code type); set itins;
  node=anode;
  if check4='#' then dwcode=1;
  else if check4='>' then dwcode=2;
  else if check4='<' then dwcode=3;
  else if check4='+' then dwcode=4;
  else if check4='*' then dwcode=5;
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
