import sqlite3
DB = 'leer_mexico.db'
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Tables:")
for row in c.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view');"):
    print(" ", row)

print("\nUsers table DDL (if exists):")
for row in c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='Users';"):
    print(row[0])

print("\nUsers columns:")
for row in c.execute("PRAGMA table_info('Users');"):
    # cid, name, type, notnull, dflt_value, pk
    print(" ", row)

print("\nSample rows (id, name, phone, email):")
for row in c.execute("SELECT id, name, phone, email FROM Users ORDER BY id DESC LIMIT 10;"):
    print(" ", row)

print("\nTransactions table DDL (if exists):")
for row in c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='Transactions';"):
    print(row[0])

print("\nUsers columns:")
for row in c.execute("PRAGMA table_info('Transactions');"):
    # cid, name, type, notnull, dflt_value, pk
    print(" ", row)

# print("\nSample rows (id, name, phone, email):")
# for row in c.execute("SELECT id, name, phone, email FROM Users ORDER BY id DESC LIMIT 10;"):
#    print(" ", row)
conn.close()