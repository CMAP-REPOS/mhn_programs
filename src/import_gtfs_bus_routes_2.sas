/*
   import_gtfs_bus_routes_2.sas
   authors: cheither & npeterson
   revised: 5/18/17
   ----------------------------------------------------------------------------
   Program is called by import_gtfs_bus_routes.py & formats bus itineraries
   to build with arcpy.

   Hardcoded inputs (after filename section):
   1. Pseudo nodes - Inserted into routes to force passage through specific
      nodes; generally used to correct express bus coding that is routed
      incorrectly when left to its own devices. Review before importing routes
      after major network edits.
   2. Pace zone fares - Listing of Pace Premium service with a surcharge even
      for pass-holders. Review when GTFS updates are imported.

   Processing steps:
    1. Import header & itinerary files.
       - Identify & remove routes with only one itinerary segment where
         ITIN_A = ITIN_B.
       - Only keep coding for routes with corresponding itinerary coding.
       - Create variables (TRANSIT_LINE, MODE, TYPE, DESCRIPTION, ETC.) to
         store coding.
    2. Make adjustments if necessary.
       - Adjust itinerary coding if segment has same node at beginning & end.
       - Insert pseudo nodes into itinerary.
       - Apportion line times over Pace segments with duplicate times & attach
         Pace zone fare.
       - Adjust itinerary coding if it contains nodes not available in the
         network (if the initial processing network is out of sync with the
         current MHN).
       - Iterate through list of itinerary gaps to find shortest path.
           * shortest_path.py - A Python script that finds the shortest path
             between the nodes identifying the itinerary gap. This script uses
             brute force so limiting the MHN being analyzed greatly increased
             the efficiency.
           * read_path_output.sas - Inserts the shortest path information into
             the itineraries & recalculates values.
       - Calculate the AM Peak share of the route.

*/
options noxwait;

%let peakst = 25200;   ** 7:00 AM in seconds;
%let peakend = 32400;  ** 9:00 AM in seconds;
%let search = 5280;    ** search distance (ft) for shortest path file;

** FIXED VARIABLES **;
%let rawhead = %scan(&sysparm, 1, $);
%let rawitin = %scan(&sysparm, 2, $);
%let transact = %scan(&sysparm, 3, $);
%let network = %scan(&sysparm, 4, $);
%let nodes = %scan(&sysparm, 5, $);
%let srcdir = %scan(&sysparm, 6, $);
%let head = %scan(&sysparm, 7, $);
%let itin = %scan(&sysparm, 8, $);
%let pseudo = %scan(&sysparm, 9, $);
%let linkdict = %scan(&sysparm, 10, $);
%let shrtpath = %scan(&sysparm, 11, $);
%let ptherrtx = %scan(&sysparm, 12, $);
%let holdchck = %scan(&sysparm, 13, $);
%let holdtime = %scan(&sysparm, 14, $);
%let rteprcss = %scan(&sysparm, 15, $);
%let counter = %scan(&sysparm, 16, $);
%let maxzn = %scan(&sysparm, 17, $);
%let lst = %scan(&sysparm, 18, $);
%let pypath = %sysfunc(tranwrd(&srcdir./pypath.txt, /, \));
%let count = 1;
%let tothold = 0;
%let samenode = 0;
%let badnode = 0;
%let totfix = 0;
%let xmin = 0; %let xmax = 0; %let ymin = 0; %let ymax = 0;
%let pnd = 0;
%let patherr = 0;
*%let timefix = 0;

** INPUT FILES **;
filename in1 "&rawhead";
filename in2 "&rawitin";
filename in3 "&network";
filename in4 "&shrtpath";
filename in5 "&nodes";
filename in6 "&transact";

** OUTPUT FILES **;
filename out1 "&head";
filename out2 "&itin";
filename out3 "&linkdict";
filename out4 "&holdtime";
filename out5 "&rteprcss";

*============================================================================*;
  ** IMPORT PSEUDO-NODES USED TO LOCATE ROUTE CORRECTLY **;
   * These are inserted into routes to force them to pass through specific nodes;
   * Pnode1 & 2 are forced locations, newlink is number of segments inserted (number of pnodes + 1);
   * Each entry represents 1 direction only;
   * Switched to CSV import after C15Q3;
*============================================================================*;
data pseudo; infile "&pseudo" firstobs=2 missover dsd;
    length mode $ 1;
    input mode $ route_id $ itinerary_a itinerary_b pnode1 pnode2 newlink;
    proc sort; by mode route_id;


