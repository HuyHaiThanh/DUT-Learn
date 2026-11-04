import { afterEach, expect, it, vi } from 'vitest';
import { apiFetch, ApiError } from './client';
afterEach(() => vi.unstubAllGlobals());
it.each(['POST', 'PUT', 'PATCH', 'DELETE', 'post'])('%s tự thêm CSRF và gửi cookie', async method => {
  const mock = vi.fn().mockResolvedValue(new Response(null, { status: 204 })); vi.stubGlobal('fetch', mock);
  await apiFetch('/auth/logout', { method, headers: { 'X-DUT-CSRF': '0' } });
  const init = mock.mock.calls[0][1] as RequestInit;
  expect(init.credentials).toBe('include'); expect(new Headers(init.headers).get('X-DUT-CSRF')).toBe('1');
});
it('GET không thêm CSRF, giữ header tùy chỉnh', async () => {
  const mock = vi.fn().mockResolvedValue(new Response('{}')); vi.stubGlobal('fetch', mock);
  await apiFetch('/auth/me', { headers: { 'X-Test': 'yes' } });
  const headers = new Headers(mock.mock.calls[0][1].headers);
  expect(headers.has('X-DUT-CSRF')).toBe(false); expect(headers.get('X-Test')).toBe('yes');
});
it('parse lỗi chuẩn và request_id', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'invalid_credentials', message: 'Sai mật khẩu', request_id: 'req1', details: { attempts_remaining: 3 } } }), { status: 401 })));
  const error = await apiFetch('/auth/login', { method: 'POST' }).catch(e => e);
  expect(error).toBeInstanceOf(ApiError); expect(error).toMatchObject({ status: 401, code: 'invalid_credentials', message: 'Sai mật khẩu', request_id: 'req1', details: { attempts_remaining: 3 } });
});
it('lỗi proxy không có JSON vẫn thành ApiError', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad gateway', { status: 502, headers: { 'X-Request-ID': 'proxy1' } })));
  await expect(apiFetch('/classes')).rejects.toMatchObject({ status: 502, code: 'request_failed', request_id: 'proxy1' });
});
