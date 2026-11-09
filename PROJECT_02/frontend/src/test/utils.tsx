import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { FeedbackProvider } from '../components/feedback';

export interface Call {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string>;
}

type Handler = (call: Call) => unknown | Response;

/** Route fetch calls to handlers keyed by "METHOD /path" (query string ignored). */
export function mockApi(handlers: Record<string, Handler>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost');
    const method = (init.method ?? 'GET').toUpperCase();
    const path = url.pathname.replace(/^\/api/, '');
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body;
    const call = { method, path, body, headers: (init.headers ?? {}) as Record<string, string> };
    calls.push(call);
    const handler = handlers[`${method} ${path}`];
    if (!handler) return new Response(JSON.stringify({ detail: `No mock for ${method} ${path}` }), { status: 404 });
    const result = handler(call);
    if (result instanceof Response) return result;
    if (result === undefined) return new Response(null, { status: 204 });
    return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  return calls;
}

export function renderApp(ui: ReactElement, route = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <FeedbackProvider>{ui}</FeedbackProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const ME = { id: 1, email: 'rhea@example.com', name: 'Rhea Kapoor' };
