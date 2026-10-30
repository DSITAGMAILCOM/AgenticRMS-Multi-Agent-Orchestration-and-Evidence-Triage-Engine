# orchestrator/router.py
"""
Central Orchestration and Multi-Query Routing Layer
Manages query sanitization, deterministic multi-intent classification,
multi-agent dispatching, parallel/sequential response synthesis,
and audit tracking for the University Multi-Agent Support System.
"""
import re
import json
from typing import Optional, List, Dict, Any
from config import client, AGENT_MODEL, console
from core.session import StudentSession
from core.tracker import QueryTracker
from core.rms_handler import detect_rms_intent, handle_tracking_query, handle_history_query

# Specialized Domain Agents
from domains.administration.agent import admin_agent
from domains.academic.academic_lead import academic_lead
from domains.examination.agent import exam_agent
from domains.edu_revolution.agent import edurev_agent
from domains.default_gateway.agent import default_gateway_agent

DOMAIN_LABELS = {
    "administration": "Administration & Fees",
    "examination": "Examination",
    "edu_revolution": "Edu-Revolution & Internships",
    "academic": "Academics & Courses",
    "default": "Campus Support"
}

# Domain keyword pattern catalogs
ADMIN_PATTERNS = [
    r"\bfees?\b", r"\bdues?\b", r"\bpayments?\b", r"\bhostels?\b",
    r"\bresidential\b", r"\bscholarships?\b", r"\bchallans?\b",
    r"\bfines?\b", r"\badmissions?\b", r"\breceipts?\b", r"\btransport\b", r"\bbus\b",
    r"\brms\b", r"\btrack(?:ing)?\b", r"\btickets?\b", r"\bhelpdesk\b", r"\bgrievances?\b", r"\bcomplaints?\b"
]

EXAM_PATTERNS = [
    r"\bexams?\b", r"\bexaminations?\b", r"\bhall\s*tickets?\b",
    r"\bdatesheets?\b", r"\bdate\s*sheets?\b", r"\badmit\s*cards?\b",
    r"\bseatings?\b", r"\bdesks?\b", r"\bre-?eval\b", r"\bbacklogs?\b",
    r"\bgrades?\b", r"\bcgpa\b", r"\bsgpa\b", r"\bresults?\b", r"\bmarks\b"
]

EDUREV_PATTERNS = [
    r"\binternships?\b", r"\bnoc\b", r"\bstipends?\b", r"\bcompany\b",
    r"\bcoordinator\b", r"\bindustrial\b", r"\bweekly\s*reports?\b",
    r"\bedu[-_ ]?revolution\b", r"\bcareers?\b", r"\bplacements?\b"
]

ACADEMIC_PATTERNS = [
    r"\bcourses?\b", r"\bsyllabus\b", r"\bsyllabi\b", r"\bcurriculum\b",
    r"\bcredits?\b", r"\bprofessors?\b", r"\bfacult(?:y|ies)\b",
    r"\binstructors?\b", r"\bmentors?\b", r"\battendance\b",
    r"\bsubjects?\b", r"\blabs?\b", r"\bschedules?\b", r"\btimetables?\b",
    r"\bclassrooms?\b", r"\bengineering\b", r"\bcomputer\s*science\b"
]


def clean_query(query: str) -> str:
    """
    Sanitizes and normalizes the user query to reduce token count and optimize matching:
    1. Lowercases all characters.
    2. Deletes commas, punctuation, and special symbols (retaining letters, digits, and spaces).
    3. Collapses multiple consecutive spaces into a single space and strips margins.
    """
    q = query.lower()
    q = re.sub(r"[^\w\s]", " ", q)
    return " ".join(q.split())


def detect_all_matching_domains(query: str) -> List[str]:
    """
    Scans the query against all domain catalogs and returns all matched functional domains.
    Detects whether a student has asked multiple questions spanning different domains.
    """
    q = query.lower().strip()
    matched = []

    if any(re.search(pat, q) for pat in ADMIN_PATTERNS) or re.fullmatch(r"\d{5,12}", q):
        matched.append("administration")

    if any(re.search(pat, q) for pat in EXAM_PATTERNS):
        matched.append("examination")

    if any(re.search(pat, q) for pat in EDUREV_PATTERNS):
        matched.append("edu_revolution")

    if any(re.search(pat, q) for pat in ACADEMIC_PATTERNS):
        matched.append("academic")

    return matched


def active_gate_classify(query: str) -> str:
    """
    Deterministic regex-based intent classifier for single-intent queries.
    Maintained for backward compatibility.
    """
    domains = detect_all_matching_domains(query)
    if domains:
        return domains[0]
    return "default"


