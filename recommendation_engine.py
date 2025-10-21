#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Движок рекомендаций ставок для аукционов мотоциклов
Работает без AI, использует статистический анализ исторических данных
"""

import re
from typing import Dict, List, Any, Optional, Tuple


def parse_number(value: Any) -> Optional[float]:
    """Извлекает число из строки или возвращает None"""
    if value is None or value == '':
        return None
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        # Убираем пробелы, символы валют, запятые
        cleaned = value.replace(' ', '').replace('₽', '').replace('¥', '').replace(',', '').replace('км', '')
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    return None


def parse_int(value: Any) -> Optional[int]:
    """Извлекает целое число из строки или возвращает None"""
    num = parse_number(value)
    return int(num) if num is not None else None


def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """Рассчитывает перцентили без numpy (для легкости)"""
    if not values:
        return {}
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    
    def percentile(p: int) -> float:
        k = (n - 1) * p / 100.0
        f = int(k)
        c = f + 1 if f + 1 < n else f
        d0 = sorted_vals[f]
        d1 = sorted_vals[c]
        return d0 + (d1 - d0) * (k - f)
    
    return {
        'mean': sum(values) / len(values),
        'median': percentile(50),
        'p25': percentile(25),
        'p30': percentile(30),
        'p40': percentile(40),
        'p50': percentile(50),
        'p60': percentile(60),
        'p70': percentile(70),
        'max': max(values),
        'min': min(values)
    }


def filter_comparables(target_lot: Dict[str, Any], all_lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Фильтрует аналогичные лоты по критериям:
    - Точное совпадение модели
    - Год ±1
    - Пробег ±50%
    - Оценка ±1
    """
    target_model = target_lot.get('Наименование', '').strip()
    target_year = parse_int(target_lot.get('Год'))
    target_mileage = parse_int(target_lot.get('Пробег'))
    target_rating = parse_number(target_lot.get('Оценка'))
    
    comparables = []
    
    for lot in all_lots:
        # Точное совпадение модели
        lot_model = lot.get('Наименование', '').strip()
        if lot_model != target_model:
            continue
        
        # Парсим параметры лота
        lot_year = parse_int(lot.get('Год'))
        lot_mileage = parse_int(lot.get('Пробег'))
        lot_rating = parse_number(lot.get('Оценка'))
        
        # Фильтр по году ±1
        if target_year and lot_year:
            if abs(lot_year - target_year) > 1:
                continue
        
        # Фильтр по пробегу ±50%
        if target_mileage and lot_mileage:
            min_mileage = target_mileage * 0.5
            max_mileage = target_mileage * 1.5
            if lot_mileage < min_mileage or lot_mileage > max_mileage:
                continue
        
        # Фильтр по оценке ±1
        if target_rating and lot_rating:
            if abs(lot_rating - target_rating) > 1:
                continue
        
        # Проверяем наличие цен
        start_price = parse_number(lot.get('Стартовая цена (₽)'))
        final_price = parse_number(lot.get('Цена (₽)'))
        
        if start_price and final_price and start_price > 0:
            coefficient = final_price / start_price
            # Убираем аномальные выбросы (коэффициент > 1.5)
            if coefficient <= 1.5:
                comparables.append({
                    'lot': lot,
                    'coefficient': coefficient,
                    'start_price': start_price,
                    'final_price': final_price
                })
    
    return comparables


def choose_coefficient(target_lot: Dict[str, Any], stats: Dict[str, float], comparables_count: int) -> Tuple[float, List[float], str]:
    """
    Выбирает коэффициент на основе характеристик лота
    Возвращает: (коэффициент, [мин_диапазон, макс_диапазон], перцентиль)
    """
    target_rating = parse_number(target_lot.get('Оценка'))
    target_mileage = parse_int(target_lot.get('Пробег'))
    
    # Если аналогов мало - используем консервативный фоллбэк
    if comparables_count < 5:
        return 1.15, [1.10, 1.20], "fallback"
    
    # Применяем таблицу правил
    if target_rating and target_rating >= 7 and target_mileage and target_mileage <= 5000:
        # Высокое качество, малый пробег → p60
        return stats['p60'], [stats['p50'], stats['p70']], "p60"
    
    elif target_rating and target_rating >= 6 and target_mileage and target_mileage <= 5000:
        # Хорошее качество, малый пробег → p50 (медиана)
        return stats['p50'], [stats['p40'], stats['p60']], "p50"
    
    elif target_rating and target_rating >= 5 and target_mileage and target_mileage <= 5000:
        # Среднее качество, малый пробег → p40
        return stats['p40'], [stats['p30'], stats['p50']], "p40"
    
    elif target_rating and 5 <= target_rating <= 6 and target_mileage and 5000 < target_mileage <= 15000:
        # Среднее качество, средний пробег → p40
        return stats['p40'], [stats['p30'], stats['p50']], "p40"
    
    else:
        # Низкое качество или высокий пробег → p30 (консервативно)
        return stats['p30'], [stats['p25'], stats['p40']], "p30"


