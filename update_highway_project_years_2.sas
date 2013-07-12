/*
   update_highway_project_years_2.sas
   authors: cheither & npeterson
   revised: 7/9/13
   ----------------------------------------------------------------------------
   Program checks rail & bus project scenario year against tip completion year.

*/

%let yearcsv=%scan(&sysparm,1,$);
%let raildbf=%scan(&sysparm,2,$);
%let busdbf=%scan(&sysparm,3,$);
%let pmdbf=%scan(&sysparm,4,$);
%let yearadj=%scan(&sysparm,5,$);

filename in1 "&yearcsv";
filename out1 "&yearadj";


*** READ IN RAIL INFORMATION ***;
proc import datafile="&raildbf" dbms=dbf out=routes replace;
data rail(keep=trline10 scen10 notes50 code); set routes(where=(scenario not in ('','7','9') & notes is not null));
 length trline10 scen10 $10. notes50 $50.;
  trline10=tr_line;
  scen10=scenario;
  notes=compress(notes,'-');
  notes50=notes;
  code='R';
data rail(rename=(trline10=tr_line scen10=scenario notes50=notes)); set rail;

*** READ IN PEOPLE MOVER INFORMATION ***;
proc import datafile="&pmdbf" dbms=dbf out=routes replace;
data mover(keep=tr_line scen10 notes50 code); set routes(where=(scenario not in ('','9') & notes is not null));
 length tr_line scen10 $10. notes50 $50.;
  tr_line='ppl_mover';
  scen10=scenario;
  notes=compress(notes,'-');
  notes50=notes;
  code='P';
data mover(rename=(scen10=scenario notes50=notes)); set mover;

*** READ IN BUS INFORMATION ***;
proc import datafile="&busdbf" dbms=dbf out=routes replace;
data bus(keep=tr_line scn notes code); set routes(where=(scenario not in ('','9') & notes is not null));
 length tr_line scn $10.;
  tr_line=transit_li;
  scn=scenario;
  notes=compress(notes,'-');
  code='B';
data bus(rename=(scn=scenario)); set bus;
  if scn='X' or scn='Z' then delete;

*** ISOLATE TIPID NUMBERS ***;
data rail; set rail mover bus;
  length tip $20.;
    output;
    c=count(notes,':'); if c>0 then c=c+1;
     if c>0 then do;
        do i=1 to c;
	    tip=scan(notes,i,':'); output;
	end;
     end;

data rail; set rail;
  if c>0 then do; if notdigit(tip)=9 then tipid=input(tip,best8.); end;
  else do; if notdigit(notes)=9 then tipid=input(notes,best8.); end;

  *** IDENTIFY EARLIEST SCENARIO ***;
data rail2(keep=tipid scen code); set rail(where=(tipid>0));
  l=length(scenario);
  if l=1 then scen=input(scenario,best1.);
  output;
     if l>1 then do;
        do j=1 to l;
	    scen=input(substr(scenario,j,1),best1.); output;
	end;
     end;

data rail2; set rail2(where=(scen>=1)); proc sort; by tipid scen;
data rail2; set rail2; by tipid scen;
  if first.tipid;


   *** READ IN TIP PROJECT COMPLETION YEAR LIST ***;
data proj; infile in1 missover dsd;
  input tipid year;
    proc sort; by tipid;

data nomatch; merge proj rail2 (in=hit); by tipid;
 *** BRT projects in line below also have hwy project coding ***;
  if tipid<16080005 or tipid>16080007 then do;
      if hit then delete;
  end;


  *** WRITE FILE OF NON-MATCHES TO COMPARE TO HIGHWAY CODING ***;
data print (keep=tipid year); set nomatch;
   label tipid='TIPID'
         year='COMPLETION_YEAR';
   proc export outfile=out1 dbms=csv label replace;


  *** CHECK FOR SCENARIO CODING-COMPLETION YEAR MISMATCH ***;
data check; merge proj rail2 (in=hit); by tipid;
  if hit;
  *** c13q1 scenarios***;
   if 1990<=year<=2010 then compscen=1;
   else if 2011<=year<=2015 then compscen=2;
   else if 2016<=year<=2020 then compscen=3;
   else if 2021<=year<=2025 then compscen=4;
   else if 2026<=year<=2030 then compscen=5;
   else if 2031<=year<=2040 then compscen=6;

   if scen=compscen then delete;
    proc print; title "Coded Scenario Does Not Match Completion Year";
       title2 "[Year=. Means the Project is Not in the Completion Year File]";


run;
