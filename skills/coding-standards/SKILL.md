---
name: coding-standards
description: Universal coding standards, best practices, and patterns applicable to any programming language and technology stack.
---

# Coding Standards & Best Practices

Universal coding standards applicable across all projects and programming languages.

## Code Quality Principles

### 1. Readability First

- Code is read more than written
- Clear variable and function names
- Self-documenting code preferred over comments
- Consistent formatting

### 2. KISS (Keep It Simple, Stupid)

- Simplest solution that works
- Avoid over-engineering
- No premature optimization
- Easy to understand > clever code

### 3. DRY (Don't Repeat Yourself)

- Extract common logic into functions
- Create reusable components
- Share utilities across modules
- Avoid copy-paste programming

### 4. YAGNI (You Aren't Gonna Need It)

- Don't build features before they're needed
- Avoid speculative generality
- Add complexity only when required
- Start simple, refactor when needed

## Language-Agnostic Standards

### Variable Naming

```text
✅ GOOD: Descriptive names
- market_search_query = 'election'
- is_user_authenticated = True
- total_revenue = 1000
- user_count = 42

❌ BAD: Unclear names
- q = 'election'
- flag = True
- x = 1000
- tmp = 42
```

**Principles:**

- Use descriptive names that explain purpose
- Boolean variables should be questions (is_*, has_*, can_*)
- Avoid abbreviations unless widely understood
- Follow language-specific naming conventions (camelCase, snake_case, PascalCase)

### Function/Method Naming

```text
✅ GOOD: Verb-noun pattern
- fetchMarketData(marketId)
- calculateSimilarity(a, b)
- isValidEmail(email)
- getUserById(id)

❌ BAD: Unclear or noun-only
- market(id)
- similarity(a, b)
- email(e)
- user(id)
```

**Principles:**

- Functions should be verbs or verb phrases
- Methods that return booleans should be questions (isValid, hasPermission)
- Be consistent with language conventions (get_*, fetch_*, calculate_*)

### Immutability Pattern

**When applicable (functional languages, immutable data structures):**

```python
✅ GOOD: Create new objects/collections
# Python example
updated_user = {**user, 'name': 'New Name'}
updated_list = items + [new_item]

# Or use immutable data structures
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class User:
    name: str
    email: str

❌ BAD: Direct mutation (when immutability is expected)
user.name = 'New Name'  # BAD if immutability is required
items.append(new_item)  # BAD if immutability is required
```

**Principles:**

- Prefer immutability where language supports it
- When mutation is necessary, document why
- Use immutable data structures when available (tuples, frozen dataclasses, etc.)

### Error Handling

```python
✅ GOOD: Comprehensive error handling
def fetch_data(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        logger.error(f'HTTP error {e.response.status_code}: {e}')
        raise DataFetchError(f'Failed to fetch data: {e}') from e
    except requests.RequestException as e:
        logger.error(f'Request failed: {e}')
        raise DataFetchError(f'Network error: {e}') from e

❌ BAD: No error handling
def fetch_data(url):
    response = requests.get(url)
    return response.json()
```

**Principles:**

- Always handle expected errors
- Use specific exception types, not generic ones
- Log errors with context
- Re-raise with meaningful messages
- Follow language-specific error handling patterns (exceptions, Result types, etc.)

### Concurrency Best Practices

```python
✅ GOOD: Parallel execution when possible
# Python example
import asyncio

async def fetch_all():
    users, markets, stats = await asyncio.gather(
        fetch_users(),
        fetch_markets(),
        fetch_stats()
    )
    return users, markets, stats

# Or with threads/processes
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor() as executor:
    results = executor.map(fetch_data, urls)

❌ BAD: Sequential when unnecessary
users = fetch_users()
markets = fetch_markets()
stats = fetch_stats()
```

**Principles:**

- Execute independent operations in parallel
- Use appropriate concurrency primitives (async/await, threads, processes, goroutines)
- Be aware of language-specific best practices

### Type Safety

**For statically-typed languages:**

```python
✅ GOOD: Proper types
# Python with type hints
from typing import Protocol, Literal

class Market(Protocol):
    id: str
    name: str
    status: Literal['active', 'resolved', 'closed']
    created_at: datetime

def get_market(market_id: str) -> Market:
    # Implementation
    pass

❌ BAD: Using generic types or no types
def get_market(market_id):  # No type hints
    # Implementation
    pass

def get_market(market_id: Any) -> Any:  # Too generic
    # Implementation
    pass
```

**Principles:**

