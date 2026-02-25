---
name: backend-patterns
description: Backend architecture patterns, API design, database optimization, and server-side best practices for Node.js, Express, and Next.js API routes.
---

# Backend Development Patterns

Backend architecture patterns and best practices for scalable server-side applications.

## ⚠️ Security First

**CRITICAL**: All examples in this document are educational patterns. In production:

- ✅ Always validate and sanitize user input
- ✅ Never hardcode secrets (use environment variables)
- ✅ Verify environment variables exist before use
- ✅ Use parameterized queries (never string concatenation)
- ✅ Implement rate limiting on all public endpoints
- ✅ Enable Row Level Security (RLS) on database tables
- ✅ Use HTTPS in production
- ✅ Sanitize error messages (don't expose internal details)
- ✅ Implement proper authentication and authorization
- ✅ Log security events but never log secrets or PII

## API Design Patterns

### RESTful API Structure

```typescript
// ✅ Resource-based URLs
GET    /api/markets                 # List resources
GET    /api/markets/:id             # Get single resource
POST   /api/markets                 # Create resource
PUT    /api/markets/:id             # Replace resource
PATCH  /api/markets/:id             # Update resource
DELETE /api/markets/:id             # Delete resource

// ✅ Query parameters for filtering, sorting, pagination
GET /api/markets?status=active&sort=volume&limit=20&offset=0
```

### Repository Pattern

```typescript
// Abstract data access logic
interface MarketRepository {
  findAll(filters?: MarketFilters): Promise<Market[]>
  findById(id: string): Promise<Market | null>
  create(data: CreateMarketDto): Promise<Market>
  update(id: string, data: UpdateMarketDto): Promise<Market>
  delete(id: string): Promise<void>
}

class SupabaseMarketRepository implements MarketRepository {
  async findAll(filters?: MarketFilters): Promise<Market[]> {
    // ✅ SECURITY: Select specific columns (not *) to prevent data leakage
    let query = supabase.from('markets').select('id, name, status, volume, created_at')

    // ✅ SECURITY: Validate and sanitize filter inputs
    if (filters?.status) {
      // Whitelist allowed status values
      const allowedStatuses = ['active', 'inactive', 'pending']
      if (allowedStatuses.includes(filters.status)) {
        query = query.eq('status', filters.status)
      }
    }

    // ✅ SECURITY: Limit max results to prevent DoS
    const limit = filters?.limit
      ? Math.min(Math.max(1, filters.limit), 100)  // Between 1 and 100
      : 10
    query = query.limit(limit)

    const { data, error } = await query

    if (error) {
      // ✅ SECURITY: Don't expose database error details
      console.error('Database error:', error)
      throw new Error('Failed to fetch markets')
    }
    return data || []
  }

  // Other methods...
}
```

### Service Layer Pattern

```typescript
// Business logic separated from data access
class MarketService {
  constructor(private marketRepo: MarketRepository) {}

  async searchMarkets(query: string, limit: number = 10): Promise<Market[]> {
    // ✅ SECURITY: Validate and sanitize search query
    if (!query || typeof query !== 'string') {
      throw new Error('Invalid search query')
    }

    // ✅ SECURITY: Sanitize query (remove potentially dangerous characters)
    const sanitizedQuery = query.trim().slice(0, 500)  // Max length

    // ✅ SECURITY: Limit max results to prevent DoS
    const safeLimit = Math.min(Math.max(1, limit), 50)  // Between 1 and 50

    // Business logic
    const embedding = await generateEmbedding(sanitizedQuery)
    const results = await this.vectorSearch(embedding, safeLimit)

    // Fetch full data
    const markets = await this.marketRepo.findByIds(results.map(r => r.id))

    // Sort by similarity
    return markets.sort((a, b) => {
      const scoreA = results.find(r => r.id === a.id)?.score || 0
      const scoreB = results.find(r => r.id === b.id)?.score || 0
      return scoreA - scoreB
    })
  }

  private async vectorSearch(embedding: number[], limit: number) {
    // Vector search implementation
  }
}
```

### Middleware Pattern

```typescript
// Request/response processing pipeline
export function withAuth(handler: NextApiHandler): NextApiHandler {
  return async (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '')

    if (!token) {
      return res.status(401).json({ error: 'Unauthorized' })
    }

    try {
      const user = await verifyToken(token)
      req.user = user
      return handler(req, res)
    } catch (error) {
      return res.status(401).json({ error: 'Invalid token' })
    }
  }
}

// Usage
export default withAuth(async (req, res) => {
  // Handler has access to req.user
})
```

## Database Patterns

### Query Optimization

```typescript
// ✅ GOOD: Select only needed columns
const { data } = await supabase
  .from('markets')
  .select('id, name, status, volume')
  .eq('status', 'active')
  .order('volume', { ascending: false })
  .limit(10)

// ❌ BAD: Select everything
const { data } = await supabase
  .from('markets')
  .select('*')
```

### N+1 Query Prevention

```typescript
// ❌ BAD: N+1 query problem
const markets = await getMarkets()
for (const market of markets) {
  market.creator = await getUser(market.creator_id)  // N queries
}

// ✅ GOOD: Batch fetch
const markets = await getMarkets()
const creatorIds = markets.map(m => m.creator_id)
const creators = await getUsers(creatorIds)  // 1 query
const creatorMap = new Map(creators.map(c => [c.id, c]))

markets.forEach(market => {
  market.creator = creatorMap.get(market.creator_id)
})
```

### Transaction Pattern

```typescript
async function createMarketWithPosition(
  marketData: CreateMarketDto,
  positionData: CreatePositionDto
) {
  // Use Supabase transaction
  const { data, error } = await supabase.rpc('create_market_with_position', {
    market_data: marketData,
    position_data: positionData
  })

  if (error) throw new Error('Transaction failed')
  return data
}

// SQL function in Supabase
CREATE OR REPLACE FUNCTION create_market_with_position(
  market_data jsonb,
  position_data jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
BEGIN
  -- Start transaction automatically
  INSERT INTO markets VALUES (market_data);
  INSERT INTO positions VALUES (position_data);
  RETURN jsonb_build_object('success', true);
EXCEPTION
  WHEN OTHERS THEN
    -- Rollback happens automatically
    RETURN jsonb_build_object('success', false, 'error', SQLERRM);
END;
$$;
```

## Caching Strategies

### Redis Caching Layer

```typescript
class CachedMarketRepository implements MarketRepository {
  constructor(
    private baseRepo: MarketRepository,
    private redis: RedisClient
  ) {}

  async findById(id: string): Promise<Market | null> {
    // Check cache first
    const cached = await this.redis.get(`market:${id}`)

    if (cached) {
      return JSON.parse(cached)
    }

    // Cache miss - fetch from database
    const market = await this.baseRepo.findById(id)

    if (market) {
      // Cache for 5 minutes
      await this.redis.setex(`market:${id}`, 300, JSON.stringify(market))
    }

    return market
  }

  async invalidateCache(id: string): Promise<void> {
    await this.redis.del(`market:${id}`)
  }
}
```

### Cache-Aside Pattern

```typescript
async function getMarketWithCache(id: string): Promise<Market> {
  // ✅ SECURITY: Validate and sanitize ID input
  if (!id || typeof id !== 'string' || id.length > 100) {
    throw new Error('Invalid market ID')
  }

  // ✅ SECURITY: Sanitize cache key to prevent injection
  const sanitizedId = id.replace(/[^a-zA-Z0-9-_]/g, '')
  const cacheKey = `market:${sanitizedId}`

  // Try cache
  const cached = await redis.get(cacheKey)
  if (cached) {
    try {
      return JSON.parse(cached)
    } catch (error) {
      // Invalid cache data - continue to DB fetch
      console.warn('Invalid cache data for', cacheKey)
    }
  }

  // Cache miss - fetch from DB
  const market = await db.markets.findUnique({ where: { id: sanitizedId } })

  if (!market) throw new Error('Market not found')

  // Update cache
  await redis.setex(cacheKey, 300, JSON.stringify(market))

  return market
}
```

## Error Handling Patterns

### Centralized Error Handler

```typescript
class ApiError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public isOperational = true
  ) {
    super(message)
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

export function errorHandler(error: unknown, req: Request): Response {
  if (error instanceof ApiError) {
    return NextResponse.json({
      success: false,
      error: error.message
    }, { status: error.statusCode })
  }

  if (error instanceof z.ZodError) {
    return NextResponse.json({
      success: false,
      error: 'Validation failed',
      details: error.errors
    }, { status: 400 })
  }

  // ✅ SECURITY: Log errors but don't expose sensitive details
  console.error('Unexpected error:', {
    message: error instanceof Error ? error.message : 'Unknown error',
    // Never log full stack traces or sensitive data in production
    ...(process.env.NODE_ENV === 'development' && { stack: error instanceof Error ? error.stack : undefined })
  })

  // ✅ SECURITY: Generic error message for users (don't leak internal details)
  return NextResponse.json({
    success: false,
    error: 'Internal server error'
  }, { status: 500 })
}

// Usage
export async function GET(request: Request) {
  try {
    const data = await fetchData()
    return NextResponse.json({ success: true, data })
  } catch (error) {
    return errorHandler(error, request)
  }
}
```

### Retry with Exponential Backoff

```typescript
async function fetchWithRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3
): Promise<T> {
  let lastError: Error

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error as Error

      if (i < maxRetries - 1) {
        // Exponential backoff: 1s, 2s, 4s
        const delay = Math.pow(2, i) * 1000
        await new Promise(resolve => setTimeout(resolve, delay))
      }
    }
  }

  throw lastError!
}

// Usage
const data = await fetchWithRetry(() => fetchFromAPI())
```

## Authentication & Authorization

### JWT Token Validation

```typescript
import jwt from 'jsonwebtoken'

interface JWTPayload {
  userId: string
  email: string
  role: 'admin' | 'user'
}

export function verifyToken(token: string): JWTPayload {
  // ✅ SECURITY: Verify secret exists before use
  const secret = process.env.JWT_SECRET
  if (!secret) {
    throw new Error('JWT_SECRET environment variable not configured')
  }

  // ✅ SECURITY: Validate token format
  if (!token || typeof token !== 'string' || token.length < 10) {
    throw new ApiError(401, 'Invalid token format')
  }

  try {
    const payload = jwt.verify(token, secret) as JWTPayload
    return payload
  } catch (error) {
    throw new ApiError(401, 'Invalid token')
  }
}

export async function requireAuth(request: Request) {
  // ✅ SECURITY: Validate authorization header format
  const authHeader = request.headers.get('authorization')
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new ApiError(401, 'Missing or invalid authorization header')
  }

  const token = authHeader.replace('Bearer ', '').trim()

  if (!token) {
    throw new ApiError(401, 'Missing authorization token')
  }

  return verifyToken(token)
}

// Usage in API route
export async function GET(request: Request) {
  const user = await requireAuth(request)

  const data = await getDataForUser(user.userId)

  return NextResponse.json({ success: true, data })
}
```

### Role-Based Access Control

```typescript
type Permission = 'read' | 'write' | 'delete' | 'admin'

interface User {
  id: string
  role: 'admin' | 'moderator' | 'user'
}

const rolePermissions: Record<User['role'], Permission[]> = {
  admin: ['read', 'write', 'delete', 'admin'],
  moderator: ['read', 'write', 'delete'],
  user: ['read', 'write']
}

export function hasPermission(user: User, permission: Permission): boolean {
  return rolePermissions[user.role].includes(permission)
}

export function requirePermission(permission: Permission) {
  return async (request: Request) => {
    const user = await requireAuth(request)

    if (!hasPermission(user, permission)) {
      throw new ApiError(403, 'Insufficient permissions')
    }

    return user
  }
}

// Usage
export const DELETE = requirePermission('delete')(async (request: Request) => {
  // Handler with permission check
})
```

## Rate Limiting

### Simple In-Memory Rate Limiter

```typescript
class RateLimiter {
  private requests = new Map<string, number[]>()

  async checkLimit(
    identifier: string,
    maxRequests: number,
    windowMs: number
  ): Promise<boolean> {
    const now = Date.now()
    const requests = this.requests.get(identifier) || []

    // Remove old requests outside window
    const recentRequests = requests.filter(time => now - time < windowMs)

    if (recentRequests.length >= maxRequests) {
      return false  // Rate limit exceeded
    }

    // Add current request
    recentRequests.push(now)
    this.requests.set(identifier, recentRequests)

    return true
  }
}

const limiter = new RateLimiter()

export async function GET(request: Request) {
  // ✅ SECURITY: Sanitize IP address to prevent injection
  const forwardedFor = request.headers.get('x-forwarded-for')
  const ip = forwardedFor
    ? forwardedFor.split(',')[0].trim()  // Take first IP if multiple
    : 'unknown'

  // ✅ SECURITY: Validate IP format (basic check)
  if (ip !== 'unknown' && !/^[\d.:a-fA-F]+$/.test(ip)) {
    return NextResponse.json({
      error: 'Invalid request'
    }, { status: 400 })
  }

  const allowed = await limiter.checkLimit(ip, 100, 60000)  // 100 req/min

  if (!allowed) {
    return NextResponse.json({
      error: 'Rate limit exceeded'
    }, { status: 429 })
  }

  // Continue with request
}
```

## Background Jobs & Queues

### Simple Queue Pattern

```typescript
class JobQueue<T> {
  private queue: T[] = []
  private processing = false

  async add(job: T): Promise<void> {
    this.queue.push(job)

    if (!this.processing) {
      this.process()
    }
  }

  private async process(): Promise<void> {
    this.processing = true

    while (this.queue.length > 0) {
      const job = this.queue.shift()!

      try {
        await this.execute(job)
      } catch (error) {
        console.error('Job failed:', error)
      }
    }

    this.processing = false
  }

  private async execute(job: T): Promise<void> {
    // Job execution logic
  }
}

// Usage for indexing markets
interface IndexJob {
  marketId: string
}

const indexQueue = new JobQueue<IndexJob>()

export async function POST(request: Request) {
  // ✅ SECURITY: Validate input data
  const body = await request.json()

  if (!body || typeof body.marketId !== 'string') {
    return NextResponse.json({
      error: 'Invalid request: marketId required'
    }, { status: 400 })
  }

  // ✅ SECURITY: Sanitize marketId (UUID format check)
  const marketId = body.marketId.trim()
  if (!/^[a-f0-9-]{36}$/i.test(marketId)) {
    return NextResponse.json({
      error: 'Invalid marketId format'
    }, { status: 400 })
  }

  // Add to queue instead of blocking
  await indexQueue.add({ marketId })

  return NextResponse.json({ success: true, message: 'Job queued' })
}
```

## Logging & Monitoring

### Structured Logging

```typescript
interface LogContext {
  userId?: string
  requestId?: string
  method?: string
  path?: string
  [key: string]: unknown
}

class Logger {
  log(level: 'info' | 'warn' | 'error', message: string, context?: LogContext) {
    const entry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      ...context
    }

    console.log(JSON.stringify(entry))
  }

  info(message: string, context?: LogContext) {
    this.log('info', message, context)
  }

  warn(message: string, context?: LogContext) {
    this.log('warn', message, context)
  }

  error(message: string, error: Error, context?: LogContext) {
    this.log('error', message, {
      ...context,
      error: error.message,
      stack: error.stack
    })
  }
}

const logger = new Logger()

// Usage
export async function GET(request: Request) {
  const requestId = crypto.randomUUID()

  logger.info('Fetching markets', {
    requestId,
    method: 'GET',
    path: '/api/markets'
  })

  try {
    const markets = await fetchMarkets()
    return NextResponse.json({ success: true, data: markets })
  } catch (error) {
    logger.error('Failed to fetch markets', error as Error, { requestId })
    return NextResponse.json({ error: 'Internal error' }, { status: 500 })
  }
}
```

## Security Reminders

Before deploying any code based on these patterns:

1. **Environment Variables**: Never commit secrets. Always verify they exist:

```typescript
const secret = process.env.SECRET_KEY
if (!secret) throw new Error('SECRET_KEY not configured')
```

2. **Input Validation**: Always validate and sanitize user input using Zod or similar:

```typescript
const schema = z.object({ id: z.string().uuid() })
const validated = schema.parse(input)
```

3. **Database Security**:
   - Use parameterized queries (Supabase client does this automatically)
   - Enable Row Level Security (RLS) on all tables
   - Never expose database credentials

4. **Error Handling**: Never expose internal error details to users:

```typescript
// ❌ BAD
return res.json({ error: error.message })

// ✅ GOOD
console.error('Internal error:', error)
return res.json({ error: 'An error occurred' })
```

5. **Rate Limiting**: Always implement rate limiting on public endpoints

6. **Authentication**: Verify tokens on every protected endpoint

7. **Logging**: Log security events but never log secrets, passwords, or PII

**Remember**: Backend patterns enable scalable, maintainable server-side applications. Choose patterns that fit your complexity level, but **never compromise on security**.
