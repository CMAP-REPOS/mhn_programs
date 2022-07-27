/*
    generate_transit_files_2.sas
    authors: cheither & npeterson
    revised: 1/25/22
    ----------------------------------------------------------------------------
    Program creates bus transit network batchin files. Bus transit network is
    built using a modified version of MHN processing procedures.

*/
options noxwait;

%let dirpath = %scan(&sysparm, 1, $);
%let hwypath = %scan(&sysparm, 2, $);
%let lines = %scan(&sysparm, 3, $);
%let itins = %scan(&sysparm, 4, $);
%let replace = %scan(&sysparm, 5, $);
%let reroute = %scan(&sysparm, 6, $);
%let pnrcsv = %scan(&sysparm, 7, $);
%let scen = %scan(&sysparm, 8, $);
%let tod = %scan(&sysparm, 9, $);        * time-of-day period;
%let zone1 = %scan(&sysparm, 10, $);      * zone09 CBD start zone;
%let zone2 = %scan(&sysparm, 11, $);     * zone09 CBD end zone;
%let maxzone = %scan(&sysparm, 12, $);   * highest zone09 POE zone number;
%let procfut = %scan(&sysparm, 13, $);   * is scenario year later than MHN base year?;
%let progdir = %scan(&sysparm, 14, $);
%let misslink = %scan(&sysparm, 15, $);
%let linkdict = %scan(&sysparm, 16, $);
%let shrt = %scan(&sysparm, 17, $);
%let pathfail = %scan(&sysparm, 18, $);
%let mode4lk = %scan(&sysparm, 19, $);
%let mode4nd = %scan(&sysparm, 20, $);
%let outtxt = %scan(&sysparm, 21, $);
%let shrtpath = %sysfunc(tranwrd(&shrt, /, \));
%let pypath = %sysfunc(tranwrd(&progdir./pypath.txt, /, \));
%let newln = 0;
%let tothold = 0;
%let totfix = 0;
%let xmin = 0; %let xmax = 0; %let ymin = 0; %let ymax = 0;
%let count = 1;
%let search = 5280;  * search distance for shortest path file;
%let patherr = 0;
%let badnode = 0;

%macro time;
    %global tp;   ** Set Value for Highway Network Input File **;
    %if &tod = am %then %let tp = 3;
    %else %let tp = &tod;
%mend time;
%time
run;
%put time period: &tp;

/* ------------------------------------------------------------------------------ */
*** INPUT FILES ***;
filename in1 "&lines";
filename in2 "&itins";
filename innd "&hwypath.\&scen.0&tp..n1";
filename innd2 "&hwypath.\&scen.0&tp..n2";
filename inlk "&hwypath.\&scen.0&tp..l1";
filename pnrnd "&pnrcsv";
filename bwylk "&mode4lk";
filename bwynd "&mode4nd";

*** OUTPUT FILES ***;
filename later "&dirpath.\itin.final";
filename out1 "&dirpath.\bus.itinerary_&tod";
filename out2 "&dirpath.\bus.network_&tod";
filename nod "&dirpath.\busnode.extatt_&tod";
filename out3 "&dirpath.\busstop.pnt";
filename out4 "&dirpath.\ctabus.pnt";
filename out5 "&dirpath.\pacebus.pnt";
filename bus "&hwypath.\bus.link";
/* ------------------------------------------------------------------------------ */

proc printto print="&outtxt";

*-----------------------------------;
  ** READ IN TRANSIT LINE TABLE **;
*-----------------------------------;
data routes; infile in1 dsd missover firstobs=2;
    length descr $20;
    input linename $ descr mode $ vehtype speed headway;
    descr = left(descr);
    order = 0;
    proc sort; by linename;

