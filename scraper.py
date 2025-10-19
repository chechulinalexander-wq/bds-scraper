import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

url = "https://cemeco.ru/stat/ducati/desert-x/"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

lots = []

# Находим все карточки продуктов на странице статистики
product_items = soup.find_all('div', class_='b-product-item')

for item in product_items:
    # Извлекаем данные
    try:
        # Извлекаем название
        brand = item.find('div', class_='b-product-title__brand')
        model = item.find('div', class_='b-product-title__model')
        
        brand_text = brand.text.strip() if brand else ''
        model_text = model.text.strip() if model else ''
        
        full_name = f"{brand_text} {model_text}".strip()
        
        # Извлекаем параметры из таблицы
        params = {}
        param_table = item.find('table', class_='b-product-params')
        if param_table:
            rows = param_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 2:
                    key = cells[0].text.strip().rstrip(':')
                    value = cells[1].text.strip()
                    params[key] = value
        
        # Извлекаем информацию об аукционе
        crumbs = item.find_all('li', class_='b-product-crumbs__item')
        auction_date = crumbs[0].text.strip() if len(crumbs) > 0 else ''
        auction_house = crumbs[1].text.strip() if len(crumbs) > 1 else ''
        lot_number = crumbs[2].text.strip() if len(crumbs) > 2 else ''
        
        # Извлекаем статус
        notice = item.find('div', class_='b-product-notice__text')
        status = notice.text.strip() if notice else ''
        
        # Извлекаем цену
        price_items = item.find_all('div', class_='b-product-price__item')
        price_yen = ''
        price_rub = ''
        for price_item in price_items:
            if '_yen' in price_item.get('class', []):
                price_yen = price_item.text.strip()
            elif '_rur' in price_item.get('class', []):
                price_rub = price_item.text.strip()
        
        lots.append({
            'Наименование': full_name,
            'Дата аукциона': auction_date,
            'Аукционный дом': auction_house,
            'Номер лота': lot_number,
            'Год': params.get('Год', ''),
            'Пробег': params.get('Пробег', ''),
            'Объем': params.get('Объем', ''),
            'Оценка': params.get('Оценка', ''),
            'Статус': status,
            'Цена (¥)': price_yen,
            'Цена (₽)': price_rub
        })
    except Exception as e:
        print(f"Ошибка при обработке лота: {e}")
        continue

# Создаем DataFrame и сохраняем в Excel
df = pd.DataFrame(lots)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'lots_{timestamp}.xlsx'

df.to_excel(filename, index=False, sheet_name='Лоты')

print(f"Найдено лотов: {len(lots)}")
print(f"Данные сохранены в файл: {filename}")
print("\nСписок лотов:")
for i, lot in enumerate(lots, 1):
    print(f"{i}. {lot['Наименование']} - {lot['Статус']}")