*============================================================================*;
  ** PACE ZONE FARES LIST **;
   * From Pace Year 2011 fare sheet on pacebus.com;
   * Premium service has a $2.25 surcharge even for pass-holders;
*============================================================================*;
data pacezf; infile datalines missover dsd;
    length mode $ 1;
    input mode $ route_id $ zonefr;
    datalines;
        Q,237,225
        Q,282,225
        Q,284,225
        Q,755,225
        Q,768,225
        Q,769,225
        Q,773,225
        Q,774,225
        Q,775,225
        Q,776,225
        Q,779,225
        Q,855,225
    ;
    proc sort; by mode route_id;

/*---------------------------------------------------------------------------*/

** READ IN BUS CODING **;
%macro getdata;
    %if %sysfunc(fexist(in1)) %then %do;
        proc import out=route datafile="&rawhead" dbms=csv replace; getnames=yes; guessingrows=10000;
        data route(drop=route_id); set route;
            length temp_id $8.;
            temp_id = route_id;
        data route(rename=(temp_id=route_id)); set route; proc sort; by line;
    %end;
    %else %do;
        data null; file "&lst"; put "File not found: &rawhead";
    %end;

    %if %sysfunc(fexist(in2)) %then %do;
        proc import out=sec1 datafile="&rawitin" dbms=csv replace; getnames=yes; guessingrows=10000;
        proc sort data=sec1; by line;
    %end;
    %else %do;
        data null; file "&lst" mod; put "File not found: &rawitin";
    %end;
%mend getdata;
%getdata
run;


** IDENTIFY & REMOVE ROUTES WITH ONLY ONE ITINERARY SEGMENT WHERE ITINA=ITINB & BAD DATA **;
data sec1; set sec1(where=(line is not null & itinerary_a is not null & itinerary_b is not null));  ** drop garbage;
data check; set sec1; proc summary nway; class line; output out=chk1;
data sec1; merge sec1 chk1; by line;
data sec1(drop=_type_ _freq_) bad; set sec1;
    if _freq_ = 1 & itinerary_a = itinerary_b then output bad;
    else output sec1;

data bad; set bad; proc print; title "Bad Itinerary Coding";

data keeprte(keep=line); set sec1; proc sort nodupkey; by line;
data route; merge route keeprte (in=hit); by line; if hit;


** PROCESS ROUTES FOR ARC PATH BUILDING **;
data route(drop=shape_id); set route;
    if line = '' then delete;  ** drop blank rows in spreadsheet;
    description = upcase(compress(description, "'"));
    route_long_name = upcase(compress(route_long_name, "'"));
    direction = upcase(compress(direction, "'"));
    terminal = upcase(compress(terminal, "'"));
    speed = round(max(speed, 15));

    if mode = 'B' then type = 1;
    else if mode = 'E' then type = 2;
    else if mode = 'P' then type = 3;
    else if mode = 'Q' then type = 4;
    else if mode = 'L' then type = 5;
    proc sort; by mode line;

data route; set route; by mode line;
    ty = lag(type);
data route; set route; by mode line;
    retain q &counter;
    q + 1;
    if type ^= ty then q = &counter + 1;
    output;

data route(drop=q ty); set route;
    length newline $6. temp1 $5. descr $50.;
    temp1 = q;
    newline = tranwrd(lowcase(substr(mode, 1, 1)) || temp1, '', '0');
    descr = trim(route_id) || " " || trim(route_long_name) || ": " || trim(direction) || " TO " || trim(terminal);
    proc sort; by newline;

data rte1(drop=description type temp1);
    retain line route_id route_long_name direction terminal descr mode speed newline; set route;
proc export data=rte1 outfile=out5 dbms=csv replace;


proc sql noprint;
    create table section as
        select sec1.*, route.newline
        from sec1,route
        where sec1.line=route.line;


data section(drop=shape_id shape_dist_trav_a shape_dist_trav_b); set section;
    if order ^= int(order) then delete;  ** drop skeleton link coding accidentally left in;
    zfare = max(zfare, 0);
    ttf = max(ttf, 0);
    ltime = round(max(ltime, 0), .1);
    imputed = 0;
    link_stops = max(link_stops, 0);
    group = lag(line);
    rename skip_flag = dwcode;
    proc sort; by newline order;

data x; set section(where=(itinerary_a is null or itinerary_b is null)); proc print; title "Check1";

