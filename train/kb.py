#!/usr/bin/env python3
"""What the BASIC helper knows: one entry per answer.

Every entry has
    id      a short name
    kind    cmd | err | idea | how | prog | talk
    want    what the child wants to know (English; given to the question writers)
    a       the answer, as the PRIMO prints it
    kw      BASIC words or messages the entry explains (questions about them are generated)
    direct  [(statement, text expected on the screen)]   checked on the emulated PRIMO
    prog    (inputs typed after RUN, [texts expected], [(x, y) points expected lit])
            for answers that are a program; the program is the answer itself

An answer may take a number from the question (the program fills it in by rule, see
number() and expression() below; the network only chooses the answer):
    {N:10}   the largest number in the question, or 10 if there is none
    {X:1+2}  the sum typed in the question, or 1+2
    [ ... ]  printed only if the question has a number

All of it is checked by tools/kbcheck.py, which types the statements and programs into the
PRIMO's BASIC in the emulator: nothing here is taught unless the PRIMO really does it.
Strings in the examples are in lower case because that is what the PRIMO's keyboard types
without SHIFT (BASIC words may be typed in lower case too; LIST shows them in capitals).
"""

import re

KB = []


def K(id, kind, want, a, kw=(), direct=(), prog=None, wait=300):
    KB.append(dict(id=id, kind=kind, want=want, a=a, kw=list(kw), direct=list(direct), prog=prog,
                   wait=wait))


# ---- statements ---------------------------------------------------------------------------
K("print", "cmd", "how to write/show text on the screen; what PRINT does",
  'A PRINT kiír a képernyőre. Például: PRINT "szia"', ["PRINT"], [('PRINT "szia"', "szia")])
K("calc", "cmd", "how to calculate with the computer, use it as a calculator, add/multiply numbers",
  "A PRINT számol is. Például: PRINT 2+3*4", [], [("PRINT 2+3*4", " 14")])
K("calc_x", "cmd", "how much an arithmetic expression typed with digits is, e.g. 'mennyi 12*7'",
  "Írd be: PRINT {X:12*7}", [], [("PRINT 12*7", " 84")])
K("qmark", "cmd", "what the question mark does in BASIC / a shorter way to write PRINT",
  'A ? a PRINT rövidítése. Például: ? "szia"', ["?"], [('? "szia"', "szia")])
K("input", "cmd", "how the program can ask the user for a number or text; what INPUT does",
  'Az INPUT bekér valamit. Például: 10 INPUT "neved";N$', ["INPUT"])
K("let", "cmd", "what LET does",
  "A LET értéket ad a változónak, de el is hagyható: LET A=5 ugyanaz, mint A=5", ["LET"],
  [("LET A=5:PRINT A", " 5")])
K("assign", "how", "how to put a value into a variable / store a number",
  'Változónak így adsz értéket: A=5 vagy N$="primo"', [], [('A=5:N$="primo":PRINT A;N$', " 5 primo")])
K("if", "cmd", "how to make a decision / check a condition; what IF does",
  'Az IF feltételt vizsgál. Például: IF A>5 THEN PRINT "nagy"', ["IF"],
  [('A=7:IF A>5 THEN PRINT "nagy"', "nagy")])
K("then", "cmd", "what THEN means",
  "A THEN után áll, amit a gép akkor csinál, ha az IF feltétele igaz.", ["THEN"])
K("else", "cmd", "what ELSE means; how to do something when the condition is false",
  'Az ELSE után áll, ami akkor történik, ha a feltétel nem igaz. Például: IF A>5 THEN PRINT "nagy" ELSE PRINT "kicsi"',
  ["ELSE"], [('A=1:IF A>5 THEN PRINT "nagy" ELSE PRINT "kicsi"', "kicsi")])
K("for", "cmd", "how to repeat something several times; what FOR does; how to make a loop",
  "A FOR és a NEXT közötti rész ismétlődik. Például: 10 FOR I=1 TO 5:PRINT I:NEXT I", ["FOR"])
K("next", "cmd", "what NEXT does",
  "A NEXT a FOR ciklus vége: innen ugrik vissza a gép a ciklus elejére.", ["NEXT"])
K("to", "cmd", "what TO means in a FOR loop",
  "A TO a FOR ciklusban azt mondja meg, meddig számoljon. Például: FOR I=1 TO 10", ["TO"])
K("step", "cmd", "how to count by twos or backwards in a loop; what STEP does",
  "A STEP a ciklus lépése. Például: FOR I=10 TO 1 STEP -1 visszafelé számol.", ["STEP"])
K("goto", "cmd", "how to jump to another line; what GOTO does",
  "A GOTO a megadott sorra ugrik. Például: 30 GOTO 10", ["GOTO"])
