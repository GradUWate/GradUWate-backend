import re
import json
import time
import typing as t
import requests
from bs4 import BeautifulSoup, Tag

URL_TEMPLATE = "https://ucalendar.uwaterloo.ca/{term}/COURSE/course-{subject}.html"

SUBJECTS = [
    "ACTSC", "AFM", "AMATH", "ANTH", "APPLS", "ARBUS", "ARCH", "ARTS",
    "AVIA", "BET", "BIOL", "BUS", "CDNST", "CHE", "CHEM", "CHINA", "CIVE",
    "CLAS", "CMW", "CO", "COMM", "COOP", "CROAT", "CS", "DAC",
    "DUTCH", "EARTH", "EASIA", "ECE", "ECON","ENBUS",
    "ENGL", "ENVE", "ENVS", "ERS", "FINE", "FR", "GBDA",
    "GENE", "GEOE", "GEOG", "GER", "GERON", "GRK","HIST", "HLTH",
    "HRM", "HUMSC", "INDEV", "INTEG", "INTST", "ITAL", "ITALST",
    "JAPAN", "JS", "KIN", "KOREA", "LAT", "LS", "MATBUS", "MATH", "ME",
    "MEDVL", "MNS", "MSCI", "MTE", "MTHEL", "MUSIC", "NE",
    "OPTOM", "PACS", "PD", "PDARCH", "PDPHRM", "PHARM", "PHIL", "PHYS",
    "PLAN", "PMATH", "PORT", "PSCI", "PSYCH", "REC", "REES", "RS",
    "RUSS", "SCBUS", "SCI", "SDS", "SE", "SI", "SMF", "SOC",
    "SOCWK", "SPAN", "SPCOM", "STAT", "STV", "SWREN", "SYDE",
    "UNIV", "VCULT", "WKRPT"
    ]

# Match headers like: "CS 135 LAB,LEC,TST,TUT 0.50" OR "CS 136L LAB 0.25" OR "CS 489 LEC,TUT 0.50"
HEADER_RE = re.compile(r"^([A-Z]{2,4})\s+(\d{2,3}[A-Z]?)\s+[A-Z, ]+\s+([0-9.]+)\s*$")

REQ_KEYS = ("Prereq:", "Antireq:", "Coreq:")

def clean_space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def collapse_req_lines(text: str) -> str:
    """
    From a blob of description and <em> notes, pull out lines starting with
    Prereq:/Antireq:/Coreq: and join them. Keep order.
    """
    out: list[str] = []
    for key in REQ_KEYS:
        # capture from key to next requirement tag or end-of-string
        m = re.search(rf"({re.escape(key)}.*?)(?=(?:Prereq:|Antireq:|Coreq:|$))", text)
        if m:
            piece = clean_space(m.group(1))
            if piece and piece not in out:
                out.append(piece)
    return " ".join(out)

def parse_divtable(divtable: Tag) -> t.Optional[dict]:
    """
    Parse one <div class="divTable">…</div> course block.
    Expected structure (cells are all <div class="divTableCell ...">):
      [0]: "<strong>CS 135 LAB,LEC,TST,TUT 0.50</strong>"
      [1]: 'Course ID: 012040'  (class 'crseid')
      [2]: "<strong>Designing Functional Programs</strong>"  (title)
      [3+]: description (plain text cell(s)); other <em> lines include notes/prereq/antireq/coreq
    """
    cells = [c for c in divtable.find_all("div", class_=lambda x: x and "divTableCell" in x)]
    if not cells:
        return None

    # cell[0] – header with subject code, number, components & credit weight
    header_cell = cells[0]
    header_strong = header_cell.find("strong")
    if not header_strong:
        return None
    header_text = clean_space(header_strong.get_text(" ", strip=True))

    m = HEADER_RE.match(header_text)
    if not m:
        # skip non-course blocks
        return None

    subject, number, credit = m.groups()

    # Find Course ID from any cell with class 'crseid'
    course_id = None
    for c in cells:
        if "crseid" in (c.get("class") or []):
            cid_txt = clean_space(c.get_text(" ", strip=True))
            # e.g. "Course ID: 012040"
            m_id = re.search(r"Course\s*ID\s*:\s*([0-9A-Za-z]+)", cid_txt)
            if m_id:
                course_id = m_id.group(1)
                break

    # Title is the first subsequent cell that has a <strong> not equal to the header.
    title = ""
    for c in cells[1:]:
        st = c.find("strong")
        if st:
            ttxt = clean_space(st.get_text(" ", strip=True))
            if ttxt and ttxt != header_text:
                title = ttxt
                break

    # Description is the concatenation of later cells' text (excluding header/title-only cells),
    # but we ignore pure empty and we keep <em> content (notes/prereqs) inside description too.
    desc_parts: list[str] = []
    # Once we've passed the title cell, we collect everything that isn't only whitespace.
    passed_title = False if title else True
    for c in cells[1:]:
        # if this cell was the title cell, mark passed_title and continue
        st = c.find("strong")
        if st:
            ctxt = clean_space(st.get_text(" ", strip=True))
            if ctxt == title and not passed_title:
                passed_title = True
                # capture *other* text in the title cell if any besides the strong:
                extra = clean_space(c.get_text(" ", strip=True).replace(ctxt, "", 1))
                if extra:
                    desc_parts.append(extra)
                continue

        if not passed_title:
            continue

        txt = clean_space(c.get_text(" ", strip=True))
        if txt:
            desc_parts.append(txt)

    description = clean_space(" ".join(desc_parts))
    requirements = collapse_req_lines(description)

    return {
        # matching your schema keys
        "courseId": course_id,
        "courseOfferNumber": None,  # not on page
        "termCode": None,
        "termName": None,
        "associatedAcademicCareer": None,
        "associatedAcademicGroupCode": None,
        "associatedAcademicOrgCode": None,
        "subjectCode": subject,
        "catalogNumber": number,
        "title": title or None,
        "descriptionAbbreviated": None,
        "description": description or None,
        "gradingBasis": None,
        "courseComponentCode": None,  # e.g., LEC/LAB/TST is in header but multi-valued; keeping None for now
        "enrollConsentCode": None,
        "enrollConsentDescription": None,
        "dropConsentCode": None,
        "dropConsentDescription": None,
        "requirementsDescription": requirements or None,
        # (You can add "creditWeight": credit if you want to persist it)
    }

def parse_subject(url: str) -> list[dict]:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    courses: list[dict] = []
    # Each individual course is wrapped in <center><div class="divTable">…</div></center>
    for divtable in soup.find_all("div", class_="divTable"):
        rec = parse_divtable(divtable)
        if rec:
            courses.append(rec)
    return courses

def fetch_courses(term_code: str = "2223"):
    """
    Public helper to fetch a subject's courses from live uCalendar HTML
    (used as a stand-in for the real UW API).
    """
    all_courses: list[dict] = []

    try:
        for s in SUBJECTS:
            url = URL_TEMPLATE.format(term=term_code, subject=s)
            subj_courses = parse_subject(url)
            all_courses.extend(subj_courses)

    except Exception as e:
        print(f"[warn] failed {url}: {e}")
    
    return all_courses