def generate_explanation(target_lot: Dict[str, Any], comparables: List[Dict[str, Any]], 
                        stats: Dict[str, float], chosen_coef: float, percentile: str) -> str:
    """Генерирует текстовое пояснение рекомендации"""
    model = target_lot.get('Наименование', 'Unknown')
    rating = target_lot.get('Оценка', '?')
    mileage = target_lot.get('Пробег', '?')
    year = target_lot.get('Год', '?')
    
    explanation = []
    
    explanation.append(f"Найдено {len(comparables)} аналогичных лотов модели {model}.")
    
    if len(comparables) < 5:
        explanation.append(f"Из-за малого количества данных используется консервативный коэффициент 1.15.")
    else:
        explanation.append(f"Медианный коэффициент роста цены: {stats['median']:.3f}.")
        explanation.append(f"Для данных характеристик (год {year}, пробег {mileage}, оценка {rating}) выбран перцентиль {percentile} = {chosen_coef:.3f}.")
    
    explanation.append(f"Рекомендуемая ставка учитывает исторические результаты торгов аналогичных мотоциклов.")
    
    return " ".join(explanation)


def generate_warnings(target_lot: Dict[str, Any], comparables: List[Dict[str, Any]], 
                      stats: Dict[str, float]) -> List[str]:
    """Генерирует предупреждения"""
    warnings = []
    
    if len(comparables) < 5:
        warnings.append(f"Мало аналогов ({len(comparables)} шт.). Рекомендация может быть неточной.")
    
    if len(comparables) >= 5:
        spread = stats['max'] - stats['min']
        if spread > 0.5:
            warnings.append(f"Высокая волатильность цен (разброс {spread:.2f}). Торги могут быть непредсказуемыми.")
    
    target_rating = parse_number(target_lot.get('Оценка'))
    if target_rating and target_rating < 4:
        warnings.append("Низкая оценка состояния. Возможны скрытые дефекты.")
    
    target_mileage = parse_int(target_lot.get('Пробег'))
    if target_mileage and target_mileage > 50000:
        warnings.append("Высокий пробег. Учитывайте износ и стоимость обслуживания.")
    
    return warnings