def decompose_multi_query(raw_query: str, detected_domains: List[str]) -> List[Dict[str, str]]:
    """
    Decomposes a compound question into separate sub-queries, each mapped to its domain.
    Uses fast clause splitting first, with smart LLM decomposition fallback for complex sentences.
    """
    # 1. Deterministic clause splitting
    split_pattern = r"(?:\?+|\n+|;\s*|\band\s+also\b|\bas\s+well\s+as\b|\band\s+(?:what|when|where|who|how|can|is|are|tell|check)\b|\balso\b|\band\b)"
    raw_segments = [s.strip() for s in re.split(split_pattern, raw_query, flags=re.IGNORECASE) if s.strip()]

    # Filter out trivial segments (< 2 words)
    valid_segments = [s for s in raw_segments if len(s.split()) >= 2]

    # Map segments to domains
    segment_map: List[Dict[str, str]] = []
    covered_domains = set()

    for seg in valid_segments:
        dom = active_gate_classify(seg)
        if dom != "default" and dom in detected_domains and dom not in covered_domains:
            segment_map.append({"sub_query": seg, "domain": dom})
            covered_domains.add(dom)

    # If deterministic splitting successfully covered all detected domains, use it
    if len(segment_map) >= 2 and len(covered_domains) == len(detected_domains):
        return segment_map

    # 2. LLM Fast Decomposition Fallback (sub-200ms on Groq)
    try:
        prompt = (
            f"The student asked a multi-part question: \"{raw_query}\"\n"
            f"Split this question into distinct single-topic sub-queries.\n"
            f"Target domains: administration, examination, edu_revolution, academic, default.\n"
            f"Return ONLY a valid JSON array of objects with keys 'sub_query' and 'domain'.\n"
            f"Example:\n"
            f"[\n"
            f"  {{\"sub_query\": \"What is my fee balance?\", \"domain\": \"administration\"}},\n"
            f"  {{\"sub_query\": \"When is my CSE423 exam?\", \"domain\": \"examination\"}}\n"
            f"]\n"
            f"JSON:"
        )
        res = client.chat.completions.create(
            model=AGENT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        raw_json = res.choices[0].message.content or "[]"
        # Extract json array
        m = re.search(r"\[.*\]", raw_json, re.DOTALL)
        if m:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, list) and len(parsed) >= 2:
                valid_parsed = []
                for item in parsed:
                    if isinstance(item, dict) and "sub_query" in item and "domain" in item:
                        valid_parsed.append({
                            "sub_query": str(item["sub_query"]).strip(),
                            "domain": str(item["domain"]).strip().lower()
                        })
                if len(valid_parsed) >= 2:
                    return valid_parsed
    except Exception as e:
        console.print(f"[dim red]Decomposition fallback note: {e}[/dim red]")

    # Fallback to single query if decomposition cannot resolve distinct sub-queries
    return [{"sub_query": raw_query, "domain": detected_domains[0] if detected_domains else "default"}]


def dispatch_single_agent(domain: str, query: str, session: StudentSession) -> str:
    """Dispatches a single sub-query directly to its specialized domain agent."""
    if domain == "administration":
        return admin_agent.run(query, session=session)
    elif domain == "examination":
        return exam_agent.run(query, session=session)
    elif domain == "academic":
        return academic_lead.run(query, session=session)
    elif domain == "edu_revolution":
        return edurev_agent.run(query, session=session)
    else:
        # Check Default Gateway FAQs first
        faq_ans = default_gateway_agent.check_faq(query)
        if faq_ans:
            return faq_ans

        system_prompt = (
            f"You are the University Support Portal Assistant.\n"
            f"Student: {session.full_name} ({session.university_id}), Dept: {session.department_id}.\n"
            f"Read the student's question carefully and provide a direct, point-to-point answer strictly within 2 to 3 lines. "
            f"Do not write long paragraphs or unnecessary filler."
        )
        res = client.chat.completions.create(
            model=AGENT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.2
        )
        return res.choices[0].message.content or "No response generated."