- Use type hints/annotations when available
- Prefer specific types over generic ones (Any, object, etc.)
- Leverage language type system features (generics, unions, protocols)
- For dynamically-typed languages, use type hints where supported

## Component/Module Architecture

### Separation of Concerns

```python
✅ GOOD: Clear separation
# Business logic
class MarketService:
    def calculate_odds(self, market: Market) -> float:
        # Pure business logic
        pass

# Presentation/UI layer
class MarketView:
    def render(self, market: Market):
        # Only presentation logic
        pass

❌ BAD: Mixed concerns
class Market:
    def calculate_odds(self):
        # Business logic
        pass

    def render_html(self):
        # Presentation logic mixed with business logic
        pass
```

**Principles:**

- Separate business logic from presentation
- Keep components/modules focused on single responsibility
- Use dependency injection for testability
- Follow language/framework-specific patterns (MVC, MVP, MVVM, etc.)

### Reusability

```python
✅ GOOD: Reusable utilities
# Generic debounce function
def debounce(func, delay):
    """Debounce function calls"""
    # Implementation
    pass

# Usage
debounced_search = debounce(search_function, 500)

❌ BAD: Duplicated logic
# Same logic repeated in multiple places
def search_a():
    # ... debounce logic ...
    pass

def search_b():
    # ... same debounce logic ...
    pass
```

**Principles:**

- Extract common logic into reusable functions/utilities
- Create generic solutions that work across contexts
- Use composition over inheritance where appropriate

### State Management

```python
✅ GOOD: Immutable state updates
# Functional update pattern
def update_count(current_count):
    return current_count + 1

# Or with state management libraries
state = update_state(state, lambda s: {**s, 'count': s['count'] + 1})

❌ BAD: Direct mutation in shared state
state['count'] = state['count'] + 1  # Can cause issues in concurrent scenarios
```

**Principles:**

- Prefer immutable state updates
- Use functional updates when state depends on previous state
- Be careful with shared mutable state in concurrent environments
- Follow framework-specific state management patterns

## API Design Standards

### REST API Conventions

```text
GET    /api/markets              # List all markets
GET    /api/markets/:id          # Get specific market
POST   /api/markets              # Create new market
PUT    /api/markets/:id          # Update market (full)
PATCH  /api/markets/:id          # Update market (partial)
DELETE /api/markets/:id          # Delete market

# Query parameters for filtering
GET /api/markets?status=active&limit=10&offset=0
```

**Principles:**

- Use standard HTTP methods correctly
- Use plural nouns for resource names
- Use query parameters for filtering, sorting, pagination
- Use path parameters for resource identification
- Follow RESTful conventions for your domain

### Response Format

```json
✅ GOOD: Consistent response structure
{
  "success": true,
  "data": { ... },
  "meta": {
    "total": 100,
    "page": 1,
    "limit": 10
  }
}

# Error response
{
  "success": false,
  "error": "Invalid request",
  "details": { ... }
}

❌ BAD: Inconsistent structure
# Sometimes returns data directly
{ "id": 1, "name": "Market" }

# Sometimes wrapped
{ "result": { "id": 1, "name": "Market" } }
```

**Principles:**

- Use consistent response structure across all endpoints
- Include success/error indicators
- Provide metadata for paginated responses
- Use appropriate HTTP status codes
- Include error details for debugging (in development)

### Input Validation

```python
✅ GOOD: Schema validation
# Python example with Pydantic
from pydantic import BaseModel, Field, validator
from typing import List
from datetime import datetime

class CreateMarketSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    end_date: datetime
    categories: List[str] = Field(..., min_items=1)

def create_market(data: dict):
    try:
        validated = CreateMarketSchema(**data)
        # Proceed with validated data
    except ValidationError as e:
        return {
            "success": False,
            "error": "Validation failed",
            "details": e.errors()
        }, 400
```

**Principles:**

- Always validate input data
- Use schema validation libraries when available
- Return clear validation error messages
- Validate at API boundaries
- Use type-safe validation where possible

## File Organization

### Project Structure

**General principles:**

- Organize by feature or by layer (depending on project size)
- Keep related code together
- Separate concerns (business logic, data access, presentation)
- Use clear, descriptive directory names

**Example structure (language-agnostic):**