*** Process Future Scenario Bus coding ***;
%macro future;
    %if &procfut = 1 %then %do;
        * Set headway multipliers for each time period;
        %let hdwymult = 2;  * For peak shoulders;
        %if &tp = 3 or &tp = 7 %then %let hdwymult = 1;
        %else %if &tp = 1 %then %let hdwymult = 4;
        %else %if &tp = 5 %then %let hdwymult = 3;

        data routes; set routes;
            length replace $8.;
            pos = anyspace(descr);
            replace = compress(mode || "-" || substr(descr, 1, pos - 1));

        data rep; infile "&replace" dsd missover firstobs=2;
            length repgrp $30;
            input linename $ replace $ repgrp $ timeper $;
            proc sort; by linename;
        data rep0(keep=linename new); set rep;
            new = 1;
            proc sort nodupkey; by linename;
        data rep00(keep=linename keeptod); set rep(where=(timeper = "0" or timeper ? "&tp"));
            keeptod = 1;
            proc sort nodupkey; by linename;
        data _null_; set rep00 nobs=newobs;
            call symput('newln', left(put(newobs, 8.))); run;

        %if &newln > 0 %then %do;  *** execute block only if there are future lines for time period;
            data rep1(keep=replace repgrp del); set rep(where=(replace is not null and (timeper = "0" or timeper ? "&tp")));
                del = 1;
                proc sort nodupkey; by replace;

            *** Remove Base Scenario Routes Replaced by Future Coding ***;
            data routes; merge routes(in=hit) rep0 rep00; by linename;
                if hit;
                proc sort; by replace;
            data routes(drop=pos); merge routes rep1; by replace;
                if substr(linename, 2, 2) = '99' then del = .;  *** reset value for future bus so not included in existing headway calculation;
                proc sort; by linename;

            data rte1; set routes(where=(del is null and keeptod is null and new is null));  *** current coding moving through to final file;

            data exist; set routes(where=(del = 1));  *** lines being replaced;
                proc summary nway; class repgrp; var headway;
                    output out=existing min=exhdw;  *** get headways of existing lines being deleted;

            proc summary nway data=rte1; class mode; var headway;
                output out=modeavg mean=modeavg;  *** get avg mode headway for period (existing routes);

            *** Create Final Route Table ***;
            data rep2(keep=linename repgrp); set rep(where=(replace is not null and (timeper = "0" or timeper ? "&tp")));
                proc sort nodupkey; by linename;
            data rte2(drop=new del replace); set routes(where=(keeptod = 1));
                proc sort; by linename;
            data rte2; merge rte2(in=hit) rep2; by linename;
                if hit;
                proc sort; by repgrp;  *** reset replace value to route table coding value for matching;
            data rte2; merge rte2(in=hit) existing; by repgrp;
                if hit;
                proc sort; by mode;  *** attach existing line headway for period;
            data rte2(drop=_type_ _freq_); merge rte2(in=hit) modeavg; by mode;
                if hit;  *** attach average time period headway for mode;

                ** ## Final Time Period Headway Calculation ## **;
                if headway > 0 then headway = headway * &hdwymult;  *** -- apply TOD headway multiplier to coded headway;
                else headway = -1;  *** -- coded value of zero means use existing headways;

                if headway > 0 then do;               *** -- Priority 1: use coded headway (or existing headway, if shorter);
                    if exhdw > 0 then hfin = min(headway, exhdw);
                    else hfin = headway;
                end;
                else if exhdw > 0 then hfin = exhdw;  *** -- Priority 2: use existing TOD headway for transit line;
                else hfin = max(modeavg, 90);         *** -- Priority 3: maximum of mode average/90 minutes;

                ** Limit headway to length of time period;
                if &tp = 1 then maxtime = 600;
                else if &tp in (2, 4) then maxtime = 60;
                else if &tp = 5 then maxtime = 240;
                else maxtime = 120;
                hfin = min(hfin, maxtime);

                headway = round(hfin, 0.1);

            data routes(drop=new del keeptod exhdw modeavg hfin maxtime); set rte1 rte2;
                proc sort; by linename;
            %end;

        data routes(drop=pos); set routes;
            length reroute $8.;
            pos = anyspace(descr);
            reroute = compress(mode || "-" || substr(descr, 1, pos - 1));

        data rrte; infile "&reroute" dsd missover firstobs=2;
            length rrtegrp $30;
            input linename $ reroute $ rrtegrp $ timeper $;
            proc sort; by linename;

        data rrte0(keep=linename modline); set rrte(where=(reroute is not null));
            modline = 1;
            proc sort nodupkey; by linename;

        data rrte00(keep=linename keeptod); set rrte(where=(reroute is not null and (timeper = "0" or timeper ? "&tp")));
            keeptod = 1;
            proc sort nodupkey; by linename;

        data _null_; set rrte00 nobs=newobs;
            call symput('modln', left(put(newobs, 8.)));
            run;

        %if &modln > 0 %then %do;  *** execute block only if there are future itinerary modifications for time period;

            data rrte; merge rrte(in=hit) rrte0 rrte00; by linename;
			    if hit;

            data rrte1(keep=linename rrtegrp modline); set rrte(where=(modline = 1));  *** dummy line IDs with itinerary modifications;
				proc sort nodupkey; by linename;

			data rrte2(keep=reroute rrtegrp mod); set rrte(where=(keeptod = 1));  ***  route IDs being modified;
			    mod = modline;
                proc sort nodupkey; by reroute;

		    *** Select Base Scenario Routes With Itinerary Modified by Future Coding ***;
            data routes; merge routes(in=hit) rrte1(drop=rrtegrp); by linename;
                if hit;
                proc sort; by reroute;

            data routes; merge routes(in=hit) rrte2; by reroute;
                if hit;
                proc sort; by linename;

            data rte3; set routes(where=(missing(modline)));  *** remove dummy lines from final file;

            data modify(keep=descr linename rrtegrp mod); set routes(where=(mod = 1));  *** lines with itineraries being modified;

            data modlines(keep=descr linename modline); set routes(where=(modline = 1)); *** dummy lines with itinerary modifications;

			data modlines; merge modlines(in=hit) rrte1(drop=modline); by linename;

            data routes(drop=modline mod); set rte3;
			    proc sort; by linename;

            %end;

        %end;
    %mend future;
%future
run;

* - - - - - - - - - - - - - - - - - *;
** REPORT HEADWAY PROBLEMS **;
data check; set routes(where=(headway = 0));
    proc print; var linename headway;
    title "NETWORK &scen No Headway On Bus Lines";
