-- Загрузка данных из incomes.csv с добавлением значения 'IN' для столбца direction
COPY transactions(transaction_id, customer_id, account_id, amount, date_time, direction)
FROM PROGRAM 'cat /docker-entrypoint-initdb.d/incomes.csv | sed "s/$/,IN/"'
DELIMITER ',' CSV HEADER;

-- Загрузка данных из outcomes.csv с добавлением значения 'OUT' для столбца direction
COPY transactions(transaction_id, customer_id, account_id, amount, date_time, direction)
FROM PROGRAM 'cat /docker-entrypoint-initdb.d/outcomes.csv | sed "s/$/,OUT/"'
DELIMITER ',' CSV HEADER;