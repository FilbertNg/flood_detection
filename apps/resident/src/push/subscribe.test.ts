import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { enablePush, isSubscribed, pushSupport, stopPush, syncPush, urlBase64ToUint8Array } from './subscribe';

const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1';
const ANDROID = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126.0 Mobile Safari/537.36';

const subJson = { endpoint: 'https://push.example/abc', expirationTime: null, keys: { p256dh: 'p', auth: 'a' } };

function setup(opts: { ua?: string; standalone?: boolean; permission?: NotificationPermission; existing?: boolean } = {}) {
  vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(opts.ua ?? ANDROID);
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('standalone') && !!opts.standalone }));
  vi.stubGlobal('PushManager', class {});
  const unsubscribe = vi.fn(async () => true);
  const subscription = { toJSON: () => subJson, unsubscribe };
  const pushManager = {
    getSubscription: vi.fn(async () => (opts.existing ? subscription : null)),
    subscribe: vi.fn(async (_options: PushSubscriptionOptionsInit) => subscription),
  };
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { ready: Promise.resolve({ pushManager }) },
  });
  vi.stubGlobal('Notification', { permission: opts.permission ?? 'default', requestPermission: vi.fn(async () => opts.permission ?? 'granted') });
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
    url.endsWith('/push/public-key')
      ? new Response(JSON.stringify({ key: 'AQID' }), { status: 200 })
      : new Response(null, { status: 204 }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return { pushManager, unsubscribe, fetchMock };
}

type FetchMock = ReturnType<typeof setup>['fetchMock'];
const calls = (f: FetchMock, method: string) => f.mock.calls.filter(([, init]) => init?.method === method);

beforeEach(() => vi.restoreAllMocks());
afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, 'serviceWorker');
});

describe('pushSupport', () => {
  it('is ok on Android Chrome', () => {
    setup();
    expect(pushSupport()).toBe('ok');
  });
  it('asks iPhone Safari outside the installed app to install first', () => {
    setup({ ua: IPHONE });
    expect(pushSupport()).toBe('needs-install');
  });
  it('is ok on iPhone once installed (standalone)', () => {
    setup({ ua: IPHONE, standalone: true });
    expect(pushSupport()).toBe('ok');
  });
  it('is unsupported without PushManager', () => {
    setup();
    Reflect.deleteProperty(window, 'PushManager');
    expect(pushSupport()).toBe('unsupported');
  });
});

describe('urlBase64ToUint8Array', () => {
  it('decodes url-safe base64', () => {
    expect(Array.from(urlBase64ToUint8Array('AQID'))).toEqual([1, 2, 3]);
    expect(Array.from(urlBase64ToUint8Array('-_8'))).toEqual([251, 255]);
  });
});

const input = { deviceId: 'dev_1', streetIds: ['BBR-a', 'BBR-b'], lang: 'ms' as const };

describe('enablePush', () => {
  it('subscribes with the server key and posts the SubscriptionRequest', async () => {
    const { pushManager, fetchMock } = setup();
    expect(await enablePush(input)).toBe('granted');
    const arg = pushManager.subscribe.mock.calls[0][0];
    expect(arg.userVisibleOnly).toBe(true);
    expect(Array.from(arg.applicationServerKey as Uint8Array)).toEqual([1, 2, 3]);
    const [call] = calls(fetchMock, 'POST');
    expect(String(call[0])).toMatch(/\/api\/v1\/subscriptions$/);
    expect(JSON.parse(call[1]!.body as string)).toEqual({
      device_id: 'dev_1',
      subscription: subJson,
      street_ids: ['BBR-a', 'BBR-b'],
      lang: 'ms',
    });
  });
  it('does not POST when permission is denied', async () => {
    const { pushManager, fetchMock } = setup({ permission: 'denied' });
    expect(await enablePush(input)).toBe('denied');
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(calls(fetchMock, 'POST')).toHaveLength(0);
  });
  it('reports an error when the server rejects', async () => {
    const { fetchMock } = setup();
    fetchMock.mockImplementation(async (url: string) =>
      url.endsWith('/push/public-key') ? new Response(JSON.stringify({ key: 'AQID' })) : new Response('x', { status: 500 }),
    );
    expect(await enablePush(input)).toBe('error');
  });
});

describe('syncPush', () => {
  it('re-posts when already subscribed', async () => {
    const { fetchMock } = setup({ existing: true, permission: 'granted' });
    await syncPush({ ...input, streetIds: ['BBR-c'] });
    expect(JSON.parse(calls(fetchMock, 'POST')[0][1]!.body as string).street_ids).toEqual(['BBR-c']);
  });
  it('does nothing when not subscribed', async () => {
    const { fetchMock } = setup({ existing: false, permission: 'granted' });
    await syncPush(input);
    expect(calls(fetchMock, 'POST')).toHaveLength(0);
  });
});

describe('stopPush / isSubscribed', () => {
  it('reports subscription state', async () => {
    setup({ existing: true });
    expect(await isSubscribed()).toBe(true);
    setup({ existing: false });
    expect(await isSubscribed()).toBe(false);
  });
  it('DELETEs the device and unsubscribes', async () => {
    const { fetchMock, unsubscribe } = setup({ existing: true });
    await stopPush('dev_1');
    const [del] = calls(fetchMock, 'DELETE');
    expect(String(del[0])).toMatch(/\/api\/v1\/subscriptions\/dev_1$/);
    expect(unsubscribe).toHaveBeenCalled();
  });
});