/*---------------------------------------------------------------------------*/

** Adjust itinerary coding if segment has same node at beginning & ending, if necessary **;

data same section; set section;
    if itinerary_a = itinerary_b then output same;
    else output section;

data temp; set same nobs=smnode; call symput('samenode', left(put(smnode, 8.))); run;

%macro segfix;
    %if &samenode > 0 %then %do;
        proc sort data=same; by newline order;
        data same; set same; by newline order;
            nl = lag(newline);
            o = lag(order);
        data same; set same;
            retain g 0;
            if newline ^= nl & order ^= o + 1 then g + 1;
            output;

        proc summary nway; class g newline; var order dep_time arr_time ltime link_stops;
            output out=fixit max(order)=ordmax min(order)=ordmin min(dep_time)= max(arr_time)= sum(ltime)=addtime sum(link_stops)=addstop;
        proc summary nway data=section; class newline; var order;
            output out=lineend max=lnmax;
        data fixit(drop=_type_ _freq_); merge fixit lineend; by newline;
        data fix1(keep=newline order arr_time addtime addstop); set fixit(where=(ordmax > lnmax));  ** adjust data if last entry in itinerary;
            order = ordmin - 1;
        data fix2(keep=newline order dep_time addtime2 addstop2); set fixit(where=(ordmax <= lnmax));  ** apply to subsequent segment;
            order = ordmax + 1;
            rename addtime=addtime2 addstop=addstop2;

        data section(drop=addtime addstop addtime2 addstop2); merge section (in=hit) fix1 fix2; by newline order; if hit;
            if addtime > 0 or addtime2 > 0 then do;
                addtime = max(addtime, 0); addtime2 = max(addtime2, 0);
                ltime = ltime + addtime + addtime2;
                addstop = max(addstop, 0); addstop2 = max(addstop2, 0);
                link_stops = link_stops + addstop + addstop2;
            end;
    %end;
%mend segfix;
%segfix
/* end macro*/

/*---------------------------------------------------------------------------*/

data x; set section(where=(itinerary_a is null or itinerary_b is null)); proc print; title "Check2";

/*---------------------------------------------------------------------------*/

** Insert pseudo nodes into itinerary, if necessary **;
proc sql noprint;
    create table check as
        select route.newline, pseudo.itinerary_a, itinerary_b, pnode1, pnode2, newlink
        from route, pseudo
        where route.mode=pseudo.mode & route.route_id=pseudo.route_id
        order by newline,itinerary_a,itinerary_b;

data temp; set check nobs=pndfix; call symput('pnd', left(put(pndfix, 8.))); run;

%macro fixpseudo;
    %if &pnd > 0 %then %do;
        proc sort data=section; by newline itinerary_a itinerary_b;
        data pfix; merge section(in=hit) check; by newline itinerary_a itinerary_b;
            if hit;
        data pfix section; set pfix;
            if pnode1 > 0 then output pfix;
            else output section;
        data pfix; set pfix;
            n = 1; output;
            n = 2; output;
            if newlink = 3 then do;
                n = 3; output;
            end;
        data pfix; set pfix;
            ltime = round(ltime / newlink, 0.1);
            order = n / 10 + order;
            tm = round((arr_time - dep_time) / newlink);
            if newlink = 2 then do;
                if n = 1 then do;
                    itinerary_b = pnode1;
                    dwcode = 1;
                    arr_time = dep_time + tm;
                end;
                else do;
                    itinerary_a = pnode1;
                    dep_time + tm;
                end;
            end;
            if newlink = 3 then do;
                if n = 1 then do;
                    itinerary_b = pnode1;
                    dwcode = 1;
                    arr_time = dep_time + tm;
                end;
                else if n = 2 then do;
                    itinerary_a = pnode1;
                    itinerary_b = pnode2;
                    dwcode = 1;
                    dep_time + tm;
                    arr_time = dep_time + tm;
                end;
                else do;
                    itinerary_a = pnode2;
                    dep_time + (tm * 2);
                end;
            end;

        data dwadj(keep=newline newb pnode1); set pfix(where=(itinerary_b = pnode1 or itinerary_b = pnode2));
            rename itinerary_b=newb;
        data section(drop=pnode1 pnode2 newlink n tm); set section pfix;
            proc sort; by newline order;
        run;
    %end;
%mend fixpseudo;
%fixpseudo
/* end macro*/

/*---------------------------------------------------------------------------*/