K("gosub", "cmd", "how to call a subroutine; what GOSUB does",
  "A GOSUB szubrutint hív, a RETURN visszatér belőle. Például: 10 GOSUB 100", ["GOSUB"])
K("return", "cmd", "what RETURN does",
  "A RETURN a szubrutin vége: visszatér oda, ahonnan a GOSUB hívta.", ["RETURN"])
K("rem", "cmd", "how to write a comment or note into the program; what REM does",
  "A REM megjegyzés, a gép átugorja. Például: 10 REM ez az első programom", ["REM"])
K("end", "cmd", "how to finish the program; what END does",
  "Az END befejezi a programot.", ["END"])
K("stop", "cmd", "what STOP does; how to pause the program from inside",
  "A STOP megállítja a programot. A CONT paranccsal folytathatod.", ["STOP"])
K("cont", "cmd", "how to continue a stopped program; what CONT does",
  "A CONT folytatja a megállított programot.", ["CONT"])
K("dim", "cmd", "how to make an array / store many numbers; what DIM does",
  "A DIM tömböt készít. Például: DIM T(10) után T(3)=7", ["DIM"],
  [("DIM T(10):T(3)=7:PRINT T(3)", " 7")])
K("data", "cmd", "how to keep a list of numbers inside the program; what DATA does",
  "A DATA sorban adatok állnak, a READ olvassa be őket. Például: 20 DATA 3,4", ["DATA"])
K("read", "cmd", "what READ does",
  "A READ a DATA sorok adatait olvassa be. Például: 10 READ A,B", ["READ"])
K("restore", "cmd", "how to read the DATA again from the beginning; what RESTORE does",
  "A RESTORE után a READ megint az első DATA adattól olvas.", ["RESTORE"])
K("cls", "cmd", "how to clear / erase the screen; what CLS does",
  "A CLS letörli a képernyőt.", ["CLS"], [("CLS", None)])
K("run", "cmd", "how to start the program; what RUN does",
  "A RUN elindítja a programot.", ["RUN"])
K("list", "cmd", "how to see the program that is in the memory; what LIST does",
  "A LIST kiírja a programot. Tarts lenyomva egy gombot, amíg megy! Egy része: LIST 10-50", ["LIST"])
K("new", "cmd", "how to delete the whole program and start a new one; what NEW does",
  "A NEW kitörli a programot a memóriából.", ["NEW"])
K("delete", "cmd", "how to delete one line or several lines of the program; what DELETE does",
  "Egy sort úgy törölsz, hogy csak a számát írod be. Több sor: DELETE 10-50", ["DELETE"])
K("auto", "cmd", "how to get line numbers automatically; what AUTO does",
  "Az AUTO magától számozza a sorokat. A BRK gombbal lépsz ki belőle.", ["AUTO"])
K("save", "cmd", "how to save the program to cassette tape; what SAVE does",
  'A SAVE kazettára menti a programot. Például: SAVE "jatek"', ["SAVE"])
K("load", "cmd", "how to load a program from cassette tape; what LOAD does",
  'A LOAD betölti a programot a kazettáról. Például: LOAD "jatek"', ["LOAD"])
K("rnd", "cmd", "how to get a random number; what RND does",
  "Az RND véletlen számot ad. Például: PRINT RND({N:6}) egy számot ír ki 1 és {N:6} között.", ["RND"])
K("random", "cmd", "what RANDOM does; why the random numbers are the same every time",
  "A RANDOM megkeveri a véletlen számokat, hogy minden futáskor mások legyenek.", ["RANDOM"],
  [("RANDOM", None)])
K("int", "cmd", "how to cut off the decimals / get a whole number; what INT does",
  "Az INT levágja a tizedeseket. Például: PRINT INT(3.7) eredménye 3", ["INT"], [("PRINT INT(3.7)", " 3")])
K("abs", "cmd", "what ABS does; absolute value",
  "Az ABS a szám értéke előjel nélkül. Például: PRINT ABS(-5) eredménye 5", ["ABS"], [("PRINT ABS(-5)", " 5")])
K("sqr", "cmd", "how to calculate a square root; what SQR does",
  "Az SQR négyzetgyököt von. Például: PRINT SQR(16) eredménye 4", ["SQR"], [("PRINT SQR(16)", " 4")])
K("sin", "cmd", "what SIN does; sine",
  "A SIN szinuszt számol, a szöget radiánban kéri. Például: PRINT SIN(1)", ["SIN"], [("PRINT SIN(1)", ".841471")])
K("cos", "cmd", "what COS does; cosine",
  "A COS koszinuszt számol, a szöget radiánban kéri. Például: PRINT COS(0)", ["COS"], [("PRINT COS(0)", " 1")])
