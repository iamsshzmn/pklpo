---
name: frontend-patterns
description: Frontend development patterns for React, Next.js, state management, performance optimization, and UI best practices.
---

# Frontend Development Patterns

Modern frontend patterns for React, Next.js, and performant user interfaces.

## Component Patterns

### Composition Over Inheritance

```typescript
// ✅ GOOD: Component composition
interface CardProps {
  children: React.ReactNode
  variant?: 'default' | 'outlined'
}

export function Card({ children, variant = 'default' }: CardProps) {
  return <div className={`card card-${variant}`}>{children}</div>
}

export function CardHeader({ children }: { children: React.ReactNode }) {
  return <div className="card-header">{children}</div>
}

export function CardBody({ children }: { children: React.ReactNode }) {
  return <div className="card-body">{children}</div>
}

// Usage
<Card>
  <CardHeader>Title</CardHeader>
  <CardBody>Content</CardBody>
</Card>
```

### Compound Components

```typescript
interface TabsContextValue {
  activeTab: string
  setActiveTab: (tab: string) => void
}

const TabsContext = createContext<TabsContextValue | undefined>(undefined)

export function Tabs({ children, defaultTab }: {
  children: React.ReactNode
  defaultTab: string
}) {
  const [activeTab, setActiveTab] = useState(defaultTab)

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      {children}
    </TabsContext.Provider>
  )
}

export function TabList({ children }: { children: React.ReactNode }) {
  return <div className="tab-list">{children}</div>
}

export function Tab({ id, children }: { id: string, children: React.ReactNode }) {
  const context = useContext(TabsContext)
  if (!context) throw new Error('Tab must be used within Tabs')

  return (
    <button
      className={context.activeTab === id ? 'active' : ''}
      onClick={() => context.setActiveTab(id)}
    >
      {children}
    </button>
  )
}

// Usage
<Tabs defaultTab="overview">
  <TabList>
    <Tab id="overview">Overview</Tab>
    <Tab id="details">Details</Tab>
  </TabList>
</Tabs>
```

### Render Props Pattern

```typescript
interface DataLoaderProps<T> {
  url: string
  children: (data: T | null, loading: boolean, error: Error | null) => React.ReactNode
}

// ✅ SECURE: Validate URL to prevent SSRF
function validateUrl(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin)
    // Only allow same-origin or whitelisted domains
    const allowedHosts = ['api.example.com', 'cdn.example.com']
    return parsed.origin === window.location.origin ||
           allowedHosts.includes(parsed.hostname)
  } catch {
    return false
  }
}

export function DataLoader<T>({ url, children }: DataLoaderProps<T>) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    // ✅ SECURITY: Validate URL before fetching
    if (!validateUrl(url)) {
      setError(new Error('Invalid URL'))
      setLoading(false)
      return
    }

    fetch(url, {
      credentials: 'same-origin', // ✅ Don't send credentials to external domains
      headers: {
        'Content-Type': 'application/json',
      }
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false))
  }, [url])

  return <>{children(data, loading, error)}</>
}

// Usage
<DataLoader<Market[]> url="/api/markets">
  {(markets, loading, error) => {
    if (loading) return <Spinner />
    if (error) return <Error error={error} />
    return <MarketList markets={markets!} />
  }}
</DataLoader>
```

## Custom Hooks Patterns

### State Management Hook

```typescript
export function useToggle(initialValue = false): [boolean, () => void] {
  const [value, setValue] = useState(initialValue)

  const toggle = useCallback(() => {
    setValue(v => !v)
  }, [])

  return [value, toggle]
}

// Usage
const [isOpen, toggleOpen] = useToggle()
```

### Async Data Fetching Hook

```typescript
interface UseQueryOptions<T> {
  onSuccess?: (data: T) => void
  onError?: (error: Error) => void
  enabled?: boolean
}

export function useQuery<T>(
  key: string,
  fetcher: () => Promise<T>,
  options?: UseQueryOptions<T>
) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(false)

  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const result = await fetcher()
      setData(result)
      options?.onSuccess?.(result)
    } catch (err) {
      const error = err as Error
      setError(error)
      // ✅ SECURITY: Don't log sensitive error details to console in production
      if (process.env.NODE_ENV === 'development') {
        options?.onError?.(error)
      } else {
        options?.onError?.(new Error('Request failed'))
      }
    } finally {
      setLoading(false)
    }
  }, [fetcher, options])

  useEffect(() => {
    if (options?.enabled !== false) {
      refetch()
    }
  }, [key, refetch, options?.enabled])

  return { data, error, loading, refetch }
}

// ✅ SECURE Usage with validated URL
const { data: markets, loading, error, refetch } = useQuery(
  'markets',
  async () => {
    const response = await fetch('/api/markets', {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  },
  {
    onSuccess: data => {
      // ✅ SECURITY: Only log non-sensitive data
      if (process.env.NODE_ENV === 'development') {
        console.log('Fetched', data.length, 'markets')
      }
    },
    onError: err => {
      // ✅ SECURITY: Generic error messages in production
      console.error('Failed to fetch markets')
    }
  }
)
```