```text
src/
├── api/                    # API endpoints/routes
│   ├── markets/           # Market-related endpoints
│   └── auth/              # Authentication endpoints
├── services/              # Business logic layer
│   ├── market_service.py
│   └── user_service.py
├── models/                # Data models/entities
│   ├── market.py
│   └── user.py
├── repositories/          # Data access layer
│   ├── market_repository.py
│   └── user_repository.py
├── utils/                 # Utility functions
│   ├── validators.py
│   └── formatters.py
├── config/                # Configuration files
└── tests/                 # Test files
    ├── unit/
    └── integration/
```

**Principles:**

- Follow language/framework conventions (Django, Rails, Spring Boot, etc.)
- Group related functionality together
- Keep directory depth reasonable (3-4 levels max)
- Use clear, descriptive names

### File Naming

**Follow language-specific conventions:**

```text
# Python: snake_case
market_service.py
user_repository.py
calculate_odds.py

# Java: PascalCase
MarketService.java
UserRepository.java
CalculateOdds.java

# Go: snake_case or camelCase
market_service.go
userRepository.go

# JavaScript/TypeScript: camelCase
marketService.ts
userRepository.ts
calculateOdds.ts
```

**Principles:**

- Follow language and framework conventions
- Be consistent within a project
- Use descriptive names that indicate purpose
- Group related files with prefixes/suffixes when helpful

## Comments & Documentation

### When to Comment

```python
✅ GOOD: Explain WHY, not WHAT
# Use exponential backoff to avoid overwhelming the API during outages
delay = min(1000 * (2 ** retry_count), 30000)

# Deliberately using mutation here for performance with large arrays
items.append(new_item)

# This algorithm uses O(n log n) time complexity, which is acceptable
# for our use case where n < 1000
result = sorted(data, key=lambda x: x.priority)

❌ BAD: Stating the obvious
# Increment counter by 1
count += 1

# Set name to user's name
name = user.name

# Calculate total
total = sum(items)
```

**Principles:**

- Explain **why** something is done, not **what** it does
- Document complex algorithms and business logic
- Explain non-obvious decisions and trade-offs
- Comment on performance considerations
- Avoid redundant comments that just restate the code

### Documentation for Public APIs

**Python example (docstrings):**

```python
def search_markets(query: str, limit: int = 10) -> List[Market]:
    """
    Searches markets using semantic similarity.

    Args:
        query: Natural language search query
        limit: Maximum number of results (default: 10)

    Returns:
        List of markets sorted by similarity score

    Raises:
        APIError: If OpenAI API fails or Redis unavailable

    Example:
        >>> results = search_markets('election', 5)
        >>> print(results[0].name)
        "Trump vs Biden"
    """
    # Implementation
    pass
```

**Java example (Javadoc):**

```java
/**
 * Searches markets using semantic similarity.
 *
 * @param query Natural language search query
 * @param limit Maximum number of results (default: 10)
 * @return List of markets sorted by similarity score
 * @throws APIException If OpenAI API fails or Redis unavailable
 */
public List<Market> searchMarkets(String query, int limit) {
    // Implementation
}
```

**Principles:**

- Document all public APIs (functions, classes, methods)
- Use language-standard documentation formats (docstrings, JSDoc, Javadoc, etc.)
- Include parameter descriptions, return values, exceptions
- Provide usage examples
- Keep documentation up-to-date with code changes

## Performance Best Practices

### Memoization and Caching

```python
✅ GOOD: Cache expensive computations
# Python example
from functools import lru_cache

@lru_cache(maxsize=128)
def calculate_fibonacci(n: int) -> int:
    if n < 2:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# Or manual caching
cache = {}

def expensive_operation(key):
    if key not in cache:
        cache[key] = compute_expensive_value(key)
    return cache[key]

❌ BAD: Recomputing same values
def expensive_operation(key):
    return compute_expensive_value(key)  # Computes every time
```

**Principles:**

- Cache results of expensive computations
- Use language-provided caching mechanisms (decorators, memoization libraries)
- Be aware of memory trade-offs
- Invalidate cache when data changes

### Lazy Loading

```python
✅ GOOD: Load resources on demand
# Python example
def get_heavy_module():
    # Only import when needed
    import heavy_module
    return heavy_module

# Or with lazy initialization
class DataLoader:
    def __init__(self):
        self._data = None

    @property
    def data(self):
        if self._data is None:
            self._data = self._load_data()
        return self._data

❌ BAD: Loading everything upfront
# Loading all modules at startup
import heavy_module_1
import heavy_module_2
import heavy_module_3
```

**Principles:**

- Load resources only when needed
- Use lazy initialization for expensive operations
- Defer loading of optional features
- Consider lazy evaluation in functional languages

### Database Queries

