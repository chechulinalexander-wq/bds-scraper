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

class RequestHandler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            stats = get_stats()
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/parse':
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


