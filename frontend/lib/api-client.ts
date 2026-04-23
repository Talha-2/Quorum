/**
 * Production API client with error handling, retry logic, and caching
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
const RETRY_ATTEMPTS = 3
const RETRY_DELAY_MS = 1000
const CACHE_DURATION_MS = 5000

interface CacheEntry<T> {
  data: T
  timestamp: number
}

const responseCache = new Map<string, CacheEntry<any>>()

export class APIError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string,
    public details?: any
  ) {
    super(message)
    this.name = 'APIError'
  }
}

/**
 * Execute API request with retry logic and error handling
 */
async function fetchWithRetry<T>(
  path: string,
  options?: RequestInit,
  attempt = 1
): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      cache: 'no-store',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers ?? {}),
      },
    })

    if (!response.ok) {
      let detail = 'Request failed'
      try {
        const data = await response.json()
        detail = data.detail ?? detail
      } catch {
        // Response wasn't JSON, use status text
        detail = response.statusText || detail
      }

      throw new APIError(response.status, response.statusText, detail)
    }

    return await response.json()
  } catch (error) {
    // Retry on network errors or 5xx errors
    const shouldRetry =
      error instanceof TypeError ||
      (error instanceof APIError && error.status >= 500)

    if (shouldRetry && attempt < RETRY_ATTEMPTS) {
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS * attempt))
      return fetchWithRetry<T>(path, options, attempt + 1)
    }

    if (error instanceof TypeError) {
      throw new APIError(0, 'Network Error', `Backend unavailable at ${API_BASE}`)
    }

    throw error
  }
}

/**
 * API client with caching support
 */
export const apiClient = {
  /**
   * GET request with optional caching
   */
  async get<T>(path: string, options?: { skipCache?: boolean }): Promise<T> {
    // Check cache first
    if (!options?.skipCache) {
      const cached = responseCache.get(path)
      if (cached && Date.now() - cached.timestamp < CACHE_DURATION_MS) {
        return cached.data
      }
    }

    const data = await fetchWithRetry<T>(path, { method: 'GET' })

    // Store in cache
    responseCache.set(path, { data, timestamp: Date.now() })
    return data
  },

  /**
   * POST request
   */
  async post<T>(path: string, body?: any, options?: RequestInit): Promise<T> {
    const data = await fetchWithRetry<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    })

    // Invalidate related cache entries
    invalidateCache()
    return data
  },

  /**
   * PUT request
   */
  async put<T>(path: string, body?: any, options?: RequestInit): Promise<T> {
    const data = await fetchWithRetry<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    })

    invalidateCache()
    return data
  },

  /**
   * DELETE request
   */
  async delete<T>(path: string, options?: RequestInit): Promise<T> {
    const data = await fetchWithRetry<T>(path, {
      method: 'DELETE',
      ...options,
    })

    invalidateCache()
    return data
  },
}

/**
 * Clear all cache entries
 */
export function invalidateCache(): void {
  responseCache.clear()
}

/**
 * Clear specific cache entry
 */
export function invalidateCachePath(path: string): void {
  responseCache.delete(path)
}

/**
 * Health check with automatic retry
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`, {
      method: 'GET',
      cache: 'no-store',
    })
    return response.ok
  } catch {
    return false
  }
}

/**
 * Handle API errors gracefully
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof APIError) {
    if (error.status === 0) {
      return 'Backend service is unavailable. Make sure Docker containers are running.'
    }
    if (error.status === 404) {
      return 'Resource not found.'
    }
    if (error.status === 500) {
      return 'Server error. Try again in a moment.'
    }
    return error.message
  }

  if (error instanceof TypeError) {
    return 'Network error. Check your connection and ensure the backend is running.'
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'An unknown error occurred.'
}
