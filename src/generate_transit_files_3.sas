/*
    generate_transit_files_3.sas
    authors: cheither & npeterson
    revised: 2/23/16
    ----------------------------------------------------------------------------
    Program creates batchin file of mode c, m, u, v, w, x, y and z links.

*/
options pagesize=50 linesize=125;

%let dirpath = %scan(&sysparm, 1, $);   ** directory path;
%let scen = %scan(&sysparm, 2, $);      ** transit scenario number;
%let zonecbdl = %scan(&sysparm, 3, $);  ** Zone17 CBD start zone;
%let zonecbdh = %scan(&sysparm, 4, $);  ** Zone17 CBD end zone;
%let zonecnta = %scan(&sysparm, 5, $);   ** Zone17 central area end zone;
%let zonechi = %scan(&sysparm, 6, $);  ** Zone17 chi end zone;
%let tod = %scan(&sysparm, 7, $);       ** time of day;

/* ------------------------------------------------------------------------------ */
** INPUT FILES **;
filename in1 "&dirpath.\cbddist.txt";
filename in2a "&dirpath.\metracta.txt";
filename in2b "&dirpath.\metrapace.txt";
filename in3 "&dirpath.\ctadist.txt";
filename in4 "&dirpath.\busz.txt";
filename in5 "&dirpath.\busz2.txt";
filename in15 "&dirpath.\busz3.txt";
filename in6 "&dirpath.\itin.final";
filename in7 "&dirpath.\ctaz.txt";
filename in8 "&dirpath.\ctaz2.txt";
filename in9 "&dirpath.\c1z.txt";
filename in10 "&dirpath.\c2z.txt";
filename in11 "&dirpath.\metraz.txt";
filename in16 "&dirpath.\metraz2.txt";
filename in17 "&dirpath.\metraz3.txt";
filename in12 "&dirpath.\mz.txt";
filename in13 "&dirpath.\buscentroids.txt";
filename in14 "&dirpath.\railaccess.txt";

** OUTPUT FILES **;
filename out1 "&dirpath.\access.network_&tod";
/* ------------------------------------------------------------------------------ */

/*======================================*/
/*  1. CREATE LINKS FOR c & m           */
/*======================================*/

 ** READ IN CTA STOP FILES **;
data cbd; infile in1 dlm=',' missover;
    input anode bnode dist;

data cta; infile in3 dlm=',' missover;
    input anode bnode dist;

data allcta; set cta cbd;
    itina = anode;
    proc sort; by itina;

data allcta2; set allcta;
    itinb = anode;
    proc sort; by itinb;

** READ IN BUS ITINERARY FILE **;
data itin; infile in6 dlm=',' missover;
    input linename $ itina itinb order layover dwcode;
    proc sort; by itina;

** MERGE ITINERARY AND CTA STOP FILE **;
data a; set itin;
    proc sql noprint;
        create table stop1 as
        select itin.itina, linename, dwcode, allcta.anode, bnode, dist
        from itin, allcta
        where itin.itina=allcta.itina;

data b; set itin;
    proc sql noprint;
        create table stop2 as
        select itin.itinb, linename, dwcode, allcta2.anode, bnode, dist
        from itin, allcta2
        where itin.itinb=allcta2.itinb;

** ELIMINATE NON-STOPS **;
data stop2; set stop2;
    if dwcode ^= 1;

data stops(drop=itina itinb dwcode); set stop1 stop2;
    proc sort; by bnode linename dist;

** KEEP SHORTEST LINK TO EACH BUS ROUTE FROM CTA RAIL STATIONS **;
data stops; set stops; by bnode linename dist;
    if first.linename then output;
    proc sort; by anode bnode;

** ELIMINATE REDUNDANT LINKS **;
data stops(drop=linename); set stops; by anode bnode;
    if first.bnode;
    mode = 'c';

*-------------------------------;
 ** READ IN METRA STOP FILES **;
