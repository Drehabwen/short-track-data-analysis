import sqlite3
from datetime import datetime

conn = sqlite3.connect(r'C:\Users\labops\.codex\logs_2.sqlite')
cur = conn.cursor()
rows = cur.execute("""
    SELECT ts, feedback_log_body FROM logs
    WHERE feedback_log_body LIKE '%responses_websocket%' AND level='ERROR'
    ORDER BY ts DESC LIMIT 3
""").fetchall()
for r in rows:
    print(f'[{datetime.fromtimestamp(r[0]).strftime("%H:%M:%S")}]')
    print(r[1][:1200])
    print('---')
conn.close()
