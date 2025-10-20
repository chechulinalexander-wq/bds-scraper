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

# Загружаем переменные из .env файла
try:
    from dotenv import load_dotenv
    # Определяем путь к .env файлу относительно текущего скрипта
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path)
    print(f"DEBUG: Загрузка .env из: {dotenv_path}", flush=True)
    api_key = os.environ.get('OPENAI_API_KEY', 'НЕ НАЙДЕН')
    if api_key != 'НЕ НАЙДЕН':
        print(f"DEBUG: API ключ загружен (начало): {api_key[:20]}...", flush=True)
    else:
        print(f"DEBUG: API ключ НЕ НАЙДЕН в окружении!", flush=True)
except ImportError:
    print("Warning: python-dotenv не установлен. Используйте переменные окружения.", flush=True)

DB_FILE = 'lots.db'

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

def check_duplicate(conn, date_auc, place, num_lot):
    """Проверяет существование записи в базе"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM lots 
        WHERE "Date-auc" = ? AND Place = ? AND "Num-lot" = ?
    ''', (date_auc, place, num_lot))
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
                    
                    name = f"{brand_text} {model_text}".strip()
                    
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
                    date_auc = crumbs[0].text.strip() if len(crumbs) > 0 else ''
                    place = crumbs[1].text.strip() if len(crumbs) > 1 else ''
                    num_lot = crumbs[2].text.strip() if len(crumbs) > 2 else ''
                    
                    if check_duplicate(conn, date_auc, place, num_lot):
                        results['duplicates'] += 1
                        continue
                    
                    status_div = item.find('div', class_='b-product-status')
                    status = status_div.text.strip() if status_div else ''
                    
                    # Цены из списка (ФИНАЛЬНЫЕ)
                    price_items = item.find_all('div', class_='b-product-price__item')
                    real_prize_jap = ''
                    real_prize_rub = ''
                    for price_item in price_items:
                        if '_yen' in price_item.get('class', []):
                            real_prize_jap = price_item.text.strip()
                        elif '_rur' in price_item.get('class', []):
                            real_prize_rub = price_item.text.strip()
                    
                    notice = item.find('div', class_='b-product-notice__text')
                    auc_stat = notice.text.strip() if notice else ''
                    
                    # Стартовые цены ИЗ КАРТОЧКИ ЛОТА
                    start_price_jap = ''
                    start_price_rub = ''
                    if lot_url:
                        start_price_jap, start_price_rub = get_start_prices(lot_url)
                        time.sleep(0.3)
                    
                    # Записываем в БД с НОВОЙ СТРУКТУРОЙ
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO lots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        name,                               # Name
                        date_auc,                          # Date-auc
                        place,                             # Place
                        num_lot,                           # Num-lot
                        item_params.get('Год', ''),       # Year
                        item_params.get('Пробег', ''),    # Probeg
                        item_params.get('Объем', ''),     # Vol
                        item_params.get('Оценка', ''),    # Ozenka
                        status,                            # Status
                        start_price_jap,                   # Start-price-jap
                        start_price_rub,                   # Start-price-rub
                        real_prize_jap,                    # Real-prize-jap
                        real_prize_rub,                    # Real-prize-rub
                        auc_stat,                          # Auc-stat
                        lot_url                            # Url
                    ))
                    conn.commit()
                    
                    results['new'] += 1
                    results['lots'].append({
                        'Наименование': name,
                        'Дата аукциона': date_auc,
                        'Год': item_params.get('Год', ''),
                        'Пробег': item_params.get('Пробег', ''),
                        'Цена (₽)': real_prize_rub
                    })
                    
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
            SELECT Name, COUNT(*) as cnt 
            FROM lots 
            GROUP BY Name 
            ORDER BY cnt DESC 
            LIMIT 10
        ''')
        models_stats = cursor.fetchall()
        
        cursor.execute('''
            SELECT Name, "Date-auc", Year, Probeg, "Real-prize-rub"
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
        
        # Выбираем данные из новой структуры lots.db
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
        print(f"Ошибка получения лотов: {e}")
        import traceback
        traceback.print_exc()
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
        system_prompt = """Ты — аналитик аукционов, который рассчитывает РЕКОМЕНДУЕМУЮ СТАВКУ для покупки мотоцикла на аукционе.

