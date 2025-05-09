package com.example.transactionservice;

import com.sun.net.httpserver.HttpServer;

import java.net.InetSocketAddress;

public class Main {
    public static void main(String[] args) throws Exception {
        String dbUrl = "jdbc:postgresql://db:5432/transactions";
        String dbUser = "postgres";
        String dbPassword = "postgres";

        TransactionDAO transactionDAO = new TransactionDAO(dbUrl, dbUser, dbPassword);
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
        server.createContext("/transactions", new TransactionHandler(transactionDAO));
        server.setExecutor(null);
        server.start();
        System.out.println("Server started on port 8080");
    }
}