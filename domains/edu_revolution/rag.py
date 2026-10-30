import os
from core.base_rag import DepartmentVectorStore

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
edurev_rag = DepartmentVectorStore(faculty_id="central", dept_id="edu_revolution", base_dir=CURRENT_DIR)