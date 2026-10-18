import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnswerError, postAnswer } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('postAnswer', () => {
  it('sends multipart fields', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ answer_id: 'ans_1' }), { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    const photo = new Blob(['x'], { type: 'image/jpeg' });
    const created = await postAnswer({ device_id: 'd1', street_id: 'S1', alert_id: 'a_01', answer: 'yes', depth: 'knee', lat: 3.107, lon: 101.355, photo });
    expect(created.answer_id).toBe('ans_1');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/answers$/);
    expect(init.method).toBe('POST');
    const body = init.body as FormData;
    expect(body.get('device_id')).toBe('d1');
    expect(body.get('alert_id')).toBe('a_01');
    expect(body.get('answer')).toBe('yes');
    expect(body.get('depth')).toBe('knee');
    expect(body.get('lat')).toBe('3.107');
    expect(body.get('photo')).toBeInstanceOf(Blob);
    expect(init.headers).toBeUndefined();
  });

  it('leaves out alert_id, depth, location and photo when absent', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ answer_id: 'x' }), { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    await postAnswer({ device_id: 'd1', street_id: 'S1', answer: 'report' });
    const body = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as FormData;
    for (const k of ['alert_id', 'depth', 'lat', 'lon', 'photo']) expect(body.has(k)).toBe(false);
  });

  it('throws AnswerError carrying the status', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"detail":"dup"}', { status: 409 })));
    await expect(postAnswer({ device_id: 'd', street_id: 's', answer: 'no' })).rejects.toMatchObject({ status: 409 });
    await expect(postAnswer({ device_id: 'd', street_id: 's', answer: 'no' })).rejects.toBeInstanceOf(AnswerError);
  });
});
