#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой HTTP сервер для BDS Scraper
Запуск: python server.py
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from urllib.parse import parse_qs
import os

DB_FILE = 'lots_multi_20251017_142157.db'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_start_prices(lot_url):
    """Получает стартовые цены из карточки лота"""
    try:
        response = requests.get(lot_url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        buy_block = soup.find('div', class_='b-product-buy')
        if not buy_block:
            return '', ''
        
        start_block = buy_block.find('div', class_='b-product-buy__start')
        if not start_block:
            return '', ''
        
        price_yen = ''
        price_rub = ''
        
        price_items = start_block.find_all('div', class_='b-product-price__item')
        for price_item in price_items:
            if '_yen' in price_item.get('class', []):
                price_yen = price_item.text.strip()
            elif '_rur' in price_item.get('class', []):
                price_rub = price_item.text.strip()
        
        return price_yen, price_rub
        
    except Exception as e:
        return '', ''

def check_duplicate(conn, auction_date, auction_house, lot_number):
    """Проверяет существование записи в базе"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM lots 
        WHERE "Дата аукциона" = ? AND "Аукционный дом" = ? AND "Номер лота" = ?
    ''', (auction_date, auction_house, lot_number))
    count = cursor.fetchone()[0]
    return count > 0

def parse_url(url):
    """Парсит все лоты по URL"""
    results = {
        'total': 0,
        'new': 0,
        'duplicates': 0,
        'errors': 0,
        'lots': []
    }
    
    conn = sqlite3.connect(DB_FILE)
    page = 1
    
    while True:
        if page == 1:
            current_url = url
        else:
            if '?' in url:
                base_url = url.split('?')[0]
                params = '?' + url.split('?')[1]
                current_url = f"{base_url}page/{page}/{params}"
            else:
                current_url = f"{url}page/{page}/"
        
        try:
            response = requests.get(current_url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            product_items = soup.find_all('div', class_='b-product-item')
            
            if not product_items:
                break
            
            for item in product_items:
                if 'wpa_subscribe' in item.get('class', []):
                    continue
                
                try:
                    results['total'] += 1
                    
                    lot_link = item.find('a', class_='b-product-item__href')
                    lot_url = ''
                    if lot_link and lot_link.get('href'):
                        lot_url = 'https://cemeco.ru' + lot_link['href']
                    
                    brand = item.find('div', class_='b-product-title__brand')
                    model = item.find('div', class_='b-product-title__model')
                    
                    brand_text = brand.text.strip() if brand else ''
                    model_text = model.text.strip() if model else ''
                    
                    full_name = f"{brand_text} {model_text}".strip()
                    
                    item_params = {}
                    param_table = item.find('table', class_='b-product-params')
                    if param_table:
                        rows = param_table.find_all('tr')
                        for row in rows:
                            cells = row.find_all('td')
                            if len(cells) == 2:
                                key = cells[0].text.strip().rstrip(':')
                                value = cells[1].text.strip()
                                item_params[key] = value
                    
                    crumbs = item.find_all('li', class_='b-product-crumbs__item')
                    auction_date = crumbs[0].text.strip() if len(crumbs) > 0 else ''
                    auction_house = crumbs[1].text.strip() if len(crumbs) > 1 else ''
                    lot_number = crumbs[2].text.strip() if len(crumbs) > 2 else ''
                    
                    if check_duplicate(conn, auction_date, auction_house, lot_number):
                        results['duplicates'] += 1
                        continue
                    
                    status_div = item.find('div', class_='b-product-status')
                    status = status_div.text.strip() if status_div else ''
                    
                    price_items = item.find_all('div', class_='b-product-price__item')
                    price_yen = ''
                    price_rub = ''
                    for price_item in price_items:
                        if '_yen' in price_item.get('class', []):
                            price_yen = price_item.text.strip()
                        elif '_rur' in price_item.get('class', []):
                            price_rub = price_item.text.strip()
                    
                    notice = item.find('div', class_='b-product-notice__text')
                    auction_status = notice.text.strip() if notice else ''
                    
                    start_price_yen = ''
                    start_price_rub = ''
                    if lot_url:
                        start_price_yen, start_price_rub = get_start_prices(lot_url)
                        time.sleep(0.3)
                    
                    lot_data = {
                        'Наименование': full_name,
                        'Дата аукциона': auction_date,
                        'Аукционный дом': auction_house,
                        'Номер лота': lot_number,
                        'Год': item_params.get('Год', ''),
                        'Пробег': item_params.get('Пробег', ''),
                        'Объем': item_params.get('Объем', ''),
                        'Оценка': item_params.get('Оценка', ''),
                        'Статус аукциона': auction_status,
                        'Статус': status,
                        'Цена (¥)': price_yen,
                        'Цена (₽)': price_rub,
                        'Стартовая цена (¥)': start_price_yen,
                        'Стартовая цена (₽)': start_price_rub,
                        'URL карточки': lot_url
                    }
                    
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO lots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        lot_data['Наименование'],
                        lot_data['Дата аукциона'],
                        lot_data['Аукционный дом'],
                        lot_data['Номер лота'],
                        lot_data['Год'],
                        lot_data['Пробег'],
                        lot_data['Объем'],
                        lot_data['Оценка'],
                        lot_data['Статус аукциона'],
                        lot_data['Статус'],
                        lot_data['Цена (¥)'],
                        lot_data['Цена (₽)'],
                        lot_data['Стартовая цена (¥)'],
                        lot_data['Стартовая цена (₽)'],
                        lot_data['URL карточки']
                    ))
                    conn.commit()
                    
                    results['new'] += 1
                    results['lots'].append(lot_data)
                    
                except Exception as e:
                    results['errors'] += 1
                    continue
            
            pagination = soup.find('div', class_='wp-pagenavi')
            if pagination:
                next_link = pagination.find('a', class_='next')
                if next_link and 'not_active' not in next_link.get('class', []):
                    page += 1
                    time.sleep(1)
                else:
                    break
            else:
                break
                
        except Exception as e:
            results['errors'] += 1
            break
    
    conn.close()
    return results

def get_stats():
    """Получает статистику из БД"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM lots')
        total_count = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT "Наименование", COUNT(*) as cnt 
            FROM lots 
            GROUP BY "Наименование" 
            ORDER BY cnt DESC 
            LIMIT 10
        ''')
        models_stats = cursor.fetchall()
        
        cursor.execute('''
            SELECT "Наименование", "Дата аукциона", "Год", "Пробег", "Цена (₽)" 
            FROM lots 
            ORDER BY rowid DESC 
            LIMIT 10
        ''')
        recent_lots = cursor.fetchall()
        
        conn.close()
        
        return {
            'total': total_count,
            'models': [{'name': m[0], 'count': m[1]} for m in models_stats],
            'recent': [
                {
                    'name': l[0],
                    'date': l[1],
                    'year': l[2],
                    'mileage': l[3],
                    'price': l[4]
                } for l in recent_lots
            ]
        }
    except Exception as e:
        return {'error': str(e)}

def get_all_lots():
    """Получает все лоты из БД для анализа"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT "Наименование", "Год", "Пробег", "Оценка", "Стартовая цена (₽)", "Цена (₽)"
            FROM lots
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        lots = []
        for row in rows:
            lots.append({
                'Наименование': row[0],
                'Год': row[1],
                'Пробег': row[2],
                'Оценка': row[3],
                'Стартовая цена (₽)': row[4],
                'Цена (₽)': row[5]
            })
        
        return lots
    except Exception as e:
        print(f"Ошибка получения лотов: {e}")
        return []

def get_openai_recommendation(target_lot, all_lots):
    """Получает рекомендацию от OpenAI"""
    try:
        import openai
        
        # Получаем API ключ из переменной окружения
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return {'error': 'OPENAI_API_KEY не установлен. Установите: set OPENAI_API_KEY=ваш_ключ'}
        
        client = openai.OpenAI(api_key=api_key)
        
        # Формируем промпт согласно алгоритму
        system_prompt = """Ты — аналитик аукционов, который рассчитывает оптимальную максимальную ставку на мотоцикл по историческим данным прошедших аукционов. Используй **только** эти поля:

* «Наименование»
* «Год» (или «Год выпуска»)
* «Пробег»
* «Оценка»
* «Стартовая цена (₽)»
* «Цена (₽)»

Никакие другие колонки игнорируй.

Результат должен быть точным, воспроизводимым и прозрачным: укажи, какие аналоги использовал, какие коэффициенты получил и почему выбрал именно такую ставку.

Верни **один** JSON-объект строго по схеме (всё должно быть внутри JSON, включая пояснение):

{
  "recommended_bid_min": number,
  "recommended_bid_optimal": number,
  "recommended_bid_max": number,
  "chosen_coefficient": number,
  "coefficient_band": [number, number],
  "percentile_used": "median|p60|p70|p75|p80|p85|fallback",
  "comparables_used": number,
  "explanation": string,
  "filters": {
    "model_filter": string,
    "year_range": [number, number],
    "mileage_rule": string,
    "rating_rule": string
  },
  "stats": {
    "coef_mean": number,
    "coef_median": number,
    "coef_p60": number,
    "coef_p70": number,
    "coef_p75": number,
    "coef_p80": number,
    "coef_p85": number,
    "coef_max": number
  },
  "warnings": [string]
}

В поле "explanation" добавь 4–6 строк краткого пояснения на русском (без лишних деталей, только смысл).

Алгоритм:

1. **Нормализация**: Преобразуй цены и пробег в числа
2. **Фильтр по модели**: Оставь только строки с похожей моделью
3. **Фильтр по году/пробегу/оценке**: Целевой Год ±1-2; пробег близкий; оценка >= target-1
4. **Расчёт коэффициентов**: Для каждого аналога Коэффициент = Цена(₽) / Стартовая(₽)
5. **Удаление выбросов**: По IQR методу
6. **Статистика**: mean, median, p60, p70, p75, p80, p85, max
7. **Выбор коэффициента**:
   - Оценка ≥7, пробег ≤2000км: p80, диапазон [p75, p85]
   - Оценка =5, пробег ≤2000км: p65, диапазон [p60, p75]
   - Пробег 2-7тыс, оценка ≥5: p70, диапазон [p60, p80]
   - Если аналогов <8: фоллбэк [1.42, 1.50] для оценки 7, [1.24, 1.30] для оценки 5
8. **Расчёт ставок**: Умножь стартовую цену на коэффициенты
9. **Проверка адекватности**: Если max слишком низкий, подними
10. **Возврат**: JSON с полем explanation внутри

Важно: 
- Используй только указанные поля, не притягивай внешние данные
- Весь ответ должен быть валидным JSON
- Пояснение помести в поле "explanation" внутри JSON"""

        user_message = f"""TARGET_LOT:
{json.dumps(target_lot, ensure_ascii=False, indent=2)}

TABLE (все прошедшие аукционы):
{json.dumps(all_lots[:1000], ensure_ascii=False)}

Рассчитай оптимальную ставку."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        
        # Парсим JSON из ответа
        try:
            # Сначала пробуем напрямую
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # Если не получилось, ищем JSON с учетом вложенности скобок
            try:
                start = result_text.find('{')
                if start == -1:
                    raise ValueError("JSON не найден в ответе")
                
                # Считаем скобки чтобы найти правильный конец JSON
                brace_count = 0
                end = start
                for i in range(start, len(result_text)):
                    if result_text[i] == '{':
                        brace_count += 1
                    elif result_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                
                if end > start:
                    json_text = result_text[start:end]
                    print(f"Извлечен JSON длиной {len(json_text)} символов")
                    result = json.loads(json_text)
                else:
                    raise ValueError("Не удалось найти корректные границы JSON")
                    
            except Exception as e:
                print(f"Ошибка парсинга JSON: {e}")
                print(f"Ответ от AI (первые 500 символов):\n{result_text[:500]}")
                if len(result_text) > 500:
                    print(f"Ответ от AI (последние 200 символов):\n{result_text[-200:]}")
                return {'error': f'Ошибка парсинга ответа AI: {str(e)}'}
        
        # Добавляем текстовое пояснение если его нет
        if 'explanation' not in result:
            result['explanation'] = "Анализ завершён на основе исторических данных аукционов."
        
        return result
        
    except ImportError:
        return {'error': 'OpenAI библиотека не установлена. Установите: pip install openai'}
    except Exception as e:
        return {'error': f'Ошибка OpenAI API: {str(e)}'}

class RequestHandler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            try:
                with open('index.html', 'r', encoding='utf-8') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
            except Exception as e:
                self.send_error(404, f'File not found: {str(e)}')
        
        elif self.path == '/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            stats = get_stats()
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/recommend':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            target_lot = data.get('target_lot', {})
            
            if not target_lot:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Целевой лот не указан'}, ensure_ascii=False).encode('utf-8'))
                return
            
            try:
                print(f"Получение рекомендации для: {target_lot.get('Наименование', 'Unknown')}")
                
                # Получаем все лоты из БД
                all_lots = get_all_lots()
                
                if not all_lots:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Не удалось загрузить данные из БД'}, ensure_ascii=False).encode('utf-8'))
                    return
                
                print(f"Загружено {len(all_lots)} лотов из БД")
                
                # Получаем рекомендацию от OpenAI
                recommendation = get_openai_recommendation(target_lot, all_lots)
                
                if 'error' in recommendation:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    response_json = json.dumps(recommendation, ensure_ascii=False)
                    self.wfile.write(response_json.encode('utf-8'))
                    print(f"Ошибка отправлена клиенту: {recommendation.get('error', 'Unknown')}")
                    return
                
                # Проверяем что recommendation это валидный dict и можно сериализовать в JSON
                try:
                    response_json = json.dumps(recommendation, ensure_ascii=False)
                    # Проверяем что JSON валидный - парсим обратно
                    test_parse = json.loads(response_json)
                    print(f"JSON валидация пройдена, длина: {len(response_json)} символов")
                except Exception as e:
                    print(f"Ошибка сериализации ответа: {e}")
                    error_response = json.dumps({'error': f'Ошибка формирования ответа: {str(e)}'}, ensure_ascii=False)
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(error_response.encode('utf-8'))
                    return
                
                # Отправляем ответ
                response_bytes = response_json.encode('utf-8')
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(response_bytes)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(response_bytes)
                
                print(f"Рекомендация отправлена: {recommendation.get('recommended_bid_optimal', 0):,.0f} ₽")
                print(f"Отправлено байт: {len(response_bytes)}, символов JSON: {len(response_json)}")
                print(f"Первые 100 символов: {response_json[:100]}")
                print(f"Последние 100 символов: {response_json[-100:]}")
                
            except Exception as e:
                print(f"Ошибка: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}, ensure_ascii=False).encode('utf-8'))
        
        elif self.path == '/parse':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            url = data.get('url', '').strip()
            
            if not url:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'URL не указан'}, ensure_ascii=False).encode('utf-8'))
                return
            
            if not url.startswith('https://cemeco.ru/stat/'):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'URL должен начинаться с https://cemeco.ru/stat/'}, ensure_ascii=False).encode('utf-8'))
                return
            
            try:
                print(f"Парсинг URL: {url}")
                results = parse_url(url)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(results, ensure_ascii=False).encode('utf-8'))
                
                print(f"Результат: найдено={results['total']}, добавлено={results['new']}, дубликатов={results['duplicates']}")
            except Exception as e:
                print(f"Ошибка: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        # Подавляем лишние логи
        pass

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'\n{"="*70}')
    print(f'BDS Scraper Server')
    print(f'{"="*70}')
    print(f'Сервер запущен на порту {port}')
    print(f'Откройте в браузере: index.html')
    print(f'База данных: {DB_FILE}')
    print(f'{"="*70}\n')
    print('Для остановки нажмите Ctrl+C\n')
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n\nСервер остановлен')
        httpd.server_close()

if __name__ == '__main__':
    run_server()


