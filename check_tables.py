import sqlite3
import sys

db_file = 'lots_multi_20251017_142157.db'

print(f"\n{'='*70}")
print(f"ПРОВЕРКА ТАБЛИЦ В БАЗЕ ДАННЫХ")
print(f"{'='*70}")
print(f"База: {db_file}\n")

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Проверяем таблицы
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print(f"Таблиц в базе: {len(tables)}")
for table in tables:
    print(f"  - {table[0]}")

print(f"\n{'='*70}")

# Статистика по таблице lots_backup
if any('lots_backup' in t for t in tables):
    print("ТАБЛИЦА 'lots_backup' (бекап старых данных):")
    print(f"{'='*70}")
    
    cursor.execute('SELECT COUNT(*) FROM lots_backup')
    backup_count = cursor.fetchone()[0]
    print(f"Записей: {backup_count}")
    
    cursor.execute('SELECT "Наименование", COUNT(*) as cnt FROM lots_backup GROUP BY "Наименование"')
    models = cursor.fetchall()
    print(f"\nМодели в бекапе:")
    for model, count in models:
        print(f"  {model}: {count}")

print(f"\n{'='*70}")

# Статистика по таблице lots
print("ТАБЛИЦА 'lots' (все данные):")
print(f"{'='*70}")

cursor.execute('SELECT COUNT(*) FROM lots')
total_count = cursor.fetchone()[0]
print(f"Всего записей: {total_count}")

cursor.execute('SELECT "Наименование", COUNT(*) as cnt FROM lots GROUP BY "Наименование" ORDER BY cnt DESC')
models = cursor.fetchall()
print(f"\nМодели:")
for model, count in models:
    print(f"  {model}: {count}")

# Статистика по годам
print(f"\n{'='*70}")
print("СТАТИСТИКА ПО ГОДАМ:")
print(f"{'='*70}")

cursor.execute('SELECT "Год", COUNT(*) as cnt FROM lots GROUP BY "Год" ORDER BY "Год" DESC')
years = cursor.fetchall()
for year, count in years:
    print(f"  {year}: {count}")

# Последние добавленные лоты
print(f"\n{'='*70}")
print("ПОСЛЕДНИЕ 5 ЗАПИСЕЙ:")
print(f"{'='*70}")

cursor.execute('SELECT "Наименование", "Дата аукциона", "Год", "Пробег" FROM lots ORDER BY rowid DESC LIMIT 5')
recent = cursor.fetchall()
for i, (model, date, year, mileage) in enumerate(recent, 1):
    print(f"\n{i}. {model}")
    print(f"   Дата: {date}, Год: {year}, Пробег: {mileage}")

conn.close()

print(f"\n{'='*70}")
print("ПРОВЕРКА ЗАВЕРШЕНА")
print(f"{'='*70}\n")


