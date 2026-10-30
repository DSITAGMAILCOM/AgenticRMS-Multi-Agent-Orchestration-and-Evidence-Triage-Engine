import os
from domains.academic.faculties.registry import FACULTY_CATALOG
from domains.academic.faculties.faculty_agent import FacultyAgent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FACULTY_AGENTS = {}
for fac_id, meta in FACULTY_CATALOG.items():
    fac_folder = os.path.join(BASE_DIR, fac_id)
    os.makedirs(fac_folder, exist_ok=True)
    FACULTY_AGENTS[fac_id] = FacultyAgent(
        faculty_id=fac_id,
        faculty_name=meta["name"],
        departments=meta["departments"],
        faculty_folder=fac_folder
    )
    