ВАЖНО: Рекомендуемая ставка должна быть НИЖЕ ожидаемой цены продажи, чтобы покупатель мог выиграть лот с прибылью.

Используй **только** эти поля:
* «Наименование»
* «Год»
* «Пробег»
* «Оценка»
* «Стартовая цена (₽)»
* «Цена (₽)»

Верни **один** JSON-объект строго по схеме:

{
  "recommended_bid_min": number,
  "recommended_bid_optimal": number,
  "recommended_bid_max": number,
  "chosen_coefficient": number,
  "coefficient_band": [number, number],
  "percentile_used": "p25|p30|p40|p50|p60|p70|fallback",
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
    "coef_p25": number,
    "coef_p30": number,
    "coef_p40": number,
    "coef_p50": number,
    "coef_p60": number,
    "coef_p70": number,
    "coef_max": number
  },
  "warnings": [string]
}

Алгоритм:

1. **Нормализация**: Преобразуй цены и пробег в числа
2. **Фильтр по модели**: Оставь только строки с ТОЧНО такой же моделью
3. **Фильтр по году/пробегу/оценке**: Целевой Год ±1; пробег ±50%; оценка ±1
4. **Расчёт коэффициентов**: Для каждого аналога Коэффициент = Цена(₽) / Стартовая(₽)
5. **Удаление выбросов**: Убери коэффициенты >1.5 (аномалии)
6. **Статистика**: mean, median, p25, p30, p40, p50, p60, p70, max
7. **Выбор коэффициента** (СБАЛАНСИРОВАННЫЙ ПОДХОД):
   - Оценка ≥7, пробег ≤5000км: p60, диапазон [p50, p70]
   - Оценка 6, пробег ≤5000км: p50 (медиана), диапазон [p40, p60]
   - Оценка 5, пробег ≤5000км: p40, диапазон [p30, p50]
   - Оценка 5-6, пробег 5-15тыс: p40, диапазон [p30, p50]
   - Оценка <5 или пробег >15тыс: p30, диапазон [p25, p40]
   - Если аналогов <5: фоллбэк [1.10, 1.20]
8. **Расчёт ставок**: 
   - recommended_bid_min = Стартовая × нижняя_граница_диапазона
   - recommended_bid_optimal = Стартовая × chosen_coefficient
   - recommended_bid_max = Стартовая × верхняя_граница_диапазона
9. **Проверка**: recommended_bid_optimal должна быть близка к p40-p60 от реальных цен продажи аналогов
10. **Возврат**: JSON с полем explanation

Пояснение (explanation): 3-4 строки на русском, почему выбран этот коэффициент.

КРИТИЧНО: 
- recommended_bid_optimal должна давать шанс выиграть ~40-60% аналогичных лотов
- recommended_bid_max должна давать шанс выиграть ~70-80% аналогичных лотов
- recommended_bid_min - для очень консервативных покупателей (~20-30% шанс)"""

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
    
    # Записываем статус запуска в файл
    try:
        with open('.server_status', 'w', encoding='utf-8') as f:
            f.write(f'RUNNING|{port}|{os.getpid()}\n')
    except:
        pass
    
    print(f'\n{"="*70}', flush=True)
    print(f'BDS Scraper Server', flush=True)
    print(f'{"="*70}', flush=True)
    print(f'Сервер запущен на порту {port}', flush=True)
    print(f'Откройте в браузере: http://localhost:{port}', flush=True)
    print(f'База данных: {DB_FILE}', flush=True)
    print(f'{"="*70}\n', flush=True)
    print('Для остановки нажмите Ctrl+C\n', flush=True)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n\nСервер остановлен', flush=True)
        httpd.server_close()
        # Удаляем статус файл
        try:
            os.remove('.server_status')
        except:
            pass

if __name__ == '__main__':
    run_server()


