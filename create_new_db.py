import sqlite3

# Создаем новую базу данных
conn = sqlite3.connect('lots.db')
cursor = conn.cursor()

# Создаем таблицу с правильной структурой
cursor.execute('''
CREATE TABLE IF NOT EXISTS lots (
    Name TEXT,
    "Date-auc" TEXT,
    Place TEXT,
    "Num-lot" TEXT,
    Year TEXT,
    Probeg TEXT,
    Vol TEXT,
    Ozenka TEXT,
    Status TEXT,
    "Start-price-jap" TEXT,
    "Start-price-rub" TEXT,
    "Real-prize-jap" TEXT,
    "Real-prize-rub" TEXT,
    "Auc-stat" TEXT,
    Url TEXT
)
''')

# Создаем индексы для быстрого поиска
cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON lots (Name)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON lots ("Date-auc")')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_year ON lots (Year)')

conn.commit()
conn.close()

print("OK: Database lots.db created successfully!")
print("\nTable structure:")
print("  - Name")
print("  - Date-auc")
print("  - Place")
print("  - Num-lot")
print("  - Year")
print("  - Probeg")
print("  - Vol")
print("  - Ozenka")
print("  - Status")
print("  - Start-price-jap")
print("  - Start-price-rub")
print("  - Real-prize-jap")
print("  - Real-prize-rub")
print("  - Auc-stat")
print("  - Url")