* - - - - - - - - - - - - - - - - - *;


*----------------------------------------;
  ** READ IN TRANSIT ITINERARY TABLE **;
*----------------------------------------;
data itins; infile in2 dsd missover firstobs=2;
    input linename $ itina itinb order layover dwcode zfare ltime ttf fmeas tmeas miles;
    if ttf = 0 then ttf = 1;
    proc sort; by linename order;

data _null_; set modify nobs=newobs;
    call symput('moditin', left(put(newobs, 8.)));
	run;

%macro futureitin;

    %if &moditin > 0 %then %do;  *** execute block only if there are itineraries that are being modified;

        data itins; merge itins(in=hit) modify modlines; by linename;  *** flag modified itineraries and existing itineraries being modified;
			if hit;

		data itin1; set itins(where=(missing(mod) and missing(modline)));  *** select existing itineraries not being modified;

        data existitin; set itins(where=(mod = 1));  *** select existing itineraries being modified;
		    proc sort; by itina rrtegrp;

		data modifyitin(drop=linename); set itins(where=(modline = 1));  *** select modified itineraries;
		    modlinename = linename;
		    proc sort; by modlinename order;

		data modifyends(keep=modlinename itina itinb order rrtegrp); set modifyitin; by modlinename order;  *** select modified itinerary ends;
            if first.modlinename then output;
			if last.modlinename then output;

		data modifystart(drop=modlinename itinb order); set modifyends(where=(order = 1));  *** select start nodes;
		    modstart = modlinename;
            proc sort; by itina rrtegrp;

		data modifyfinish(drop=modlinename itina order); set modifyends(where=(order > 1));  *** select finish nodes;
		    modfinish = modlinename;
		    proc sort; by itinb rrtegrp;

		data existitin; merge existitin(in=hit) modifystart; by itina rrtegrp;  *** add dummy line id to existing itineraries at start nodes;
		    proc sort; by itinb rrtegrp;

        data existitin; merge existitin(in=hit) modifyfinish; by itinb rrtegrp;  *** add dummy line id to existing itineraries at finish nodes;
		    proc sort; by linename order;

		data existitin(drop=part line); set existitin; by linename;  *** partition existing itineraries and add dummy line id to parts being rerouted;
		    retain part line;
            if first.linename then do;
                part = 1; line = linename;
				end;
            if mod(part, 2) = 1 and line = linename and not missing(modstart) then do;
			    part = part + 1; line = modstart;
				end;
			if line = lag(modfinish) then do;
			    part = part + 1; line = linename;
				end;
			modpart = part; modlinename = line;

		data mod1(keep=linename modpart modlinename); set existitin(where=(modlinename ~= linename));  *** select partitions to modify;
		    proc sort nodupkey; by linename modpart modlinename;
			proc sort; by modlinename;

		proc sort data=modifyitin; by modlinename;

		proc sql; create table mod2(drop=modlinename_1) as  
            select * from mod1 as t1
            left join modifyitin(rename=(modlinename = modlinename_1)) as t2
            on t1.modlinename = t2.modlinename_1;  *** join modified itineraries to partitions to modify;
			quit;
			proc sort; by linename order;

		data mod3; set existitin mod2;  *** append modified itinerary partitions to existing itineraries;
		    proc sort; by linename modpart order;

		data itin2(drop=modorder) ; set mod3(where=(modlinename = linename or modline = 1)); by linename;  *** filter out itinerary partitions that are being replaced and update itinerary order;
		    retain modorder;
			if first.linename then modorder = 1;
			order = modorder;
			modorder = modorder + 1;

		data itins(keep=linename itina itinb order layover dwcode zfare ltime ttf fmeas tmeas miles); set itin1 itin2;
		    proc sort; by linename order;

        %end;

    %mend futureitin;

%futureitin
run;

data itins; set itins;
    miles = round(miles, 0.01);
    proc sort; by linename itina itinb;

data r(keep=linename mode headway); set routes;
    proc sort; by linename;
data itins; merge itins r(in=hit); by linename;
    if hit;

* - - - - - - - - - - - - - - - - - *;
** REPORT LAYOVER PROBLEMS **;
** A MAXIMUM OF TWO LAYOVERS ARE ALLOWED PER TRANSIT LINE **;
data check; set itins(where=(layover > 0));
proc freq; tables linename / noprint out=check;
data check; set check;
    if count > 2;
    proc print; var linename count;
    title "NETWORK &scen Too Many Layovers Coded";
* - - - - - - - - - - - - - - - - - *;

data verify; set itins;
    proc sort; by itina itinb;

*~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~*;

** -- Adjust Itinerary Coding if it Contains Nodes not Available in the Network, If Necessary -- **;
data nodes(drop=flag); infile innd missover;
    input @1 flag $2. @;
        select(flag);
        when('a ', 'a*') input itina x_a y_a;
        otherwise delete;
    end;
    proc sort; by itina;

