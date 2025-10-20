import requests
from bs4 import BeautifulSoup
import sqlite3
import time

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

DB_FILE = 'lots.db'

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
        
        print(f"\nPage {page}: {current_url}")
        
        try:
            response = requests.get(current_url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            product_items = soup.find_all('div', class_='b-product-item')
            
            if not product_items:
                print("No more items, stopping")
                break
            
            print(f"Found {len(product_items)} items")
            
            for item in product_items:
                if 'wpa_subscribe' in item.get('class', []):
                    continue
                
                try:
                    results['total'] += 1
                    
                    # URL карточки
                    lot_link = item.find('a', class_='b-product-item__href')
                    lot_url = ''
                    if lot_link and lot_link.get('href'):
                        lot_url = 'https://cemeco.ru' + lot_link['href']
                    
                    # Наименование
                    brand = item.find('div', class_='b-product-title__brand')
                    model = item.find('div', class_='b-product-title__model')
                    brand_text = brand.text.strip() if brand else ''
                    model_text = model.text.strip() if model else ''
                    name = f"{brand_text} {model_text}".strip()
                    
                    # Параметры из таблицы
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
                    
                    # Информация об аукционе
                    crumbs = item.find_all('li', class_='b-product-crumbs__item')
                    date_auc = crumbs[0].text.strip() if len(crumbs) > 0 else ''
                    place = crumbs[1].text.strip() if len(crumbs) > 1 else ''
                    num_lot = crumbs[2].text.strip() if len(crumbs) > 2 else ''
                    
                    # Проверяем дубликаты
                    if check_duplicate(conn, date_auc, place, num_lot):
                        results['duplicates'] += 1
                        print(f"  [{results['total']}] DUPLICATE: {name}")
                        continue
                    
                    # Статус
                    status_div = item.find('div', class_='b-product-status')
                    status = status_div.text.strip() if status_div else ''
                    
                    # Цены ИЗ СПИСКА (финальные)
                    price_items = item.find_all('div', class_='b-product-price__item')
                    real_prize_jap = ''
                    real_prize_rub = ''
                    for price_item in price_items:
                        if '_yen' in price_item.get('class', []):
                            real_prize_jap = price_item.text.strip()
                        elif '_rur' in price_item.get('class', []):
                            real_prize_rub = price_item.text.strip()
                    
                    # Статус аукциона
                    notice = item.find('div', class_='b-product-notice__text')
                    auc_stat = notice.text.strip() if notice else ''
                    
                    # Стартовые цены ИЗ КАРТОЧКИ ЛОТА
                    start_price_jap = ''
                    start_price_rub = ''
                    if lot_url:
                        start_price_jap, start_price_rub = get_start_prices(lot_url)
                        time.sleep(0.3)
                    
                    # Записываем в БД
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
                    print(f"  [{results['total']}] NEW: {name}")
                    
                except Exception as e:
                    print(f"  [{results['total']}] ERROR: {e}")
                    results['errors'] += 1
                    continue
            
            # Проверяем следующую страницу
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
            print(f"ERROR loading page: {e}")
            results['errors'] += 1
            break
    
    conn.close()
    return results

if __name__ == '__main__':
    print("="*70)
    print("BDS SCRAPER - New Version")
    print("="*70)
    
    url = input("\nEnter URL to parse: ").strip()
    
    if not url:
        print("ERROR: URL is required")
        exit(1)
    
    print(f"\nParsing: {url}\n")
    results = parse_url(url)
    
    print("\n" + "="*70)
    print("RESULTS:")
    print("="*70)
    print(f"Total found: {results['total']}")
    print(f"New added: {results['new']}")
    print(f"Duplicates: {results['duplicates']}")
    print(f"Errors: {results['errors']}")
    print("="*70)