K("tan", "cmd", "what TAN does; tangent",
  "A TAN tangenst számol, a szöget radiánban kéri. Például: PRINT TAN(1)", ["TAN"], [("PRINT TAN(1)", "1.5574")])
K("atn", "cmd", "what ATN does; arc tangent",
  "Az ATN arkusz tangenst számol. Például: PRINT ATN(1)*4 a pi értékét adja.", ["ATN"],
  [("PRINT ATN(1)*4", "3.14159")])
K("pi", "cmd", "the value of pi; what PI is",
  "A PI értéke 3.14159. Például: PRINT 2*PI*5", ["PI"], [("PRINT 2*PI*5", "31.4159")])
K("sgn", "cmd", "what SGN does; the sign of a number",
  "Az SGN a szám előjele: -1, 0 vagy 1. Például: PRINT SGN(-3) eredménye -1", ["SGN"], [("PRINT SGN(-3)", "-1")])
K("log", "cmd", "what LOG does; logarithm",
  "A LOG természetes logaritmust számol. Például: PRINT LOG(10)", ["LOG"], [("PRINT LOG(10)", "2.30259")])
K("exp", "cmd", "what EXP does",
  "Az EXP az e szám hatványát adja. Például: PRINT EXP(1)", ["EXP"], [("PRINT EXP(1)", "2.71828")])
K("power", "how", "how to raise a number to a power / square a number",
  "Hatványozni a felfelé nyíl gombbal lehet: PRINT 2↑3 eredménye 8. Négyzet: A*A", [],
  [("PRINT 2↑3", " 8")])
K("len", "cmd", "how to get the length of a text; what LEN does",
  'A LEN a szöveg hossza. Például: PRINT LEN("primo") eredménye 5', ["LEN"], [('PRINT LEN("primo")', " 5")])
K("left", "cmd", "how to get the first letters of a text; what LEFT$ does",
  'A LEFT$ a szöveg elejét adja. Például: PRINT LEFT$("primo",2) eredménye pr', ["LEFT$"],
  [('PRINT LEFT$("primo",2)', "pr")])
K("right", "cmd", "how to get the last letters of a text; what RIGHT$ does",
  'A RIGHT$ a szöveg végét adja. Például: PRINT RIGHT$("primo",2) eredménye mo', ["RIGHT$"],
  [('PRINT RIGHT$("primo",2)', "mo")])
K("mid", "cmd", "how to get letters from the middle of a text; what MID$ does",
  'A MID$ a szöveg közepéből vesz ki. Például: PRINT MID$("primo",2,3) eredménye rim', ["MID$"],
  [('PRINT MID$("primo",2,3)', "rim")])
K("chr", "cmd", "how to make a character from its code; what CHR$ does",
  "A CHR$ a kódból betűt csinál. Például: PRINT CHR$(65) eredménye A", ["CHR$"], [("PRINT CHR$(65)", "A")])
K("asc", "cmd", "how to get the code of a character; what ASC does",
  'Az ASC a betű kódját adja. Például: PRINT ASC("A") eredménye 65', ["ASC"], [('PRINT ASC("A")', " 65")])
K("str", "cmd", "how to turn a number into text; what STR$ does",
  "Az STR$ a számból szöveget csinál. Például: A$=STR$(12)", ["STR$"], [("A$=STR$(12):PRINT A$", " 12")])
K("val", "cmd", "how to turn text into a number; what VAL does",
  'A VAL a szövegből számot csinál. Például: PRINT VAL("12")+1 eredménye 13', ["VAL"],
  [('PRINT VAL("12")+1', " 13")])
K("string", "cmd", "how to print the same character many times; what STRING$ does",
  'A STRING$ egy jelet ismétel. Például: PRINT STRING$(5,"*")', ["STRING$"], [('PRINT STRING$(5,"*")', "*****")])
K("concat", "how", "how to join two texts together",
  'Szövegeket a + jellel fűzöl össze. Például: PRINT "alma"+"fa"', [], [('PRINT "alma"+"fa"', "almafa")])
K("inkey", "cmd", "how to read a key press without waiting for RETURN; what INKEY$ does",
  'Az INKEY$ a lenyomott gombot adja, nem vár. Például: 10 A$=INKEY$:IF A$="" THEN 10', ["INKEY$"])
K("set", "cmd", "how to draw a dot / point on the screen; how to draw; what SET does",
  "A SET kigyújt egy pontot. Például: SET(100,50). X 0 és 255, Y 0 és 191 között lehet.", ["SET"],
  [("SET(100,50):PRINT POINT(100,50)", "-1")])
