import os
from core.base_rag import DepartmentVectorStore

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
admin_rag = DepartmentVectorStore(faculty_id="central", dept_id="administration", base_dir=CURRENT_DIR)