*** Get and append busway (MODES=4) nodes ***;
data buswaynd;
    infile bwynd delimiter=',' dsd missover firstobs=2;
    input itina: 5. x_a: 20. y_a: 20. zone: 5. atype: 2.; run;
    proc sort; by itina; run;
data nodes; merge nodes buswaynd; by itina;
proc sort; by itina; run;

*** Compare itinerary nodes against available network nodes ***;
data nodechk(keep=itina); set itins;
    output;
    itina = itinb;
    output;
    proc sort nodupkey; by itina;
data nodechk(keep=itina); merge nodechk nodes (in=hit); by itina;
    if hit then delete;

data temp; set nodechk nobs=nonode;
    call symput('badnode', left(put(nonode, 8.))); run;

%macro nodefix;
    %if &badnode > 0 %then %do;
        data nodechk; set nodechk;
            fixa = 1;
        data nodechk2(rename=(itina=itinb fixa=fixb)); set nodechk;
            proc sort; by itinb;

        data verify; merge verify nodechk; by itina;
            proc sort; by itinb;
        data verify; merge verify nodechk2; by itinb;

        data fix verify(drop=fixa fixb); set verify;
            if fixa = 1 or fixb = 1 then output fix;
            else output verify;

        proc sort data=fix; by linename order;
        data fix; set fix;
            nl = lag(linename);
            o = lag(order);
        data fix(drop=nl o fixa fixb); set fix; by linename order;
            retain grp 0;
            if (linename ^= nl) or (order ^= o + 1) then grp + 1;
            output;
            proc sort; by grp order;

        data pt1(keep=grp linename itina order fmeas mode headway) pt2(keep=grp itinb layover tmeas); set fix; by grp;
            if first.grp then output pt1;
            if last.grp then output pt2;

        proc summary nway data=fix; class grp; var ltime dwcode miles zfare ttf;
            output out=pt3 sum(ltime)= max(dwcode)= sum(miles)= max(zfare)= max(ttf)=;
        data pt(drop=_type_ _freq_ grp); merge pt1 pt2 pt3; by grp;
        data verify; set verify pt;
            proc sort; by itina itinb;
    %end;
%mend nodefix;
%nodefix
run;

*~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~*;

*--------------------------------------------------------;
  ** VERIFY SEGMENTS WORK ON SCENARIO NETWORK LINKS **;
*--------------------------------------------------------;
data ndzone; infile innd2 missover firstobs=2;
    input itina zone atype;
    proc sort; by itina;
data nodes; merge nodes(in=hit) ndzone; by itina;
    if hit;

*** Join Park-n-Ride data to nodes;
data pnr (drop=scens); infile pnrnd dsd missover firstobs=2;
    input itina pcost pspac scens;
    proc sort; by itina;
data nodes; merge nodes pnr; by itina;
    if pcost = . then pcost = 0;
    if pspac = . then pspac = 0;

data bnode(rename=(itina=itinb x_a=x_b y_a=y_b)) ; set nodes;
    drop zone atype pcost pspac;

*** Get available highway links from highway batchin file ***;
data links(drop=flag j1-j2); infile inlk missover;
    input @1 flag $2. @;
        select(flag);
        when('a ', 'a=') input itina itinb miles j1 $ j2 thruln vdf;
        otherwise delete;
    end;
    if vdf = 6 then delete;
    proc sort; by itina itinb;

*** Get and append busway (MODES=4) links ***;
data buswaylk;
    infile bwylk delimiter=',' dsd missover firstobs=2;
    input itina: 5. itinb: 5. miles: 20. thruln: 2. vdf: 1.; run;
    proc sort; by itina itinb; run;
data links; merge links buswaylk; by itina itinb;
    proc sort; by itina itinb; run;

data links; merge links(in=hit) nodes; by itina;
    if hit;
    proc sort; by itinb;
data links; merge links(in=hit) bnode; by itinb;
    if hit;
    base=1;
    proc sort; by itina itinb;

data verify; merge verify(in=hit) links; by itina itinb;
    if hit;

*** Hold segments that do not match MHN links ***;
data gapcheck(drop=miles thruln vdf x_a y_a zone atype x_b y_b base); set verify;
    proc sort; by linename order;
data gapcheck; set gapcheck; by linename order;
    z = lag(itinb);
    o = lag(order);
    if itina ^= z and not first.linename then do;
        itinb = itina;
        itina = z;
        order = o + 1;
        output;
    end;

data nomatch(drop=miles thruln vdf x_a y_a zone atype x_b y_b base); set verify(where=(base = .));

data hold(drop=z o); set gapcheck nomatch;
    proc export data=hold outfile="&misslink" dbms=csv replace;
data _null_; set hold nobs=totobs;
    call symput('tothold', left(put(totobs, 8.))); run;
%put tothold = &tothold;

*~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~*;

*====================================================================================;
  ** Iterate Through List of Itinerary Gaps to Find Shortest Path, If Necessary **;
