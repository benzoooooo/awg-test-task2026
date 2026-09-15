import { vi } from 'vitest'

type Handler = unknown | ((url: URL, init?: RequestInit) => unknown)

/** Route `fetch` by pathname (after the API prefix) to canned JSON bodies. */
export function mockFetch(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const path = url.pathname.replace(/^\/git\/api\/v1/, '')
    if (!(path in routes)) {
      return { ok: false, status: 404, json: async () => ({ detail: `no mock for ${path}` }) } as Response
    }
    const handler = routes[path]
    const body = typeof handler === 'function' ? handler(url, init) : handler
    return { ok: true, status: 200, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