def orchestrate_query(user_query: str, session: Optional[StudentSession] = None, tracker: Optional[QueryTracker] = None) -> str:
    """
    Main orchestration pipeline:
    1. Preprocesses the query via clean_query.
    2. Ensures an active authenticated StudentSession is loaded.
    3. Initializes audit logging in QueryTracker.
    4. Detects single vs. multiple intent domains.
    5. For MULTI-QUERY questions:
       - Decomposes into independent sub-queries.
       - Dispatches each to its specialized domain agent.
       - Records hops for all routed agents.
       - Synthesizes a clean, point-to-point response within 2-3 lines per topic.
    6. For SINGLE-QUERY questions:
       - Routes directly to the specialized domain agent with zero extra overhead.
    """
    cleaned_query = clean_query(user_query)

    # Step 1: Ensure authenticated session
    if session is None:
        session = StudentSession()
        session.authenticate_or_lookup("12204521")
    elif not isinstance(session, StudentSession):
        u_id = getattr(session, "university_id", None) or getattr(session, "registration_no", "12204521")
        u_name = getattr(session, "user_name", None) or getattr(session, "full_name", "Student")
        session = StudentSession(registration_no=u_id, user_name=u_name)

    # Step 2: Initialize Audit Tracker
    if tracker is None:
        u_id = getattr(session, "university_id", "12204521")
        s_name = getattr(session, "full_name", "Student")
        s_email = getattr(session, "university_email", "student@lpu.in")
        tracker = QueryTracker(university_id=u_id, student_name=s_name, email=s_email, raw_query=cleaned_query)

    # Step 3: Check for pure RMS History & Tracking Queries (Single intent fast-path)
    rms_intent = detect_rms_intent(cleaned_query)
    detected_domains = detect_all_matching_domains(cleaned_query)

    if rms_intent and len(detected_domains) <= 1:
        if rms_intent == "RMS_TRACKING":
            tracker.log_hop("Top Orchestrator", "AdministrationAgent (RMS Tracker)", "RMS_TRACKING", payload={"query": cleaned_query})
            res = handle_tracking_query(cleaned_query, session.university_id, session.full_name)
            tracker.finalize(resolution_type="AUTOMATED_RMS_TRACKING", ticket_id=res.get("ticket_id"))
            return res["markdown"]
        elif rms_intent == "RMS_HISTORY":
            tracker.log_hop("Top Orchestrator", "AdministrationAgent (RMS History)", "RMS_HISTORY", payload={"query": cleaned_query})
            res = handle_history_query(session.university_id, session.full_name)
            tracker.finalize(resolution_type="AUTOMATED_RMS_HISTORY", ticket_id=res.get("ticket_id"))
            return res["markdown"]

    # Step 4: Multi-Query vs Single-Query Branching
    is_multi_query = len(detected_domains) > 1 or (
        any(sep in user_query.lower() for sep in [" and also ", " as well as ", " and what ", " and when ", " and who ", " and how "])
        and len(detected_domains) >= 1
    )

    if is_multi_query:
        console.print(f"[bold magenta]🔀 [Multi-Query Orchestrator] Detected Domains: {[d.upper() for d in detected_domains]}[/bold magenta]")
        sub_queries = decompose_multi_query(user_query, detected_domains)

        # If decomposition confirmed 2 or more sub-queries
        if len(sub_queries) >= 2:
            results = []
            for item in sub_queries:
                sq = item["sub_query"]
                s_dom = item["domain"]
                tracker.log_hop(
                    from_agent="Top Orchestrator",
                    to_agent=f"{s_dom.title()}Agent",
                    action_type="MULTI_QUERY_ROUTE",
                    payload={"sub_query": sq, "domain": s_dom}
                )
                raw_ans = dispatch_single_agent(s_dom, sq, session)

                # Clean badges and headers to maintain point-to-point brevity
                clean_ans = re.sub(r"^⚡\s*\*\*\[Instant FAQ Deflection[^\]]*\]\*\*\s*", "", raw_ans, flags=re.IGNORECASE).strip()
                clean_ans = re.sub(r"^###\s+[^\n]+\n*", "", clean_ans).strip()
                results.append({"domain": s_dom, "answer": clean_ans})

            # Synthesize point-to-point answer within 2-3 lines per topic
            synthesis_lines = []
            for i, r in enumerate(results, 1):
                label = DOMAIN_LABELS.get(r["domain"], r["domain"].title())
                synthesis_lines.append(f"{i}. **{label}**: {r['answer']}")

            tracker.finalize(resolution_type="AUTOMATED_MULTI_QUERY")
            return "\n\n".join(synthesis_lines)

    # Step 5: Single-Query Routing
    domain = detected_domains[0] if detected_domains else "default"
    console.print(f"[bold dodger_blue1]🧭 [Orchestrator Routing] Single Intent: {domain.upper()}[/bold dodger_blue1]")

    try:
        tracker.log_hop("Top Orchestrator", f"{domain.title()}Agent", "ROUTING", payload={"domain": domain})
        response = dispatch_single_agent(domain, cleaned_query, session)
        tracker.finalize(resolution_type=f"AUTOMATED_{domain.upper()}")
        return response
    except Exception as e:
        console.print(f"[bold red]⚠️  Error in domain '{domain}': {e}[/bold red]")
        return default_gateway_agent.run(
            query=cleaned_query,
            session=session,
            tracker=tracker,
            reason=f"Error in {domain} agent: {str(e)}"
        )