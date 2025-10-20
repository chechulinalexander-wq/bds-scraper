#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест движка рекомендаций без AI
"""

import sys
import io
import sqlite3
from recommendation_engine import calculate_recommendation, parse_number

# Исправление кодировки для Windows консоли
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB_FILE = 'lots.db'


def get_all_lots_from_db():
    """Загружает все лоты из базы"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT Name, Year, Probeg, Ozenka, "Start-price-rub", "Real-prize-rub"
            FROM lots
            WHERE "Real-prize-rub" IS NOT NULL 
            AND "Real-prize-rub" != ''
            AND "Start-price-rub" IS NOT NULL
            AND "Start-price-rub" != ''
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        lots = []
        for row in rows:
            lots.append({
                'Наименование': row[0] if row[0] else '',
                'Год': row[1] if row[1] else '',
                'Пробег': row[2] if row[2] else '',
                'Оценка': row[3] if row[3] else '',
                'Стартовая цена (₽)': row[4] if row[4] else '',
                'Цена (₽)': row[5] if row[5] else ''
            })
        
        return lots
    except Exception as e:
        print(f"❌ Ошибка загрузки из БД: {e}")
        return []


def test_with_real_data():
    """Тест с реальными данными из базы"""
    print("\n" + "="*70)
    print("ТЕСТ: Рекомендация ставки (Реальные данные из БД)")
    print("="*70)
    
    # Загружаем все лоты
    all_lots = get_all_lots_from_db()
    
    if not all_lots:
        print("❌ Нет данных в БД. Запустите парсинг сначала.")
        return
    
    print(f"✓ Загружено {len(all_lots)} лотов из БД\n")
    
    # Тестовый лот 1: Ducati DESERT X
    test_lot_1 = {
        'Наименование': 'Ducati DESERT X',
        'Год': '2023',
        'Пробег': '4 471',
        'Оценка': '5',
        'Стартовая цена (₽)': '1 173 506'
    }
    
    print("Тест 1: Ducati DESERT X")
    print("-" * 70)
    print(f"Модель: {test_lot_1['Наименование']}")
    print(f"Год: {test_lot_1['Год']}")
    print(f"Пробег: {test_lot_1['Пробег']} км")
    print(f"Оценка: {test_lot_1['Оценка']}")
    print(f"Стартовая цена: {test_lot_1['Стартовая цена (₽)']} ₽")
    print()
    
    result = calculate_recommendation(test_lot_1, all_lots)
    
    if 'error' in result:
        print(f"❌ Ошибка: {result['error']}")
    else:
        print("РЕЗУЛЬТАТ:")
        print(f"  Минимум:  {result['recommended_bid_min']:,.0f} ₽")
        print(f"  Оптимум:  {result['recommended_bid_optimal']:,.0f} ₽")
        print(f"  Максимум: {result['recommended_bid_max']:,.0f} ₽")
        print()
        print(f"Коэффициент: {result['chosen_coefficient']:.4f}")
        print(f"Диапазон: [{result['coefficient_band'][0]:.4f}, {result['coefficient_band'][1]:.4f}]")
        print(f"Перцентиль: {result['percentile_used']}")
        print(f"Использовано аналогов: {result['comparables_used']}")
        print()
        print(f"Пояснение:\n{result['explanation']}")
        print()
        
        if result['warnings']:
            print("⚠️  Предупреждения:")
            for w in result['warnings']:
                print(f"  - {w}")
            print()
        
        print("Статистика по аналогам:")
        stats = result['stats']
        print(f"  Среднее:  {stats['coef_mean']:.4f}")
        print(f"  Медиана:  {stats['coef_median']:.4f}")
        print(f"  p25:      {stats['coef_p25']:.4f}")
        print(f"  p50:      {stats['coef_p50']:.4f}")
        print(f"  p70:      {stats['coef_p70']:.4f}")
        print(f"  Макс:     {stats['coef_max']:.4f}")
    
    print("="*70)
    print()


def test_edge_cases():
    """Тест граничных случаев"""
    print("\n" + "="*70)
    print("ТЕСТ: Граничные случаи")
    print("="*70)
    
    # Тест 1: Нет стартовой цены
    test_1 = {
        'Наименование': 'Test Model',
        'Год': '2023',
        'Пробег': '5000',
        'Оценка': '5',
        'Стартовая цена (₽)': ''
    }
    
    result = calculate_recommendation(test_1, [])
    print("Тест 1 - Нет стартовой цены:")
    if 'error' in result:
        print(f"  ✓ Правильно обработана ошибка: {result['error']}")
    else:
        print(f"  ❌ Должна быть ошибка!")
    print()
    
    # Тест 2: Нет аналогов
    test_2 = {
        'Наименование': 'Очень редкая модель XXX',
        'Год': '2023',
        'Пробег': '5000',
        'Оценка': '5',
        'Стартовая цена (₽)': '1000000'
    }
    
    result = calculate_recommendation(test_2, [])
    print("Тест 2 - Нет аналогов (фоллбэк):")
    if 'error' not in result:
        print(f"  ✓ Коэффициент: {result['chosen_coefficient']:.4f}")
        print(f"  ✓ Перцентиль: {result['percentile_used']}")
        print(f"  ✓ Аналогов: {result['comparables_used']}")
        if result['percentile_used'] == 'fallback':
            print(f"  ✓ Правильно применен фоллбэк!")
    else:
        print(f"  ❌ Ошибка: {result['error']}")
    print()
    
    print("="*70)


def test_parsing():
    """Тест функций парсинга"""
    print("\n" + "="*70)
    print("ТЕСТ: Парсинг чисел")
    print("="*70)
    
    tests = [
        ('1 173 506', 1173506.0),
        ('1 173 506 ₽', 1173506.0),
        ('4 471 км', 4471.0),
        ('5', 5.0),
        ('', None),
        (None, None),
        (12345, 12345.0),
    ]
    
    for value, expected in tests:
        result = parse_number(value)
        status = "✓" if result == expected else "❌"
        print(f"{status} parse_number({repr(value)}) = {result} (ожидалось {expected})")
    
    print("="*70)


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🧪 ТЕСТИРОВАНИЕ ДВИЖКА РЕКОМЕНДАЦИЙ БЕЗ AI")
    print("="*70)
    
    # Запускаем все тесты
    test_parsing()
    test_edge_cases()
    test_with_real_data()
    
    print("\n" + "="*70)
    print("✅ Все тесты завершены!")
    print("="*70 + "\n")