def filter_comparables_by_final_price(target_lot: Dict[str, Any], all_lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Фильтрует аналогичные лоты по тем же критериям, но учитывая только финальную цену
    Используется когда стартовая цена целевого лота отсутствует
    """
    target_model = target_lot.get('Наименование', '').strip()
    target_year = parse_int(target_lot.get('Год'))
    target_mileage = parse_int(target_lot.get('Пробег'))
    target_rating = parse_number(target_lot.get('Оценка'))
    
    comparables = []
    
    for lot in all_lots:
        # Точное совпадение модели
        lot_model = lot.get('Наименование', '').strip()
        if lot_model != target_model:
            continue
        
        # Парсим параметры лота
        lot_year = parse_int(lot.get('Год'))
        lot_mileage = parse_int(lot.get('Пробег'))
        lot_rating = parse_number(lot.get('Оценка'))
        
        # Фильтр по году ±1
        if target_year and lot_year:
            if abs(lot_year - target_year) > 1:
                continue
        
        # Фильтр по пробегу ±50%
        if target_mileage and lot_mileage:
            min_mileage = target_mileage * 0.5
            max_mileage = target_mileage * 1.5
            if lot_mileage < min_mileage or lot_mileage > max_mileage:
                continue
        
        # Фильтр по оценке ±1
        if target_rating and lot_rating:
            if abs(lot_rating - target_rating) > 1:
                continue
        
        # Проверяем наличие финальной цены
        final_price = parse_number(lot.get('Цена (₽)'))
        
        if final_price and final_price > 0:
            comparables.append({
                'lot': lot,
                'final_price': final_price
            })
    
    return comparables


def calculate_recommendation_without_start_price(target_lot: Dict[str, Any], all_lots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Альтернативный алгоритм расчета когда стартовая цена отсутствует
    Использует прямые финальные цены из аналогов
    """
    
    # Фильтруем аналоги
    comparables = filter_comparables_by_final_price(target_lot, all_lots)
    
    if not comparables:
        return {
            'error': 'Стартовая цена отсутствует, аналогов не найдено',
            'recommended_bid_min': 0,
            'recommended_bid_optimal': 0,
            'recommended_bid_max': 0,
            'warnings': ['Невозможно рассчитать рекомендацию без стартовой цены и аналогов']
        }
    
    # Собираем финальные цены
    final_prices = [c['final_price'] for c in comparables]
    
    if not final_prices:
        return {
            'error': 'Стартовая цена отсутствует, у аналогов нет финальных цен',
            'recommended_bid_min': 0,
            'recommended_bid_optimal': 0,
            'recommended_bid_max': 0,
            'warnings': ['У найденных аналогов отсутствуют финальные цены']
        }
    
    # Рассчитываем статистику по финальным ценам
    sorted_prices = sorted(final_prices)
    n = len(sorted_prices)
    
    def percentile(p: int) -> float:
        k = (n - 1) * p / 100.0
        f = int(k)
        c = f + 1 if f + 1 < n else f
        d0 = sorted_prices[f]
        d1 = sorted_prices[c]
        return d0 + (d1 - d0) * (k - f)
    
    target_rating = parse_number(target_lot.get('Оценка'))
    target_mileage = parse_int(target_lot.get('Пробег'))
    
    # Выбираем перцентиль на основе качества
    if target_rating and target_rating >= 7 and target_mileage and target_mileage <= 5000:
        recommended_bid = percentile(60)
        band = [percentile(50), percentile(70)]
        perc = "p60"
    elif target_rating and target_rating >= 6:
        recommended_bid = percentile(50)
        band = [percentile(40), percentile(60)]
        perc = "p50"
    elif target_rating and target_rating >= 5:
        recommended_bid = percentile(40)
        band = [percentile(30), percentile(50)]
        perc = "p40"
    else:
        recommended_bid = percentile(30)
        band = [percentile(25), percentile(40)]
        perc = "p30"
    
    explanation = (
        f"Стартовая цена отсутствует. "
        f"Рекомендация основана на финальных ценах {len(comparables)} аналогичных лотов. "
        f"Медианная цена продажи: {percentile(50):,.0f} руб. "
        f"Использован перцентиль {perc}."
    )
    
    warnings = [
        "ВНИМАНИЕ: Стартовая цена отсутствует - рекомендация основана только на финальных ценах аналогов",
        "Точность оценки может быть ниже обычной"
    ]
    
    if len(comparables) < 5:
        warnings.append(f"Мало аналогов ({len(comparables)} шт.) - результат может быть неточным")
    
    if len(comparables) >= 5:
        spread = max(final_prices) - min(final_prices)
        if spread > percentile(50) * 0.3:
            warnings.append(f"Высокая волатильность цен аналогов (разброс {spread:,.0f} руб)")
    
    if target_rating and target_rating < 4:
        warnings.append("Низкая оценка состояния - возможны скрытые дефекты")
    
    if target_mileage and target_mileage > 50000:
        warnings.append("Высокий пробег - учитывайте износ")
    
    target_year = parse_int(target_lot.get('Год'))
    
    return {
        'recommended_bid_min': round(band[0], 2),
        'recommended_bid_optimal': round(recommended_bid, 2),
        'recommended_bid_max': round(band[1], 2),
        'chosen_coefficient': None,
        'coefficient_band': None,
        'percentile_used': perc,
        'comparables_used': len(comparables),
        'explanation': explanation,
        'filters': {
            'model_filter': target_lot.get('Наименование', ''),
            'year_range': [target_year - 1, target_year + 1] if target_year else None,
            'mileage_rule': f"±50% от {target_mileage}" if target_mileage else "не применено",
            'rating_rule': f"±1 от {target_rating}" if target_rating else "не применено"
        },
        'stats': {
            'final_price_mean': round(sum(final_prices) / len(final_prices), 2),
            'final_price_median': round(percentile(50), 2),
            'final_price_min': round(min(final_prices), 2),
            'final_price_max': round(max(final_prices), 2)
        },
        'warnings': warnings,
        'alternative_algorithm': True
    }


def calculate_recommendation(target_lot: Dict[str, Any], all_lots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Главная функция расчета рекомендации
    
    Args:
        target_lot: Целевой лот для анализа
        all_lots: Все исторические лоты из базы данных
    
    Returns:
        Словарь с рекомендациями и статистикой
    """
    
    # Парсим стартовую цену целевого лота
    start_price = parse_number(target_lot.get('Стартовая цена (₽)'))
    
    # Если стартовая цена отсутствует - используем альтернативный алгоритм
    if not start_price or start_price <= 0:
        return calculate_recommendation_without_start_price(target_lot, all_lots)
    
    # Фильтруем аналоги
    comparables = filter_comparables(target_lot, all_lots)
    
    # Извлекаем коэффициенты
    coefficients = [c['coefficient'] for c in comparables]
    
    # Рассчитываем статистику
    if coefficients:
        stats = calculate_percentiles(coefficients)
    else:
        # Нет аналогов - используем фоллбэк
        stats = {
            'mean': 1.15,
            'median': 1.15,
            'p25': 1.10,
            'p30': 1.12,
            'p40': 1.13,
            'p50': 1.15,
            'p60': 1.17,
            'p70': 1.18,
            'max': 1.20,
            'min': 1.10
        }
    
    # Выбираем коэффициент на основе характеристик
    chosen_coef, band, percentile_used = choose_coefficient(target_lot, stats, len(comparables))
    
    # Рассчитываем рекомендуемые ставки
    recommended_bid_min = start_price * band[0]
    recommended_bid_optimal = start_price * chosen_coef
    recommended_bid_max = start_price * band[1]
    
    # Генерируем пояснение
    explanation = generate_explanation(target_lot, comparables, stats, chosen_coef, percentile_used)
    
    # Генерируем предупреждения
    warnings = generate_warnings(target_lot, comparables, stats)
    
    # Формируем данные о фильтрах
    target_year = parse_int(target_lot.get('Год'))
    target_mileage = parse_int(target_lot.get('Пробег'))
    target_rating = parse_number(target_lot.get('Оценка'))
    
    filters = {
        'model_filter': target_lot.get('Наименование', ''),
        'year_range': [target_year - 1, target_year + 1] if target_year else None,
        'mileage_rule': f"±50% от {target_mileage}" if target_mileage else "не применено",
        'rating_rule': f"±1 от {target_rating}" if target_rating else "не применено"
    }
    
    return {
        'recommended_bid_min': round(recommended_bid_min, 2),
        'recommended_bid_optimal': round(recommended_bid_optimal, 2),
        'recommended_bid_max': round(recommended_bid_max, 2),
        'chosen_coefficient': round(chosen_coef, 4),
        'coefficient_band': [round(band[0], 4), round(band[1], 4)],
        'percentile_used': percentile_used,
        'comparables_used': len(comparables),
        'explanation': explanation,
        'filters': filters,
        'stats': {
            'coef_mean': round(stats['mean'], 4),
            'coef_median': round(stats['median'], 4),
            'coef_p25': round(stats['p25'], 4),
            'coef_p30': round(stats['p30'], 4),
            'coef_p40': round(stats['p40'], 4),
            'coef_p50': round(stats['p50'], 4),
            'coef_p60': round(stats['p60'], 4),
            'coef_p70': round(stats['p70'], 4),
            'coef_max': round(stats['max'], 4)
        },
        'warnings': warnings
    }


if __name__ == '__main__':
    # Простой тест
    test_lot = {
        'Наименование': 'Ducati DESERT X',
        'Год': '2023',
        'Пробег': '4 471',
        'Оценка': '5',
        'Стартовая цена (₽)': '1 173 506'
    }
    
    test_history = [
        {
            'Наименование': 'Ducati DESERT X',
            'Год': '2023',
            'Пробег': '3 000',
            'Оценка': '5',
            'Стартовая цена (₽)': '1 100 000',
            'Цена (₽)': '1 200 000'
        },
        {
            'Наименование': 'Ducati DESERT X',
            'Год': '2023',
            'Пробег': '5 000',
            'Оценка': '6',
            'Стартовая цена (₽)': '1 150 000',
            'Цена (₽)': '1 300 000'
        }
    ]
    
    result = calculate_recommendation(test_lot, test_history)
    
    print("\n" + "="*70)
    print("ТЕСТ: Рекомендация ставки")
    print("="*70)
    print(f"Модель: {test_lot['Наименование']}")
    print(f"Стартовая цена: {test_lot['Стартовая цена (₽)']}")
    print(f"\nРекомендуемые ставки:")
    print(f"  Минимум:  {result['recommended_bid_min']:,.0f}")
    print(f"  Оптимум:  {result['recommended_bid_optimal']:,.0f}")
    print(f"  Максимум: {result['recommended_bid_max']:,.0f}")
    print(f"\nКоэффициент: {result['chosen_coefficient']}")
    print(f"Использовано аналогов: {result['comparables_used']}")
    print(f"\nПояснение:\n{result['explanation']}")
    print("="*70 + "\n")

