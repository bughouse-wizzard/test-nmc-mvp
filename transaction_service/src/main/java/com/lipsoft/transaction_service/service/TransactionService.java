package com.lipsoft.transaction_service.service;

import com.lipsoft.transaction_service.model.TransactionEntity;
import com.lipsoft.transaction_service.repository.TransactionRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class TransactionService {
    
    private final TransactionRepository transactionRepository;
    
    public TransactionService(TransactionRepository transactionRepository) {
        this.transactionRepository = transactionRepository;
    }
    
    /**
     * Save a transaction entity
     */
    public TransactionEntity saveTransaction(TransactionEntity transaction) {
        return transactionRepository.save(transaction);
    }
    
    /**
     * Save multiple transaction entities
     */
    public List<TransactionEntity> saveAllTransactions(List<TransactionEntity> transactions) {
        return transactionRepository.saveAll(transactions);
    }
    
    /**
     * Get transaction by ID
     */
    public Optional<TransactionEntity> getTransactionById(Long transactionId) {
        return transactionRepository.findById(transactionId);
    }
    
    /**
     * Get all transactions for a customer with pagination
     * Mirrors the logic from legacy TransactionDAO.getTransactions()
     * Orders by date_time DESC as in the legacy SQL query
     */
    public List<TransactionEntity> getTransactions(Long customerId, Long accountId, LocalDate date, int page, int size) {
        // Create pageable with sort by dateTime descending
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "dateTime"));
        
        if (accountId != null && date != null) {
            // Both accountId and date specified - need to manually paginate and sort
            List<TransactionEntity> allTransactions = transactionRepository.findByCustomerIdAndAccountIdAndDate(customerId, accountId, date);
            // Sort by dateTime descending
            allTransactions.sort(Comparator.comparing(TransactionEntity::getDateTime).reversed());
            return paginateList(allTransactions, page, size);
        } else if (accountId != null) {
            // Only accountId specified - use repository method with pagination
            return transactionRepository.findByCustomerIdAndAccountId(customerId, accountId, pageable);
        } else if (date != null) {
            // Only date specified - need to manually paginate and sort
            List<TransactionEntity> allTransactions = transactionRepository.findByCustomerIdAndDate(customerId, date);
            // Sort by dateTime descending
            allTransactions.sort(Comparator.comparing(TransactionEntity::getDateTime).reversed());
            return paginateList(allTransactions, page, size);
        } else {
            // Only customerId specified - use repository method with pagination
            return transactionRepository.findByCustomerId(customerId, pageable);
        }
    }
    
    /**
     * Get all transactions for a customer (without pagination)
     */
    public List<TransactionEntity> getTransactionsByCustomerId(Long customerId) {
        return transactionRepository.findByCustomerId(customerId);
    }
    
    /**
     * Get transactions for a customer with account filter
     */
    public List<TransactionEntity> getTransactionsByCustomerIdAndAccountId(Long customerId, Long accountId) {
        return transactionRepository.findByCustomerIdAndAccountId(customerId, accountId);
    }
    
    /**
     * Get transactions for a customer on a specific date
     */
    public List<TransactionEntity> getTransactionsByCustomerIdAndDate(Long customerId, LocalDate date) {
        return transactionRepository.findByCustomerIdAndDate(customerId, date);
    }
    
    /**
     * Get transactions for a customer within a date range
     */
    public List<TransactionEntity> getTransactionsByCustomerIdAndDateRange(Long customerId, LocalDate startDate, LocalDate endDate) {
        LocalDateTime startDateTime = startDate.atStartOfDay();
        LocalDateTime endDateTime = endDate.atTime(LocalTime.MAX);
        return transactionRepository.findByCustomerIdAndDateTimeBetween(customerId, startDateTime, endDateTime);
    }
    
    /**
     * Get transactions ordered by date descending (most recent first)
     */
    public List<TransactionEntity> getTransactionsByCustomerIdOrderByDateDesc(Long customerId) {
        return transactionRepository.findByCustomerIdOrderByDateTimeDesc(customerId);
    }
    
    /**
     * Calculate total sum of amounts for a customer
     */
    public Double calculateTotalAmountByCustomerId(Long customerId) {
        Double sum = transactionRepository.sumAmountByCustomerId(customerId);
        return sum != null ? sum : 0.0;
    }
    
    /**
     * Calculate sum of amounts for a customer by direction (IN/OUT)
     */
    public Double calculateAmountByCustomerIdAndDirection(Long customerId, String direction) {
        // We need to implement this logic since repository doesn't have this exact method
        List<TransactionEntity> transactions = transactionRepository.findByCustomerIdAndDirection(customerId, direction);
        return transactions.stream()
                .mapToDouble(TransactionEntity::getAmount)
                .sum();
    }
    
    /**
     * Calculate sum of amounts for a customer and account by direction (IN/OUT)
     */
    public Double calculateAmountByCustomerIdAndAccountIdAndDirection(Long customerId, Long accountId, String direction) {
        List<TransactionEntity> transactions = transactionRepository.findByCustomerIdAndAccountId(customerId, accountId);
        return transactions.stream()
                .filter(t -> direction.equals(t.getDirection()))
                .mapToDouble(TransactionEntity::getAmount)
                .sum();
    }
    
    /**
     * Count transactions for a customer
     */
    public Long countTransactionsByCustomerId(Long customerId) {
        return transactionRepository.countByCustomerId(customerId);
    }
    
    /**
     * Get transactions by direction (IN/OUT)
     */
    public List<TransactionEntity> getTransactionsByDirection(String direction) {
        return transactionRepository.findByDirection(direction);
    }
    
    /**
     * Get transactions with amount greater than specified value
     */
    public List<TransactionEntity> getTransactionsWithAmountGreaterThan(Double amount) {
        return transactionRepository.findByAmountGreaterThan(amount);
    }
    
    /**
     * Get transactions with amount less than specified value
     */
    public List<TransactionEntity> getTransactionsWithAmountLessThan(Double amount) {
        return transactionRepository.findByAmountLessThan(amount);
    }
    
    /**
     * Delete a transaction by ID
     */
    public void deleteTransaction(Long transactionId) {
        transactionRepository.deleteById(transactionId);
    }
    
    /**
     * Check if transaction exists by ID
     */
    public boolean transactionExists(Long transactionId) {
        return transactionRepository.existsById(transactionId);
    }
    
    /**
     * Helper method to paginate a list manually
     */
    private List<TransactionEntity> paginateList(List<TransactionEntity> list, int page, int size) {
        int start = page * size;
        if (start >= list.size()) {
            return List.of();
        }
        int end = Math.min(start + size, list.size());
        return list.subList(start, end);
    }
}