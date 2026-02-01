package com.lipsoft.transaction_service.bootstrap;

import com.lipsoft.transaction_service.model.TransactionEntity;
import com.lipsoft.transaction_service.repository.TransactionRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.core.io.ClassPathResource;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Component
public class DataLoader implements CommandLineRunner {

    private final TransactionRepository transactionRepository;
    
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ISO_LOCAL_DATE_TIME;
    
    public DataLoader(TransactionRepository transactionRepository) {
        this.transactionRepository = transactionRepository;
    }
    
    @Override
    public void run(String... args) throws Exception {
        System.out.println("Starting CSV data loading...");
        
        // Check if database already has data
        long count = transactionRepository.count();
        if (count > 0) {
            System.out.println("Database already contains " + count + " transactions. Skipping data loading.");
            return;
        }
        
        List<TransactionEntity> transactions = new ArrayList<>();
        
        // Load incomes.csv with direction "IN"
        System.out.println("Loading incomes.csv...");
        loadCsvData("incomes.csv", "IN", transactions);
        
        // Load outcomes.csv with direction "OUT"
        System.out.println("Loading outcomes.csv...");
        loadCsvData("outcomes.csv", "OUT", transactions);
        
        // Save all transactions to database
        System.out.println("Saving " + transactions.size() + " transactions to database...");
        transactionRepository.saveAll(transactions);
        
        System.out.println("CSV data loading completed successfully!");
    }
    
    private void loadCsvData(String filename, String direction, List<TransactionEntity> transactions) {
        try {
            ClassPathResource resource = new ClassPathResource("init-db/" + filename);
            BufferedReader reader = new BufferedReader(new InputStreamReader(resource.getInputStream()));
            
            // Skip header line
            String line = reader.readLine();
            
            while ((line = reader.readLine()) != null) {
                try {
                    TransactionEntity transaction = parseCsvLine(line, direction);
                    if (transaction != null) {
                        transactions.add(transaction);
                    }
                } catch (Exception e) {
                    System.err.println("Error parsing line in " + filename + ": " + line);
                    System.err.println("Error: " + e.getMessage());
                }
            }
            
            reader.close();
        } catch (Exception e) {
            System.err.println("Error loading CSV file " + filename + ": " + e.getMessage());
            e.printStackTrace();
        }
    }
    
    private TransactionEntity parseCsvLine(String line, String direction) {
        String[] parts = line.split(",");
        
        if (parts.length < 5) {
            System.err.println("Invalid CSV line (expected 5 columns): " + line);
            return null;
        }
        
        try {
            TransactionEntity transaction = new TransactionEntity();
            transaction.setTransactionId(Long.parseLong(parts[0].trim()));
            transaction.setCustomerId(Long.parseLong(parts[1].trim()));
            transaction.setAccountId(Long.parseLong(parts[2].trim()));
            transaction.setAmount(Double.parseDouble(parts[3].trim()));
            transaction.setDateTime(LocalDateTime.parse(parts[4].trim(), DATE_TIME_FORMATTER));
            transaction.setDirection(direction);
            
            return transaction;
        } catch (Exception e) {
            System.err.println("Error parsing CSV line: " + line);
            System.err.println("Error: " + e.getMessage());
            return null;
        }
    }
}