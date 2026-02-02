# НМЦК Поиск - Статический фронтенд с FastAPI

Этот проект интегрирует статический фронтенд (front13.html) с FastAPI бэкендом.

## Структура проекта

```
.
├── app/
│   └── static/
│       ├── index.html          # Главная HTML страница (бывший front13.html)
│       ├── css/
│       │   └── styles.css      # CSS стили, извлеченные из HTML
│       └── js/
│           └── app.js          # JavaScript логика, извлеченная из HTML
├── main.py                     # FastAPI приложение
├── requirements.txt            # Зависимости Python
└── README.md                   # Эта документация
```

## Установка и запуск

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите сервер:
```bash
python3 main.py
```

3. Откройте в браузере:
- http://localhost:8000/ - главная страница
- http://localhost:8000/api/health - проверка работы API

## API эндпоинты

- `GET /` - Главная HTML страница
- `GET /api/health` - Проверка здоровья сервиса
- `GET /api/search` - Моковые данные истории поисков

## Что было сделано

1. Создана структура каталогов `app/static/` с подкаталогами `js` и `css`
2. Существующий `index.html` (файл front13.html) перемещен в `app/static/`
3. JavaScript логика извлечена из HTML в отдельный файл `app/static/js/app.js`
4. CSS стили извлечены из HTML в отдельный файл `app/static/css/styles.css`
5. Создано FastAPI приложение с монтированием статических файлов
6. Добавлен mock эндпоинт `GET /api/health` для проверки соединения
7. Установлены необходимые зависимости (FastAPI, uvicorn)