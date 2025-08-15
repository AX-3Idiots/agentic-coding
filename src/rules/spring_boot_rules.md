# Spring Boot Development Rules and Best Practices

This document outlines the essential rules and best practices for developing robust, scalable, and maintainable applications using the Spring Boot framework.

---

## 1. Project Structure

A consistent and logical project structure is crucial for maintainability.

**1.1 Recommended Package Structure**

Group classes by feature or domain. Avoid layering packages by type (e.g., `controller`, `service`).

```
com.example.project/
├── Application.java
├── config/
│   ├── SecurityConfig.java
│   └── WebConfig.java
├── features/
│   ├── user/
│   │   ├── UserController.java
│   │   ├── UserService.java
│   │   ├── UserRepository.java
│   │   └── User.java
│   └── order/
│       ├── OrderController.java
│       ├── OrderService.java
│       └── Order.java
├── security/
│   ├── JwtTokenProvider.java
│   └── UserDetailsServiceImpl.java
├── exception/
│   ├── GlobalExceptionHandler.java
│   └── ResourceNotFoundException.java
└── utils/
    └── DateUtils.java
```

**1.2 Naming Conventions**

- **Classes:** PascalCase (`UserService`).
- **Methods & Variables:** camelCase (`getUserById`).
- **Packages:** lowercase (`com.example.project.features.user`).

---

## 2. Dependency Management

Use Maven or Gradle for dependency management.

- **Spring Boot Starters:** Prefer starters (`spring-boot-starter-web`) to manage dependency versions.
- **BOM (Bill of Materials):** Use the Spring Boot BOM to ensure compatible dependency versions.
- **Versioning:** Keep the Spring Boot parent version up-to-date.

---

## 3. Configuration

**3.1 Application Properties**

- Use `application.yml` or `application.properties` for configuration. YAML is preferred for its readability.
- Externalize configuration — do not hardcode values.

**3.2 Profile-Specific Configuration**

Use profiles (`dev`, `prod`, `test`) for environment-specific settings.

- `application-dev.yml`
- `application-prod.yml`

Activate a profile using `spring.profiles.active=dev`.

**3.3 `@ConfigurationProperties`**

Bind configuration to strongly-typed Java objects for type safety.

```java
@ConfigurationProperties(prefix = "app.security")
public class AppSecurityProperties {
    private String jwtSecret;
    // getters and setters
}
```

---

## 4. API Design

**4.1 RESTful Conventions**

- Use nouns for resource URIs (`/api/users`).
- Use standard HTTP methods (GET, POST, PUT, DELETE).
- Use HTTP status codes correctly (200, 201, 400, 404, 500).

**4.2 DTOs (Data Transfer Objects)**

- Use DTOs to separate internal domain models from external API contracts.
- Use validation annotations (`@Valid`, `@NotNull`) on DTOs.

Example:

```java
public class CreateUserRequest {
    @NotBlank
    private String username;
    @Email
    private String email;
}
```

**4.3 Versioning**

Use URI versioning (`/api/v1/users`).

---

## 5. Error Handling

**5.1 Centralized Exception Handling**

Use `@RestControllerAdvice` and `@ExceptionHandler` for global error handling.

```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ErrorResponse handleNotFound(ResourceNotFoundException ex) {
        // ...
    }
}
```

**5.2 Custom Exceptions**

Create custom, semantic exceptions for specific error cases.

---

## 6. Data Persistence

**6.1 JPA / Spring Data**

- Use Spring Data JPA for repository abstraction.
- Keep repositories focused on data access.
- Business logic belongs in service layers.

**6.2 Transactions**

Use `@Transactional` at the service layer to ensure data consistency.

---

## 7. Security

**7.1 Spring Security**

- Use the Spring Security starter (`spring-boot-starter-security`).
- Configure security rules in a `SecurityConfig` class.
- Use method-level security (`@PreAuthorize`) for fine-grained control.

**7.2 Passwords**

Always hash passwords using `BCryptPasswordEncoder`.

**7.3 CORS**

Configure CORS globally in your `WebConfig` or with `@CrossOrigin` annotations.

---

## 8. Testing

**8.1 Test Layers**

- **Unit Tests:** Test services and components in isolation (`@ExtendWith(MockitoExtension.class)`).
- **Integration Tests:** Test the full application context (`@SpringBootTest`).
- **API Tests:** Use `@WebMvcTest` or `@SpringBootTest` with `TestRestTemplate`.

**8.2 Test Slices**

Use test slices like `@DataJpaTest` and `@WebMvcTest` to test specific parts of the application.

---

## 9. Performance

- Enable caching with `@EnableCaching` and `@Cacheable`.
- Use asynchronous processing with `@Async` for long-running tasks.
- Monitor application performance with Actuator (`spring-boot-starter-actuator`).
