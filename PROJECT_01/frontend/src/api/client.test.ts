import { describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './client';
import { mockApi } from '../test/utils';

describe('api client', () => {
  it('sends the CSRF header on writes but not on reads', async () => {
    const calls = mockApi({ 'GET /tasks': () => [], 'POST /tasks': () => ({ id: 1 }) });
    await api('/tasks');
    await api('/tasks', { method: 'POST', body: { title: 'x' } });
    expect(calls[0].headers['X-Requested-With']).toBeUndefined();
    expect(calls[1].headers['X-Requested-With']).toBe('dashboard');
    expect(calls[1].body).toEqual({ title: 'x' });
  });

  it('surfaces the server’s detail message', async () => {
    mockApi({ 'POST /auth/login': () => new Response(JSON.stringify({ detail: 'Incorrect email or password' }), { status: 401 }) });
    const err = await api('/auth/login', { method: 'POST', body: {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 401, message: 'Incorrect email or password' });
  });

  it('handles 204 and network failures', async () => {
    mockApi({ 'DELETE /tasks/1': () => undefined });
    await expect(api('/tasks/1', { method: 'DELETE' })).resolves.toBeUndefined();

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(api('/tasks')).rejects.toMatchObject({ status: 0, message: expect.stringContaining('Cannot reach') });
  });
});