*-------------------------------;
data metra1; infile in2a dlm=',' missover;
    input anode bnode dist;
    mode = 'm';

data metra2; infile in2b dlm=',' missover;
    input anode bnode dist;
    mode = 'm';

data combine(drop=dist); set stops metra1 metra2;
    miles = round(dist / 5280, 0.01);
    flag = 'a=';
    proc sort; by anode bnode;

data combine; set combine; by anode bnode;
    if first.bnode then output;


/*==============================================*/
/*  2. CREATE LINKS FOR u,v,w,x,y & z           */
/*==============================================*/

/* -------- u & x -------- */
*--------------------------------------;
 ** READ IN BUS STOP DISTANCE FILES **;
*--------------------------------------;
/* Within CBD */
data bus(drop=dist); infile in4 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);

/* In Chicago Remainder*/
data bus2(drop=dist); infile in5 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);

/* Outside Chicago */
data bus3(drop=dist); infile in15 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);

data bus; set bus bus2 bus3;
    proc sort; by stop;

*---------------------------------;
 ** READ IN BUS ITINERARY FILE **;
*---------------------------------;
data itin; infile in6 dlm=',' missover;
    input linename $ itina itinb order layover dwcode;
    proc sort; by linename order;

data itin; set itin; by linename order;
    if first.linename then mark = 1;

data itinnode (keep=linename stop layover dwcode mark); set itin;
    if mark = 1 then do;
        stop = itina;
        output;
        stop = itinb;
        mark = '.';
        output;
    end;
    else do;
        stop = itinb;
        output;
    end;

data itinnode; set itinnode;
    if mark = 1 then do;
        layover = 0;
        dwcode = 0;
    end;

/* GIVE DIRECTIONS (INBOUND/OUTBOUND) TO LINE SEGMENTS */
/* INBOUND STOPS ARE BEFORE LAYOVER IN ITINERARY, OUTBOUND AFTER */
data inout; set itinnode;
    retain x 0;
    output;
    if mark = 1 then x = 0;
    x + layover;

/* COMPLETE UN-EDITED ITINERARY */
data inout(drop=mark); set inout;
    if mark = 1 then x = 0;
    if x > 0 then x = 1;

/* ELIMINATE NON-STOPS FROM ITINERARY */
data stops; set inout;
    if dwcode = 1 then delete;
    proc sort; by linename stop x;

/* REMOVE DUPLICATE STOPS BY LINE AND DIRECTION */
data stops; set stops; by linename stop x;
    if first.x then output;

/* ATTACH ACCESS LINKS TO ITINERARY */
/* SQL ENSURES MULTIPLE OCCURRENCES CAPTURED */
proc sql noprint;
    create table totitin as
    select stops.stop, linename, x, bus.centroid, miles
    from stops, bus
    where stops.stop=bus.stop
    order by 2,1;

data final1; set totitin;

/* CHECK IF ITINERARY SAME IN BOTH DIRECTIONS */
/* DIRECTION 1 */
data dir1; set inout;
    if x = 0;
    group = lag1(linename);

data dir1; set dir1;
    retain ord 1;
    ord + 1;
    if linename ^= group then ord = 1;
    output;
    proc sort; by linename ord;

/* ELIMINATE LAYOVER STOPS */
data dir1; set dir1; by linename ord;
    if last.linename then delete;

/* DIRECTION 2 */
data dir2; set inout;
    if x = 1;
    group = lag1(linename);

data dir2; set dir2;
    retain ord 1;
    ord + 1;
    if linename ^= group then ord = 1;
    output;
    proc sort; by linename ord;

/* RE-ORDER DIRECTION 2 IN REVERSE ORDER */
data dir2(drop=group); set dir2;
    proc sort; by linename descending ord;

data dir2(drop=ord dwcode stop); set dir2;
    group = lag1(linename);
    dwcode2 = dwcode;
    stop2 = stop;

