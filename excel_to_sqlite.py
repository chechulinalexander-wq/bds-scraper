import pandas as pd
import sqlite3
import sys
import os

def convert_excel_to_sqlite(excel_file):
    """Конвертирует Excel файл в SQLite базу данных"""
    
    if not os.path.exists(excel_file):
        print(f"[ERROR] Файл {excel_file} не найден!")
        return
    
    print(f"\n{'='*70}")
    print(f"КОНВЕРТАЦИЯ EXCEL В SQLITE")
    print(f"{'='*70}")
    print(f"Входной файл: {excel_file}")
    
    # Читаем Excel
    print("\n[1/2] Чтение Excel файла...")
    df = pd.read_excel(excel_file, sheet_name='Лоты')
    print(f"    [OK] Прочитано строк: {len(df)}")
    
    # Создаем имя для SQLite базы
    db_file = excel_file.replace('.xlsx', '.db')
    
    # Сохраняем в SQLite
    print(f"\n[2/2] Создание SQLite базы данных...")
    conn = sqlite3.connect(db_file)
    
    # Сохраняем DataFrame в SQLite
    df.to_sql('lots', conn, if_exists='replace', index=False)
    
    # Создаем индексы для ускорения поиска
    cursor = conn.cursor()
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_model ON lots ("Наименование")')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_auction_date ON lots ("Дата аукциона")')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON lots ("Статус")')
    conn.commit()
    
    # Выводим статистику
    cursor.execute('SELECT COUNT(*) FROM lots')
    count = cursor.fetchone()[0]
    
    # Выводим структуру таблицы
    cursor.execute("PRAGMA table_info(lots)")
    columns = cursor.fetchall()
    
    conn.close()
    
    print(f"    [OK] SQLite база создана: {db_file}")
    print(f"    [OK] Записей в базе: {count}")
    
    print(f"\n{'='*70}")
    print(f"СТРУКТУРА ТАБЛИЦЫ 'lots':")
    print(f"{'='*70}")
    print(f"  Колонок в таблице: {len(columns)}")
    
    print(f"\n{'='*70}")
    print(f"КОНВЕРТАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
    print(f"{'='*70}")
    print(f"  Входной файл: {excel_file}")
    print(f"  Выходная база: {db_file}")
    print(f"  Записей: {count}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
    else:
        # Ищем последний созданный Excel файл
        import glob
        excel_files = glob.glob('lots_*.xlsx')
        if excel_files:
            excel_file = max(excel_files, key=os.path.getctime)
            print(f"Используется последний файл: {excel_file}")
        else:
            print("Использование: python excel_to_sqlite.py <файл.xlsx>")
            print("Или запустите без параметров для конвертации последнего файла")
            sys.exit(1)
    
    convert_excel_to_sqlite(excel_file)