K("reset", "cmd", "how to erase a dot from the screen; what RESET does",
  "A RESET kiolt egy pontot. Például: RESET(100,50)", ["RESET"],
  [("SET(100,50):RESET(100,50):PRINT POINT(100,50)", " 0")])
K("point", "cmd", "how to find out whether a dot on the screen is lit; what POINT does",
  "A POINT megmondja, világít-e a pont: -1 ha igen, 0 ha nem. Például: PRINT POINT(100,50)", ["POINT"],
  [("PRINT POINT(100,50)", " 0")])
K("beep", "cmd", "how to make a sound / beep / music; what BEEP does",
  "A BEEP hangot ad, két számot kér. Például: BEEP 10,100", ["BEEP"], [("BEEP 10,100", None)])
K("peek", "cmd", "how to look into the memory; what PEEK does",
  "A PEEK kiolvas egy bájtot a memóriából. Például: PRINT PEEK(16384)", ["PEEK"], [("PRINT PEEK(16384)", " 195")])
K("poke", "cmd", "how to write into the memory; what POKE does",
  "A POKE beír egy bájtot a memóriába. Például: POKE 30000,201. Vigyázz vele!", ["POKE"],
  [("POKE 30000,201:PRINT PEEK(30000)", " 201")])
K("inp", "cmd", "what INP does",
  "Az INP beolvas egy bájtot a gép egyik kapujáról. Például: PRINT INP(0)", ["INP"], [("PRINT INP(0)", None)])
K("out", "cmd", "what OUT does",
  "Az OUT kiküld egy bájtot a gép egyik kapujára. Vigyázz vele!", ["OUT"])
K("tab", "cmd", "how to print at a given column of the line; what TAB does",
  'A TAB a sor megadott oszlopára ugrik. Például: PRINT TAB(10);"x"', ["TAB"],
  [('PRINT TAB(10);"x"', "          x")])
K("using", "cmd", "how to print a number with two decimals; what USING does",
  'A PRINT USING megadott alakban ír ki számot. Például: PRINT USING "##.##";3.14159', ["USING"],
  [('PRINT USING "##.##";3.14159', " 3.14")])
K("on", "cmd", "how to jump to one of several lines depending on a number; what ON does",
  "Az ON a szám szerint választ sort. Például: ON A GOTO 100,200", ["ON"])
K("tron", "cmd", "how to see which line the program is running (trace); what TRON and TROFF do",
  "A TRON után a gép kiírja, melyik sort hajtja végre. A TROFF kikapcsolja.", ["TRON", "TROFF"],
  [("TRON", None), ("TROFF", None)])
K("clear", "cmd", "how to erase all variables; what CLEAR does",
  "A CLEAR töröl minden változót. CLEAR 500 több helyet ad a szövegeknek.", ["CLEAR"], [("CLEAR 500", None)])
K("fre", "cmd", "how much memory is free; what FRE does",
  "Az FRE megmondja, mennyi a szabad memória. Például: PRINT FRE(0)", ["FRE"], [("PRINT FRE(0)", None)])
K("onerror", "cmd", "how the program can catch an error itself; what ON ERROR and RESUME do",
  "Az ON ERROR GOTO 100 hiba esetén a 100-as sorra ugrik. A RESUME NEXT onnan folytatja.",
  ["ON ERROR", "RESUME", "ERROR"])
K("and", "cmd", "how to check two conditions at once; what AND means",
  'Az AND azt jelenti: és. Például: IF A>0 AND A<10 THEN PRINT "jó"', ["AND"],
  [('A=5:IF A>0 AND A<10 THEN PRINT "jó"', "jó")])
K("or", "cmd", "how to check whether one of two conditions is true; what OR means",
  'Az OR azt jelenti: vagy. Például: IF A=1 OR A=2 THEN PRINT "jó"', ["OR"],
  [('A=2:IF A=1 OR A=2 THEN PRINT "jó"', "jó")])
K("not", "cmd", "what NOT means",
  "A NOT tagad: ami igaz volt, hamis lesz. Például: IF NOT(A=5) THEN PRINT A", ["NOT"],
  [("A=3:IF NOT(A=5) THEN PRINT A", " 3")])
K("edit", "cmd", "how to correct a mistake in a program line; what EDIT does",
  "Sort úgy javítasz, hogy újra beírod ugyanazzal a számmal.", ["EDIT"])

# ---- how do I ... -------------------------------------------------------------------------
K("semi", "how", "how to print two things next to each other on one line / what ; and , do in PRINT",
  "A PRINT-ben a ; után szorosan folytatja a kiírást, a , után távolabb. Például: PRINT 1;2,3", [],
  [("PRINT 1;2,3", " 1  2            3")])