*====================================================================================;
%macro itinfix;
    %if &tothold > 0 %then %do;
        ** Collapse consecutive missing segments from route to get outlying nodes **;
        **  -- initial grouping -- **;
        proc sort data=hold; by linename order;
        data hold; set hold;
            ln = lag(linename);
            od = lag(order);
        data hold; set hold; by linename order;
            retain group 0;
            if (linename ^= ln or order ^= od + 1) then group + 1;
            output;
            proc sort; by group order;

        ** Initial Groups **;
        data a(keep=group itina) b(keep=group itinb); set hold; by group order;
            if first.group then output a;
            if last.group then output b;
        data a1(rename=(itina=itna)); set a;
        data b1(rename=(itinb=itnb)); set b;
        data hold; merge hold a1 b1; by group;

        ** Final Grouping: Ensures the Same node is not the Beginning and Ending Point of Group **;
        data hold; set hold; by group;
            retain group2 0;
            if ((linename ^= ln) or (order ^= od+1) or (itna = itnb)) then group2 + 1;
            output;
            proc sort; by group2 order;

        data a(keep=group2 itina) b(keep=group2 itinb); set hold; by group2 order;
            if first.group2 then output a;
            if last.group2 then output b;
        proc summary nway data=hold; class group2; var layover dwcode zfare ltime ttf;
            output out=grpatt max(layover)= max(dwcode)= sum(zfare)= sum(ltime)= max(ttf)=;
        data ab(drop=_type_ _freq_); merge a b grpatt; by group2;

        data short(keep=itina itinb); set ab;
            proc sort nodupkey; by itina itinb;
        data short; set short;
            num = _n_;
        data temp; set short nobs=fixobs;
            call symput('totfix', left(put(fixobs, 8.))); run;

        x "if exist &pypath (del &pypath /Q)";
        %let command = %nrstr(for %i in (pythonw.exe) do @echo.%~$PATH:i);
        x "&command >> &pypath"; run;

        data null; infile "&pypath" length=reclen obs=1;
            input location $varying254. reclen;
            call symput('runpython', trim(location));
            run;

        x "if exist &pypath (del &pypath /Q)";
        x "if exist &shrtpath (del &shrtpath /Q)";

        ** -- RUN PYTHON SCRIPT -- **;
        %do %while (&count <= &totfix);
            data shrt; set short(where=(num = &count));
                call symput('a', left(put(itina, 5.)));
                call symput('b', left(put(itinb, 5.))); run;

            data node1; set nodes(where=(itina = &a or itina = &b));
            proc summary nway data=node1; var x_a y_a;
                output out=coord min(x_a)=axmin max(x_a)=axmax min(y_a)=aymin max(y_a)=aymax;
            data coord; set coord;
                d = round(sqrt((axmax - axmin)**2 + (aymax-aymin)**2), 0.5);
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

            data net1; set links(where=(&xmin <= x_a <= &xmax and &ymin <= y_a <= &ymax and miles > 0));
            data dict(keep=itina itinb miles); set net1(where=(itina > &maxzone and itinb > &maxzone));
                miles = int(miles * 100);

            *** Write Python dictionary file ***;
            data dict; set dict; by itina;
                file "&linkdict";
                if first.itina then do;
                    if last.itina then put itina +0 "${" +0 itinb +0 ":" miles +0 "}";
                    else put itina +0 "${" +0 itinb +0 ":" miles @;
                end;
                else if last.itina then put +0 "," itinb +0 ":" miles +0 "}";
                else put +0 "," itinb +0 ":" miles @;

            data _null_;
                %put a=&a b=&b;
                x "%str(%'&runpython.%') &progdir.\shortest_path.py &a &b &linkdict &shrtpath";
            %let count = %eval(&count + 1);
        %end;


        ** -- CALCULATE TRANSIT ROUTE LENGTHS BEFORE SHORTEST PATH PROCESSING -- **;
        proc summary nway data=itins; class linename; var miles;
            output out=befpath sum=b;
        data check; set itins(where=(linename is null));
            proc print; title "Bad Itinerary Data";

        ** -- READ SHORTEST PATHS FOUND -- **;
        ** Do a First Pass to Check for Paths not Found **;
        data nopath; infile "&shrtpath" dlm="(,)";
            input length node $;
            if length = 0;

        data _null_; set nopath nobs=totobs;
            call symput('patherr', left(put(totobs, 8.))); run;
        %if &patherr > 0 %then %do;
             proc printto print="&pathfail";
             proc print noobs data=nopath; title "***** SHORTEST PATH ERROR: NO PATH FOUND, REVIEW CODING *****";
             proc printto print="&outtxt";
        %end;

        *** RE-FORMAT PATH DATA AS ITINERARY SEGMENTS ***;
        data read(keep=newb set i totmiles); infile "&shrtpath" length=reclen lrecl=1000;
            input alldata $varying1000. reclen;
            set = _n_;
            alldata = compress(alldata, "[] ()");
            totmiles = input(scan(alldata, 1, ","), best5.) / 100;
            c = count(alldata, ",");
            *** format itinerary segments ***;
            do i = 1 to c;
                newb = input(scan(alldata, i + 1, ","), best5.);
                output;
            end;
            proc sort; by set i;

        data first; set read; by set i;
            if first.set then itina = newb;
            if last.set then itinb = newb;
            proc summary nway; class set; var itina itinb;
                output out=ends max=;

        data read(drop=_type_ _freq_ grp); merge read ends; by set;
            newa = lag(newb);
            grp = lag(set);
            if set = grp;
            proc sort; by newa newb;

        ** Attach Individual Segment Lengths ***;
        data len2(keep=newa newb miles); set links;
            rename itina=newa itinb=newb;
        data read; merge read (in=hit) len2; by newa newb;
            if hit;

        ** -- UPDATE ITINERARIES -- **;
        ** 1. Merge Group2 Attributes into Hold Dataset; **;
        data ab(rename=(itina=grp2a itinb=grp2b)); set ab;
        data new(drop=ln od group itina itinb itna itnb); merge hold ab; by group2;
            proc sort; by group2 grp2a grp2b;
        data new; set new; by group2 grp2a grp2b;
            if first.group2;

        ** 2. Attach New Paths & Update Attributes; **;
        proc sql noprint;
            create table newitin as
                select new.*, read.*
                from new left join read on new.grp2a=read.itina & new.grp2b=read.itinb
                order by linename,order,i;

        data newitin(drop=group2 grp2a grp2b set totmiles newb newa); set newitin; by linename order i;
            itina = newa;
            itinb = newb;
            ltime = max(round(miles / totmiles * ltime, 0.1), 0.1);
            if i > 2 then zfare = 0;  ** if there is a zone fare - only apply it to the first segment in the set **;
            if substr(linename, 1, 1) in ('e', 'q') then dwcode = 1;  ** flag imputed nodes as non-stops on express bus runs **;
            if last.order then layover = layover;
            else layover = 0;

        ** 3. Remove Missing Segments from Itinerary Dataset **;
        proc sort data=verify; by linename order;
        data dropmiss(keep=linename order); set hold;
            proc sort; by linename order;
        data verify; merge verify dropmiss(in=hit); by linename order;
            if not hit;

        ** 4. Combine Everything and Re-order Segments **;
        data verify; set verify newitin; proc sort; by linename order i;
        data verify(drop=order i); set verify;
            rank = _n_;
            ln = lag(linename);
            if miles > 0 then do;
                fmeas = 0;
                tmeas = miles;
            end;
            proc sort; by rank;
        data verify(drop=rank ln); set verify; by rank;
            retain order 0;
            order + 1;
            if linename ^= ln then order = 1;
            output;
        data verify; set verify; by linename order;
            if last.linename then do;
                layover = 3;
                dwcode = 0;
            end;

        data check; set verify(where=(linename is null));
            proc print; title "Bad Itinerary Data After Path";

        ** -- CALCULATE TRANSIT ROUTE LENGTHS AFTER SHORTEST PATH PROCESSING -- **;
        proc summary nway data=verify; class linename; var miles;
            output out=aftpath sum=a;
        data check; merge befpath aftpath; by linename;
            change = (a - b) / b;
            if abs(change) > 0.05;
            label b='Original Route Length'
                  a='Route Length After Shortest Path';
         proc print label; var linename b a change; format change percent6.2;
            title "SCENARIO &scen TOD &tod BUS ROUTE LENGTH DISCREPANCIES";

    %end;
