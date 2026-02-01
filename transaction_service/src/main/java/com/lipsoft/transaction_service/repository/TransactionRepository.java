package com.lipsoft.transaction_service.repository;

import com.lipsoft.transaction_service.model.TransactionEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

public interface TransactionRepository extends JpaRepository<TransactionEntity, Long> {
    
    // Find transactions by customer ID with pagination
    Page<TransactionEntity> findByCustomerId(Long customerId, Pageable pageable);
    
    // Find transactions by customer ID and account ID with pagination
    Page<TransactionEntity> findByCustomerIdAndAccountId(Long customerId, Long accountId, Pageable pageable);
    
    // Find transactions by customer ID and date (date part only) with pagination
    @Query("SELECT t FROM TransactionEntity t WHERE t.customerId = :customerId AND DATE(t.dateTime) = :date")
    Page<TransactionEntity> findByCustomerIdAndDate(
            @Param("customerId") Long customerId, 
            @Param("date") LocalDate date, 
            Pageable pageable);
    
    // Find transactions by customer ID, account ID and date (date part only) with pagination
    @Query("SELECT t FROM TransactionEntity t WHERE t.customerId = :customerId AND t.accountId = :accountId AND DATE(t.dateTime) = :date")
    Page<TransactionEntity> findByCustomerIdAndAccountIdAndDate(
            @Param("customerId") Long customerId, 
            @Param("accountId") Long accountId,
            @Param("date") LocalDate date, 
            Pageable pageable);
    
    // Find transactions by direction (IN/OUT)
    List<TransactionEntity> findByDirection(String direction);
    
    // Find transactions by amount greater than
    List<TransactionEntity> findByAmountGreaterThan(Double amount);
    
    // Find transactions by amount less than
    List<TransactionEntity> findByAmountLessThan(Double amount);
    
    // Find transactions by date range
    List<TransactionEntity> findByDateTimeBetween(LocalDateTime start, LocalDateTime end);
    
    // Find transactions by customer ID and direction
    List<TransactionEntity> findByCustomerIdAndDirection(Long customerId, String direction);
    
    // Find transactions by account ID
    List<TransactionEntity> findByAccountId(Long accountId);
    
    // Find transactions by account ID with pagination
    Page<TransactionEntity> findByAccountId(Long accountId, Pageable pageable);
}