K("colon", "how", "how to write several statements in one line",
  'Egy sorba több utasítást kettősponttal írhatsz. Például: 10 CLS:PRINT "szia"', [])
K("wait", "how", "how to make the program wait / slow down / pause for a while",
  "Várakozni üres ciklussal lehet. Például: FOR T=1 TO 600:NEXT T egy másodpercig tart.", [],
  [("FOR T=1 TO 600:NEXT T", None)])
K("remainder", "how", "how to get the remainder of a division",
  "A maradék így jön ki: PRINT A-INT(A/B)*B", [], [("A=7:B=2:PRINT A-INT(A/B)*B", " 1")])
K("round", "how", "how to round a number",
  "Kerekíteni így lehet: PRINT INT(X+.5)", [], [("X=3.6:PRINT INT(X+.5)", " 4")])
K("forever", "how", "how to make something repeat forever / an endless loop",
  "Végtelen ciklus: 10 GOTO 10. A BRK gombbal állíthatod meg.", [])
K("compare", "how", "how to compare two numbers; which signs mean equal, not equal, less, greater",
  "Összehasonlítás: = egyenlő, <> nem egyenlő, < kisebb, > nagyobb.", [],
  [("PRINT 5<>3;5<3;5>3;5=5", "-1  0 -1 -1")])
K("emptyline", "how", "how to print an empty line",
  "Üres sort a magában álló PRINT ír ki.", [], [("PRINT", None)])
K("insert", "how", "how to put a new line between two existing lines of the program",
  "Új sort két sor közé úgy teszel, hogy közéjük eső számot adsz neki, például 15.", [])
K("runfrom", "how", "how to start the program from a given line, not from the beginning",
  "A RUN 100 a 100-as sortól indítja a programot.", [])
K("break", "how", "how to stop a running program",
  "A futó programot a BRK gombbal állíthatod meg.", ["BRK"])
K("capital", "how", "how to type capital letters",
  "Nagybetűt a SHIFT gombbal együtt lenyomva írhatsz.", ["SHIFT"])
K("backspace", "how", "how to delete a wrongly typed letter",
  "Az elírt betűt a balra nyíl gombbal törölheted.", [])
K("quotes", "how", "why text must be in quotation marks; how to print a word",
  'A szöveget idézőjelek közé kell írni. Például: PRINT "primo"', [], [('PRINT "primo"', "primo")])
K("commands", "how", "which commands exist / what words the computer knows",
  "Néhány parancs: PRINT, INPUT, IF, FOR, GOTO, CLS, SET, BEEP. Kérdezz rájuk!", [])
K("begin", "how", "how to start learning programming; what the first program should be",
  'Kezdd ezzel: 10 PRINT "szia" és utána RUN. Aztán kérdezz a FOR-ról!', [])
K("game", "how", "how to write a game",
  "Játékhoz INPUT vagy INKEY$, IF és GOTO kell. Kérj tőlem számkitaláló programot!", [])
K("color", "how", "how to use colours",
  "A Primo képe fekete-fehér, színek nincsenek.", [])

# ---- ideas --------------------------------------------------------------------------------
K("variable", "idea", "what a variable is",
  "A változó egy névvel ellátott tároló, számot tehetsz bele. Például: A=5", [])
K("strvar", "idea", "what the $ sign means / how to store text in a variable",
  'A szöveges változó neve $ jelre végződik. Például: N$="primo"', ["$"])
K("program", "idea", "what a program is",
  "A program számozott sorokból áll, a gép sorban hajtja végre őket.", [])
K("lineno", "idea", "why program lines have numbers / how to number the lines",
  "Minden programsor számmal kezdődik. Érdemes tízesével számozni: 10, 20, 30.", [])
K("loop", "idea", "what a loop (ciklus) is",
  "A ciklus többször megismétel valamit. Erre való a FOR és a NEXT.", [])
K("array", "idea", "what an array (tömb) is",
  "A tömb sok szám egy név alatt, sorszámmal éred el őket. Például: T(3)", [])
K("subroutine", "idea", "what a subroutine is",
  "A szubrutin olyan programrész, amit több helyről meghívhatsz a GOSUB paranccsal.", [])
K("basic", "idea", "what BASIC is",
  "A BASIC egy programnyelv. Ezen a nyelven beszélhetsz a Primóval.", ["BASIC"])
K("primo", "idea", "what the PRIMO is / where and when it was made",
  "A Primo magyar számítógép, 1984-ben készült.", [])
K("memory", "idea", "how much memory the PRIMO has",
  "Ebben a Primóban 48 kilobájt memória van.", [])
