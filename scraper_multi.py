import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import sqlite3

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

def parse_model(base_url, params, model_name):
    """Парсит один мотоцикл"""
    print(f"\n{'='*70}")
    print(f"ПАРСИНГ МОДЕЛИ: {model_name}")
    print(f"{'='*70}")
    
    lots = []
    page = 1
    total_lots_processed = 0
    
    while True:
        if page == 1:
            url = base_url + params
        else:
            url = f"{base_url}page/{page}/{params}"
        
        print(f"\n[Страница {page}] URL: {url}")
        
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Находим все карточки продуктов
            product_items = soup.find_all('div', class_='b-product-item')
            
            if not product_items:
                print(f"Страница {page} пуста, завершаем")
                break
            
            print(f"Найдено: {len(product_items)} лотов")
            
            for idx, item in enumerate(product_items, 1):
                # Пропускаем карточку с подпиской
                if 'wpa_subscribe' in item.get('class', []):
                    continue
                
                # Извлекаем данные
                try:
                    total_lots_processed += 1
                    print(f"  [{total_lots_processed}] Лот {idx}/{len(product_items)}", end=' ')
                    
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
                    
                    lots.append({
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
                    })
                    print("[OK]")
                except Exception as e:
                    print(f"[ERROR] {e}")
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
            print(f"[ERROR] Ошибка загрузки страницы: {e}")
            break
    
    print(f"\n[{model_name}] Собрано лотов: {len(lots)}")
    return lots

# Конфигурация моделей для парсинга
models_config = [
    {
        'name': 'Yamaha XT690Z TENERE 700',
        'url': 'https://cemeco.ru/stat/yamaha/xt690z-tenere-700/',
        'params': '?f-st=0&f-name=&f-year-from=2023'
    },
    {
        'name': 'Aprilia TOUAREG 660',
        'url': 'https://cemeco.ru/stat/aprilia/touareg-660/',
        'params': ''
    },
    {
        'name': 'KTM 890 ADVENTURE',
        'url': 'https://cemeco.ru/stat/ktm/890-adventure/',
        'params': ''
    },
    {
        'name': 'KTM 890 ADVENTURE R',
        'url': 'https://cemeco.ru/stat/ktm/890-adventure-r/',
        'params': ''
    }
]

print(f"\n{'#'*70}")
print(f"МУЛЬТИМОДЕЛЬНЫЙ ПАРСЕР МОТОЦИКЛОВ")
print(f"{'#'*70}")
print(f"Моделей для парсинга: {len(models_config)}")

# Собираем данные со всех моделей
all_lots = []

for model_config in models_config:
    lots = parse_model(model_config['url'], model_config['params'], model_config['name'])
    all_lots.extend(lots)
    print(f"\n>>> Всего собрано лотов: {len(all_lots)}")

print(f"\n{'='*70}")
print(f"ЗАВЕРШЕНИЕ ПАРСИНГА")
print(f"{'='*70}")

# Создаем DataFrame
df = pd.DataFrame(all_lots)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

# Сохраняем в Excel
print("\n[1/3] Создание Excel файла...")
filename_xlsx = f'lots_multi_{timestamp}.xlsx'
df.to_excel(filename_xlsx, index=False, sheet_name='Лоты')
print(f"    [OK] Excel сохранен: {filename_xlsx}")

# Работаем с SQLite
print("\n[2/3] Работа с SQLite базой данных...")
filename_db = f'lots_multi_{timestamp}.db'

# Проверяем существование старой базы
import glob
old_db_files = glob.glob('lots_*.db')
old_db_files = [f for f in old_db_files if not f.startswith('lots_multi_')]

if old_db_files:
    # Берем последнюю старую базу
    old_db = max(old_db_files, key=lambda x: x)
    print(f"    Найдена старая база: {old_db}")
    
    # Загружаем старые данные
    try:
        old_conn = sqlite3.connect(old_db)
        df_old = pd.read_sql_query("SELECT * FROM lots", old_conn)
        old_conn.close()
        print(f"    [OK] Загружено {len(df_old)} старых записей")
        
        # Объединяем старые и новые данные
        df_combined = pd.concat([df_old, df], ignore_index=True)
        print(f"    [OK] Объединено записей: {len(df_combined)}")
    except Exception as e:
        print(f"    [!] Не удалось загрузить старые данные: {e}")
        df_combined = df
else:
    print("    Старая база не найдена, создаем новую")
    df_combined = df

# Создаем новую базу
conn = sqlite3.connect(filename_db)

# Сохраняем бекап старых данных (если были)
if old_db_files:
    try:
        df_old.to_sql('lots_backup', conn, if_exists='replace', index=False)
        print(f"    [OK] Бекап создан: таблица 'lots_backup' ({len(df_old)} записей)")
    except:
        pass

# Сохраняем объединенные данные
df_combined.to_sql('lots', conn, if_exists='replace', index=False)

# Создаем индексы
cursor = conn.cursor()
cursor.execute('CREATE INDEX IF NOT EXISTS idx_model ON lots ("Наименование")')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_auction_date ON lots ("Дата аукциона")')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON lots ("Статус")')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_year ON lots ("Год")')
conn.commit()

# Статистика
cursor.execute('SELECT COUNT(*) FROM lots')
total_count = cursor.fetchone()[0]

cursor.execute('SELECT "Наименование", COUNT(*) as cnt FROM lots GROUP BY "Наименование" ORDER BY cnt DESC')
models_stats = cursor.fetchall()

conn.close()

print(f"    [OK] SQLite база создана: {filename_db}")
print(f"    [OK] Таблица 'lots': {total_count} записей")

print("\n[3/3] Статистика по моделям:")
for model, count in models_stats:
    print(f"    {model}: {count} лотов")

print(f"\n{'='*70}")
print(f"ПАРСИНГ ЗАВЕРШЕН УСПЕШНО")
print(f"{'='*70}")
print(f"  Всего собрано лотов: {len(all_lots)}")
print(f"  В базе после объединения: {total_count}")
print(f"  Excel файл: {filename_xlsx}")
print(f"  SQLite база: {filename_db}")
print(f"{'='*70}\n")