%mend itinfix;
%itinfix
run;

*~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~*;

*-----------------------------------------------;
  ** WRITE OUT ITINERARY FILE FOR LATER USE **;
*-----------------------------------------------;
data print1; set verify;
    file later dsd;
    put linename itina itinb order layover dwcode;

data chk(keep=itina); set verify;
    output;
    itina = itinb;
    output;
    proc sort nodupkey; by itina;

data chk; merge chk nodes(in=hit); by itina;
    if not hit;
    proc print; title "Still Bad Nodes";


*=====================================================================;
  ** CREATE MODE b (BusBusWalk) LINKS **;
*=====================================================================;
data walkcbd; set links(where=(vdf = 1 and zone in (&zone1:&zone2)));
    mode = 'b';


*=====================================================================;
  ** ADD TRANSIT MODES TO NETWORK LINKS **;
*=====================================================================;
proc summary nway data=verify; class itina itinb mode; output out=unique;
data b(keep=itina itinb mode1); set unique(where=(mode = 'B'));
    mode1 = mode;
data e(keep=itina itinb mode2); set unique(where=(mode = 'E'));
    mode2 = mode;
data p(keep=itina itinb mode3); set unique(where=(mode = 'P'));
    mode3 = mode;
data q(keep=itina itinb mode4); set unique(where=(mode = 'Q'));
    mode4 = mode;
data l(keep=itina itinb mode5); set unique(where=(mode = 'L'));
    mode5 = mode;
data all(keep=itina itinb modes); merge b e p q l; by itina itinb;
    modes = compress(mode1 || mode2 || mode3 || mode4 || mode5);


*=====================================================================;
  ** WRITE EMME BATCHIN FILES **;
*=====================================================================;
*--------------------------------------------;
  ** WRITE OUT TRANSIT LINE BATCHIN FILE **;
*--------------------------------------------;
data segout; set routes verify;
    proc sort; by linename order;
