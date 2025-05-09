package com.example.transactionservice;

import java.util.HashMap;
import java.util.Map;

public class QueryParamsParser {
    public static Map<String, String> parse(String query) {
        Map<String, String> map = new HashMap<>();
        if (query == null || query.isEmpty()) return map;
        for (String param : query.split("&")) {
            String[] pair = param.split("=");
            if (pair.length == 2) {
                map.put(pair[0], pair[1]);
            }
        }
        return map;
    }
}