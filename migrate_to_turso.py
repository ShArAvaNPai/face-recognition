import sqlite3
import urllib.request
import json
import base64
import os

LOCAL_DB = "attendance.db"
TURSO_URL = "https://pai-pai3530.aws-ap-south-1.turso.io"
AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODkxODk5NjYsImlkIjoiMDFhMDk0MDAtMzkwMS03Y2YxLWFhMTgtYjU2MjBmMDJhZjI3Iiwia2lkIjoiQVp0dG9yTXRRdjdwSDhtVEtPZUJrZFByVVlQNFlWWUV0QVVENjlBWjBWNCIsInJpZCI6IjNiOWYzMzY4LTZjOTEtNDM5NS05YjNjLTA2YzY5ZTE3NzRhNSJ9.4my1J5hXKErliLyazN-oJA5UIjwxBXuZ_8PQakxKNgZNLVQJOoLf7bcEflIpUkVXr9P5xnTHmA5rxYM0idIXDA"

import time

def execute_turso_batch(statements, max_retries=3):
    url = f"{TURSO_URL}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    requests_list = []
    for stmt in statements:
        if isinstance(stmt, str):
            requests_list.append({
                "type": "execute",
                "stmt": {"sql": stmt}
            })
        elif isinstance(stmt, dict):
            requests_list.append({
                "type": "execute",
                "stmt": stmt
            })
            
    requests_list.append({"type": "close"})
    payload = json.dumps({"requests": requests_list}).encode("utf-8")
    
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                results = res_data.get("results", [])
                for r in results:
                    if r.get("type") == "error":
                        err_msg = r.get("error", {}).get("message", "")
                        if "already exists" not in err_msg:
                            print(f"Error in batch: {r.get('error')}")
                return res_data
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
            else:
                print(f"HTTP Error after {max_retries} attempts: {e}")
                if hasattr(e, "read"):
                    print("Error details:", e.read().decode("utf-8"))
                return None

def format_arg(val):
    if val is None:
        return {"type": "null"}
    elif isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    elif isinstance(val, float):
        return {"type": "float", "value": val}
    elif isinstance(val, bytes):
        return {"type": "blob", "base64": base64.b64encode(val).decode("utf-8")}
    else:
        return {"type": "text", "value": str(val)}

def sync_upsert():
    print(f"Connecting to {LOCAL_DB}...")
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = cursor.fetchall()
    
    # 1. Ensure table schemas exist on Turso
    for name, sql in tables:
        if sql:
            execute_turso_batch([sql + ";"])
            
    print("Schema checked. Now performing INSERT OR REPLACE sync...")
    
    # 2. Sync all records using INSERT OR REPLACE
    for table_name, _ in tables:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        if not rows:
            continue
            
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        col_names = ", ".join([f'"{c}"' for c in columns])
        placeholders = ", ".join(["?" for _ in columns])
        sql_template = f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})"
        
        print(f"Syncing {len(rows)} rows into '{table_name}'...")
        
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            stmts = []
            for row in chunk:
                args = [format_arg(v) for v in row]
                stmts.append({
                    "sql": sql_template,
                    "args": args
                })
            execute_turso_batch(stmts)
            
    print("\n[SUCCESS] All data merged and synced to Turso cleanly!")
    conn.close()

if __name__ == "__main__":
    sync_upsert()
