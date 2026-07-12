"""Job-title classifier for JobSeek's category filter.

Maps every job title to one category key. Rules are ordered by specificity —
first match wins. Titles matching HIDDEN patterns (non-tech corporate roles)
are excluded from the app entirely.

Categories (UI chips):
  intern       Internships & new-grad
  leadership   Architects, tech leads, EM/Director/VP/CTO
  security     Security / AppSec / IAM / crypto
  qa           QA / SDET / test automation
  mobile       iOS / Android / cross-platform
  data-ml      Data eng, data science, ML/AI, analytics, database, BI
  cloud-devops DevOps, SRE, platform, infra, cloud, reliability
  systems      Embedded, distributed, networking, kernel, HPC, game/graphics
  frontend     Frontend / web UI
  fullstack    Full-stack
  backend      Backend + language-specific (Java/Python/Go/.NET/...)
  product-ba   Product managers/owners/analysts + business analysts
  swe          General software engineering (catch-all engineer/developer)
"""
from __future__ import annotations

import re

# Titles matching these are hidden from JobSeek entirely (non-tech corporate).
HIDDEN = re.compile(
    r"counsel|legal|paralegal|attorney|lawyer|account executive|account manager"
    r"|sales|revenue|partnership|business development|\bbd\b|customer success"
    r"|customer support|customer experience|community|marketing|brand|content"
    r"|communications|public relations|\bpr\b|social media|recruit|sourcer"
    r"|talent|people ops|people operations|human resources|\bhr\b|hris"
    r"|workplace|facilities|office manager|executive assistant|admin assistant"
    r"|administrative|finance|financial analyst|accounting|accountant|payroll"
    r"|treasury|\btax\b|procurement|billing|compliance officer|policy"
    r"|events? (manager|coordinator)|designer|design (lead|manager)|copywriter"
    r"|editor|translator|localization|chef|barista|driver|warehouse|janitor",
    re.I,
)

# Analyst/consultant-family qualifier: these titles are part of Siva's
# Business Analysis taxonomy and must stay visible even when they contain
# words from the HIDDEN list (e.g. "Marketing Analyst", "Procurement
# Analyst", "Compliance Analyst", "Sales Operations Analyst").
BA_OVERRIDE = re.compile(
    r"\banalyst\b|consultant|business analysis|\bpmo\b|project coordinator"
    r"|scrum master|program manager|product (manager|owner)",
    re.I,
)

# Ordered rules: (category, compiled pattern). First match wins.
RULES: list[tuple[str, re.Pattern]] = [
    ("intern", re.compile(r"\bintern\b|internship|new grad|university grad|campus", re.I)),
    ("leadership", re.compile(
        r"architect|chief technology|(^|\W)cto(\W|$)|vp of|vice president"
        r"|head of engineering|director|engineering manager|manager, (software|engineering)"
        r"|\btech(nical)? lead\b|engineering lead|\bfellow\b", re.I)),
    ("security", re.compile(
        r"security|appsec|devsecops|\biam\b|identity engineer|cryptograph|cyber", re.I)),
    ("qa", re.compile(
        r"\bqa\b|quality (assurance|engineer)|\bsdet\b|test (engineer|automation)"
        r"|automation qa|(performance|load) test", re.I)),
    ("mobile", re.compile(
        r"\bios\b|android|mobile|react native|flutter|xamarin|cross[- ]platform", re.I)),
    ("data-ml", re.compile(
        r"machine learning|\bml\b|\bai\b|artificial intelligence|deep learning"
        r"|\bnlp\b|computer vision|\bllm\b|mlops|data (scientist|engineer|science"
        r"|platform|analyst|analytics|warehouse|insights)|big data|\betl\b"
        r"|analytics engineer|business intelligence|\bbi (engineer|analyst)\b"
        r"|applied scientist|research scientist|database|\bdba\b|\bsql\b|nosql"
        r"|hadoop|spark|streaming data|recommendation", re.I)),
    ("cloud-devops", re.compile(
        r"devops|site reliability|\bsre\b|platform engineer|infrastructure"
        r"|cloud|\baws\b|azure|\bgcp\b|kubernetes|docker|ci/cd|release engineer"
        r"|build engineer|reliability|automation engineer|capacity|scalability", re.I)),
    ("systems", re.compile(
        r"embedded|firmware|kernel|operating system|device driver|real[- ]time"
        r"|\bbsp\b|distributed|storage engineer|search engineer|networking"
        r"|network (software|automation|engineer)|telecom|\bsdn\b|wireless"
        r"|high performance computing|\bhpc\b|compiler|graphics|game|gameplay"
        r"|physics engine|multiplayer|\bar\b engineer|\bvr\b|\bxr\b|robotics"
        r"|\bros\b|autonomous|iot|edge computing|simulation|quant", re.I)),
    ("frontend", re.compile(
        r"front[- ]?end|\bui (developer|engineer)\b|web developer|react(?! native)"
        r"|angular|vue|javascript|typescript|html|css|web ui", re.I)),
    ("fullstack", re.compile(r"full[- ]?stack", re.I)),
    ("backend", re.compile(
        r"back[- ]?end|\bjava\b|python|\bc#\b|\.net|golang|\bgo (engineer|developer)\b"
        r"|node\.?js|\bphp\b|ruby|scala|kotlin|\bapi (developer|engineer)\b"
        r"|microservices", re.I)),
    ("product-ba", re.compile(
        r"product (manager|owner|analyst|operations|strategy)|business analy"
        r"|systems analyst|requirements (analyst|engineer)|solution analyst"
        r"|use case analyst|process (analyst|improvement)|reporting analyst"
        r"|functional (consultant|analyst)|scrum master|program manager"
        r"|\btpm\b|technical program|consultant|\bpmo\b|project (analyst|coordinator)"
        r"|program analyst|portfolio analyst|operations analyst|strategy analyst"
        r"|supply chain|procurement analyst|logistics analyst|\bcrm\b"
        r"|compliance analyst|governance|audit analyst|risk analyst"
        r"|internal controls|\banalyst\b", re.I)),
    ("swe", re.compile(
        r"software (engineer|developer)|\bsde\b|\bswe\b|engineer|developer|programmer", re.I)),
]

CATEGORY_LABELS: dict[str, str] = {
    "swe": "Software Eng",
    "backend": "Backend",
    "frontend": "Frontend",
    "fullstack": "Full Stack",
    "mobile": "Mobile",
    "data-ml": "Data & ML",
    "cloud-devops": "Cloud & DevOps",
    "security": "Security",
    "qa": "QA & Testing",
    "systems": "Systems",
    "product-ba": "Product & BA",
    "leadership": "Leadership",
    "intern": "Intern",
}


BA_FIRST = re.compile(
    r"business analy(st|sis)|migration analyst|integration analyst", re.I
)


def categorize(title: str) -> str | None:
    """Return the category key for a job title, or None if it should be hidden."""
    if not title:
        return None
    if HIDDEN.search(title) and not BA_OVERRIDE.search(title):
        return None
    # Seniority/level rules outrank everything (Director of Business
    # Analysis is Leadership, not BA). Then BA titles outrank tech keywords
    # (Cloud Business Analyst is a BA). Then the normal rule order.
    for key, pattern in RULES[:2]:          # intern, leadership
        if pattern.search(title):
            return key
    if BA_FIRST.search(title):
        return "product-ba"
    for key, pattern in RULES[2:]:
        if pattern.search(title):
            return key
    return None  # unmatched, non-engineering-looking titles are hidden too
