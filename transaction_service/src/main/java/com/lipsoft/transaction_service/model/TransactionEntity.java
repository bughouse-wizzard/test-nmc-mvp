package com.lipsoft.transaction_service.model;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "transactions")
@Data
public class TransactionEntity {
    
    @Id
    @Column(name = "transaction_id")
    private Long transactionId;
    
    @Column(name = "customer_id", nullable = false)
    private Long customerId;
    
    @Column(name = "account_id", nullable = false)
    private Long accountId;
    
    @Column(name = "amount", nullable = false)
    private Double amount;
    
    @Column(name = "date_time", nullable = false)
    private LocalDateTime dateTime;
    
    @Column(name = "direction", nullable = false, length = 4)
    private String direction;
}