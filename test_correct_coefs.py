# -*- coding: utf-8 -*-
import sqlite3
import re

DB_FILE = 'lots_multi_20251017_142157.db'

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Используем ПРАВИЛЬНЫЕ колонки
cursor.execute('''
    SELECT "Наименование", "Год", "Пробег", "Оценка", "Статус аукциона", "Цена (¥)"
    FROM lots
    WHERE "Наименование" LIKE "%DESERT X%"
    LIMIT 10
''')

def parse_price(price_str):
    if not price_str:
        return None
    numbers = re.sub(r'[^\d]', '', str(price_str))
    if numbers:
        return float(numbers)
    return None

with open('correct_coefs.txt', 'w', encoding='utf-8') as f:
    f.write("DUCATI DESERT X - ПРАВИЛЬНЫЕ КОЭФФИЦИЕНТЫ:\n")
    f.write("=" * 80 + "\n\n")
    
    coefs = []
    for row in cursor.fetchall():
        name, year, mileage, rating, start_price_str, final_price_str = row
        
        start = parse_price(start_price_str)
        final = parse_price(final_price_str)
        
        if start and final and start > 0:
            coef = final / start
            coefs.append(coef)
            
            f.write(f"Пробег: {mileage}, Оценка: {rating}\n")
            f.write(f"  Старт: {start:,.0f} ₽\n")
            f.write(f"  Финал: {final:,.0f} ₽\n")
            f.write(f"  Коэф: {coef:.3f}\n\n")
    
    if coefs:
        coefs.sort()
        f.write("\nСТАТИСТИКА:\n")
        f.write(f"Минимум: {min(coefs):.3f}\n")
        f.write(f"Максимум: {max(coefs):.3f}\n")
        f.write(f"Медиана: {coefs[len(coefs)//2]:.3f}\n")
        f.write(f"Среднее: {sum(coefs)/len(coefs):.3f}\n")

conn.close()
print("Записано в correct_coefs.txt")

