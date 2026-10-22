const KEY = 'floodready.admin.token';
const PREVIEW_KEY = 'floodready.admin.preview';

let token: string | null = null;
let preview = false;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function store(value: string | null, isPreview: boolean) {
  try {
    if (value === null) sessionStorage.removeItem(KEY);
    else sessionStorage.setItem(KEY, value);
    if (isPreview) sessionStorage.setItem(PREVIEW_KEY, '1');
    else sessionStorage.removeItem(PREVIEW_KEY);
  } catch {
    // sessionStorage can be blocked; the in-memory token still works for this page load.
  }
}

/** Admin session: token in memory, mirrored to sessionStorage so a reload keeps it. A preview session is the
 * read-only look-around without an account (the server decides what it may do; the UI hides what it may not). */
export const auth = {
  getToken: (): string | null => token,
  isPreview: (): boolean => preview,
  login(next: string, opts: { preview?: boolean } = {}) {
    token = next;
    preview = !!opts.preview;
    store(next, preview);
    emit();
  },
  logout() {
    token = null;
    preview = false;
    store(null, false);
    emit();
  },
  restore() {
    try {
      token = sessionStorage.getItem(KEY);
      preview = token !== null && sessionStorage.getItem(PREVIEW_KEY) === '1';
    } catch {
      token = null;
      preview = false;
    }
    emit();
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
