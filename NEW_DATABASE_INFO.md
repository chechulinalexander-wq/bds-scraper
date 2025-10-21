# Новая структура базы данных lots.db

## Что изменилось

Создана новая БД **`lots.db`** с правильной структурой колонок на английском языке.

## Структура таблицы

| Колонка | Описание | Пример |
|---------|----------|--------|
| `Name` | Наименование лота | "Ducati DESERT X" |
| `Date-auc` | Дата аукциона | "2025.10.08" |
| `Place` | Аукционный дом | "BDS Kantou" |
| `Num-lot` | Номер лота | "№ 2545" |
| `Year` | Год выпуска | "2023" |
| `Probeg` | Пробег | "4 471 км" |
| `Vol` | Объем двигателя | "937 сс." |
| `Ozenka` | Оценка | "5" |
| `Status` | Статус | "Продан" |
| `Start-price-jap` | Стартовая цена (¥) | "1 100 000 ¥" |
| `Start-price-rub` | Стартовая цена (₽) | "1 179 444 ₽" |
| `Real-prize-jap` | Финальная цена (¥) | "1 000 000 ¥" |
| `Real-prize-rub` | Финальная цена (₽) | "1 277 630 ₽" |
| `Auc-stat` | Статус аукциона | "Продан" |
| `Url` | URL карточки | "https://..." |

## Файлы

### Созданы:
- ✅ **lots.db** - новая база данных с правильной структурой
- ✅ **parser_new.py** - новый парсер для правильной записи данных
- ✅ **create_new_db.py** - скрипт для создания БД

### Обновлены:
- ✅ **server.py** - обновлен для работы с новой БД

## Как использовать

### 1. Парсинг через веб-интерфейс:

```bash
# Запустите сервер
start_server.bat

# Откройте браузер: http://localhost:8000
# Вставьте URL и парсите
```

### 2. Парсинг через скрипт:

```bash
python parser_new.py
# Введите URL когда попросит
```

## Важно!

### Правильная запись цен:

- **Start-price-jap/rub** - берутся ИЗ КАРТОЧКИ ЛОТА (раздел "Стартовая цена")
- **Real-prize-jap/rub** - берутся ИЗ СПИСКА (финальная цена продажи)

Это исправляет проблему перепутанных колонок в старой БД!

## Миграция данных

Если нужно перенести данные из старой БД (`lots_multi_20251017_142157.db`), используйте:

```python
import sqlite3

# Читаем из старой БД с правильными колонками
old_conn = sqlite3.connect('lots_multi_20251017_142157.db')
old_cursor = old_conn.cursor()

old_cursor.execute('''
    SELECT "Наименование", "Дата аукциона", "Аукционный дом", "Номер лота",
           "Год", "Пробег", "Объем", "Оценка", "Статус",
           "Стартовая цена (¥)", "Статус аукциона",  
           "Цена (₽)", "Цена (¥)",
           "Продан", "URL карточки"
    FROM lots
''')

# Записываем в новую БД
new_conn = sqlite3.connect('lots.db')
new_cursor = new_conn.cursor()

for row in old_cursor.fetchall():
    new_cursor.execute('''
        INSERT INTO lots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', row)

new_conn.commit()
old_conn.close()
new_conn.close()
```

## Проверка данных

```python
import sqlite3

conn = sqlite3.connect('lots.db')
cursor = conn.cursor()

# Проверяем количество записей
cursor.execute('SELECT COUNT(*) FROM lots')
print(f"Всего записей: {cursor.fetchone()[0]}")

# Проверяем последнюю запись
cursor.execute('SELECT Name, "Start-price-rub", "Real-prize-rub" FROM lots ORDER BY rowid DESC LIMIT 1')
print(cursor.fetchone())

conn.close()
```

## Следующие шаги

- ✅ Создана новая БД lots.db
- ✅ Обновлен парсер
- ✅ Обновлен server.py
- ⏳ AI рекомендации будут обновлены отдельно


