from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import re
from datetime import datetime

app = Flask(__name__)

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
    
    # Подключаемся к БД
    conn = sqlite3.connect(DB_FILE)
    
    page = 1
    
    while True:
        if page == 1:
            current_url = url
        else:
            # Формируем URL для пагинации
            if '?' in url:
                base_url = url.split('?')[0]
                params = '?' + url.split('?')[1]
                current_url = f"{base_url}page/{page}/{params}"
            else:
                current_url = f"{url}page/{page}/"
        
        try:
            response = requests.get(current_url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Находим все карточки продуктов
            product_items = soup.find_all('div', class_='b-product-item')
            
            if not product_items:
                break
            
            for item in product_items:
                # Пропускаем карточку с подпиской
                if 'wpa_subscribe' in item.get('class', []):
                    continue
                
                try:
                    results['total'] += 1
                    
                    # Извлекаем ссылку на карточку лота
                    lot_link = item.find('a', class_='b-product-item__href')
                    lot_url = ''
                    if lot_link and lot_link.get('href'):
                        lot_url = 'https://cemeco.ru' + lot_link['href']
                    
                    brand = item.find('div', class_='b-product-title__brand')
                    model = item.find('div', class_='b-product-title__model')
                    
                    brand_text = brand.text.strip() if brand else ''
                    model_text = model.text.strip() if model else ''
                    
                    full_name = f"{brand_text} {model_text}".strip()
                    
                    # Извлекаем параметры из таблицы
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
                    
                    # Извлекаем информацию об аукционе
                    crumbs = item.find_all('li', class_='b-product-crumbs__item')
                    auction_date = crumbs[0].text.strip() if len(crumbs) > 0 else ''
                    auction_house = crumbs[1].text.strip() if len(crumbs) > 1 else ''
                    lot_number = crumbs[2].text.strip() if len(crumbs) > 2 else ''
                    
                    # Проверяем на дубликаты
                    if check_duplicate(conn, auction_date, auction_house, lot_number):
                        results['duplicates'] += 1
                        continue
                    
                    # Извлекаем статус и цену
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
                    
                    # Статус аукциона
                    notice = item.find('div', class_='b-product-notice__text')
                    auction_status = notice.text.strip() if notice else ''
                    
                    # Получаем стартовые цены из карточки лота
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
                    
                    # Сохраняем в БД
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
            
            # Проверяем наличие следующей страницы
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse', methods=['POST'])
def parse():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL не указан'}), 400
    
    # Проверяем формат URL
    if not url.startswith('https://cemeco.ru/stat/'):
        return jsonify({'error': 'URL должен начинаться с https://cemeco.ru/stat/'}), 400
    
    try:
        results = parse_url(url)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stats')
def stats():
    """Получает статистику из БД"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Общее количество записей
        cursor.execute('SELECT COUNT(*) FROM lots')
        total_count = cursor.fetchone()[0]
        
        # Статистика по моделям
        cursor.execute('''
            SELECT "Наименование", COUNT(*) as cnt 
            FROM lots 
            GROUP BY "Наименование" 
            ORDER BY cnt DESC 
            LIMIT 10
        ''')
        models_stats = cursor.fetchall()
        
        # Последние добавленные лоты
        cursor.execute('''
            SELECT "Наименование", "Дата аукциона", "Год", "Пробег", "Цена (₽)" 
            FROM lots 
            ORDER BY rowid DESC 
            LIMIT 10
        ''')
        recent_lots = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
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
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)