data segout; set segout; by linename;
    if last.linename then end = 1;
    else end = 0;

data out1; set segout; by linename;
    length desc $22 dwell $4 d $9;
    layov = lag1(layover);
    if dwcode = 1 then dwell = '0';
    else dwell = '0.01';
    if descr ^= ' ' then layov = 0;
    name = "'" || compress(linename) || "'";
    desc = "'" || descr || "'";
    ltime = round(ltime, 0.1);
    if dwcode = 1 then d = compress('dwt=#' || dwell);
    else if dwcode = 2 then d = compress('dwt=>' || dwell);
    else if dwcode = 3 then d = compress('dwt=<' || dwell);
    else if dwcode = 4 then d = compress('dwt=+' || dwell);
    else if dwcode = 5 then d = compress('dwt=*' || dwell);
    else d = compress('dwt=' || dwell);
    tf = compress('ttf=' || ttf);
    us1 = compress('us1=' || ltime);
    us2 = compress('us2=' || zfare);

data out1; set out1;
    file out1;
    if _n_ = 1 then do;
        put "c BUS TRANSIT BATCHIN FILE FOR SCENARIO &scen TOD &tod" /
            "c &sysdate" /
            "c us1 holds segment travel time, us2 holds zone fare" /
            "t lines";
    end;
    if descr ^= ' ' then do;
        put 'a' +1 name +2 mode +2 vehtype +2 headway +2 speed +2 desc /
            +2 'path=no';
    end;
    else if end = 1 then do;
        put +4 d +(10-length(left(trim(d)))) itina +(7-length(left(trim(itina)))) tf +2 us1 +(6-length(left(trim(ltime)))) us2 /
            +4 'dwt=0.01' +3 itinb +(7-length(left(trim(itinb)))) 'lay=' +0 layover;
    end;
    else if layov > 0 then do;
        put +4 d +(10-length(left(trim(d)))) itina +(7-length(left(trim(itina)))) tf +2 us1 +(6-length(left(trim(ltime)))) us2 +2 'lay=' +0 layov;
    end;
    else do;
        put +4 d +(10-length(left(trim(d)))) itina +(7-length(left(trim(itina)))) tf +2 us1 +(6-length(left(trim(ltime)))) us2;
    end;


*----------------------------------;
  ** FORMAT LINKS FOR BATCHOUT **;
*----------------------------------;
data keeplnk(drop=modes mode); merge links all(in=hit1) walkcbd(in=hit2); by itina itinb;
    if hit1 or hit2;
    md = compress(modes || mode);

*----------------------------------;
  ** FORMAT NODES FOR BATCHOUT **;
*----------------------------------;
data kplnk(keep=itina); set keeplnk;
    output;
    itina = itinb;
    output;
    proc sort nodupkey; by itina;
data allnd; merge kplnk(in=hit) nodes; by itina;
    if hit;
    flag = 'a ';
data centroid; set nodes(where=(itina <= &maxzone));
    flag = 'a*';
data allnd; set allnd centroid;
    proc sort; by itina;
data parking; set nodes(where=(pspac > 0));
    flag='a ';
    proc sort; by itina;
data allnd; merge allnd parking; by itina;
    proc sort; by itina;

*-------------------------------------------;
  ** WRITE OUT BUS NETWORK BATCHIN FILE **;
*-------------------------------------------;
data print2; set allnd;
    file out2;
    if _n_ = 1 then do;
        put "c BUS NETWORK BATCHIN FILE FOR TRANSIT SCENARIO NETWORK &scen TOD &tod" /
            "c  &sysdate" /  'c a  node  x  y' / 't nodes';
    end;
    put flag +2 itina +2 x_a +2 y_a;

data print2; set keeplnk;
    file out2 mod;
    if _n_ = 1 then do;
        put / 'c a,i-node,j-node,length,modes,type,lanes,vdf' / 't links';
    end;
    put 'a' +3 itina +2 itinb +2 miles +2 md +2 '1' +2 thruln +2 vdf;

* - - - - - - - - - - - - - - - - - - - - - - - - - - *;
** VERIFY THAT ALL ATTRIBUTES ON LINK USED MORE THAN ONCE ARE SAME **;
data check; set keeplnk;
    proc summary nway; class itina itinb thruln vdf md;
        output out=junk;
data junk; set junk;
    if _freq_ > 1;
proc print; var itina itinb _freq_; title "NETWORK &scen - SAME LINK USED WITH DIFFERENT ATTRIBUTES";

** VERIFY THAT EACH LINK HAS A TYPE **;
data check; set keeplnk(where=(vdf = 0));
    proc print; var itina itinb vdf; title "NETWORK &scen LINKS WITHOUT A CODED TYPE";

** VERIFY THAT EACH LINK HAS LANES **;
data check; set keeplnk(where=(thruln = 0));
proc print; var itina itinb thruln; title "NETWORK &scen LINKS WITHOUT CODED LANES";

** VERIFY THAT EACH LINK HAS A LENGTH **;
data check; set keeplnk(where=(miles = 0));
proc print; var itina itinb miles; title "NETWORK &scen LINKS WITHOUT A CODED LENGTH";
* - - - - - - - - - - - - - - - - - - - - - - - - - - *;