K("direct", "idea", "what happens when a command is typed without a line number",
  "Ha sorszám nélkül írsz be egy parancsot, a gép azonnal végrehajtja.", [])
K("screen", "idea", "how big the screen is / how many characters or dots fit on it",
  "A képernyőre 16 sor és 42 oszlop szöveg fér, a rajz 256x192 pontból áll.", [])
K("byte", "idea", "what a byte is",
  "A bájt egy szám 0 és 255 között. A memória bájtokból áll.", [])
K("ram", "idea", "what RAM is",
  "A RAM a gép memóriája, ide kerül a programod. Kikapcsoláskor törlődik.", ["RAM"])
K("rom", "idea", "what ROM is",
  "A ROM-ban lakik a BASIC. Ez kikapcsoláskor is megmarad.", ["ROM"])
K("cpu", "idea", "what processor the PRIMO has / what a processor is",
  "A Primo esze egy Z80 típusú processzor, ez hajtja végre a parancsokat.", [])
K("ok", "idea", "what the Ok message means",
  "Az Ok azt jelenti: a gép kész, várja a következő parancsot.", ["Ok"])
K("breakin", "idea", "what the 'Break in 20' message means",
  "A Break in azt jelenti: a program megállt abban a sorban. CONT-tal folytathatod.", ["Break in", "Break"])
K("redo", "idea", "what the ?REDO message means",
  "A ?REDO azt jelenti: számot kért a gép, de mást írtál. Írd be újra!", ["?REDO", "REDO"])
K("extra", "idea", "what the '?Extra ignored' message means",
  "Az Extra ignored azt jelenti: több adatot írtál be, mint amennyit az INPUT kért.",
  ["?Extra ignored", "Extra ignored"])
K("errorhelp", "idea", "the computer printed an error and the child does not know what to do",
  "Ha hibát ír a gép, nézd meg a sort, amit mond: LIST és a sor száma. Írd meg nekem a hiba két betűjét!", [])

# ---- error messages -----------------------------------------------------------------------
for code, text in [
    ("NF", "NEXT van, de nincs hozzá FOR."),
    ("SN", "elírtál valamit a sorban. Nézd meg betűről betűre!"),
    ("RG", "RETURN van, de a gép nem GOSUB-bal jutott oda."),
    ("OD", "a READ több adatot kér, mint amennyi a DATA sorokban van."),
    ("FC", "egy parancs rossz számot kapott, például SET(300,0)."),
    ("OV", "túl nagy lett egy szám."),
    ("OM", "elfogyott a memória."),
    ("UL", "olyan sorra ugranál, ami nincs a programban."),
    ("BS", "a tömbnek nincs ilyen sorszámú eleme. Nézd meg a DIM-et!"),
    ("DD", "ugyanazt a tömböt kétszer adtad meg DIM-mel."),
    ("/0", "nullával osztottál, azt nem lehet."),
    ("ID", "ezt a parancsot csak programsorban lehet használni."),
    ("TM", "számot és szöveget kevertél össze. A szöveges változó végére $ kell."),
    ("OS", "elfogyott a szövegek helye. Segít a CLEAR 500."),
    ("LS", "túl hosszú lett a szöveg, legfeljebb 255 jel lehet."),
    ("ST", "túl bonyolult a szöveges kifejezés. Bontsd több sorra!"),
    ("CN", "a programot már nem lehet folytatni. Indítsd újra RUN-nal!"),
    ("NR", "a hibakezelő rész végéről hiányzik a RESUME."),
    ("RW", "RESUME van, de nem volt hiba."),
    ("UE", "ismeretlen hiba."),
    ("MO", "hiányzik valami a parancs végéről, például a BEEP számai."),
    ("FD", "hibás adat jött a kazettáról."),
    ("L3", "ezt a parancsot csak a lemezes BASIC ismeri."),
]:
    K("e_" + code.lower().replace("/", "div"), "err",
      f"the computer printed '{code} Error' and the child asks what it means / what went wrong",
      f"{code} Error: {text}[ A sor: LIST {{N}}]", [code + " Error"])

# ---- programs -----------------------------------------------------------------------------
K("p_count", "prog", "a program that counts from 1 to 10",
  "10 FOR I=1 TO {N:10}:PRINT I:NEXT I", prog=([], [" 1", " 10"], []))
K("p_countdown", "prog", "a program that counts backwards / a countdown",
  '10 FOR I={N:10} TO 1 STEP -1:PRINT I:NEXT I\n20 PRINT "start!"', prog=([], [" 10", "start!"], []))
K("p_hello", "prog", "a program that asks my name and greets me",
  '10 INPUT "neved";N$\n20 PRINT "szia, ";N$;"!"', prog=(["peti"], ["szia, peti!"], []))
