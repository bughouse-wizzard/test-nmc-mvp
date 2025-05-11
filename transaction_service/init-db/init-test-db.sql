-- Создание тестовой базы данных, если она не существует
CREATE DATABASE transactions_test;

-- Создание таблицы transactions
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    date_time TIMESTAMP NOT NULL,
    direction VARCHAR(4) NOT NULL -- 'IN' или 'OUT'
);

-- Вставка тестовых данных
INSERT INTO transactions (transaction_id, customer_id, account_id, amount, date_time, direction) VALUES
(1, 45022, 12345, 100.0, '2023-01-01 10:00:00', 'IN'),
(2, 45022, 12346, 200.0, '2023-01-02 10:00:00', 'OUT'),
(3, 45023, 12347, 300.0, '2023-01-03 10:00:00', 'IN');