data dir2; set dir2;
    retain ord 1;
    ord + 1;
    if linename ^= group then ord = 1;
    output;
    proc sort; by linename ord;

/* MERGE DIRECTIONS 1 AND  2 */
/* ELIMINATE LINES WITH SAME ITINERARY IN BOTH DIRECTIONS */
data itinchek; merge dir1 dir2; by linename ord;
    if stop = stop2 and dwcode = dwcode2 then delete;
    if stop2 = '.' then delete;

/* SUMMARIZE LINES WITH A DIFFERENT ITINERARY IN DIRECTION 2 */
proc summary nway; by linename; output out=dir2diff;

/* KEEP ACCESS LINKS FOR LINES WITH A DIFFERENT ITINERARY IN DIRECTION 2 */
data final2(drop=_type_ _freq_); merge final1 dir2diff(in=hit); by linename;
    if x = 1 and hit = 0 then delete;

/* ELIMINATE REDUNDANCIES */
proc summary nway; var miles; class stop centroid; output out=finlist mean=;

/* toleary 2-21-2024: new method to access/egress: no limit to # links within distance*/
/* negate below */

/* ORDER ACCESS LINKS BY CENTROID BY MILES */
proc sort data=finlist; by centroid miles;

data finlist (drop=_type_ _freq_); set finlist;
    match = lag1(centroid);

data finlist; set finlist;
    retain ord 1;
    ord + 1;
    if centroid ^= match then ord = 1;
    output; 

/* toleary: old method listed below. kept distance, removed ord */ 
/* FOLLOWING USES MARY LUPA'S LOGIC TO LIMIT NUMBER OF ACCESS LINKS PER ZONE */
/* MODE x - IN CBD MAX. OF 8 PER ZONE, OUTSIDE CBD MAX. OF 2 PER ZONE */
/* data corex extrax; set finlist;
    mode = 'x';
    if miles > 0.55 then output extrax;
    else if centroid in (&zone1:&zone2) and ord > 8 then output extrax;
    else if centroid not in (&zone1:&zone2) and ord > 2 then output extrax;
    else output corex; */

/* Limit links based on distance and geography */
data corex extrax; set finlist;
    mode = 'x';
    if miles > 0.75 then output extrax;                                            ** outside chicago, limit is 0.75 mi;
    else if miles > 0.25 and centroid in (&zonecbdl:&zonecbdh) then output extrax; ** within chicago cbd, limit is 0.25 mi;
    else if miles > 0.55 and centroid in (&zonecbdh:&zonechi) then output extrax;  ** within chicago outside cbd, limit is 0.55 mi;
    else output corex;    

/* toleary: old method listed below. removed ord, treats modes x and u the same */
/* FOLLOWING USES MARY LUPA'S LOGIC TO LIMIT NUMBER OF ACCESS LINKS PER ZONE */
/* MODE u - MAXIMUM OF 3 PER ZONE */
data coreu extrau; set finlist;
    mode = 'u';
    /* if miles > 0.55 then output extrau;
    else if ord > 3 then output extrau;
    else output coreu; */

    if miles > 0.75 then output extrau;                                           ** outside chicago, limit is 0.75 mi;
    else if miles > 0.25 and centroid in (&zonecbdl:&zonecbdh) then output extrau;** within chicago cbd, limit is 0.25 mi;
    else if miles > 0.55 and centroid in (&zonecbdh:&zonechi) then output extrau; ** within chicago outside cbd, limit is 0.55 mi;
    else output coreu;    

/* ADD EXTRA u/x LINKS TO ENSURE ROUTES HAVE ACCESS TO ALL ZONES THEY STOP IN */
data zndist (drop=dist); infile in13 dlm=',' missover;
    input stop centroid dist;
    proc sort; by stop;

proc sort data=stops; by stop;
data stopzn (keep=linename stop centroid); merge stops (in=hit) zndist; by stop;
    if hit;  ** Only keep actual stops (dwtime > 0);
    proc sort; by stop centroid;
    
