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

# Импортируем движок рекомендаций
from recommendation_engine import calculate_recommendation

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

def get_recommendation(target_lot, all_lots):
    """Получает рекомендацию от движка расчета"""
    try:
        # Используем встроенный движок расчета (без AI)
        result = calculate_recommendation(target_lot, all_lots)
        return result
    except Exception as e:
        print(f"Ошибка расчета рекомендации: {e}")
        import traceback
        traceback.print_exc()
        return {'error': f'Ошибка расчета: {str(e)}'}

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
                
                # Получаем рекомендацию от движка расчета
                recommendation = get_recommendation(target_lot, all_lots)
                
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