```python
✅ GOOD: Select only needed columns
# SQL
SELECT id, name, status FROM markets LIMIT 10;

# ORM example (SQLAlchemy)
markets = session.query(Market.id, Market.name, Market.status)\
    .limit(10).all()

❌ BAD: Select everything
SELECT * FROM markets;

# ORM
markets = session.query(Market).limit(10).all()  # Loads all columns
```

**Principles:**

- Select only columns you need
- Use pagination for large result sets
- Use indexes appropriately
- Avoid N+1 query problems
- Use query optimization tools (EXPLAIN, query analyzers)

## Testing Standards

### Test Structure (AAA Pattern)

```python
✅ GOOD: Arrange-Act-Assert pattern
def test_calculates_similarity_correctly():
    # Arrange
    vector1 = [1, 0, 0]
    vector2 = [0, 1, 0]

    # Act
    similarity = calculate_cosine_similarity(vector1, vector2)

    # Assert
    assert similarity == 0

# Java example
@Test
public void testCalculatesSimilarityCorrectly() {
    // Arrange
    double[] vector1 = {1, 0, 0};
    double[] vector2 = {0, 1, 0};

    // Act
    double similarity = calculateCosineSimilarity(vector1, vector2);

    // Assert
    assertEquals(0.0, similarity, 0.001);
}
```

**Principles:**

- Use Arrange-Act-Assert (AAA) or Given-When-Then pattern
- Keep tests focused on single behavior
- Make test intent clear through structure

### Test Naming

```python
✅ GOOD: Descriptive test names
def test_returns_empty_array_when_no_markets_match_query():
    pass

def test_throws_error_when_api_key_is_missing():
    pass

def test_falls_back_to_substring_search_when_redis_unavailable():
    pass

❌ BAD: Vague test names
def test_works():
    pass

def test_search():
    pass

def test_market():
    pass
```

**Principles:**

- Test names should describe the behavior being tested
- Include expected outcome in name
- Use language-appropriate naming conventions
- Be specific about conditions and expected results

## Code Smell Detection

Watch for these anti-patterns:

### 1. Long Functions

```python
❌ BAD: Function > 50 lines
def process_market_data():
    # 100 lines of code
    pass

✅ GOOD: Split into smaller functions
def process_market_data():
    validated = validate_data()
    transformed = transform_data(validated)
    return save_data(transformed)
```

**Principles:**

- Keep functions focused and short (typically < 50 lines)
- Extract complex logic into separate functions
- One function should do one thing well

### 2. Deep Nesting

```python
❌ BAD: 5+ levels of nesting
if user:
    if user.is_admin:
        if market:
            if market.is_active:
                if has_permission:
                    # Do something
                    pass

✅ GOOD: Early returns/guards
if not user:
    return
if not user.is_admin:
    return
if not market:
    return
if not market.is_active:
    return
if not has_permission:
    return

# Do something
```

**Principles:**

- Use early returns/guard clauses to reduce nesting
- Prefer flat structure over deep nesting
- Extract complex conditions into well-named functions
- Maximum nesting depth: 3-4 levels

### 3. Magic Numbers and Strings

```python
❌ BAD: Unexplained numbers/strings
if retry_count > 3:
    pass
time.sleep(500)

status = "active"

✅ GOOD: Named constants
MAX_RETRIES = 3
DEBOUNCE_DELAY_MS = 500
MARKET_STATUS_ACTIVE = "active"

if retry_count > MAX_RETRIES:
    pass
time.sleep(DEBOUNCE_DELAY_MS / 1000)

status = MARKET_STATUS_ACTIVE
```

**Principles:**

- Replace magic numbers with named constants
- Replace magic strings with constants or enums
- Use configuration files for environment-specific values
- Make constants easy to find and modify

### 4. Code Duplication

```python
❌ BAD: Repeated logic
def process_user_a(user):
    if user.is_valid():
        user.save()
        send_email(user.email)

def process_user_b(user):
    if user.is_valid():
        user.save()
        send_email(user.email)

✅ GOOD: Extract common logic
def save_and_notify_user(user):
    if user.is_valid():
        user.save()
        send_email(user.email)

def process_user_a(user):
    save_and_notify_user(user)

def process_user_b(user):
    save_and_notify_user(user)
```

**Principles:**

- Don't repeat yourself (DRY)
- Extract common patterns into reusable functions
- Use inheritance or composition to share behavior
- Be careful not to over-abstract

**Remember**: Code quality is not negotiable. Clear, maintainable code enables rapid development and confident refactoring.