* Identify all stops by line without access and egress to centroid via core u/x links;
proc sort data=corex; by stop centroid;
proc sort data=coreu; by stop centroid;

data accegr (keep=linename stop centroid flag); merge stopzn (in=hit1) coreu (in=hit2) corex (in=hit3); by stop centroid;
    if hit1;
    flag = min(hit2, hit3);

proc means noprint data=accegr; var flag; class linename centroid; output out=noacc max=;
data noacc (keep=linename centroid); set noacc;
    if flag = 0 and centroid > 0 and linename ^= ' ';
    proc sort; by linename centroid;

* Create list of stops (by route) within zones which do not have both access and egress;
proc sort data=accegr; by linename centroid;
data needlink; merge accegr noacc (in=hit); by linename centroid;
    if hit;
    proc sort; by stop centroid;

* Prepare all potential extra links;
data allextra (drop=mode); set extrau extrax;
    proc sort nodupkey; by stop centroid;

* Merge with extra links, sort by ascending length by linename-centroid & keep shortest link; 
data needlink; merge needlink (in=hit) allextra; by stop centroid;
    if hit;
    proc sort; by linename centroid miles;
data needlink; set needlink; by linename centroid miles;
    if first.centroid;
  
* Add needlink to corex and coreu;
data finlistx (keep=stop centroid miles mode); set corex needlink;
    mode = 'x';
    if 0.55 < miles <= 1.25 then miles = 0.75;
    else if miles > 1.25 then miles = 0.75;
    *needlinks that are cbd will be set at 0.25 mi, and 0.55 mi otherwise;
    else if miles = '.' and centroid in (&zonecbdl:&zonecbdh) then miles = 0.25;
    else if miles = '.' and centroid > &zonecbdh then miles = 0.55;
    proc sort nodupkey; by stop centroid;
           
data finlistu (keep=stop centroid miles mode); set coreu needlink;
    mode = 'u';
    if 0.55 < miles <= 1.25 then miles = 0.75;
    else if miles > 1.25 then miles = 0.75;
    *needlinks that are cbd will be set at 0.25 mi, and 0.55 mi otherwise;
    else if miles = '.' and centroid in (&zonecbdl:&zonecbdh) then miles = 0.25;
    else if miles = '.' and centroid > &zonecbdh then miles = 0.55;
    proc sort nodupkey; by stop centroid;

* Verify every bus line has access to centroids of all stop zones;
data ckaccegr; merge stopzn finlistu (in=hitu) finlistx (in=hitx); by stop centroid;
    if hitu then acc = 1;
    else acc = 0;
    if hitx then egr = 1;
    else egr = 0;
proc means noprint data=ckaccegr; var acc egr; class linename centroid; output out=ckacceg2 max=;
data ckacceg2; set ckacceg2;
    if centroid > 0 and linename ^= ' ' and (acc = 0 or egr = 0);
    proc print noobs; var linename centroid acc egr;
    title "BUS LINES MISSING ZONE ACCESS/EGRESS LINKS";

* Switch directionality of u links to reflect access, not egress;
data finlistu (drop=t); set finlistu;
    t = stop; stop = centroid; centroid = t;  ** Reverse direction;


/* -------- v & y -------- */
*-------------------------------------------;
 ** READ IN CTA RAIL STOP DISTANCE FILES **;
*-------------------------------------------;
data cta1(drop=dist); infile in7 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);

data cta2(drop=dist); infile in8 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);

data cta1; set cta1 cta2;
    proc sort; by stop centroid;

*----------------------------------;
 ** READ IN CTA RAIL-ZONE FILES **;
*----------------------------------;
data czone1; infile in9 dlm=',' missover;
    input stop centroid;

data czone2; infile in10 dlm=',' missover;
    input stop centroid;

data czone; set czone1 czone2;
    need = 1;
    proc sort; by stop centroid;

*---------------------------;
 ** MERGE CTA RAIL FILES **;