### Debounce Hook

```typescript
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}

// Usage
const [searchQuery, setSearchQuery] = useState('')
const debouncedQuery = useDebounce(searchQuery, 500)

useEffect(() => {
  if (debouncedQuery) {
    performSearch(debouncedQuery)
  }
}, [debouncedQuery])
```

## State Management Patterns

### Context + Reducer Pattern

```typescript
interface State {
  markets: Market[]
  selectedMarket: Market | null
  loading: boolean
}

type Action =
  | { type: 'SET_MARKETS'; payload: Market[] }
  | { type: 'SELECT_MARKET'; payload: Market }
  | { type: 'SET_LOADING'; payload: boolean }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_MARKETS':
      return { ...state, markets: action.payload }
    case 'SELECT_MARKET':
      return { ...state, selectedMarket: action.payload }
    case 'SET_LOADING':
      return { ...state, loading: action.payload }
    default:
      return state
  }
}

const MarketContext = createContext<{
  state: State
  dispatch: Dispatch<Action>
} | undefined>(undefined)

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    markets: [],
    selectedMarket: null,
    loading: false
  })

  return (
    <MarketContext.Provider value={{ state, dispatch }}>
      {children}
    </MarketContext.Provider>
  )
}

export function useMarkets() {
  const context = useContext(MarketContext)
  if (!context) throw new Error('useMarkets must be used within MarketProvider')
  return context
}
```

## Performance Optimization

### Memoization

```typescript
// ✅ useMemo for expensive computations
const sortedMarkets = useMemo(() => {
  return markets.sort((a, b) => b.volume - a.volume)
}, [markets])

// ✅ useCallback for functions passed to children
const handleSearch = useCallback((query: string) => {
  setSearchQuery(query)
}, [])

// ✅ React.memo for pure components
export const MarketCard = React.memo<MarketCardProps>(({ market }) => {
  return (
    <div className="market-card">
      <h3>{market.name}</h3>
      <p>{market.description}</p>
    </div>
  )
})
```

### Code Splitting & Lazy Loading

```typescript
import { lazy, Suspense } from 'react'

// ✅ Lazy load heavy components
const HeavyChart = lazy(() => import('./HeavyChart'))
const ThreeJsBackground = lazy(() => import('./ThreeJsBackground'))

export function Dashboard() {
  return (
    <div>
      <Suspense fallback={<ChartSkeleton />}>
        <HeavyChart data={data} />
      </Suspense>

      <Suspense fallback={null}>
        <ThreeJsBackground />
      </Suspense>
    </div>
  )
}
```

### Virtualization for Long Lists

```typescript
import { useVirtualizer } from '@tanstack/react-virtual'

export function VirtualMarketList({ markets }: { markets: Market[] }) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: markets.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 100,  // Estimated row height
    overscan: 5  // Extra items to render
  })

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          position: 'relative'
        }}
      >
        {virtualizer.getVirtualItems().map(virtualRow => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`
            }}
          >
            <MarketCard market={markets[virtualRow.index]} />
          </div>
        ))}
      </div>
    </div>
  )
}
```

## Form Handling Patterns

### Controlled Form with Validation

```typescript
import { z } from 'zod'

// ✅ SECURITY: Define validation schema with sanitization
const CreateMarketSchema = z.object({
  name: z.string()
    .min(1, 'Name is required')
    .max(200, 'Name must be under 200 characters')
    .trim()
    .refine(val => !/<script|javascript:|on\w+=/i.test(val), 'Invalid characters'),
  description: z.string()
    .min(1, 'Description is required')
    .max(5000, 'Description too long')
    .trim(),
  endDate: z.string()
    .min(1, 'End date is required')
    .refine(val => !isNaN(Date.parse(val)), 'Invalid date')
})

interface FormData {
  name: string
  description: string
  endDate: string
}

interface FormErrors {
  name?: string
  description?: string
  endDate?: string
}