data x; set section(where=(itinerary_a is null or itinerary_b is null )); proc print; title "Check3";

/*---------------------------------------------------------------------------*/

** Apportion line times over pace segments & attach pace zone fare **;
data qroute; set route(where=(mode = 'Q')); proc sort; by mode route_id;
data qroute(keep=newline zonefr); merge qroute(in=hit1) pacezf(in=hit2); by mode route_id;
    if hit1 & hit2;
    proc sort; by newline;

data cta pace; set section;
    if substr(newline, 1, 1) = 'b' or substr(newline, 1, 1) = 'e' then output cta;
    else output pace;

data pace(drop=zonefr); merge pace(in=hit) qroute; by newline; if hit;
    if zonefr > 0 & order = 1 then zfare = zonefr;
    dt = lag(dep_time);
    proc sort; by newline order;

** Estimate Times for Pace Lines where first dep_time=last arr_time **;
data first(keep=newline dep_time); set pace; by newline order;
    if first.newline;
data last(keep=newline arr_time); set pace; by newline order;
    if last.newline;
data chk; merge first last; by newline;
    if dep_time=arr_time;
proc sql noprint;
    select count(*) into :timefix from work.chk;
    quit;
run;

%macro sametime;
    %if &timefix > 0 %then %do;
        data chk(keep=newline flag); set chk;
            flag = 1;
        data pace; merge pace chk; by newline;
        data timefix; set pace(where=(flag = 1));

        ** Use Node Coordinates, 30 MPH & Euclidean distance to estimate new final arrival time ... **;
        data node; infile in5 dlm=',' firstobs=2;
            input itinerary_a ax ay;  proc sort; by itinerary_a;
        data nodeb; set node; rename itinerary_a=itinerary_b ax=bx ay=by; proc sort; by itinerary_b;

        proc sort data=timefix; by itinerary_a;
        data timefix; merge timefix(in=hit) node; by itinerary_a; if hit; proc sort; by itinerary_b;
        data timefix; merge timefix(in=hit) nodeb; by itinerary_b; if hit;
            dist = sqrt((ax - bx)**2 + (ay - by)**2) / 5280;
            minutes = round(dist / 30 * 60, 0.1);

        proc summary nway data=timefix; class newline; var order minutes;
            output out=fixed max(order)= sum(minutes)=totmin;
        data timefix(keep=newline order minutes); set timefix;  proc sort; by newline order;

        ** ... And Calculate New Estimated Ltime **;
        proc sort data=pace; by newline order;
        data pace(drop=_type_ _freq_ flag minutes totmin); merge pace timefix fixed; by newline order;
            if minutes then ltime = minutes;
            if totmin then arr_time = round(totmin * 60 + arr_time);
        run;
    %end;
%mend sametime;
%sametime
/* end macro*/

data pace; set pace;
    retain grupo 0;
    if line ^= group or dep_time ^= dt then grupo + 1;
    output;
    proc sort; by itinerary_a;

** Attach Node Coordinates to Calculate Distance **;
data node; infile in5 dlm=',' firstobs=2;
    input itinerary_a ax ay;  proc sort; by itinerary_a;
data nodeb; set node; rename itinerary_a=itinerary_b ax=bx ay=by; proc sort; by itinerary_b;
data pace; merge pace(in=hit) node; by itinerary_a;
    if hit;
    proc sort; by itinerary_b;
data pace(drop=dt ax ay bx by); merge pace(in=hit) nodeb; by itinerary_b;
    if hit;
    dist = sqrt((ax - bx)**2 + (ay - by)**2) / 5280;
    proc sort; by newline order grupo;
proc summary nway data=pace; class grupo; var dist ltime;
    output out=fixpace sum(dist)=miles sum(ltime)=time n=elements;
data pace(drop=_type_ _freq_ dist miles grupo time); merge pace fixpace; by grupo;
    if elements > 1 then do;  ** only adjust the segments that need it **;
        ltime = round(dist / miles * time, 0.1);
        if ltime > 0 then arr_time = (ltime * 60) + dep_time;
        if ltime = . then ltime = time;
    end;
    proc sort; by newline order;

proc summary nway data=pace; class newline; var dep_time;
    output out=st min=strtln;

data pace(drop=_type_ _freq_); merge pace st; by newline;
    retain all 0;
    if first.newline then all = 0;
    output;
    all + ltime;

