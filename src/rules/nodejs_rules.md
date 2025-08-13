# Node.js Development Rules and Best Practices

This document defines the conventions and best practices for building production-grade Node.js applications.
Following these rules will ensure code is **maintainable, scalable, and secure**.

---

## 1. Project Structure

A clean, modular structure improves maintainability and makes onboarding easier.

**1.1 Recommended Layout**

```
project/
├── src/
│   ├── app.js               # Express/Fastify/Koa app initialization
│   ├── server.js            # Server start script
│   ├── config/              # Configuration files
│   │   ├── index.js
│   │   └── db.js
│   ├── routes/              # Route definitions
│   │   ├── user.routes.js
│   │   └── order.routes.js
│   ├── controllers/         # Route handlers
│   │   ├── user.controller.js
│   │   └── order.controller.js
│   ├── services/            # Business logic
│   │   ├── user.service.js
│   │   └── order.service.js
│   ├── models/              # Database models (Mongoose/Sequelize)
│   ├── middlewares/         # Custom middleware
│   ├── utils/               # Utility functions/helpers
│   └── tests/               # Unit and integration tests
├── package.json
├── .env
└── README.md
```

**1.2 Naming Conventions**

* **Files & folders:** lowercase with dots or hyphens (e.g., `user.controller.js`).
* **Classes:** PascalCase (e.g., `UserService`).
* **Variables & functions:** camelCase.

**1.3 Entry Point**

* Keep environment setup minimal in `server.js`.
* Delegate app configuration to `app.js`.

---

## 2. Dependency Management

* Use `npm` or `yarn` with exact versions (`--save-exact`) to avoid surprises.
* Separate **dependencies** and **devDependencies**.
* Avoid unnecessary packages — check for maintenance status before adding.

Common packages:

* Web framework: `express`, `fastify`, or `koa`
* Database: `mongoose`, `sequelize`, `prisma`
* Config: `dotenv`, `config`
* Validation: `joi`, `zod`, `yup`
* Testing: `jest`, `mocha`, `chai`, `supertest`
* Logging: `winston`, `pino`

---

## 3. Configuration

**3.1 Environment Variables**

* Store sensitive config in `.env` (never commit).
* Use `dotenv` for loading variables.
* Centralize config in `config/index.js`.

Example:

```js
require('dotenv').config();

module.exports = {
  port: process.env.PORT || 3000,
  dbUri: process.env.DATABASE_URL,
  jwtSecret: process.env.JWT_SECRET
};
```

**3.2 Environment Separation**

* `.env.development` for local dev
* `.env.production` for production

---

## 4. API Design

**4.1 Routing**

* Group routes by resource.
* Use plural nouns (`/users`, `/orders`).
* Apply versioning (`/api/v1/users`).

**4.2 Controllers**

* Controllers handle HTTP logic only.
* Business logic goes in `services/`.

**4.3 Validation**

* Validate request bodies, params, and queries.
* Return clear, consistent error messages.

Example:

```js
const Joi = require('joi');

const schema = Joi.object({
  name: Joi.string().required(),
  email: Joi.string().email().required()
});

app.post('/users', validate(schema), userController.createUser);
```

---

## 5. Error Handling

**5.1 Centralized Error Handler**

* Use Express/Fastify error middleware to handle all errors.

Example:

```js
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(err.status || 500).json({ message: err.message || 'Internal Server Error' });
});
```

**5.2 Custom Error Classes**

* Define error classes for domain-specific errors.

---

## 6. Logging

* Use `winston` or `pino` for structured logging.
* Log level by environment:

  * Development: `debug`
  * Production: `info` or higher
* Log in JSON format in production for observability tools.

---

## 7. Testing

**7.1 Test Layers**

* Unit: individual functions and services.
* Integration: controllers and DB.
* E2E: full API workflows.

**7.2 Tools**

* `jest` + `supertest` for API testing.

Example:

```js
const request = require('supertest');
const app = require('../src/app');

test('GET /health', async () => {
  const res = await request(app).get('/health');
  expect(res.statusCode).toBe(200);
});
```

---

## 8. Security

* Use `helmet` for HTTP security headers.
* Always validate and sanitize user input.
* Hash passwords with `bcrypt` or `argon2`.
* Use JWT with expiration and refresh tokens.
* Enable CORS only for allowed origins.

Example:

```js
const helmet = require('helmet');
app.use(helmet());
```

---

## 9. Performance & Monitoring

* Use clustering (`node:cluster` or PM2) in production.
* Cache frequent DB queries with Redis.
* Use tools like `prom-client` for Prometheus metrics.
* Implement health check endpoints (`/health`).
