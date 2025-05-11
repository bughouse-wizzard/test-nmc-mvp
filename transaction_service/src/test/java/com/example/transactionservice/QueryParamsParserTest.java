package com.example.transactionservice;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

public class QueryParamsParserTest {

    @Test
    void testParseValidQuery() {
        String query = "customerId=45022&page=1&size=20";
        Map<String, String> params = QueryParamsParser.parse(query);

        assertEquals("45022", params.get("customerId"));
        assertEquals("1", params.get("page"));
        assertEquals("20", params.get("size"));
    }

    @Test
    void testParseEmptyQuery() {
        String query = "";
        Map<String, String> params = QueryParamsParser.parse(query);

        assertTrue(params.isEmpty());
    }

    @Test
    void testParseNullQuery() {
        Map<String, String> params = QueryParamsParser.parse(null);

        assertTrue(params.isEmpty());
    }
}