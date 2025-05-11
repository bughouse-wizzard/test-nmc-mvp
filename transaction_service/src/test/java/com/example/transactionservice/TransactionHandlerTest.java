package com.example.transactionservice;

import com.sun.net.httpserver.HttpExchange;
import org.junit.jupiter.api.*;
import org.mockito.Mockito;

import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.net.URI;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

public class TransactionHandlerTest {
    private TransactionHandler handler;
    private TransactionDAO transactionDAO;

    @BeforeEach
    void setup() {
        transactionDAO = mock(TransactionDAO.class);
        handler = new TransactionHandler(transactionDAO);
    }

    @Test
    void testHandleRequest() throws Exception {
        HttpExchange exchange = mock(HttpExchange.class);
        when(exchange.getRequestURI()).thenReturn(new URI("/transactions?customerId=45022&page=0&size=10"));
        when(exchange.getResponseBody()).thenReturn(new ByteArrayOutputStream());

        List<Transaction> mockTransactions = List.of(
                new Transaction(1, 45022, 12345, 100.0, null, "IN")
        );
        when(transactionDAO.getTransactions(45022, null, null, 0, 10)).thenReturn(mockTransactions);

        handler.handle(exchange);

        verify(exchange).sendResponseHeaders(eq(200), anyLong());
        OutputStream os = exchange.getResponseBody();
        assertNotNull(os);
    }
}