const KEY = 'floodready.admin.token';

let token: string | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function store(value: string | null) {
  try {
    if (value === null) sessionStorage.removeItem(KEY);
    else sessionStorage.setItem(KEY, value);
  } catch {
    // sessionStorage can be blocked; the in-memory token still works for this page load.
  }
}

/** Admin session: token in memory, mirrored to sessionStorage so a reload keeps it. */
export const auth = {
  getToken: (): string | null => token,
  login(next: string) {
    token = next;
    store(next);
    emit();
  },
  logout() {
    token = null;
    store(null);
    emit();
  },
  restore() {
    try {
      token = sessionStorage.getItem(KEY);
    } catch {
      token = null;
    }
    emit();
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
