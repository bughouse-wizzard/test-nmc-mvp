package com.example.transactionservice;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.OutputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

public class TransactionHandler implements HttpHandler {
    private final TransactionDAO transactionDAO;

    public TransactionHandler(TransactionDAO transactionDAO) {
        this.transactionDAO = transactionDAO;
    }

    @Override
    public void handle(HttpExchange exchange) {
        try {
            URI requestURI = exchange.getRequestURI();
            Map<String, String> params = QueryParamsParser.parse(requestURI.getQuery());

            long customerId = Long.parseLong(params.getOrDefault("customerId", "0"));
            int page = Integer.parseInt(params.getOrDefault("page", "0"));
            int size = Integer.parseInt(params.getOrDefault("size", "20"));
            Long accountId = params.containsKey("accountId") ? Long.parseLong(params.get("accountId")) : null;
            LocalDate date = params.containsKey("date") ? LocalDate.parse(params.get("date")) : null;

            List<Transaction> transactions = transactionDAO.getTransactions(customerId, accountId, date, page, size);
            String responseJson = JsonSerializer.toJson(transactions);

            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, responseJson.getBytes(StandardCharsets.UTF_8).length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(responseJson.getBytes(StandardCharsets.UTF_8));
            }
        } catch (Exception e) {
            System.err.println("Error handling request: " + e.getMessage());
            try {
                exchange.sendResponseHeaders(500, 0);
            } catch (Exception ignored) {
            }
        }
    }
}