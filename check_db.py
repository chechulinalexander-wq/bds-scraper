import sqlite3
import sys
import os

def check_database(db_file):
    """Проверяет содержимое SQLite базы данных"""
    
    if not os.path.exists(db_file):
        print(f"[ERROR] Файл {db_file} не найден!")
        return
    
    print(f"\n{'='*70}")
    print(f"ПРОВЕРКА БАЗЫ ДАННЫХ SQLITE")
    print(f"{'='*70}")
    print(f"Файл базы: {db_file}")
    print(f"Размер: {os.path.getsize(db_file)} байт")
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Получаем список таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n{'='*70}")
    print(f"ТАБЛИЦЫ В БАЗЕ:")
    print(f"{'='*70}")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Статистика по таблице lots
    cursor.execute('SELECT COUNT(*) FROM lots')
    total_count = cursor.fetchone()[0]
    
    print(f"\n{'='*70}")
    print(f"СТАТИСТИКА ТАБЛИЦЫ 'lots':")
    print(f"{'='*70}")
    print(f"  Всего записей: {total_count}")
    
    # Количество колонок
    cursor.execute("PRAGMA table_info(lots)")
    columns = cursor.fetchall()
    print(f"  Колонок: {len(columns)}")
    
    # Индексы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='lots'")
    indexes = cursor.fetchall()
    print(f"  Индексов: {len(indexes)}")
    
    # Первые 3 записи
    print(f"\n{'='*70}")
    print(f"ПРИМЕРЫ ЗАПИСЕЙ (первые 3):")
    print(f"{'='*70}")
    
    cursor.execute('SELECT * FROM lots LIMIT 3')
    rows = cursor.fetchall()
    
    for i, row in enumerate(rows, 1):
        print(f"\nЗапись #{i}:")
        print(f"  Модель: {row[0] if row[0] else '-'}")
        print(f"  Дата аукциона: {row[1] if row[1] else '-'}")
        print(f"  Год: {row[4] if row[4] else '-'}")
        print(f"  Пробег: {row[5] if row[5] else '-'}")
    
    # Статистика по статусам
    print(f"\n{'='*70}")
    print(f"СТАТИСТИКА ПО СТАТУСАМ:")
    print(f"{'='*70}")
    
    cursor.execute('SELECT "Статус", COUNT(*) as cnt FROM lots GROUP BY "Статус" ORDER BY cnt DESC')
    statuses = cursor.fetchall()
    for status, count in statuses:
        print(f"  {status}: {count}")
    
    # Статистика по годам
    print(f"\n{'='*70}")
    print(f"СТАТИСТИКА ПО ГОДАМ:")
    print(f"{'='*70}")
    
    cursor.execute('SELECT "Год", COUNT(*) as cnt FROM lots GROUP BY "Год" ORDER BY "Год" DESC')
    years = cursor.fetchall()
    for year, count in years:
        print(f"  {year}: {count}")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print(f"ПРОВЕРКА ЗАВЕРШЕНА")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_file = sys.argv[1]
    else:
        # Ищем последнюю созданную базу
        import glob
        db_files = glob.glob('lots_*.db')
        if db_files:
            db_file = max(db_files, key=os.path.getctime)
            print(f"Используется последняя база: {db_file}")
        else:
            print("Использование: python check_db.py <файл.db>")
            print("Или запустите без параметров для проверки последней базы")
            sys.exit(1)
    
    check_database(db_file)

