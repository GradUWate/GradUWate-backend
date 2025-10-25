import re
from typing import List, Dict

# "CS 135", "MATH 239", "MTE 121/GENE 121", "PHYS 139", "CS 146A"
COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,4})\s*(\d{2,3}[A-Z]?)\b")

def _codes_in(text: str) -> List[str]:
    return [f"{a} {b}" for a, b in COURSE_CODE_RE.findall(text or "")]

def _split_and_top_level(s: str) -> List[str]:
    """Top-level split on ' and ' while keeping parenthesized groups intact."""
    out, buf, depth = [], [], 0
    tokens = s.split()
    for tok in tokens:
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth = max(0, depth - 1)
        if depth == 0 and tok.lower() == "and":
            out.append(" ".join(buf).strip()); buf = []
        else:
            buf.append(tok)
    if buf: out.append(" ".join(buf).strip())
    return out

def _split_or_any(s: str) -> List[str]:
    """Split by ' or ', comma, or slash (OR semantics)."""
    parts = re.split(r"\s+or\s+|,|/", s, flags=re.I)
    return [p.strip() for p in parts if p.strip()]

def extract_constraints(requirements_description: str) -> Dict[str, List]:
    """
    Returns:
      {
        "prereq_groups": List[List[str]],   # AND-of-OR groups (each inner list is an OR group)
        "antireqs": List[str]
      }
    Only picks course-looking tokens; ignores 'Not open to ...' etc.
    """
    txt = (requirements_description or "").strip()

    # pull labeled spans
    m_pre  = re.search(r"Prereq:\s*(.*?)(?=Antireq:|Coreq:|$)", txt, flags=re.I|re.S)
    m_anti = re.search(r"Antireq:\s*(.*?)(?=Prereq:|Coreq:|$)", txt, flags=re.I|re.S)
    pre  = (m_pre.group(1).strip()  if m_pre  else "")
    anti = (m_anti.group(1).strip() if m_anti else "")

    prereq_groups: List[List[str]] = []
    if pre:
        # top-level AND split
        and_parts = _split_and_top_level(pre)
        for part in and_parts:
            # inside each AND part, split into OR options
            or_parts = _split_or_any(part)
            codes = []
            for chunk in or_parts:
                codes.extend(_codes_in(chunk))
            # if no explicit OR split matched, still try to mine codes from the part
            if not codes:
                codes = _codes_in(part)
            codes = sorted(set(codes))
            if codes:
                prereq_groups.append(codes)

    antireqs = sorted(set(_codes_in(anti)))

    return {"prereq_groups": prereq_groups, "antireqs": antireqs}