*--------------------------------------------;
  ** WRITE OUT NODE EXTRA ATTRIBUTE FILE **;
*--------------------------------------------;
data print3; set allnd;
    file nod;
    if _n_ = 1 then do;
        put "c BASE NETWORK NODE EXTRA ATTRIBUTE FILE FOR TRANSIT SCENARIO NETWORK &scen TOD &tod" /
            "c  &sysdate" /  'c node  @atype @zone @pspac @pcost' /
            'c ***  @atype=area type for on-street parking  ***' ;
    end;
    put itina +2 atype +2 zone +2 pspac +2 pcost;


*=====================================================================;
  **  CREATE ARC FILE OF BUS NODES (STOPS ONLY).                  **;
  **  THIS WILL BE USED TO GENERATE A POINT COVERAGE FOR USE IN   **;
  **  CREATING THE BUS-RAIL LINKS (MODES c and m).                **;
*=====================================================================;
proc sort data=verify; by linename order;
data allstops; set verify; by linename;
    output;
    **Include beginning of each itinerary**;
    if first.linename then do;
        itinb = itina;
        dwcode = 0;
        output;
    end;
proc sort data=allstops; by itinb dwcode;

/** -- All Bus Stops -- **/
data stops; set allstops; by itinb dwcode;
    if first.itinb then output;
data stops(keep=itinb); set stops(where=(dwcode ^= 1));
data stops; merge stops (in=hit) bnode; by itinb;
    if hit;

data bustop; set stops end=eof;
    file out3 dsd;
    put itinb x_b y_b;
    if eof = 1 then do;
        put 'END';
    end;

/** -- Stops on Modes BE -- **/
data ctabus; set allstops(where=((mode ? 'B' or mode ? 'E') and dwcode ^= 1));
data ctabus(keep=itinb); set ctabus; by itinb;
    if first.itinb then output;
data ctabus; merge ctabus (in=hit) bnode; by itinb;
    if hit;

data ctabus; set ctabus end=eof;
    file out4 dsd;
    put itinb x_b y_b;
    if eof = 1 then do;
        put 'END';
    end;

/** -- Stops on Modes PLQ -- **/
data pacebus; set allstops(where=((mode ? 'P' or mode ? 'L' or mode ? 'Q') and dwcode ^= 1));
data pacebus; set pacebus; by itinb;
    if first.itinb then output;
data pacebus; merge pacebus (in=hit) bnode; by itinb;
    if hit;

data pacebus; set pacebus end=eof;
    file out5 dsd;
    put itinb x_b y_b;
    if eof = 1 then do;
        put 'END';
    end;


*=====================================================================;
  ** WRITE BUS TOD VMT FILE  **;
*=====================================================================;
%macro buslink;
    %if &tod <= 8 %then %do;  ** skip for AM TOD;
        *** calculate average number of buses per route on link for time period ***;
        data temp; set verify;
            *** Set Total Minutes for time period ***;
            if &tod = 1 then minutes = 600;
            else if &tod = 2 or &tod = 4 then minutes = 60;
            else if &tod = 5 then minutes = 240;
            else minutes = 120;
            buses = round(minutes / headway, 0.1);
            tod = &tod;
            proc summary nway; class tod itina itinb; var buses;
                output out=bus sum=;

        data print; set bus;
            %if &tod = 1 %then %do;
                file bus dsd;
                if _n_ = 1 then put "tod,i,j,buses";
            %end;
            %else %do;
                file bus dsd mod;
            %end;
            put tod itina itinb buses;
    %end;
%mend buslink;
%buslink
run;

*=====================================================================;
  ** TOD NETWORK SUMMARY  **;
*=====================================================================;
proc summary nway data=allnd;
    output out=nd;
data nd(rename=(_freq_=nodes)); set nd;
    keep _freq_;

data keeplnk; set keeplnk;
    lnmi = thruln * miles;
    proc summary nway; var miles lnmi;
        output out=lnk sum=;
data lnk(rename=(_freq_ = links)); set lnk;
    keep _freq_ miles lnmi;

data l(keep=itina itinb miles); set links;
proc sort data=verify; by itina itinb;
data vmt; merge verify(in=hit) l; by itina itinb;
    if hit;
    proc summary nway; var miles;
        output out=bvmt sum=busvmt;
data bvmt(rename=(_freq_=seg)); set bvmt;
    keep _freq_ busvmt;
data last; merge nd lnk bvmt;
    label links='Directional Links'
          miles='Link Miles'
          lnmi='Lane Miles'
          nodes='Network Nodes'
          seg='Itinerary Segments'
          busvmt='Bus VMT';
    proc print label noobs; var nodes links miles lnmi seg busvmt;
        format nodes links seg comma6. miles lnmi busvmt comma9.2; title " ";
        title2 "SCENARIO &scen TOD &tod BUS TRANSIT NETWORK EMME SUMMARY for MODES BEPLQb";

proc printto;  *** return output to original location;
run;