data pace(drop=strtln all elements); set pace; by newline order;
    if elements > 1 then do;
        if first.newline then arr_time = (ltime * 60) + strtln;
        else do;
            dep_time = (all * 60) + strtln;
            arr_time = (ltime + all) * 60 + strtln;
        end;
    end;

data section; set cta pace; proc sort; by newline order;

/*---------------------------------------------------------------------------*/

data x; set section(where=(itinerary_a is null or itinerary_b is null )); proc print; title "Check4";

data verify; set section; proc sort; by itinerary_a itinerary_b;


*---------------------;
  ** VERIFY CODING **;
*---------------------;
** Read in MHN links **;
data m; infile in3 dlm=',' firstobs=2;
    length abb $ 13;
    input itinerary_a itinerary_b base abb dir typ1 typ2 spd1 spd2 mhnmi;
    proc sort; by abb;

data sec; infile in6 dlm=',' firstobs=2;
    length abb $ 13;
    input abb action spd1 spd2 dir;
    if action = 3 then action = 5;  ** Make "delete" the largest action value;
    proc summary nway; class abb; var action spd1 spd2 dir; output out=sec2 max=;
data sec2(drop=_type_ _freq_); set sec2;
    if spd1 = 0 then spd1 = .;
    if spd2 = 0 then spd2 = .;
    if dir = 0 then dir = .;
    base = 1;

data trueab(drop=action); update m sec2; by abb;
    if action = 5 or typ1 = 6 then delete;

data mhn(drop=c spd2 typ2 abb); set trueab(where=(base = 1));
    match = 1;
    output;
    if dir > 1 then do;
        c = itinerary_a; itinerary_a = itinerary_b; itinerary_b = c;  ** Flip A & B;
        typ1 = max(typ1, typ2);
        spd1 = max(spd1, spd2);
        output;
    end;
    proc sort; by itinerary_a itinerary_b;


** Read in MHN nodes **;
data node; infile in5 dlm=',' firstobs=2;
    input itinerary_a ax ay;  proc sort; by itinerary_a;
data ntwk; merge mhn (in=hit) node; by itinerary_a; if hit;

data nodechk(keep=itinerary_a); set section;
    output;
    itinerary_a = itinerary_b;
    output;
    proc sort nodupkey; by itinerary_a;
data nd; set ntwk;
    output;
    itinerary_a = itinerary_b;
    output;
    proc sort nodupkey; by itinerary_a;

/*---------------------------------------------------------------------------*/

** Adjust itinerary coding if it contains nodes not available in the network, if necessary **;

data nodechk(keep=itinerary_a); merge nodechk nd (in=hit); by itinerary_a;
    if hit then delete;
data temp; set nodechk nobs=nonode; call symput('badnode', left(put(nonode, 8.))); run;

%macro nodefix;
    %if &badnode > 0 %then %do;
        data nodechk; set nodechk;
            fixa = 1;
        data nodechk2(rename=(itinerary_a=itinerary_b fixa=fixb)); set nodechk;

        data verify; merge verify nodechk; by itinerary_a; proc sort; by itinerary_b;
        data verify; merge verify nodechk2; by itinerary_b;
        data fix verify(drop=fixa fixb); set verify;
            if fixa = 1 or fixb = 1 then output fix;
            else output verify;

        proc sort data=fix; by newline order;
        data fix; set fix;
            nl = lag(newline);
            o = lag(order);
        data fix(drop=nl o fixa fixb); set fix; by newline order;
            retain grp 0;
            if newline ^= nl or order ^= o + 1 then grp + 1;
            output;
            proc sort; by grp order;

        data pt1(keep=grp line itinerary_a dep_time order newline group) pt2(keep=grp itinerary_b arr_time); set fix; by grp;
            if first.grp then output pt1;
            if last.grp then output pt2;

        proc summary nway data=fix; class grp; var ltime dwcode link_stops zfare ttf imputed;
            output out=pt3 sum(ltime)= max(dwcode)= sum(link_stops)= max(zfare)= max(ttf)= max(imputed)=;
        data pt(drop=_type_ _freq_ grp); merge pt1 pt2 pt3; by grp;
        data verify; set verify pt; proc sort; by itinerary_a itinerary_b;
    %end;
%mend nodefix;
%nodefix
/* end macro*/

** Above does NOT fix first/last itin segments beginning/ending on bad nodes, so print still-bad itin nodes **;
data nodechk2(keep=itinerary_a); set verify;
    output;
    itinerary_a = itinerary_b;
    output;
    proc sort nodupkey; by itinerary_a;
