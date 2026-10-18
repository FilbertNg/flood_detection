import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VerifySheet } from './VerifySheet';

const userEvent = {
  setup: () => ({
    click: async (el: Element) => { fireEvent.click(el); },
    upload: async (el: Element, file: File) => { fireEvent.change(el, { target: { files: [file] } }); },
  }),
};

let fetchMock: ReturnType<typeof vi.fn>;
let revoke: ReturnType<typeof vi.fn>;

function respond(status: number) {
  fetchMock = vi.fn(async () => new Response(JSON.stringify(status === 201 ? { answer_id: 'ans_1' } : { detail: 'x' }), { status }));
  vi.stubGlobal('fetch', fetchMock);
}
function sent(): FormData {
  return (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as FormData;
}

beforeEach(() => {
  revoke = vi.fn();
  URL.createObjectURL = vi.fn(() => 'blob:photo-1');
  URL.revokeObjectURL = revoke as unknown as typeof URL.revokeObjectURL;
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const props = { deviceId: 'dev_1', streetId: 'BBR-jalan-makyong' };

describe('VerifySheet (verify)', () => {
  it('posts Yes with depth, photo and location rounded to 3 decimals', async () => {
    respond(201);
    vi.stubGlobal('navigator', { ...navigator, geolocation: { getCurrentPosition: (ok: PositionCallback) => ok({ coords: { latitude: 3.1078214, longitude: 101.3555719 } } as GeolocationPosition) } });
    const user = userEvent.setup();
    render(<VerifySheet lang="en" mode="verify" alertId="a_01" {...props} />);
    expect(screen.queryByText('Ankle')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Yes' }));
    await user.click(screen.getByRole('button', { name: 'Knee' }));
    const file = new File(['img'], 'p.jpg', { type: 'image/jpeg' });
    const input = screen.getByLabelText('Add a photo (optional)') as HTMLInputElement;
    expect(input).toHaveAttribute('accept', 'image/*');
    expect(input).toHaveAttribute('capture', 'environment');
    await user.upload(input, file);
    await user.click(screen.getByLabelText(/Share my location/));
    await user.click(screen.getByRole('button', { name: 'Send answer' }));
    const thanks = await screen.findByRole('heading', { name: 'Thank you' });
    await waitFor(() => expect(thanks).toHaveFocus());
    const body = sent();
    expect(body.get('device_id')).toBe('dev_1');
    expect(body.get('street_id')).toBe('BBR-jalan-makyong');
    expect(body.get('alert_id')).toBe('a_01');
    expect(body.get('answer')).toBe('yes');
    expect(body.get('depth')).toBe('knee');
    expect(body.get('lat')).toBe('3.108');
    expect(body.get('lon')).toBe('101.356');
    expect(body.get('photo')).toBeInstanceOf(Blob);
    expect(revoke).toHaveBeenCalledWith('blob:photo-1');
  });

  it('No and Not sure send no depth, photo or location', async () => {
    respond(201);
    const user = userEvent.setup();
    render(<VerifySheet lang="en" mode="verify" alertId="a_01" {...props} />);
    await user.click(screen.getByRole('button', { name: 'Not sure' }));
    expect(screen.queryByRole('button', { name: 'Knee' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Add a photo (optional)')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Send answer' }));
    await screen.findByRole('heading', { name: 'Thank you' });
    const body = sent();
    expect(body.get('answer')).toBe('not_sure');
    for (const k of ['depth', 'photo', 'lat', 'lon']) expect(body.has(k)).toBe(false);
  });

  it('disables Send until an answer is chosen', () => {
    respond(201);
    render(<VerifySheet lang="en" mode="verify" alertId="a_01" {...props} />);
    expect(screen.getByRole('button', { name: 'Send answer' })).toBeDisabled();
  });

  it('409 says you already answered (EN and MS) in a role=alert', async () => {
    respond(409);
    const user = userEvent.setup();
    const { unmount } = render(<VerifySheet lang="en" mode="verify" alertId="a_01" {...props} />);
    await user.click(screen.getByRole('button', { name: 'No' }));
    await user.click(screen.getByRole('button', { name: 'Send answer' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('You already answered');
    unmount();
    respond(409);
    render(<VerifySheet lang="ms" mode="verify" alertId="a_01" {...props} />);
    await user.click(screen.getByRole('button', { name: 'Tidak' }));
    await user.click(screen.getByRole('button', { name: 'Hantar jawapan' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Anda sudah menjawab');
  });

  it('a server error shows a retry message and keeps the form', async () => {
    respond(500);
    const user = userEvent.setup();
    render(<VerifySheet lang="en" mode="verify" alertId="a_01" {...props} />);
    await user.click(screen.getByRole('button', { name: 'No' }));
    await user.click(screen.getByRole('button', { name: 'Send answer' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Could not send/);
    expect(screen.getByRole('button', { name: 'Send answer' })).toBeEnabled();
  });

  it('removing the photo revokes its object URL and unmounting revokes the rest', async () => {
    respond(201);
    const user = userEvent.setup();
    const { unmount } = render(<VerifySheet lang="en" mode="verify" alertId="a_01" {...props} />);
    await user.click(screen.getByRole('button', { name: 'Yes' }));
    await user.upload(screen.getByLabelText('Add a photo (optional)'), new File(['i'], 'p.jpg', { type: 'image/jpeg' }));
    await user.click(screen.getByRole('button', { name: 'Remove photo' }));
    expect(revoke).toHaveBeenCalledWith('blob:photo-1');
    revoke.mockClear();
    await user.upload(screen.getByLabelText('Add a photo (optional)'), new File(['i'], 'q.jpg', { type: 'image/jpeg' }));
    unmount();
    expect(revoke).toHaveBeenCalledWith('blob:photo-1');
  });

  it('a refused location leaves it out and says so', async () => {
    respond(201);
    vi.stubGlobal('navigator', { ...navigator, geolocation: { getCurrentPosition: (_ok: PositionCallback, err: PositionErrorCallback) => err({ code: 1 } as GeolocationPositionError) } });
    const user = userEvent.setup();
    render(<VerifySheet lang="en" mode="verify" alertId="a_01" {...props} />);
    await user.click(screen.getByRole('button', { name: 'No' }));
    await user.click(screen.getByLabelText(/Share my location/));
    expect(await screen.findByRole('alert')).toHaveTextContent(/location/i);
    expect(screen.getByLabelText(/Share my location/)).not.toBeChecked();
    await user.click(screen.getByRole('button', { name: 'Send answer' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sent().has('lat')).toBe(false);
  });
});

describe('VerifySheet (report)', () => {
  it('posts answer=report without alert_id and offers no Yes/No', async () => {
    respond(201);
    const user = userEvent.setup();
    render(<VerifySheet lang="en" mode="report" {...props} />);
    expect(screen.queryByRole('button', { name: 'Yes' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Above knee' }));
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    await screen.findByRole('heading', { name: 'Thank you' });
    const body = sent();
    expect(body.get('answer')).toBe('report');
    expect(body.get('depth')).toBe('above_knee');
    expect(body.has('alert_id')).toBe(false);
  });
});
