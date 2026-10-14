"""Leitura de RTF: converte o texto visível, preservando acentos, parágrafos e tabelas.

Grupos de destino que não são texto do documento (fontes, cores, estilos, imagens, metadados,
campos ocultos) são descartados; de hiperlinks e campos fica apenas o texto exibido.
"""
import re

from app.ingestion.extractor import ExtractionError, Segment
from app.ingestion.text import read_text

TOKEN = re.compile(r"\\([a-z]{1,32})(-?\d{1,10})?[ ]?|\\'([0-9a-f]{2})|\\([^a-z])|([{}])|[\r\n]+|(.)",
                   re.IGNORECASE | re.DOTALL)

DESTINATIONS = set("""
aftncn aftnsep aftnsepc annotation atnauthor atndate atnicn atnid atnparent atnref atntime atrfend atrfstart
author background bkmkend bkmkstart blipuid buptim category colorschememapping colortbl comment company
creatim datafield datastore defchp defpap do doccomm docvar dptxbxtext ebcend ebcstart factoidname falt
fchars ffdeftext ffentrymcr ffexitmcr ffformat ffhelptext ffl ffname ffstattext fldinst fldtype fname
fontemb fontfile fonttbl footer footerf footerl footerr footnote formfield ftncn ftnsep ftnsepc g generator
gridtbl header headerf headerl headerr hl hlfr hlinkbase hlloc hlsrc hsv htmltag info keycode keywords
latentstyles lchars levelnumbers leveltext lfolevel linkval list listlevel listname listoverride
listoverridetable listpicture liststylename listtable listtext lsdlockedexcept macc maccPr mailmerge maln
malnScr manager margPr mbar mbarPr mbaseJc mbegChr mborderBox mborderBoxPr mbox mboxPr mchr mcount mctrlPr
md mdeg mdegHide mden mdiff mdPr me mendChr meqArr meqArrPr mf mfName mfPr mfunc mfuncPr mgroupChr
mgroupChrPr mgrow mhideBot mhideLeft mhideRight mhideTop mhtmltag mlim mlimloc mlimlow mlimlowPr mlimupp
mlimuppPr mm mmaddfieldname mmath mmathPict mmathPr mmaxdist mmc mmcJc mmconnectstr mmconnectstrdata mmcPr
mmcs mmdatasource mmheadersource mmmailsubject mmodso mmodsofilter mmodsofldmpdata mmodsomappedname
mmodsoname mmodsorecipdata mmodsosort mmodsosrc mmodsotable mmodsoudl mmodsoudldata mmodsouniquetag mmPr
mmquery mmr mnary mnaryPr mnoBreak mnum mobjDist moMath moMathPara moMathParaPr mopEmu mphant mphantPr
mplcHide mpos mr mrad mradPr mrPr msepChr mshow mshp msPre msPrePr msSub msSubPr msSubSup msSubSupPr msSup
msSupPr mstrikeBLTR mstrikeH mstrikeTLBR mstrikeV msub msubHide msup msupHide mtransp mtype mvertJc mvfmf
mvfml mvtof mvtol mzeroAsc mzeroDesc mzeroWid nesttableprops nextfile nonesttables objalias objclass
objdata object objname objsect objtime oldcprops oldpprops oldsprops oldtprops oleclsid operator panose
password passwordhash pgp pgptbl picprop pict pn pnseclvl pntext pntxta pntxtb printim private propname
protend protstart protusertbl pxe result revtbl revtim rsidtbl rxe shp shpgrp shpinst shppict shprslt
shptxt sn sp staticval stylesheet subject sv svb tc template themedata title txe ud upr userprops
wgrffmtfilter windowcaption writereservation writereservhash xe xform xmlattrname xmlattrvalue xmlclose
xmlname xmlnstbl xmlopen
""".split())

SPECIAL = {
    "par": "\n", "sect": "\n\n", "page": "\n\n", "line": "\n", "tab": "\t", "emdash": "—", "endash": "–",
    "emspace": " ", "enspace": " ", "qmspace": " ", "bullet": "•", "lquote": "‘", "rquote": "’",
    "ldblquote": "“", "rdblquote": "”", "cell": " | ", "row": "\n", "nestcell": " | ", "nestrow": "\n",
}


def to_text(rtf):
    if not rtf.lstrip().startswith("{\\rtf"):
        raise ExtractionError("O arquivo não está no formato RTF.")
    codepage = "cp1252"
    m = re.search(r"\\ansicpg(\d+)", rtf[:2000])
    if m:
        codepage = f"cp{m.group(1)}"
    stack, ignorable, ucskip, curskip, out = [], False, 1, 0, []
    for word, arg, hexcode, char, brace, tchar in TOKEN.findall(rtf):
        if brace:
            curskip = 0
            if brace == "{":
                stack.append((ucskip, ignorable))
            elif stack:
                ucskip, ignorable = stack.pop()
        elif char:
            curskip = 0
            if char == "~":
                if not ignorable:
                    out.append("\xa0")
            elif char in "{}\\":
                if not ignorable:
                    out.append(char)
            elif char == "*":
                ignorable = True
            elif char in "-_" and not ignorable:
                out.append("-" if char == "_" else "")
        elif word:
            curskip = 0
            if word in DESTINATIONS:
                ignorable = True
            elif ignorable:
                pass
            elif word in SPECIAL:
                out.append(SPECIAL[word])
            elif word == "uc":
                ucskip = int(arg or 1)
            elif word == "u":
                code = int(arg)
                out.append(chr(code + 65536 if code < 0 else code))
                curskip = ucskip
        elif hexcode:
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                try:
                    out.append(bytes([int(hexcode, 16)]).decode(codepage))
                except (LookupError, UnicodeDecodeError):
                    out.append(bytes([int(hexcode, 16)]).decode("cp1252", errors="replace"))
        elif tchar:
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                out.append(tchar)
    text = "".join(out).replace("\xa0", " ")
    text = re.sub(r"[ \t]*\|[ \t]*\n", "\n", text)  # fim de linha de tabela
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract(path):
    return [Segment(to_text(read_text(path)))], None