K("p_repeat", "prog", "a program that prints a word or my name many times",
  '10 FOR I=1 TO {N:20}:PRINT "primo ";:NEXT I', prog=([], ["primo primo primo"], []))
K("p_table", "prog", "a program that prints the multiplication table",
  '10 INPUT "melyik szám";N\n20 FOR I=1 TO 10:PRINT I;"x";N;"=";I*N:NEXT I',
  prog=(["7"], [" 3 x 7 = 21", " 10 x 7 = 70"], []))
K("p_dice", "prog", "a program that throws a dice",
  '10 RANDOM:PRINT "dobás:";RND({N:6})', prog=([], ["dobás:"], []))
K("p_guess", "prog", "a number guessing game: the computer thinks of a number and I guess it",
  '10 X=RND({N:100})\n20 INPUT "tipp";T\n30 IF T<X THEN PRINT "több":GOTO 20\n'
  '40 IF T>X THEN PRINT "kevesebb":GOTO 20\n50 PRINT "eltaláltad!"', prog=(["0"], ["több", "tipp?"], []))
K("p_sum", "prog", "a program that adds up the numbers from 1 to 100",
  "10 S=0:FOR I=1 TO {N:100}:S=S+I:NEXT I\n20 PRINT S", prog=([], [" 5050"], []))
K("p_evenodd", "prog", "a program that tells whether a number is even or odd",
  '10 INPUT A\n20 IF A=INT(A/2)*2 THEN PRINT "páros" ELSE PRINT "páratlan"', prog=(["7"], ["páratlan"], []))
K("p_max", "prog", "a program that tells which of two numbers is bigger",
  "10 INPUT A,B\n20 IF A>B THEN PRINT A ELSE PRINT B", prog=(["3,8"], [" 8"], []))
K("p_squares", "prog", "a program that prints the square numbers",
  "10 FOR I=1 TO {N:10}:PRINT I;I*I:NEXT I", prog=([], [" 9  81", " 10  100"], []))
K("p_line", "prog", "a program that draws a line",
  "10 CLS:FOR X=0 TO 255:SET(X,96):NEXT X", prog=([], [], [(0, 96), (128, 96), (255, 96)]), wait=1500)
K("p_circle", "prog", "a program that draws a circle",
  "10 CLS:FOR A=0 TO 6.3 STEP .05\n20 SET(128+60*COS(A),96+60*SIN(A)):NEXT A",
  prog=([], [], [(188, 96), (68, 96)]), wait=3000)
K("p_stars", "prog", "a program that draws stars / random dots on the screen",
  "10 CLS:FOR I=1 TO {N:200}:SET(RND(255),RND(191)):NEXT I", prog=([], [], []), wait=1500)
K("p_sine", "prog", "a program that draws a wave / sine curve",
  "10 CLS:FOR X=0 TO 255:SET(X,96+60*SIN(X/20)):NEXT X", prog=([], [], [(0, 96)]), wait=3000)
K("p_square", "prog", "a program that draws a square / rectangle",
  "10 CLS:FOR I=50 TO 150\n20 SET(I,50):SET(I,150):SET(50,I):SET(150,I):NEXT I",
  prog=([], [], [(50, 50), (150, 150), (100, 50), (50, 100)]), wait=3000)
K("p_siren", "prog", "a program that plays sounds / a siren / a tune",
  "10 FOR I=1 TO 100:BEEP 5,I:NEXT I", prog=([], [], []), wait=1500)
K("p_average", "prog", "a program that calculates the average of some numbers",
  '10 INPUT "hány szám";N:S=0\n20 FOR I=1 TO N:INPUT A:S=S+A:NEXT I\n30 PRINT "átlag:";S/N',
  prog=(["2", "3", "6"], ["átlag: 4.5"], []))
K("p_fact", "prog", "a program that calculates a factorial",
  "10 INPUT N:F=1\n20 FOR I=1 TO N:F=F*I:NEXT I\n30 PRINT F", prog=(["5"], [" 120"], []))
K("p_add", "prog", "a program that asks for two numbers and adds them",
  '10 INPUT "két szám";A,B\n20 PRINT "összegük:";A+B', prog=(["3,4"], ["összegük: 7"], []))
K("p_prime", "prog", "a program that tells whether a number is a prime",
  '10 INPUT N:FOR I=2 TO SQR(N)\n20 IF N=INT(N/I)*I THEN PRINT "összetett":END\n30 NEXT I:PRINT "törzsszám"',
  prog=(["13"], ["törzsszám"], []))
K("p_reverse", "prog", "a program that writes a word backwards",
  "10 INPUT A$:FOR I=LEN(A$) TO 1 STEP -1\n20 PRINT MID$(A$,I,1);:NEXT I", prog=(["primo"], ["omirp"], []))
