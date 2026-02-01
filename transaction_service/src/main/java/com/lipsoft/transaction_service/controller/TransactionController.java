package com.lipsoft.transaction_service.controller;

import com.lipsoft.transaction_service.model.TransactionEntity;
import com.lipsoft.transaction_service.service.TransactionService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/transactions")
public class TransactionController {

    private final TransactionService transactionService;

    @Autowired
    public TransactionController(TransactionService transactionService) {
        this.transactionService = transactionService;
    }

    /**
     * GET /transactions - Get transactions with filtering and pagination
     * Mirrors the legacy HTTP server endpoint
     * 
     * @param customerId Required customer ID
     * @param accountId Optional account ID filter
     * @param date Optional date filter (YYYY-MM-DD format)
     * @param page Page number (default: 0)
     * @param size Page size (default: 20)
     * @return List of transactions matching the criteria
     */
    @GetMapping
    public ResponseEntity<List<TransactionEntity>> getTransactions(
            @RequestParam("customerId") Long customerId,
            @RequestParam(value = "accountId", required = false) Long accountId,
            @RequestParam(value = "date", required = false) 
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "size", defaultValue = "20") int size) {
        
        List<TransactionEntity> transactions = transactionService.getTransactions(
            customerId, accountId, date, page, size
        );
        
        return ResponseEntity.ok(transactions);
    }

    /**
     * GET /transactions/{id} - Get transaction by ID
     * 
     * @param transactionId Transaction ID
     * @return Transaction if found, 404 if not found
     */
    @GetMapping("/{id}")
    public ResponseEntity<TransactionEntity> getTransactionById(@PathVariable("id") Long transactionId) {
        Optional<TransactionEntity> transaction = transactionService.getTransactionById(transactionId);
        
        return transaction
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    /**
     * POST /transactions - Create a new transaction
     * 
     * @param transaction Transaction to create
     * @return Created transaction
     */
    @PostMapping
    public ResponseEntity<TransactionEntity> createTransaction(@RequestBody TransactionEntity transaction) {
        TransactionEntity savedTransaction = transactionService.saveTransaction(transaction);
        return ResponseEntity.ok(savedTransaction);
    }

    /**
     * DELETE /transactions/{id} - Delete a transaction by ID
     * 
     * @param transactionId Transaction ID to delete
     * @return 204 No Content on success, 404 if not found
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteTransaction(@PathVariable("id") Long transactionId) {
        if (!transactionService.transactionExists(transactionId)) {
            return ResponseEntity.notFound().build();
        }
        
        transactionService.deleteTransaction(transactionId);
        return ResponseEntity.noContent().build();
    }
}