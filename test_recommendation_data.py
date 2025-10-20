#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки данных из lots.db для системы рекомендаций
"""

import sqlite3
import sys
import io

# Исправление кодировки для Windows консоли
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB_FILE = 'lots.db'

def test_data():
    """Проверяет данные в новой базе для AI рекомендаций"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Проверяем общее количество записей
        cursor.execute('SELECT COUNT(*) FROM lots')
        total_count = cursor.fetchone()[0]
        print(f"\n{'='*70}")
        print(f"Общее количество записей в lots.db: {total_count}")
        print(f"{'='*70}\n")
        
        # Проверяем записи с заполненными ценами
        cursor.execute('''
            SELECT COUNT(*) FROM lots
            WHERE "Real-prize-rub" IS NOT NULL 
            AND "Real-prize-rub" != ''
            AND "Start-price-rub" IS NOT NULL
            AND "Start-price-rub" != ''
        ''')
        valid_count = cursor.fetchone()[0]
        print(f"Записей с заполненными ценами: {valid_count}")
        print(f"{'='*70}\n")
        
        if valid_count == 0:
            print("⚠️  ВНИМАНИЕ: В базе нет записей с заполненными ценами!")
            print("   Необходимо спарсить данные с сайта.\n")
            conn.close()
            return
        
        # Выбираем несколько примеров для проверки
        cursor.execute('''
            SELECT Name, Year, Probeg, Ozenka, "Start-price-rub", "Real-prize-rub"
            FROM lots
            WHERE "Real-prize-rub" IS NOT NULL 
            AND "Real-prize-rub" != ''
            AND "Start-price-rub" IS NOT NULL
            AND "Start-price-rub" != ''
            LIMIT 10
        ''')
        
        rows = cursor.fetchall()
        
        print("Примеры записей для AI рекомендаций:\n")
        for i, row in enumerate(rows, 1):
            print(f"{i}. Модель: {row[0]}")
            print(f"   Год: {row[1]}")
            print(f"   Пробег: {row[2]}")
            print(f"   Оценка: {row[3]}")
            print(f"   Стартовая цена: {row[4]}")
            print(f"   Финальная цена: {row[5]}")
            
            # Проверяем, что можем извлечь числа из цен
            try:
                start_price_str = row[4].replace(' ', '').replace('₽', '').replace(',', '')
                final_price_str = row[5].replace(' ', '').replace('₽', '').replace(',', '')
                
                start_price = float(start_price_str)
                final_price = float(final_price_str)
                
                if start_price > 0:
                    coefficient = final_price / start_price
                    print(f"   Коэффициент: {coefficient:.3f}")
                else:
                    print(f"   ⚠️  Стартовая цена = 0")
                    
            except Exception as e:
                print(f"   ⚠️  Ошибка парсинга цен: {e}")
            
            print()
        
        # Статистика по моделям
        cursor.execute('''
            SELECT Name, COUNT(*) as cnt
            FROM lots
            WHERE "Real-prize-rub" IS NOT NULL 
            AND "Real-prize-rub" != ''
            GROUP BY Name
            ORDER BY cnt DESC
            LIMIT 10
        ''')
        
        models = cursor.fetchall()
        print(f"{'='*70}")
        print("Топ-10 моделей в базе:")
        print(f"{'='*70}\n")
        for model, count in models:
            print(f"  {model}: {count} лотов")
        
        conn.close()
        
        print(f"\n{'='*70}")
        print("✓ Тест завершен успешно!")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_data()

