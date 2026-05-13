/**
 * IndexedDB-backed queue for POS transactions submitted while offline (P1-005).
 *
 * Storage shape:
 *   db   : "vintiz-pos"
 *   store: "queued_transactions"
 *   key  : client_uuid (UUID v4 string)
 *   value: QueuedTransaction
 *
 * The cashier UI generates a client_uuid before the first submit attempt,
 * enqueues the payload locally, then fires-and-forgets the POST. On
 * success the row is removed; on network error it stays put. A drain pass
 * (triggered by online events or a manual button) replays each entry —
 * the backend's idempotence index on transactions.client_uuid keeps a
 * mid-flight crash from creating duplicates.
 */

const DB_NAME = 'vintiz-pos';
const DB_VERSION = 1;
const STORE = 'queued_transactions';

export interface QueuedTransaction {
  client_uuid: string;
  payload: unknown;
  created_at: number;       // Date.now() at enqueue time
  attempts: number;
  last_error?: string;
  last_attempt_at?: number;
}

let _dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable in this environment'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'client_uuid' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
  });
  return _dbPromise;
}

function tx(mode: IDBTransactionMode): Promise<IDBObjectStore> {
  return openDb().then((db) =>
    db.transaction(STORE, mode).objectStore(STORE),
  );
}

function asPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** Generate a v4 UUID. Uses crypto.randomUUID when available. */
export function generateClientUuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return (crypto as Crypto & { randomUUID(): string }).randomUUID();
  }
  // Fallback (très improbable sur Chrome Android moderne).
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export async function enqueue(payload: unknown): Promise<string> {
  // The caller may have generated client_uuid in advance and embedded it
  // in the payload — honour that to keep the same id across enqueue +
  // POST attempts.
  const clientUuid =
    (payload as { client_uuid?: string })?.client_uuid || generateClientUuid();

  const entry: QueuedTransaction = {
    client_uuid: clientUuid,
    payload,
    created_at: Date.now(),
    attempts: 0,
  };
  const store = await tx('readwrite');
  await asPromise(store.put(entry));
  return clientUuid;
}

export async function list(): Promise<QueuedTransaction[]> {
  const store = await tx('readonly');
  return asPromise(store.getAll() as IDBRequest<QueuedTransaction[]>);
}

export async function count(): Promise<number> {
  const store = await tx('readonly');
  return asPromise(store.count());
}

export async function remove(clientUuid: string): Promise<void> {
  const store = await tx('readwrite');
  await asPromise(store.delete(clientUuid));
}

export async function markAttempt(
  clientUuid: string,
  error?: string,
): Promise<void> {
  const store = await tx('readwrite');
  const current = await asPromise(
    store.get(clientUuid) as IDBRequest<QueuedTransaction | undefined>,
  );
  if (!current) return;
  current.attempts += 1;
  current.last_attempt_at = Date.now();
  current.last_error = error;
  await asPromise(store.put(current));
}

export interface DrainOutcome {
  attempted: number;
  succeeded: string[];   // client_uuids
  failed: { client_uuid: string; error: string }[];
}

export type Submitter = (
  payload: unknown,
) => Promise<{ ok: boolean; status: number; bodyText: string }>;

/**
 * Replay the queue in FIFO order. ``submit`` is the single-shot POST
 * function — typically wired to ``api.post('/api/pos/transactions', body)``
 * — and decides whether each entry should be removed (4xx = give up,
 * 2xx = success) or kept for the next pass (network error / 5xx).
 */
export async function drain(submit: Submitter): Promise<DrainOutcome> {
  const entries = await list();
  entries.sort((a, b) => a.created_at - b.created_at);

  const outcome: DrainOutcome = {
    attempted: entries.length,
    succeeded: [],
    failed: [],
  };

  for (const entry of entries) {
    try {
      const res = await submit(entry.payload);
      if (res.ok) {
        await remove(entry.client_uuid);
        outcome.succeeded.push(entry.client_uuid);
      } else if (res.status >= 400 && res.status < 500) {
        // Backend rejected the payload (e.g. product no longer exists).
        // Drop it from the queue so we don't retry forever — the cashier
        // will be alerted and can re-enter manually.
        await remove(entry.client_uuid);
        outcome.failed.push({
          client_uuid: entry.client_uuid,
          error: `HTTP ${res.status}: ${res.bodyText.slice(0, 200)}`,
        });
      } else {
        // 5xx — keep for next pass.
        await markAttempt(entry.client_uuid, `HTTP ${res.status}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      await markAttempt(entry.client_uuid, message);
      // Network still down — stop the drain to avoid hammering.
      break;
    }
  }

  return outcome;
}