data nodechk2(keep=itinerary_a); merge nodechk2 nd (in=hit); by itinerary_a;
    if hit then delete;
    proc print; title "Itinerary Start/End Nodes Not in the Network";

/*---------------------------------------------------------------------------*/

** Find itinerary segments that do not correspond to MHN links **;
data verify; merge verify (in=hit) mhn; by itinerary_a itinerary_b; if hit;

** Hold segments that do not match MHN links or are the wrong direction **;
** -- This file can be used for troubleshooting & verification -- **;
data hold(drop=group dir match); set verify(where=(match ^= 1));
proc export data=hold outfile=out4 dbms=csv replace;

data temp; set hold nobs=totobs; call symput('tothold', left(put(totobs, 8.))); run;


/*---------------------------------------------------------------------------*/

** Iterate through list of itinerary gaps to find shortest path, if necessary **;
%macro itinfix;
    %if &tothold > 0 %then %do;
        data short(keep=itinerary_a itinerary_b); set hold; proc sort nodupkey; by itinerary_a itinerary_b;

        /* This file can be used for troubleshooting & verification with short_path.txt */
        proc export data=short outfile="&holdchck" dbms=csv replace;
        data short; set short; num = _n_;
        data temp; set short nobs=fixobs; call symput('totfix', left(put(fixobs, 8.))); run;

        x "if exist &pypath (del &pypath /Q)";
        %let command = %nrstr(for %i in (pythonw.exe) do @echo.%~$PATH:i);
        x "&command >> &pypath"; run;

        data null; infile "&pypath" length=reclen obs=1;
            input location $varying254. reclen;
            call symput('runpython', trim(location));
            run;

        x "if exist &pypath (del &pypath /Q)";

        /* RUN PYTHON SCRIPT */
        %do %while (&count <= &totfix);
            data shrt; set short(where=(num = &count));
                call symput('a', left(put(itinerary_a, 5.)));
                call symput('b', left(put(itinerary_b, 5.))); run;

            data node1; set node(where=(itinerary_a = &a or itinerary_a = &b));
            proc summary nway data=node1; var ax ay;
                output out=coord min(ax)=axmin max(ax)=axmax min(ay)=aymin max(ay)=aymax;
            data coord; set coord;
                d = round(sqrt((axmax - axmin)**2 + (aymax - aymin)**2), 0.5);
                d = max(d / &search, 3);
                d = min(d, 3);  /* link coord search multiplier parameter capped at 3 miles */
                /* AREN'T THE ABOVE LINES EQUIVALENT TO SIMPLY d = 3? */
                x1 = axmin - (d * &search);
                x2 = axmax + (d * &search);
                y1 = aymin - (d * &search);
                y2 = aymax + (d * &search);

            data _null_; set coord;
                call symput('xmin', left(put(x1, 8.))); call symput('xmax', left(put(x2, 8.)));
                call symput('ymin', left(put(y1, 8.))); call symput('ymax', left(put(y2, 8.))); run;

            data net1; set ntwk(where=(&xmin <= ax <= &xmax and &ymin <= ay <= &ymax));

            data dict(keep=itinerary_a itinerary_b miles); set net1(where=(itinerary_a > &maxzn and itinerary_b > &maxzn));
                if base = 1 then miles = int(mhnmi * 100);
                else miles = int(mhnmi * 100) + 500;  /* add 5 mile penalty to skeleton links to prohibit selection */
                /* SHOULD SKELETON LINKS JUST BE DELETED FROM DATASET INSTEAD? */

            data dict; set dict; by itinerary_a;
                file out3;
                if first.itinerary_a then do;
                    if last.itinerary_a then put itinerary_a +0 "${" +0 itinerary_b +0 ":" miles +0 "}";
                    else put itinerary_a +0 "${" +0 itinerary_b +0 ":" miles @;
                end;
                else if last.itinerary_a then put +0 "," itinerary_b +0 ":" miles +0 "}";
                else put +0 "," itinerary_b +0 ":" miles @;

            data _null_;
                %put a=&a b=&b;
                x "%str(%'&runpython.%') &srcdir.\shortest_path.py &a &b &linkdict &shrtpath";
            %let count = %eval(&count + 1);
        %end;

        /* READ SHORTEST PATHS FOUND */
        /* Do a first pass to check for paths not found */
        data nopath; infile in4 dlm="(,)";
            input length node $; if length = 0;

        data _null_; set nopath nobs=totobs; call symput('patherr', left(put(totobs, 8.))); run;
            %if &patherr > 0 %then %do;
                proc printto print="&ptherrtx";
                proc print noobs data=nopath; title "***** SHORTEST PATH ERROR: NO PATH FOUND, REVIEW CODING *****";
                proc printto;
            %end;
        /* ADD LOGIC TO VERIFY NUMBER OF ENTRIES IN SHORT_PATH IS EQUAL TO &TOTFIX, ELSE STOP SCRIPTS */

        %include "&srcdir./read_path_output.sas";
    %end;
