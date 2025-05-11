CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    date_time TIMESTAMP NOT NULL,
    direction VARCHAR(4) NOT NULL -- 'IN' или 'OUT'
);