*---------------------------;
data cta1; merge czone cta1; by stop centroid;
    if centroid > 0;
    /*MAKE SURE EACH STATION CONNECTS TO ZONE IT IS IN */
    if miles = '.' then miles = 0.55;
    proc sort; by centroid miles;

/* SEPARATE ACCESS LINKS INTO TWO DATASETS: ONE LINKING
   STATION TO ZONE IT RESIDES IN (FORCE), ONE FOR ALL ELSE */
data force ctarail; set cta1;
    if need = 1 then output force;
    else output ctarail;

data force(drop=t); set force;
    mode = 'y';
    output;
    mode = 'v';
    t = stop; stop = centroid; centroid = t;  ** Reverse direction;
    output;

/* ORDER ACCESS LINKS BY CENTROID BY MILES */
data ctarail; set ctarail;
    match = lag1(centroid);

data ctarail; set ctarail;
    retain ord 1;
    ord + 1;
    if centroid ^= match then ord = 1;
    output;

/* toleary -- old method commented out below. removed ord, used distance*/
/* FOLLOWING USES MARY LUPA'S LOGIC TO LIMIT NUMBER OF ACCESS LINKS PER ZONE */
/* MODE y - IN CBD MAX. OF 6 PER ZONE, OUTSIDE CBD MAX. OF 2 PER ZONE */
/* THESE LINKS WILL BE ADDED TO THOSE IN DATASET FORCE. */
/* data ctay(drop=match ord); set ctarail;
    if &zone1 <= centroid <= &zone2 and ord > 6 then delete;
    if centroid < &zone1 and ord > 2 then delete;
    if centroid > &zone2 and ord > 2 then delete;
    mode = 'y'; */
data ctay(drop=match ord); set ctarail;
    if centroid in (&zonecbdl:&zonecnta) and miles > 0.55 then delete;
    if centroid > &zonecnta and miles > 1.5 then delete;
    mode = 'y';

/* FOLLOWING USES MARY LUPA'S LOGIC TO LIMIT NUMBER OF ACCESS LINKS PER ZONE */
/* MODE v - MAXIMUM OF 2 PER ZONE */
/* THESE LINKS WILL BE ADDED TO THOSE IN DATASET FORCE. */
/* data ctav(drop=match ord t); set ctarail;
    if ord > 2 then delete;
    mode = 'v';
    t = stop; stop = centroid; centroid = t;  ** Reverse direction;
    output; */
data ctav(drop=match ord t); set ctarail;
    if &zonecbdl <= centroid <= &zonecnta and miles > 0.55 then delete;
    if centroid > &zonecnta and miles > 1.5 then delete;
    mode = 'v';
    t = stop; stop = centroid; centroid = t; ** Reverse direction;
    output;


/* -------- w & z -------- */
*---------------------------------------;
 ** READ IN METRA STOP DISTANCE FILE **;
*---------------------------------------;
*for central area;
data metra1(drop=dist); infile in11 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);
    proc sort; by stop centroid;
        
*outside central area, still in chicago;
data metra2(drop=dist); infile in16 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);
    proc sort; by stop centroid;

*outside chicago;
data metra3(drop=dist); infile in17 dlm=',' missover;
    input stop centroid dist;
    miles = round(dist / 5280, 0.01);
    proc sort; by stop centroid;

        
*------------------------------;
 ** READ IN METRA-ZONE FILE **;
*------------------------------;
data mzone; infile in12 dlm=',' missover;
    input stop centroid;
    proc sort; by stop centroid;


*------------------------;
 ** MERGE METRA FILES **;
*------------------------;
*toleary 3/20/2024: trying something else here;
*this one is just central area;
data metra1; merge mzone metra1; by stop centroid;
    if centroid > 0;
    if miles = '.' then miles = 0.55;
    if centroid > &zonecnta then delete;
    if centroid <= &zonecnta and miles > 1.2 then delete;
    output;

