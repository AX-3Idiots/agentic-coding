# FastAPI Development Rules and Best Practices

This document defines the conventions and best practices for developing production-ready FastAPI applications.
Following these rules will ensure that code is **maintainable, scalable, and secure**.

---

## 1. Project Structure

A clear and consistent project structure makes the application easier to maintain and scale.

**1.1 Directory Layout (Recommended)**

```
app/
├── main.py                 # Application entry point
├── api/                    # API routes
│   ├── v1/
│   │   ├── routes/         # Route definitions
│   │   │   ├── user.py
│   │   │   └── order.py
│   │   └── dependencies.py # Shared dependencies
├── core/                   # Core configuration and utilities
│   ├── config.py           # App settings (Pydantic BaseSettings)
│   └── security.py         # Auth & security helpers
├── models/                 # SQLAlchemy models
│   ├── user.py
│   └── order.py
├── schemas/                # Pydantic models for request/response
│   ├── user.py
│   └── order.py
├── services/               # Business logic layer
│   ├── user_service.py
│   └── order_service.py
└── tests/                  # Unit and integration tests
    ├── test_user.py
    └── test_order.py
```

**1.2 Naming Conventions**

- **Packages & Modules:** lowercase with underscores (e.g., `user_service.py`).
- **Classes:** PascalCase (e.g., `UserService`).
- **Variables & Functions:** snake_case (e.g., `get_user_by_id`).

**1.3 Entry Point**

- Keep `main.py` as the only file that creates the `FastAPI()` instance.
- Use `@app.on_event("startup")` and `@app.on_event("shutdown")` for initialization and cleanup tasks.

---

## 2. Dependency Management

- Use **Poetry**, `pip-tools`, or **`uv`** for dependency pinning.
- Always separate runtime dependencies from development dependencies (`dev` extras for testing/linting tools).
- Common dependencies:

  - `fastapi` (web framework)
  - `uvicorn` (ASGI server)
  - `sqlalchemy` & `alembic` (ORM & migrations)
  - `pydantic` (data validation)
  - `pydantic-settings` (for settings management)
  - `pytest` (testing)
  - `python-dotenv` (environment variables)

---

## 3. Configuration

**3.1 Use Environment Variables**

- Store configuration in `.env` files (never commit to VCS).
- Use `pydantic_settings.BaseSettings` for type-safe config loading.

Example:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

**3.2 Environment Separation**

- `.env.dev` for development
- `.env.prod` for production

---

## 4. API Design

**4.1 Route Organization**

- Group routes by feature inside `api/v1/routes`.
- Use API versioning (e.g., `/api/v1/users`).

**4.2 Pydantic Schemas**

- Separate request & response models.
- Include `Config.orm_mode = True` for SQLAlchemy integration.

**4.3 Dependency Injection**

- Use `Depends()` for shared logic (e.g., authentication, DB session).

Example:

```python
from fastapi import Depends

@app.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
```

---

## 5. Error Handling

**5.1 Global Exception Handlers**

- Implement centralized exception handlers using `@app.exception_handler`.

Example:

```python
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )
```

**5.2 Custom Exceptions**

- Create custom exception classes for business logic errors.

---

## 6. Logging

- Use Python’s built-in `logging` module or `loguru` for structured logging.
- Log in JSON for production to integrate with monitoring tools.
- Configure log level by environment:

  - Development: `DEBUG`
  - Production: `INFO` or higher

---

## 7. Testing

**7.1 Test Strategy**

- **Unit tests** for services and utilities.
- **Integration tests** for DB/API flows.
- **End-to-end tests** for full workflows.

**7.2 Tools**

- Use `pytest` with `httpx.AsyncClient` for async API tests.

Example:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_read_main(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
```

---

## 8. Security

- Use **OAuth2 with JWT** for authentication.
- Always hash passwords with `passlib`.
- Sanitize all inputs to prevent SQL injection (use ORM/parameterized queries).
- Configure CORS by environment:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 9. Performance & Monitoring

- Use `prometheus_fastapi_instrumentator` for metrics.
- Implement `/health` endpoint for readiness/liveness checks.
- Consider using `async` for I/O-bound tasks and `BackgroundTasks` for non-blocking jobs.

---

## 10. Common Troubleshooting

This section addresses common errors and their solutions during development.

### 10.1 Pydantic v2: `ImportError` for `BaseSettings`

**Cause:**
In Pydantic version 2, the `BaseSettings` class was moved from the core `pydantic` library to a separate package, `pydantic-settings`. The code `from pydantic import BaseSettings` will fail with an `ImportError`.

**Solution:**

1.  **Install the new package:**
    ```bash
    pip install pydantic-settings
    ```
2.  **Update the import statement** in your configuration file (e.g., `app/core/config.py`):

    ```python
    # Before
    from pydantic import BaseSettings

    # After
    from pydantic_settings import BaseSettings
    ```

### 10.2 Hatch: Packaging Fails to Find Source Files

**Cause:**
By default, `hatch` looks for a source directory that matches the project name (e.g., `my_project/`) or is located at `src/my_project/`. If your source code is in a differently named directory, like `app/`, `hatch` won't automatically find the files to include in the package build.

**Solution:**
Explicitly specify the location of your package's source code in the `pyproject.toml` file. This tells `hatch` which directory to package.

**Example for `pyproject.toml`:**

```toml
[tool.hatch.build.targets.wheel]
# Add the name of your source directory to the 'packages' array.
packages = ["app"]
```