export function CreateMarketForm() {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    endDate: ''
  })

  const [errors, setErrors] = useState<FormErrors>({})

  // ✅ SECURITY: Validate and sanitize input
  const validate = (): boolean => {
    try {
      CreateMarketSchema.parse(formData)
      setErrors({})
      return true
    } catch (err) {
      if (err instanceof z.ZodError) {
        const newErrors: FormErrors = {}
        err.errors.forEach(error => {
          if (error.path[0]) {
            newErrors[error.path[0] as keyof FormErrors] = error.message
          }
        })
        setErrors(newErrors)
      }
      return false
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validate()) return

    try {
      // ✅ SECURITY: Sanitize data before sending
      const sanitized = CreateMarketSchema.parse(formData)

      // ✅ SECURITY: Include CSRF token
      const csrfToken = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content

      await fetch('/api/markets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken || '',
        },
        credentials: 'same-origin',
        body: JSON.stringify(sanitized)
      })
      // Success handling
    } catch (error) {
      // ✅ SECURITY: Don't expose error details
      setErrors({
        name: 'An error occurred. Please try again.'
      })
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        value={formData.name}
        onChange={e => {
          // ✅ SECURITY: Basic input sanitization
          const sanitized = e.target.value.replace(/[<>]/g, '')
          setFormData(prev => ({ ...prev, name: sanitized }))
        }}
        placeholder="Market name"
        maxLength={200}
        autoComplete="off"
      />
      {errors.name && <span className="error">{errors.name}</span>}

      {/* Other fields */}

      <button type="submit">Create Market</button>
    </form>
  )
}
```

## Error Boundary Pattern

```typescript
interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = {
    hasError: false,
    error: null
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error boundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-fallback">
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message}</p>
          <button onClick={() => this.setState({ hasError: false })}>
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

// Usage
<ErrorBoundary>
  <App />
</ErrorBoundary>
```

## Animation Patterns

### Framer Motion Animations

```typescript
import { motion, AnimatePresence } from 'framer-motion'

// ✅ List animations
export function AnimatedMarketList({ markets }: { markets: Market[] }) {
  return (
    <AnimatePresence>
      {markets.map(market => (
        <motion.div
          key={market.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.3 }}
        >
          <MarketCard market={market} />
        </motion.div>
      ))}
    </AnimatePresence>
  )
}

// ✅ Modal animations
export function Modal({ isOpen, onClose, children }: ModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="modal-content"
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
          >
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
```

## Accessibility Patterns

### Keyboard Navigation

```typescript
export function Dropdown({ options, onSelect }: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex(i => Math.min(i + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex(i => Math.max(i - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        onSelect(options[activeIndex])
        setIsOpen(false)
        break
      case 'Escape':
        setIsOpen(false)
        break
    }
  }

  return (
    <div
      role="combobox"
      aria-expanded={isOpen}
      aria-haspopup="listbox"
      onKeyDown={handleKeyDown}
    >
      {/* Dropdown implementation */}
    </div>
  )
}
```

### Focus Management

```typescript
export function Modal({ isOpen, onClose, children }: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (isOpen) {
      // Save currently focused element
      previousFocusRef.current = document.activeElement as HTMLElement

      // Focus modal
      modalRef.current?.focus()
    } else {
      // Restore focus when closing
      previousFocusRef.current?.focus()
    }
  }, [isOpen])

  return isOpen ? (
    <div
      ref={modalRef}
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
      onKeyDown={e => e.key === 'Escape' && onClose()}
    >
      {children}
    </div>
  ) : null
}
```

## Security Patterns

### XSS Prevention

```typescript
import DOMPurify from 'isomorphic-dompurify'

// ✅ SECURE: Sanitize user-provided HTML
export function UserContent({ html }: { html: string }) {
  const sanitized = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br'],
    ALLOWED_ATTR: []
  })

  return <div dangerouslySetInnerHTML={{ __html: sanitized }} />
}

// ✅ SECURE: Use textContent for user input
export function UserName({ name }: { name: string }) {
  // React automatically escapes, but be explicit
  return <span>{name}</span> // Safe - React escapes by default
}

