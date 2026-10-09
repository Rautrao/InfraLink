// IndexedDB offline storage layer for InfraLink Field PWA

export interface QueuedUpdatePayload {
  text: string;
  pct_complete?: number;
  explanation?: string;
}

export interface QueuedEvidencePayload {
  kind: 'progress' | 'restoration' | 'before' | 'after';
  note?: string;
  lat: number | null;
  lon: number | null;
  accuracy: number | null;
  taken_at: string;
  fileName: string;
  fileType: string;
  fileBlob: Blob;
  previewUrl?: string;
}

export interface SyncQueueItem {
  id?: number;
  type: 'update' | 'evidence';
  work_id: string;
  work_title?: string;
  work_ref?: string;
  payload: QueuedUpdatePayload | QueuedEvidencePayload;
  created_at: string;
  status: 'pending' | 'syncing' | 'failed';
  retry_count: number;
  last_error?: string;
}

const DB_NAME = 'infralink_field_pwa';
const DB_VERSION = 1;
const STORE_WORKS = 'cached_works';
const STORE_QUEUE = 'sync_queue';
const STORE_META = 'field_meta';

let dbInstance: IDBDatabase | null = null;

export function openFieldDb(): Promise<IDBDatabase> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('IndexedDB is not available on server'));
  }

  if (dbInstance) {
    return Promise.resolve(dbInstance);
  }

  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      console.error('Failed to open Field PWA IndexedDB:', request.error);
      reject(request.error);
    };

    request.onsuccess = () => {
      dbInstance = request.result;
      dbInstance.onclose = () => {
        dbInstance = null;
      };
      resolve(dbInstance);
    };

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // Object store for cached works
      if (!db.objectStoreNames.contains(STORE_WORKS)) {
        const worksStore = db.createObjectStore(STORE_WORKS, { keyPath: 'id' });
        worksStore.createIndex('status', 'status', { unique: false });
        worksStore.createIndex('cached_at', 'cached_at', { unique: false });
      }

      // Object store for sync queue (outbox)
      if (!db.objectStoreNames.contains(STORE_QUEUE)) {
        const queueStore = db.createObjectStore(STORE_QUEUE, {
          keyPath: 'id',
          autoIncrement: true,
        });
        queueStore.createIndex('work_id', 'work_id', { unique: false });
        queueStore.createIndex('status', 'status', { unique: false });
        queueStore.createIndex('created_at', 'created_at', { unique: false });
      }

      // Object store for metadata (e.g. simulated offline, last sync)
      if (!db.objectStoreNames.contains(STORE_META)) {
        db.createObjectStore(STORE_META, { keyPath: 'key' });
      }
    };
  });
}

// ---------------- Cache Works ----------------

export async function cacheWorks(works: any[]): Promise<void> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_WORKS, 'readwrite');
    const store = tx.objectStore(STORE_WORKS);

    works.forEach((work) => {
      const record = {
        ...work,
        cached_at: new Date().toISOString(),
      };
      store.put(record);
    });

    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getCachedWorks(): Promise<any[]> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_WORKS, 'readonly');
    const store = tx.objectStore(STORE_WORKS);
    const request = store.getAll();

    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => reject(request.error);
  });
}

export async function getCachedWork(id: string): Promise<any | null> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_WORKS, 'readonly');
    const store = tx.objectStore(STORE_WORKS);
    const request = store.get(id);

    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
  });
}

export async function updateCachedWork(
  id: string,
  patch: Record<string, any>
): Promise<void> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_WORKS, 'readwrite');
    const store = tx.objectStore(STORE_WORKS);
    const getReq = store.get(id);

    getReq.onsuccess = () => {
      const existing = getReq.result;
      if (existing) {
        const updated = {
          ...existing,
          ...patch,
          cached_at: new Date().toISOString(),
        };
        store.put(updated);
      }
    };

    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ---------------- Sync Queue (Outbox) ----------------

export async function enqueueSyncItem(
  item: Omit<SyncQueueItem, 'id' | 'created_at' | 'status' | 'retry_count'>
): Promise<number> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readwrite');
    const store = tx.objectStore(STORE_QUEUE);

    const record: SyncQueueItem = {
      ...item,
      created_at: new Date().toISOString(),
      status: 'pending',
      retry_count: 0,
    };

    const request = store.add(record);

    request.onsuccess = () => {
      const newId = request.result as number;
      resolve(newId);
    };
    request.onerror = () => reject(request.error);
  });
}

export async function getSyncQueue(): Promise<SyncQueueItem[]> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readonly');
    const store = tx.objectStore(STORE_QUEUE);
    const request = store.getAll();

    request.onsuccess = () => {
      const items = (request.result || []) as SyncQueueItem[];
      // sort by created_at ascending (FIFO)
      items.sort(
        (a, b) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
      resolve(items);
    };
    request.onerror = () => reject(request.error);
  });
}

export async function updateSyncItem(item: SyncQueueItem): Promise<void> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readwrite');
    const store = tx.objectStore(STORE_QUEUE);
    const request = store.put(item);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

export async function removeSyncItem(id: number): Promise<void> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readwrite');
    const store = tx.objectStore(STORE_QUEUE);
    const request = store.delete(id);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

export async function clearSyncQueue(): Promise<void> {
  const db = await openFieldDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readwrite');
    const store = tx.objectStore(STORE_QUEUE);
    const request = store.clear();

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

// ---------------- Helpers ----------------

export function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