%mend itinfix;
%itinfix
/* end macro*/

/*---------------------------------------------------------------------------*/

** ADJUST QUESTIONABLE LINE TIMES **;
data newitin; set newitin;
    group = lag(line);
    if spd1 = 0 then do;
        if typ1 = 2 or typ1 = 4 then spd1 = 55;
        else spd1 = 30;
    end;
    ltime = max(ltime, 0.1);

data check; set newitin(where=(ltime = 0)); proc print; title "BAD LINE TIMES";

/*---------------------------------------------------------------------------*/

** Ensure transit not coded on centroid links **;
data bad; set newitin(where=(itinerary_a <= &maxzn or itinerary_b <= &maxzn));
    proc print; var itinerary_a itinerary_b line order; title 'TRANSIT CODING ON CENTROID CONNECTORS';

/*---------------------------------------------------------------------------*/

*--------------------------------;
  ** FORMAT ITINERARY DATASET **;
*--------------------------------;
data section(drop=order); set newitin;
    retain ordnew 1;
    ordnew + 1;
    if line ^= group then ordnew = 1;
    output;
    proc sort; by newline ordnew;

** CALCULATE AM SHARE **;
data section; set section; by newline ordnew;
    if dep_time >= &peakst & arr_time <= &peakend then am = 1;  ** segment occurs during AM Peak;

proc summary nway data=section; class newline; var am;
    output out=stats sum=;

** Get run start time - assume zero is incorrect **;
data sect1; set section; by newline ordnew;;
    if dep_time = 0 then start = arr_time;
    else start = min(dep_time, arr_time);
    if start = 0 then delete;
data sect1(keep=newline start); set sect1; by newline ordnew; if first.newline;

data stats(keep=newline ampct); set stats;
    ampct = max(0, round(am / _freq_, .01));
proc sort data=route; by newline;
data route; merge route sect1 stats; by newline;
    if start = . then start = 0;
    strthour = mod(int(start / 3600), 24);  ** Restrict within 0-23;
    ** set headways to time period length **;
    if strthour in (0:5, 20:23) then headway = 600;  ** overnight;
    else if strthour in (6, 9) then headway = 60;  ** AM peak shoulders;
    else if strthour in (10:13) then headway = 240;  ** midday;
    else headway = 120;  ** AM/PM peaks, PM peak shoulders;

** Replace route header file for Arc **;
data rte; set route;
    length rln trmnl $32.;
    rln = substr(route_long_name, 1, 32);
    trmnl = substr(terminal, 1, 32);
data rte; set rte (keep=newline descr mode type headway speed line route_id rln direction trmnl start strthour ampct vehicle);
    label newline='TRANSIT_LINE'
        descr='DESCRIPTION'
        mode='MODE'
        type='VEHICLE_TYPE'
        headway='HEADWAY'
        speed='SPEED'
        line='FEEDLINE'
        route_id='ROUTE_ID'
        rln='LONGNAME'
        direction='DIRECTION'
        trmnl='TERMINAL'
        start='START'
        strthour='STARTHOUR'
        ampct='AM_SHARE';
   proc sort; by newline;
   proc export outfile=out1 dbms=csv label replace;


/*---------------------------------------------------------------------------*/

** REPORT ITINERARY GAPS **;
data check; set section;
    z = lag(itinerary_b);
    if itinerary_a ^= z & ordnew > 1 then output;
    proc print; var line ordnew itinerary_a itinerary_b z; title 'Itinerary Gaps';

/*---------------------------------------------------------------------------*/

** -- Logic to refine paths by condensing excessive doubling back in itineraries.                           -- **;
**    For example: a bus traveling around Woodfield Mall may keep fluctuating between selecting nodes A & B    **;
**    as the closest to the actual stop locations, thereby causing multiple successive instances of traveling  **;
**    back & forth over the same roadway segment before continuing on.                                         **;

