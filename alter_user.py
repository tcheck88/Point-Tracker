import sqlite3
DB='leer_mexico.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
stmts = [
 "ALTER TABLE Users ADD COLUMN email TEXT;",
 "ALTER TABLE Users ADD COLUMN parent_name TEXT;",
 "ALTER TABLE Users ADD COLUMN sms_consent INTEGER NOT NULL DEFAULT 0;",
 "ALTER TABLE Users ADD COLUMN merge_into INTEGER;",
 "ALTER TABLE Users ADD COLUMN merge_justification TEXT;"
]
for s in stmts:
    try:
        c.execute(s)
        print("OK:", s)
    except Exception as e:
        print("SKIP/ERR:", s, "->", e)
conn.commit()
conn.close()