*this one is non-central area chicago;
data metra2; merge mzone metra2; by stop centroid;
    if centroid > 0;
    if miles = '.' then miles = 0.55;
    if centroid <= &zonecnta then delete;
    if centroid > &zonechi then delete;
    if miles > 3 then delete;
    output;

*this one is outside chicago only;
data metra3; merge mzone metra3; by stop centroid;
    if centroid > 0;
    if miles = '.' then miles = 0.55;
    if centroid <= &zonechi then delete;
    if miles > 15 then delete;
    output;

*then merge together;        
data metra; set metra1 metra2 metra3;
    proc sort; by stop centroid;

/* data metra1(drop=t); merge mzone metra1; by stop centroid;
    if centroid > 0;
    *MAKE SURE EACH STATION CONNECTS TO ZONE IT IS IN;
    if miles = '.' then miles = 0.55;
    if &zonecbdl <= centroid <= &zonecnta and miles > 1.2 then delete;
    if &zonecnta < centroid <= &zonechi and miles > 3 then delete;
    if centroid > &zonechi and miles > 15 then delete; */

*toleary 2024-03-27: test #2 which changes metra over 1.2 miles from modes w/z to f/g;
data metra(drop=t); set metra; 
    if miles <= 1.2 then mode = 'z';
    else if miles > 1.2 then mode = 'g';
    output;
    if miles <= 1.2 then mode = 'w';
    else if miles > 1.2 then mode = 'f';
    t = stop; stop = centroid; centroid = t; ** reverse direction;
    output;

/*==============================================*/
/*  3. COMBINE ALL, WRITE OUT BATCHIN FILE      */
/*==============================================*/
data access(drop=stop centroid); set finlistu finlistx force ctay ctav metra;
    anode = stop;
    bnode = centroid;
    flag = 'a ';

data all; set access combine;
    proc sort; by anode bnode;

data c(drop=mode); set all;
    if mode = 'c';
    mode1 = mode;

data m(drop=mode); set all;
    if mode = 'm';
    mode2 = mode;

data u(drop=mode); set all;
    if mode = 'u';
    mode3 = mode;

data v(drop=mode); set all;
    if mode = 'v';
    mode4 = mode;

data w(drop=mode); set all;
    if mode = 'w';
    mode5 = mode;

data x(drop=mode); set all;
    if mode = 'x';
    mode6 = mode;

data y(drop=mode); set all;
    if mode = 'y';
    mode7 = mode;

data z(drop=mode); set all;
    if mode = 'z';
    mode8 = mode;

data f(drop=mode); set all;
    if mode = 'f';
    mode9 = mode;

data g(drop=mode); set all;
    if mode = 'g';
    mode10 = mode;

data all; merge c m u v w x y z f g; by anode bnode;
    modes = compress(mode1 || mode2 || mode3 || mode4 || mode5 || mode6 || mode7 || mode8 || mode9 || mode10);
    if miles = 0 then miles = 0.01;

** Filter out access links already in rail.network_{tod};   
data railacc; infile in14 dlm=',' missover;
    input anode bnode accmode $;
    proc sort; by anode bnode;
    
data all(drop=accmode); merge all (in=hit1) railacc (in=hit2); by anode bnode;
    if hit1 and not hit2;

*craig's rec to add a final thing that gets rid of duplicate access/egress links;
proc sort data=all nodupkey; 
    by anode bnode;

** Write final output;
data print1; set all;
    file out1;
    if _n_ = 1 then do;
        put "c BASE NETWORK LINK BATCHIN FILE FOR TRANSIT SCENARIO NETWORK &scen TOD &tod" /
            "c ACCESS LINKS  (modes c,m,u,v,w,x,y,z)" /
            "c  &sysdate" / 'c a,i-node,j-node,length,modes,type,lanes,vdf' / 't links';
    end;
    put flag +3 anode +2 bnode +2 miles +2 modes +2 '1' +2 '0' +2 '1';

run;
