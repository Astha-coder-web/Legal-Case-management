const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')

export async function authRequest(path, options = {}) {
  let response
  const isFormData = options.body instanceof FormData
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: 'include',
      signal: options.signal || (!isFormData && AbortSignal.timeout(15000)),
      headers: {
        ...(!isFormData && { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
    })
  } catch (requestError) {
    if (
      requestError.name === 'TimeoutError' ||
      requestError.name === 'AbortError'
    ) {
      throw new Error(
        'The authentication API did not respond. Start FastAPI and make sure MongoDB is available.',
      )
    }
    throw new Error(
      'Cannot reach the authentication API. Start FastAPI and check the Vite API proxy.',
    )
  }

  if (response.status === 204) return null

  const result = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(result.detail || 'The request could not be completed.')
    error.status = response.status
    throw error
  }

  return result
}
