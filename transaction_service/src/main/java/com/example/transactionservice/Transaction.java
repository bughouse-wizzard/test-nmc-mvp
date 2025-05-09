package com.example.transactionservice;

import java.time.LocalDateTime;

public class Transaction {
    private final long transactionId;
    private final long customerId;
    private final long accountId;
    private final double amount;
    private final LocalDateTime dateTime;
    private final String direction;

    public Transaction(long transactionId, long customerId, long accountId, double amount, LocalDateTime dateTime, String direction) {
        this.transactionId = transactionId;
        this.customerId = customerId;
        this.accountId = accountId;
        this.amount = amount;
        this.dateTime = dateTime;
        this.direction = direction;
    }

    public long getTransactionId() {
        return transactionId;
    }

    public long getCustomerId() {
        return customerId;
    }

    public long getAccountId() {
        return accountId;
    }

    public double getAmount() {
        return amount;
    }

    public LocalDateTime getDateTime() {
        return dateTime;
    }

    public String getDirection() {
        return direction;
    }
}