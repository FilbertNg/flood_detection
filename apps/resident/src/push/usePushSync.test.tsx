import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as subscribe from './subscribe';
import { usePushSync } from './usePushSync';

vi.mock('./subscribe');

function Probe(props: { deviceId: string; streets: string[]; lang: 'en' | 'ms' }) {
  usePushSync(props);
  return null;
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('usePushSync', () => {
  it('re-posts when streets or language change, not on first render', () => {
    const { rerender } = render(<Probe deviceId="d" streets={['a']} lang="en" />);
    expect(subscribe.syncPush).not.toHaveBeenCalled();
    rerender(<Probe deviceId="d" streets={['a', 'b']} lang="en" />);
    expect(subscribe.syncPush).toHaveBeenLastCalledWith({ deviceId: 'd', streetIds: ['a', 'b'], lang: 'en' });
    rerender(<Probe deviceId="d" streets={['a', 'b']} lang="ms" />);
    expect(subscribe.syncPush).toHaveBeenLastCalledWith({ deviceId: 'd', streetIds: ['a', 'b'], lang: 'ms' });
    expect(subscribe.syncPush).toHaveBeenCalledTimes(2);
  });
});