K("p_quiz", "prog", "a program that practises multiplication with me / asks me maths questions",
  '10 A=RND(10):B=RND(10)\n20 PRINT A;"x";B;:INPUT C\n30 IF C=A*B THEN PRINT "jó!" ELSE PRINT "nem jó"\n40 GOTO 10',
  prog=(["0"], ["nem jó"], []))
K("p_abc", "prog", "a program that prints the alphabet",
  "10 FOR I=65 TO 90:PRINT CHR$(I);:NEXT I", prog=([], ["ABCDEFGHIJKLMNOPQRSTUVWXYZ"], []))
K("p_triangle", "prog", "a program that draws a triangle / pyramid from stars (asterisks)",
  '10 FOR I=1 TO {N:10}:PRINT STRING$(I,"*"):NEXT I', prog=([], ["**********"], []))
K("p_fib", "prog", "a program that prints the Fibonacci numbers",
  "10 A=1:B=1:FOR I=1 TO {N:15}\n20 PRINT A;:C=A+B:A=B:B=C:NEXT I", prog=([], [" 1  1  2  3  5  8", " 610"], []))
K("p_key", "prog", "a program that tells which key I pressed",
  '10 A$=INKEY$:IF A$="" THEN 10\n20 PRINT "ez volt: ";A$:GOTO 10', prog=([], [], []))
K("p_clock", "prog", "a program that counts the seconds / a stopwatch",
  "10 T=0\n20 PRINT T;:T=T+1\n30 FOR I=1 TO 600:NEXT I:GOTO 20", prog=([], [" 0  1  2"], []), wait=400)

# ---- small talk ---------------------------------------------------------------------------
K("t_hello", "talk", "the child says hello", "Szia! Kérdezz a BASIC-ről!")
K("t_who", "talk", "the child asks who or what the helper is / what its name is",
  "A Primo MI vagyok, a BASIC-ben segítek.")
K("t_thanks", "talk", "the child says thank you", "Szívesen!")
K("t_bye", "talk", "the child says goodbye", "Szia! Jó programozást!")
K("t_help", "talk", "the child asks what the helper can do / what to ask / asks for help in general",
  "Kérdezz parancsot (mi az a FOR?), hibát (SN Error), vagy kérj programot!")
K("t_how", "talk", "the child asks how the helper is", "Jól vagyok, köszönöm. Programozzunk!")
K("t_praise", "talk", "the child praises the helper (you are clever, I like you)", "Köszönöm! Te is ügyes vagy.")
K("t_insult", "talk", "the child insults the helper (you are stupid)", "Csak egy kicsi gép vagyok, de igyekszem.")
K("none", "talk", "anything that is not about BASIC or the PRIMO (animals, football, school, tales, food ...)",
  "Ezt nem tudom. A BASIC-ről kérdezz!")

BY_ID = {k["id"]: k for k in KB}


def number(q):
    """The largest number typed in the question (up to four digits; digits stuck to a letter
    or a slash, as in "L3 Error" or "/0 Error", do not count), or None."""
    best = None
    for m in re.finditer(r"\d+", q):
        before = q[m.start() - 1] if m.start() else " "
        if before.isalpha() or before == "/" or len(m.group()) > 4:
            continue
        n = m.group().lstrip("0") or "0"
        if best is None or (len(n), n) > (len(best), best):
            best = n
    return best


def expression(q):
    """The first sum typed in the question, like 12*7 or 3 + 4.5, without its spaces, or None."""
    m = re.search(r"\d+(\.\d+)?( *[-+*/] *\d+(\.\d+)?)+", q)
    return m.group().replace(" ", "") if m else None


def fill(a, q=""):
    """The answer as printed for this question."""
    n, x = number(q), expression(q)
    a = re.sub(r"\[(.*?)\]", (lambda m: m.group(1)) if n else "", a, flags=re.S)
    a = re.sub(r"\{N(?::(\d+))?\}", lambda m: n or m.group(1), a)
    return re.sub(r"\{X:([^}]*)\}", lambda m: x or m.group(1), a)

assert len(BY_ID) == len(KB)

if __name__ == "__main__":
    import collections
    print(len(KB), "entries;", dict(collections.Counter(k["kind"] for k in KB)))
    print("characters of answers:", sum(len(k["a"]) for k in KB),
          " longest:", max(len(fill(k["a"], "9999")) for k in KB))
    for q in ("sn error in 30", "l3 error", "/0 error in 120", "számolj 1-től 25-ig", "mennyi 12 * 7?"):
        print(f"  {q!r}: number {number(q)}, sum {expression(q)}")
