package com.lipsoft.transaction_service.repository;

import com.lipsoft.transaction_service.model.TransactionEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

@Repository
public interface TransactionRepository extends JpaRepository<TransactionEntity, Long> {
    
    // Find transactions by customer ID
    List<TransactionEntity> findByCustomerId(Long customerId);
    
    // Find transactions by customer ID with pagination
    List<TransactionEntity> findByCustomerId(Long customerId, org.springframework.data.domain.Pageable pageable);
    
    // Find transactions by customer ID and account ID
    List<TransactionEntity> findByCustomerIdAndAccountId(Long customerId, Long accountId);
    
    // Find transactions by customer ID, account ID with pagination
    List<TransactionEntity> findByCustomerIdAndAccountId(Long customerId, Long accountId, org.springframework.data.domain.Pageable pageable);
    
    // Find transactions by customer ID and date (date only, ignoring time)
    @Query("SELECT t FROM TransactionEntity t WHERE t.customerId = :customerId AND DATE(t.dateTime) = :date")
    List<TransactionEntity> findByCustomerIdAndDate(@Param("customerId") Long customerId, @Param("date") LocalDate date);
    
    // Find transactions by customer ID and date with pagination (date only, ignoring time)
    @Query("SELECT t FROM TransactionEntity t WHERE t.customerId = :customerId AND DATE(t.dateTime) = :date")
    List<TransactionEntity> findByCustomerIdAndDate(@Param("customerId") Long customerId, @Param("date") LocalDate date, org.springframework.data.domain.Pageable pageable);
    
    // Find transactions by customer ID, account ID and date (date only, ignoring time)
    @Query("SELECT t FROM TransactionEntity t WHERE t.customerId = :customerId AND t.accountId = :accountId AND DATE(t.dateTime) = :date")
    List<TransactionEntity> findByCustomerIdAndAccountIdAndDate(@Param("customerId") Long customerId, 
                                                                @Param("accountId") Long accountId, 
                                                                @Param("date") LocalDate date);
    
    // Find transactions by customer ID, account ID and date with pagination (date only, ignoring time)
    @Query("SELECT t FROM TransactionEntity t WHERE t.customerId = :customerId AND t.accountId = :accountId AND DATE(t.dateTime) = :date")
    List<TransactionEntity> findByCustomerIdAndAccountIdAndDate(@Param("customerId") Long customerId, 
                                                                @Param("accountId") Long accountId, 
                                                                @Param("date") LocalDate date, 
                                                                org.springframework.data.domain.Pageable pageable);
    
    // Find transactions by direction (IN/OUT)
    List<TransactionEntity> findByDirection(String direction);
    
    // Find transactions by customer ID and direction
    List<TransactionEntity> findByCustomerIdAndDirection(Long customerId, String direction);
    
    // Find transactions by amount greater than
    List<TransactionEntity> findByAmountGreaterThan(Double amount);
    
    // Find transactions by amount less than
    List<TransactionEntity> findByAmountLessThan(Double amount);
    
    // Find transactions by date range
    List<TransactionEntity> findByDateTimeBetween(LocalDateTime startDate, LocalDateTime endDate);
    
    // Find transactions by customer ID and date range
    List<TransactionEntity> findByCustomerIdAndDateTimeBetween(Long customerId, LocalDateTime startDate, LocalDateTime endDate);
    
    // Count transactions by customer ID
    Long countByCustomerId(Long customerId);
    
    // Sum of amounts by customer ID
    @Query("SELECT SUM(t.amount) FROM TransactionEntity t WHERE t.customerId = :customerId")
    Double sumAmountByCustomerId(@Param("customerId") Long customerId);
    
    // Find transactions by customer ID ordered by date descending (most recent first)
    List<TransactionEntity> findByCustomerIdOrderByDateTimeDesc(Long customerId);
    
    // Find transactions by customer ID and account ID ordered by date descending
    List<TransactionEntity> findByCustomerIdAndAccountIdOrderByDateTimeDesc(Long customerId, Long accountId);
}