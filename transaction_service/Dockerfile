# Используем официальный образ OpenJDK
FROM openjdk:17-jdk-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем JAR-файл приложения
COPY target/transaction-service-1.0-SNAPSHOT.jar app.jar
# Указываем команду для запуска приложения
ENTRYPOINT ["java", "-jar", "app.jar"]