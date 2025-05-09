package com.example.transactionservice;

import java.sql.*;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

public class TransactionDAO {
    private final String url;
    private final String user;
    private final String password;

    public TransactionDAO(String url, String user, String password) {
        this.url = url;
        this.user = user;
        this.password = password;
    }

    public List<Transaction> getTransactions(long customerId, Long accountId, LocalDate date, int page, int size) {
        List<Transaction> result = new ArrayList<>();
        StringBuilder sql = new StringBuilder("SELECT * FROM transactions WHERE customer_id = ?");
        if (accountId != null) sql.append(" AND account_id = ?");
        if (date != null) sql.append(" AND date_time::date = ?");
        sql.append(" ORDER BY date_time DESC OFFSET ? LIMIT ?");

        try (Connection conn = DriverManager.getConnection(url, user, password);
             PreparedStatement ps = conn.prepareStatement(sql.toString())) {
            int i = 1;
            ps.setLong(i++, customerId);
            if (accountId != null) ps.setLong(i++, accountId);
            if (date != null) ps.setDate(i++, Date.valueOf(date));
            ps.setInt(i++, page * size);
            ps.setInt(i, size);

            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                Transaction t = new Transaction(
                        rs.getLong("transaction_id"),
                        rs.getLong("customer_id"),
                        rs.getLong("account_id"),
                        rs.getDouble("amount"),
                        rs.getTimestamp("date_time").toLocalDateTime(),
                        rs.getString("direction")
                );
                result.add(t);
            }
        } catch (SQLException e) {
            System.err.println("Error fetching transactions: " + e.getMessage());
        }
        return result;
    }
}