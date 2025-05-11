package com.example.transactionservice;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

public class JsonSerializerTest {

    @Test
    void testToJson() throws Exception {
        List<Transaction> transactions = List.of(
                new Transaction(1, 45022, 12345, 100.0, null, "IN")
        );

        String json = JsonSerializer.toJson(transactions);
        assertNotNull(json);
        assertTrue(json.contains("\"transactionId\":1"));
        assertTrue(json.contains("\"customerId\":45022"));
    }
}