** Identify multiple instances of same segment within routes **;
proc summary nway data=section; class newline itinerary_a itinerary_b;
    output out=chk2;
data chk2(keep=newline fix); set chk2(where=(_freq_ > 1));
    fix = 1;
    proc sort nodupkey; by newline;

data part1 part2a; merge section chk2; by newline;
    if fix then output part1;
    else output part2a;  ** part2a is OK;

proc sort data=part1; by newline ordnew;
data part1(drop=fix); set part1;
    ln = lag(newline);
    ita = lag(itinerary_a);
    itb = lag(itinerary_b);
data part1; set part1;
    retain grp 0;
    if (newline ^= ln) or (itinerary_a ^= itb) or (itinerary_b ^= ita) then grp + 1;  ** flag sets of back-and-forth action;
    output;

proc summary nway data=part1; class newline grp;
    output out=chk3;
data chk3(keep=newline fix); set chk3(where=(_freq_ > 1));
    fix = 1;
    proc sort nodupkey; by newline;

data part1 part2b; merge part1 chk3; by newline;
    if fix then output part1;
    else output part2b;  ** part2b is OK;

data part1(drop=fix); set part1;
    retain member 0;
    member + 1;
    if (newline ^= ln) or (itinerary_a ^= itb) or (itinerary_b ^= ita) then member = 1;  ** determine how many times back-and-forth action is present;
    output;

data odd; set part1(where=(mod(member, 2) > 0 & member > 1));  ** find set of segments that may be combined - must end in odd member number;
    proc summary nway; class grp; var member;
    output out=chk4 max=maxmem;
data chk4(keep=grp maxmem); set chk4;
data part1; merge part1 chk4; by grp;
    if member > maxmem then maxmem = .;

data fix part1; set part1;
    if maxmem then output fix;
    else output part1;

** Collapse Segments **;
proc sort data=fix; by newline grp ordnew;
data a(keep=newline itinerary_a itinerary_b ordnew grp line group); set fix; by newline grp ordnew;
    if first.grp;

proc summary nway data=fix; class newline grp;
    var dwcode zfare ttf dep_time arr_time link_stops;
    output out=fixed max(dwcode)= sum(zfare)= max(ttf)= min(dep_time)= max(arr_time)= sum(link_stops)=;

data fixed(drop=_type_ _freq_); merge a fixed; by newline grp;
   ltime = round(abs(arr_time - dep_time) / 60, 0.1);
   link_stops = link_stops + _freq_;
   imputed = 2;

data section(drop=fix ln ita itb grp member maxmem); set part1 fixed part2a part2b;
    proc sort; by newline ordnew;

data section(drop=ordnew); set section;
    retain order 1;
    order + 1;
    if line ^= group then order = 1;
    output;
    proc sort; by itinerary_a itinerary_b;

/*---------------------------------------------------------------------------*/

data arcs (keep=itinerary_a itinerary_b abb); infile in3 dlm=',' firstobs=2;
    length abb $ 13;
    input itinerary_a itinerary_b base abb dir;
    true = 1;
    output;
    if dir > 1 then do;
        c = itinerary_a; itinerary_a = itinerary_b; itinerary_b = c;  ** Flip A & B;
        output;
    end;
    proc sort; by itinerary_a itinerary_b;

** Find true arc direction in MHN **;
data section; merge section (in=hit) arcs; by itinerary_a itinerary_b;
    if hit;
    proc sort; by newline order;

data section; set section; by newline order;
    if last.newline then layover = 3;
    else layover = 0;

*---------------------------;
  ** WRITE ITINERARY FILE **
*---------------------------;
data writeout; set section (keep=newline itinerary_a itinerary_b abb order layover dwcode zfare ltime ttf link_stops imputed dep_time arr_time);
    label newline='TRANSIT_LINE'
        itinerary_a='ITIN_A'
        itinerary_b='ITIN_B'
        abb='ABB'
        order='ITIN_ORDER'
        layover='LAYOVER'
        dwcode='DWELL_CODE'
        zfare='ZONE_FARE'
        ltime='LINE_SERV_TIME'
        ttf='TTF'
        link_stops='LINK_STOPS'
        imputed='IMPUTED'
        dep_time='DEP_TIME'
        arr_time='ARR_TIME';
   proc sort; by newline order;
   proc export outfile=out2 dbms=csv label replace;

run;
