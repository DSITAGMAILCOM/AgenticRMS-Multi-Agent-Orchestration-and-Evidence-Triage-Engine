import sqlite3
from typing import Dict, Any
from config import DB_PATH

def execute_safe_query(sql_query: str, params: tuple = ()) -> Dict[str, Any]:
    """
    Executes a read-only or transactional query with comprehensive database error trapping.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql_query, params)
        
        # Check if query produces rows
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
            return {
                "success": True,
                "row_count": len(data),
                "columns": columns,
                "data": data,
                "error": None
            }
        else:
            conn.commit()
            return {
                "success": True,
                "rows_affected": cursor.rowcount,
                "error": None
            }
    except sqlite3.OperationalError as oe:
        return {
            "success": False,
            "error_type": "SQLite Operational Error (Syntax/Schema/Table missing)",
            "error": str(oe),
            "executed_query": sql_query
        }
    except sqlite3.IntegrityError as ie:
        return {
            "success": False,
            "error_type": "SQLite Integrity Violation (Unique/Foreign Key)",
            "error": str(ie),
            "executed_query": sql_query
        }
    except Exception as e:
        return {
            "success": False,
            "error_type": "Unhandled Database Exception",
            "error": str(e),
            "executed_query": sql_query
        }
    finally:
        if conn:
            conn.close()