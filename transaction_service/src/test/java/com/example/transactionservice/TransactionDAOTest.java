package com.example.transactionservice;

import org.junit.jupiter.api.*;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;
import java.time.LocalDate;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
public class TransactionDAOTest {
    private TransactionDAO transactionDAO;

    @BeforeAll
    void setup() throws Exception {
        String url = "jdbc:postgresql://db:5432/transactions_test";
        String user = "postgres";
        String password = "postgres";
        try (Connection conn = DriverManager.getConnection(url, user, password);
             Statement stmt = conn.createStatement()) {
            stmt.execute("CREATE TABLE IF NOT EXISTS transactions (" +
                    "transaction_id BIGINT PRIMARY KEY, " +
                    "customer_id BIGINT NOT NULL, " +
                    "account_id BIGINT NOT NULL, " +
                    "amount DOUBLE PRECISION NOT NULL, " +
                    "date_time TIMESTAMP NOT NULL, " +
                    "direction VARCHAR(4) NOT NULL" +
                    ")");
            stmt.execute("INSERT INTO transactions VALUES " +
                    "(1, 45022, 12345, 100.0, '2023-01-01 10:00:00', 'IN'), " +
                    "(2, 45022, 12346, 200.0, '2023-01-02 10:00:00', 'OUT')");
        }

        transactionDAO = new TransactionDAO(url, user, password);
    }

    @Test
    void testGetTransactionsByCustomerId() {
        List<Transaction> transactions = transactionDAO.getTransactions(45022, null, null, 0, 10);
        assertNotNull(transactions);
        assertEquals(2, transactions.size());
    }

    @Test
    void testGetTransactionsByAccountId() {
        List<Transaction> transactions = transactionDAO.getTransactions(45022, 12345L, null, 0, 10);
        assertNotNull(transactions);
        assertEquals(1, transactions.size());
        assertEquals(12345L, transactions.get(0).getAccountId());
    }

    @Test
    void testGetTransactionsByDate() {
        LocalDate date = LocalDate.of(2023, 1, 1);
        List<Transaction> transactions = transactionDAO.getTransactions(45022, null, date, 0, 10);
        assertNotNull(transactions);
        assertEquals(1, transactions.size());
        assertEquals(date, transactions.get(0).getDateTime().toLocalDate());
    }
}