// ❌ INSECURE: Never do this
// <div dangerouslySetInnerHTML={{ __html: userInput }} />
```

### URL Validation (SSRF Prevention)

```typescript
// ✅ SECURE: Validate URLs before fetching
function validateApiUrl(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin)

    // Only allow same-origin or whitelisted domains
    if (parsed.origin === window.location.origin) {
      return true
    }

    const allowedHosts = [
      'api.example.com',
      'cdn.example.com'
    ]

    return allowedHosts.includes(parsed.hostname) &&
           parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function SafeDataLoader({ url }: { url: string }) {
  useEffect(() => {
    if (!validateApiUrl(url)) {
      console.error('Invalid URL')
      return
    }

    fetch(url, {
      credentials: 'same-origin', // Don't send cookies to external domains
      headers: { 'Content-Type': 'application/json' }
    })
  }, [url])
}
```

### CSRF Protection

```typescript
// ✅ SECURE: Include CSRF token in requests
export async function safeApiCall(endpoint: string, data: unknown) {
  const csrfToken = document
    .querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
    ?.content

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken || '',
    },
    credentials: 'same-origin', // Include cookies
    body: JSON.stringify(data)
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  return response.json()
}

// In your HTML head:
// <meta name="csrf-token" content={csrfToken} />
```

### Input Sanitization

```typescript
import { z } from 'zod'

// ✅ SECURE: Validate and sanitize all inputs
const UserInputSchema = z.object({
  name: z.string()
    .min(1)
    .max(100)
    .trim()
    .refine(val => !/[<>]/.test(val), 'Invalid characters'),
  email: z.string().email(),
  message: z.string()
    .max(1000)
    .trim()
    .transform(val => val.replace(/<script|javascript:/gi, ''))
})

export function ContactForm() {
  const handleSubmit = async (data: unknown) => {
    try {
      // ✅ Validate and sanitize
      const sanitized = UserInputSchema.parse(data)

      // Send sanitized data
      await safeApiCall('/api/contact', sanitized)
    } catch (err) {
      if (err instanceof z.ZodError) {
        // Handle validation errors
      }
    }
  }
}
```

### Content Security Policy

```typescript
// next.config.js or middleware
export function middleware(request: NextRequest) {
  const response = NextResponse.next()

  // ✅ SECURE: Set CSP headers
  response.headers.set(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      "script-src 'self' 'unsafe-eval'", // Remove 'unsafe-eval' in production if possible
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self'",
      "connect-src 'self' https://api.example.com",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'"
    ].join('; ')
  )

  response.headers.set('X-Frame-Options', 'DENY')
  response.headers.set('X-Content-Type-Options', 'nosniff')
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')

  return response
}
```

### Secure Authentication Storage

```typescript
// ❌ INSECURE: localStorage (vulnerable to XSS)
// localStorage.setItem('token', token)

// ✅ SECURE: Use httpOnly cookies (set by server)
// Server sets: Set-Cookie: token=xxx; HttpOnly; Secure; SameSite=Strict

// ✅ SECURE: For client-side tokens, use sessionStorage (cleared on tab close)
// sessionStorage.setItem('tempToken', token)

// ✅ SECURE: Clear sensitive data on logout
export function logout() {
  sessionStorage.clear()
  // Server should clear httpOnly cookie
  window.location.href = '/login'
}
```

### Error Handling Security

```typescript
// ❌ INSECURE: Expose error details
catch (error) {
  return <div>Error: {error.message}</div> // May leak sensitive info
}

// ✅ SECURE: Generic error messages
catch (error) {
  console.error('Internal error:', error) // Log server-side only
  return <div>An error occurred. Please try again.</div>
}

// ✅ SECURE: Error boundary with safe error display
export class SecureErrorBoundary extends React.Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // ✅ Log to secure logging service, not console
    // logErrorToService(error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div>
          <h2>Something went wrong</h2>
          {/* ✅ Don't display error.message - may contain sensitive data */}
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
```

### Security Checklist for Frontend Code

- [ ] All user inputs validated with schemas (Zod, Yup)
- [ ] User-provided HTML sanitized (DOMPurify)
- [ ] URLs validated before fetching (prevent SSRF)
- [ ] CSRF tokens included in state-changing requests
- [ ] No sensitive data in localStorage (use httpOnly cookies)
- [ ] Error messages don't expose sensitive information
- [ ] Content Security Policy headers configured
- [ ] X-Frame-Options set to prevent clickjacking
- [ ] Authentication tokens stored securely
- [ ] No secrets in client-side code
- [ ] API calls use same-origin or validated URLs
- [ ] Rate limiting considered for client-side operations
- [ ] Input length limits enforced
- [ ] File uploads validated (size, type, extension)

**Remember**: Modern frontend patterns enable maintainable, performant user interfaces. Choose patterns that fit your project complexity. **Security is not optional** - always validate input, sanitize output, and protect against common vulnerabilities (XSS, CSRF, SSRF).
