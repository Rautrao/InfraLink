'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  ProgressBar,
  Skeleton,
  StatusChip,
  Textarea,
  toast,
} from '@/components/ui';
import {
  SyncQueueItem,
  QueuedEvidencePayload,
  QueuedUpdatePayload,
  cacheWorks,
  getCachedWorks,
  updateCachedWork,
  enqueueSyncItem,
  getSyncQueue,
  removeSyncItem,
  clearSyncQueue,
} from './indexedDb';

interface Work {
  id: string;
  ref_no?: string;
  title: string;
  purpose?: string;
  category?: string;
  status: string;
  delayed?: boolean;
  update_overdue?: boolean;
  road_name?: string;
  ward?: { id?: string; name?: string };
  agency?: { id?: string; name: string };
  contractor_name?: string | null;
  pct_complete?: number;
  planned_start?: string;
  current_target_end?: string;
  last_update_at?: string;
  updates?: Array<{
    id?: string;
    text: string;
    pct_complete?: number;
    at?: string;
    department?: string;
  }>;
  evidence?: Array<{
    id?: string;
    public_url?: string;
    public_path?: string;
    kind?: string;
    taken_at?: string;
    lat?: number;
    lon?: number;
  }>;
}

interface GpsCoords {
  lat: number;
  lon: number;
  accuracy: number | null;
  timestamp: number;
}

export default function FieldPage() {
  // Network and simulation state
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [simulateOffline, setSimulateOffline] = useState<boolean>(false);
  const effectiveOnline = isOnline && !simulateOffline;

  // Data state
  const [works, setWorks] = useState<Work[]>([]);
  const [selectedWorkId, setSelectedWorkId] = useState<string | null>(null);
  const [loadingWorks, setLoadingWorks] = useState<boolean>(true);
  const [isUsingCache, setIsUsingCache] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Sync state
  const [queue, setQueue] = useState<SyncQueueItem[]>([]);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [showQueueModal, setShowQueueModal] = useState<boolean>(false);

  // Navigation tab for main list
  const [statusFilter, setStatusFilter] = useState<string>('active');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Auth token state
  const [hasToken, setHasToken] = useState<boolean>(false);
  const [authEmail, setAuthEmail] = useState<string>('');
  const [authPassword, setAuthPassword] = useState<string>('');
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [authLoading, setAuthLoading] = useState<boolean>(false);

  // Quick Update Form State (in detail view)
  const [updateText, setUpdateText] = useState<string>('');
  const [updatePct, setUpdatePct] = useState<number>(0);
  const [submittingUpdate, setSubmittingUpdate] = useState<boolean>(false);

  // Progress Photo State
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoNote, setPhotoNote] = useState<string>('');
  const [gpsData, setGpsData] = useState<GpsCoords | null>(null);
  const [gpsLoading, setGpsLoading] = useState<boolean>(false);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState<boolean>(false);
  const photoInputRef = useRef<HTMLInputElement>(null);

  // Restoration Done Modal / State
  const [showRestorationModal, setShowRestorationModal] = useState<boolean>(false);
  const [restorationFile, setRestorationFile] = useState<File | null>(null);
  const [restorationPreview, setRestorationPreview] = useState<string | null>(null);
  const [restorationNote, setRestorationNote] = useState<string>('Road and surface reinstated to standard.');
  const [submittingRestoration, setSubmittingRestoration] = useState<boolean>(false);
  const restorationInputRef = useRef<HTMLInputElement>(null);

  // 1. Initialize Network Listeners & Token
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsOnline(navigator.onLine);
      const handleOnline = () => {
        setIsOnline(true);
        toast('Network connected. Ready to sync.');
      };
      const handleOffline = () => {
        setIsOnline(false);
        toast('Network disconnected. Field app is in offline mode.');
      };

      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);

      // Check auth token
      const token = localStorage.getItem('access_token');
      setHasToken(Boolean(token));
      if ('serviceWorker' in navigator) {
        void navigator.serviceWorker.register('/field-sw.js', { scope: '/field' }).catch((error) => {
          console.warn('Field offline shell could not be installed:', error);
        });
      }

      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }
  }, []);

  // 2. Load Sync Queue from IndexedDB
  const refreshQueue = useCallback(async () => {
    try {
      const items = await getSyncQueue();
      setQueue(items);
    } catch (err) {
      console.error('Failed to load sync queue from IndexedDB:', err);
    }
  }, []);

  useEffect(() => {
    refreshQueue();
  }, [refreshQueue]);

  // 3. Load Works (Online API -> fallback to IndexedDB)
  const loadWorks = useCallback(async () => {
    setLoadingWorks(true);
    setLoadError(null);
    if (effectiveOnline) {
      try {
        // Try fetching assigned works from API
        const data = await api<{ items: Work[] }>(
          '/works?status=ongoing,permitted,paused&page=1&page_size=50'
        ).catch(async () => {
          // If status filter fails, try general works list
          return await api<{ items: Work[] }>('/works?page=1&page_size=50');
        });

        const items = data.items || [];
        setWorks(items);
        setIsUsingCache(false);

        // Cache in IndexedDB for offline use
        await cacheWorks(items);
      } catch (err) {
        console.warn('API fetch failed, falling back to IndexedDB cache:', err);
        // Fall back to IndexedDB
        const cached = await getCachedWorks();
        setWorks(cached);
        setIsUsingCache(true);
        if (cached.length === 0) {
          setLoadError('Could not load works and no offline cache is available.');
        }
      } finally {
        setLoadingWorks(false);
      }
    } else {
      // Offline: Read directly from IndexedDB
      try {
        const cached = await getCachedWorks();
        setWorks(cached);
        setIsUsingCache(true);
      } catch (err) {
        console.error('Failed to read from IndexedDB:', err);
        setLoadError('Could not read saved works from this device.');
      } finally {
        setLoadingWorks(false);
      }
    }
  }, [effectiveOnline]);

  useEffect(() => {
    loadWorks();
  }, [loadWorks]);

  // Selected work object
  const selectedWork = useMemo(() => {
    if (!selectedWorkId) return null;
    return works.find((w) => w.id === selectedWorkId) || null;
  }, [works, selectedWorkId]);

  // When selected work changes, initialize updatePct
  useEffect(() => {
    if (selectedWork) {
      setUpdatePct(selectedWork.pct_complete ?? 0);
      setUpdateText('');
      setPhotoFile(null);
      setPhotoPreview(null);
      setPhotoNote('');
    }
  }, [selectedWorkId, selectedWork]);

  // 4. GPS Geolocation helper
  const captureGps = useCallback(() => {
    if (!navigator.geolocation) {
      setGpsError('Geolocation is not supported by your device.');
      return;
    }
    setGpsLoading(true);
    setGpsError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsData({
          lat: Number(pos.coords.latitude.toFixed(6)),
          lon: Number(pos.coords.longitude.toFixed(6)),
          accuracy: pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null,
          timestamp: pos.timestamp,
        });
        setGpsLoading(false);
        toast(`GPS locked (±${Math.round(pos.coords.accuracy || 0)}m)`);
      },
      (err) => {
        setGpsLoading(false);
        let msg = 'Failed to acquire GPS fix.';
        if (err.code === 1) msg = 'Location permission denied.';
        else if (err.code === 2) msg = 'Location unavailable.';
        else if (err.code === 3) msg = 'Location request timed out.';
        setGpsError(msg);
        toast(msg);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  }, []);

  // 5. Handle Progress Photo Selection
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setPhotoFile(file);
    const preview = URL.createObjectURL(file);
    setPhotoPreview(preview);

    // Automatically trigger GPS acquisition when a photo is taken
    captureGps();
  };

  // 6. Handle Restoration Photo Selection
  const handleRestorationSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setRestorationFile(file);
    const preview = URL.createObjectURL(file);
    setRestorationPreview(preview);

    // Acquire GPS fix for restoration
    captureGps();
  };

  // 7. Post Quick Update
  const handlePostUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWork) return;
    if (!updateText.trim()) {
      toast('Please enter a brief note for this update.');
      return;
    }

    setSubmittingUpdate(true);
    const payload: QueuedUpdatePayload = {
      text: updateText.trim(),
      pct_complete: updatePct,
    };

    if (effectiveOnline) {
      // Send directly via API
      try {
        await api(`/works/${encodeURIComponent(selectedWork.id)}/updates`, {
          method: 'POST',
          body: JSON.stringify(payload),
        });

        // Update local work state
        setWorks((prev) =>
          prev.map((w) =>
            w.id === selectedWork.id
              ? {
                  ...w,
                  pct_complete: updatePct,
                  last_update_at: new Date().toISOString(),
                  updates: [
                    {
                      text: payload.text,
                      pct_complete: payload.pct_complete,
                      at: new Date().toISOString(),
                    },
                    ...(w.updates || []),
                  ],
                }
              : w
          )
        );

        toast('✓ Quick update posted successfully!');
        setUpdateText('');
      } catch (err: any) {
        console.warn('Online update failed, saving to IndexedDB queue:', err);
        // Fall back to queueing if network failed during POST
        await queueUpdateLocally(selectedWork, payload);
      } finally {
        setSubmittingUpdate(false);
      }
    } else {
      // Offline: Enqueue to IndexedDB
      await queueUpdateLocally(selectedWork, payload);
      setSubmittingUpdate(false);
    }
  };

  const queueUpdateLocally = async (work: Work, payload: QueuedUpdatePayload) => {
    try {
      await enqueueSyncItem({
        type: 'update',
        work_id: work.id,
        work_title: work.title,
        work_ref: work.ref_no,
        payload,
      });

      // Optimistically update cached work in IndexedDB
      await updateCachedWork(work.id, {
        pct_complete: payload.pct_complete,
        last_update_at: new Date().toISOString(),
      });

      // Update in-memory state
      setWorks((prev) =>
        prev.map((w) =>
          w.id === work.id
            ? {
                ...w,
                pct_complete: payload.pct_complete,
                last_update_at: new Date().toISOString(),
              }
            : w
        )
      );

      await refreshQueue();
      toast('⚡ Saved to offline queue in IndexedDB. Will sync when online.');
      setUpdateText('');
    } catch (err) {
      console.error('Failed to queue update locally:', err);
      toast('Error saving update to local storage.');
    }
  };

  // 8. Upload Progress Photo
  const handleUploadPhoto = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWork || !photoFile) {
      toast('Please capture or select a photo.');
      return;
    }

    setUploadingPhoto(true);
    const takenAt = new Date().toISOString();

    const payload: QueuedEvidencePayload = {
      kind: 'progress',
      note: photoNote.trim() || undefined,
      lat: gpsData?.lat ?? null,
      lon: gpsData?.lon ?? null,
      accuracy: gpsData?.accuracy ?? null,
      taken_at: takenAt,
      fileName: photoFile.name || `progress-${Date.now()}.jpg`,
      fileType: photoFile.type || 'image/jpeg',
      fileBlob: photoFile,
      previewUrl: photoPreview || undefined,
    };

    if (effectiveOnline) {
      try {
        const formData = new FormData();
        formData.append('file', photoFile, payload.fileName);
        formData.append('kind', 'progress');
        if (payload.lat != null) formData.append('lat', String(payload.lat));
        if (payload.lon != null) formData.append('lon', String(payload.lon));
        if (payload.accuracy != null) formData.append('accuracy', String(payload.accuracy));
        formData.append('taken_at', takenAt);
        if (payload.note) formData.append('note', payload.note);

        await api(`/works/${encodeURIComponent(selectedWork.id)}/evidence`, {
          method: 'POST',
          body: formData,
        });

        toast('✓ Progress photo uploaded successfully!');
        setPhotoFile(null);
        setPhotoPreview(null);
        setPhotoNote('');
      } catch (err: any) {
        console.warn('Online photo upload failed, storing in IndexedDB queue:', err);
        await queuePhotoLocally(selectedWork, payload);
      } finally {
        setUploadingPhoto(false);
      }
    } else {
      // Offline: Enqueue in IndexedDB
      await queuePhotoLocally(selectedWork, payload);
      setUploadingPhoto(false);
    }
  };

  const queuePhotoLocally = async (work: Work, payload: QueuedEvidencePayload) => {
    try {
      await enqueueSyncItem({
        type: 'evidence',
        work_id: work.id,
        work_title: work.title,
        work_ref: work.ref_no,
        payload,
      });

      await refreshQueue();
      toast('⚡ Photo saved to IndexedDB queue. Ready to sync online.');
      setPhotoFile(null);
      setPhotoPreview(null);
      setPhotoNote('');
    } catch (err) {
      console.error('Failed to store photo in IndexedDB:', err);
      toast('Error storing photo locally.');
    }
  };

  // 9. Mark Restoration Done
  const handleMarkRestorationDone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWork) return;

    setSubmittingRestoration(true);
    const takenAt = new Date().toISOString();

    const blobToUse =
      restorationFile ||
      new Blob(['Restoration certified by site engineer'], { type: 'text/plain' });
    const fileName = restorationFile?.name || `restoration-${Date.now()}.jpg`;
    const fileType = restorationFile?.type || 'image/jpeg';

    const payload: QueuedEvidencePayload = {
      kind: 'restoration',
      note: restorationNote.trim(),
      lat: gpsData?.lat ?? null,
      lon: gpsData?.lon ?? null,
      accuracy: gpsData?.accuracy ?? null,
      taken_at: takenAt,
      fileName,
      fileType,
      fileBlob: blobToUse,
      previewUrl: restorationPreview || undefined,
    };

    if (effectiveOnline) {
      try {
        const formData = new FormData();
        formData.append('file', blobToUse, fileName);
        formData.append('kind', 'restoration');
        if (payload.lat != null) formData.append('lat', String(payload.lat));
        if (payload.lon != null) formData.append('lon', String(payload.lon));
        if (payload.accuracy != null) formData.append('accuracy', String(payload.accuracy));
        formData.append('taken_at', takenAt);
        if (payload.note) formData.append('note', payload.note);

        await api(`/works/${encodeURIComponent(selectedWork.id)}/evidence`, {
          method: 'POST',
          body: formData,
        });

        // Also post completion update to 100%
        await api(`/works/${encodeURIComponent(selectedWork.id)}/updates`, {
          method: 'POST',
          body: JSON.stringify({
            text: `Restoration completed: ${payload.note}`,
            pct_complete: 100,
          }),
        }).catch(() => {});

        // Update local work state
        setWorks((prev) =>
          prev.map((w) =>
            w.id === selectedWork.id
              ? {
                  ...w,
                  status: 'restoration_verified',
                  pct_complete: 100,
                  last_update_at: new Date().toISOString(),
                }
              : w
          )
        );

        toast('✓ Restoration marked done and verified!');
        setShowRestorationModal(false);
        setRestorationFile(null);
        setRestorationPreview(null);
      } catch (err: any) {
        console.warn('Online restoration failed, saving to IndexedDB queue:', err);
        await queueRestorationLocally(selectedWork, payload);
      } finally {
        setSubmittingRestoration(false);
      }
    } else {
      // Offline: Enqueue to IndexedDB
      await queueRestorationLocally(selectedWork, payload);
      setSubmittingRestoration(false);
    }
  };

  const queueRestorationLocally = async (work: Work, payload: QueuedEvidencePayload) => {
    try {
      await enqueueSyncItem({
        type: 'evidence',
        work_id: work.id,
        work_title: work.title,
        work_ref: work.ref_no,
        payload,
      });

      // Optimistically update cached work to 100% and restoration_verified
      await updateCachedWork(work.id, {
        pct_complete: 100,
        status: 'restoration_verified',
        last_update_at: new Date().toISOString(),
      });

      setWorks((prev) =>
        prev.map((w) =>
          w.id === work.id
            ? {
                ...w,
                status: 'restoration_verified',
                pct_complete: 100,
                last_update_at: new Date().toISOString(),
              }
            : w
        )
      );

      await refreshQueue();
      toast('⚡ Restoration verification stored in IndexedDB queue. Ready to sync.');
      setShowRestorationModal(false);
      setRestorationFile(null);
      setRestorationPreview(null);
    } catch (err) {
      console.error('Failed to queue restoration:', err);
      toast('Error saving restoration locally.');
    }
  };

  // 10. Sync Engine: Process IndexedDB Queue
  const syncQueueNow = async () => {
    if (!effectiveOnline) {
      toast('Cannot sync while in offline mode.');
      return;
    }

    const items = await getSyncQueue();
    if (items.length === 0) {
      toast('No pending items to sync.');
      return;
    }

    setIsSyncing(true);
    setSyncMessage(`Syncing 1 of ${items.length}...`);

    let syncedCount = 0;
    let failedCount = 0;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      setSyncMessage(`Syncing ${i + 1} of ${items.length}...`);

      try {
        if (item.type === 'update') {
          const p = item.payload as QueuedUpdatePayload;
          await api(`/works/${encodeURIComponent(item.work_id)}/updates`, {
            method: 'POST',
            body: JSON.stringify({
              text: p.text,
              pct_complete: p.pct_complete,
              explanation: p.explanation,
            }),
          });
        } else if (item.type === 'evidence') {
          const p = item.payload as QueuedEvidencePayload;
          const formData = new FormData();
          const fileToUpload =
            p.fileBlob instanceof File
              ? p.fileBlob
              : new File([p.fileBlob], p.fileName || 'evidence.jpg', {
                  type: p.fileType || 'image/jpeg',
                });

          formData.append('file', fileToUpload, p.fileName);
          formData.append('kind', p.kind || 'progress');
          if (p.lat != null) formData.append('lat', String(p.lat));
          if (p.lon != null) formData.append('lon', String(p.lon));
          if (p.accuracy != null) formData.append('accuracy', String(p.accuracy));
          if (p.taken_at) formData.append('taken_at', p.taken_at);
          if (p.note) formData.append('note', p.note);

          await api(`/works/${encodeURIComponent(item.work_id)}/evidence`, {
            method: 'POST',
            body: formData,
          });

          // If kind was restoration, also post completion
          if (p.kind === 'restoration') {
            await api(`/works/${encodeURIComponent(item.work_id)}/updates`, {
              method: 'POST',
              body: JSON.stringify({
                text: `Restoration synced: ${p.note || 'Site restored'}`,
                pct_complete: 100,
              }),
            }).catch(() => {});
          }
        }

        // Successfully sent, remove from queue
        if (item.id != null) {
          await removeSyncItem(item.id);
        }
        syncedCount++;
      } catch (err: any) {
        console.error(`Failed to sync queue item #${item.id}:`, err);
        failedCount++;
        break;
      }
    }

    await refreshQueue();
    setIsSyncing(false);
    setSyncMessage(null);

    if (failedCount === 0) {
      toast(`✓ Successfully synced ${syncedCount} item(s)!`);
      loadWorks();
    } else {
      toast(`Synced ${syncedCount} item(s). ${failedCount} item failed; will retry next.`);
    }
  };

  // 11. Quick Staff Login
  const handleQuickLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      const email = authEmail || 'je.ward1@demo.city';
      const password = authPassword || 'demo1234';

      const res = await api<{ access_token: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });

      if (res.access_token) {
        localStorage.setItem('access_token', res.access_token);
        setHasToken(true);
        setShowAuthModal(false);
        toast('✓ Logged in as Field Junior Engineer (Ward 1).');
        loadWorks();
      }
    } catch (err: any) {
      toast(err.message || 'Login failed. Please verify credentials.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setHasToken(false);
    toast('Logged out from field session.');
  };

  // 12. Filtered works list
  const filteredWorks = useMemo(() => {
    return works.filter((w) => {
      // Status filter
      if (statusFilter === 'active') {
        if (!['ongoing', 'permitted', 'paused'].includes(w.status)) return false;
      } else if (statusFilter === 'completed') {
        if (!['completed', 'restoration_verified', 'closed'].includes(w.status)) return false;
      }

      // Query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const match =
          w.title?.toLowerCase().includes(q) ||
          w.road_name?.toLowerCase().includes(q) ||
          w.ref_no?.toLowerCase().includes(q) ||
          w.ward?.name?.toLowerCase().includes(q);
        if (!match) return false;
      }
      return true;
    });
  }, [works, statusFilter, searchQuery]);

  // Locally pending items for the selected work
  const workPendingItems = useMemo(() => {
    if (!selectedWorkId) return [];
    return queue.filter((item) => item.work_id === selectedWorkId);
  }, [queue, selectedWorkId]);

  return (
    <div className="mx-auto max-w-md w-full bg-slate-50 min-h-screen shadow-xl flex flex-col font-sans">
      {/* ===================== NATIVE MOBILE APP HEADER ===================== */}
      <header className="sticky top-0 z-30 bg-[#075e67] text-white px-4 py-3 shadow-md flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-teal-800/80 border border-teal-400/40 flex items-center justify-center font-black text-sm text-teal-200">
            ⚡
          </div>
          <div>
            <h1 className="text-base font-extrabold tracking-tight leading-tight flex items-center gap-1.5">
              Field Ops PWA
            </h1>
            <p className="text-[11px] text-teal-100/90 font-medium leading-none">
              Demo City · Junior Engineer
            </p>
          </div>
        </div>

        {/* Right Tools: Connection Status & Queue pill */}
        <div className="flex items-center gap-2">
          {/* Connection status badge */}
          <button
            onClick={() => setSimulateOffline((prev) => !prev)}
            title={simulateOffline ? 'Simulation: Click to go online' : 'Click to simulate offline'}
            className={`text-xs px-2.5 py-1 rounded-full font-bold flex items-center gap-1.5 transition-all ${
              effectiveOnline
                ? 'bg-emerald-900/60 text-emerald-200 border border-emerald-400/30 hover:bg-emerald-800/80'
                : 'bg-amber-900/80 text-amber-200 border border-amber-400/50 animate-pulse'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                effectiveOnline ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            {effectiveOnline ? 'Online' : 'Offline'}
          </button>

          {/* Sync Queue counter */}
          <button
            onClick={() => setShowQueueModal(true)}
            className="relative p-1.5 rounded-lg bg-teal-800/60 hover:bg-teal-700/80 text-white border border-teal-500/30 flex items-center justify-center"
            title="View sync queue"
            aria-label="View sync queue"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            {queue.length > 0 && (
              <span className="absolute -top-1 -right-1 px-1.5 py-0.2 bg-amber-500 text-slate-950 font-black text-[10px] rounded-full min-w-[18px] text-center shadow">
                {queue.length}
              </span>
            )}
          </button>

          {/* Auth Button */}
          <button
            onClick={() => setShowAuthModal(true)}
            className="p-1.5 rounded-lg bg-teal-800/60 hover:bg-teal-700/80 text-white border border-teal-500/30 flex items-center justify-center"
            title={hasToken ? 'Officer Session Active' : 'Log in as Officer'}
          >
            <span className="text-sm">{hasToken ? '👤' : '🔑'}</span>
          </button>
        </div>
      </header>

      {/* ===================== OFFLINE / SYNC BANNER ===================== */}
      {!effectiveOnline && (
        <div className="bg-amber-500 text-slate-950 px-4 py-2 text-xs font-semibold flex items-center justify-between border-b border-amber-600 shadow-sm animate-fadeIn">
          <div className="flex items-center gap-2">
            <span className="text-base leading-none">⚡</span>
            <span>
              <strong>Offline Mode Active.</strong> Changes are saved in IndexedDB and will sync
              online.
            </span>
          </div>
          <button
            onClick={() => setSimulateOffline(false)}
            className="ml-2 underline text-[11px] font-bold text-slate-900 shrink-0"
          >
            Reconnect
          </button>
        </div>
      )}

      {effectiveOnline && queue.length > 0 && (
        <div className="bg-teal-700 text-white px-4 py-2 text-xs flex items-center justify-between border-b border-teal-800 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-base leading-none">🔄</span>
            <span>
              <strong>{queue.length} action(s)</strong> waiting in IndexedDB outbox.
            </span>
          </div>
          <button
            onClick={syncQueueNow}
            disabled={isSyncing}
            className="bg-white text-teal-800 px-2.5 py-1 rounded text-xs font-bold hover:bg-teal-50 active:scale-95 disabled:opacity-50"
          >
            {isSyncing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      )}

      {isSyncing && (
        <div className="bg-teal-600 text-white px-4 py-1.5 text-xs text-center font-medium animate-pulse">
          {syncMessage || 'Synchronizing with city server...'}
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 p-3.5 space-y-3.5 pb-20">
        {/* ================================================================ */}
        {/* VIEW 1: DETAIL VIEW (When a work is selected)                     */}
        {/* ================================================================ */}
        {selectedWork ? (
          <div className="space-y-4 animate-fadeIn">
            {/* Top Bar for Detail */}
            <div className="flex items-center justify-between gap-2 border-b border-slate-200 pb-2.5">
              <button
                onClick={() => setSelectedWorkId(null)}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[#075e67] bg-white border border-slate-300 px-3 py-1.5 rounded-lg shadow-sm active:bg-slate-100"
              >
                <span>←</span> Back to Works
              </button>
              <div className="flex items-center gap-1.5">
                <StatusChip status={selectedWork.status} />
                {selectedWork.delayed && <Badge tone="danger">Delayed</Badge>}
              </div>
            </div>

            {/* Work Header Card */}
            <Card className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-sm">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-teal-800 bg-teal-50 px-2 py-0.5 rounded">
                    {selectedWork.ref_no || 'WRK-2026'}
                  </span>
                  <span className="text-xs text-slate-500">
                    {selectedWork.ward?.name || 'Ward 1'}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-slate-900 leading-snug">
                  {selectedWork.title}
                </h2>
                <p className="text-xs text-slate-600 font-medium">
                  📍 {selectedWork.road_name || 'Road section'} ·{' '}
                  {selectedWork.agency?.name || 'Municipal Agency'}
                </p>
                {selectedWork.contractor_name && (
                  <p className="text-xs text-slate-500">
                    🏗 Contractor: <strong>{selectedWork.contractor_name}</strong>
                  </p>
                )}
              </div>

              {/* Progress Bar */}
              <div className="mt-3 pt-3 border-t border-slate-100">
                <ProgressBar
                  value={selectedWork.pct_complete ?? 0}
                  label="Work Completion"
                />
              </div>
            </Card>

            {/* Local Pending Queue Alerts for this work */}
            {workPendingItems.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-300 rounded-xl text-xs space-y-1.5">
                <div className="flex items-center justify-between font-bold text-amber-900">
                  <span className="flex items-center gap-1.5">
                    <span>⏱</span> {workPendingItems.length} update(s) stored in IndexedDB outbox
                  </span>
                  <span className="text-[10px] bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full font-black">
                    AWAITING SYNC
                  </span>
                </div>
                <p className="text-amber-800 text-[11px]">
                  These changes were saved while offline and will be published when connected.
                </p>
              </div>
            )}

            {/* ================= SECTION A: QUICK UPDATE FORM ================= */}
            <Card className="p-4 bg-white border border-slate-200 rounded-xl shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                  <span>📝</span> Post Quick Update
                </h3>
                <span className="text-xs font-semibold text-teal-800 bg-teal-50 px-2 py-0.5 rounded">
                  {updatePct}% complete
                </span>
              </div>

              <form onSubmit={handlePostUpdate} className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Progress Description / Site Notes *
                  </label>
                  <Textarea
                    value={updateText}
                    onChange={(e) => setUpdateText(e.target.value)}
                    placeholder="e.g. Completed 120m ducting trench, began backfilling..."
                    rows={2}
                    className="text-xs"
                    required
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700 mb-1">
                    <span>Completion Percentage:</span>
                    <span className="text-teal-800 font-extrabold text-sm">{updatePct}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={updatePct}
                    onChange={(e) => setUpdatePct(Number(e.target.value))}
                    className="w-full accent-[#075e67] cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                    <span>0% Start</span>
                    <span>50% Mid</span>
                    <span>100% Complete</span>
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={submittingUpdate || !updateText.trim()}
                  className="w-full justify-center text-xs py-2"
                >
                  {submittingUpdate
                    ? 'Saving...'
                    : effectiveOnline
                    ? 'Post Quick Update'
                    : '⚡ Save Update to IndexedDB'}
                </Button>
              </form>
            </Card>

            {/* ================= SECTION B: ADD PROGRESS PHOTO ================= */}
            <Card className="p-4 bg-white border border-slate-200 rounded-xl shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                  <span>📷</span> Add Progress Photo
                </h3>
                <span className="text-[11px] text-slate-500">Camera & GPS</span>
              </div>

              {/* Native Mobile Camera Trigger */}
              <div className="space-y-2">
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={handlePhotoSelect}
                  className="hidden"
                  id="camera-photo-input"
                />

                {!photoPreview ? (
                  <button
                    type="button"
                    onClick={() => photoInputRef.current?.click()}
                    className="w-full border-2 border-dashed border-teal-300 bg-teal-50/50 hover:bg-teal-50 rounded-xl p-4 flex flex-col items-center justify-center gap-1.5 transition active:scale-[0.99]"
                  >
                    <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center text-teal-800 text-lg">
                      📸
                    </div>
                    <span className="text-xs font-bold text-teal-900">
                      Tap to Take Photo (Camera)
                    </span>
                    <span className="text-[10px] text-teal-700">
                      Captures timestamp & geotag automatically
                    </span>
                  </button>
                ) : (
                  <div className="space-y-2">
                    <div className="relative rounded-lg overflow-hidden border border-slate-300 bg-black max-h-56 flex items-center justify-center">
                      <img
                        src={photoPreview}
                        alt="Captured site progress"
                        className="w-full object-contain max-h-52"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          setPhotoFile(null);
                          setPhotoPreview(null);
                        }}
                        className="absolute top-2 right-2 bg-black/70 text-white rounded-full p-1 text-xs px-2 hover:bg-black"
                      >
                        Retake
                      </button>
                    </div>

                    {/* Geolocation Tag display */}
                    <div className="p-2.5 rounded-lg bg-slate-100 border border-slate-200 text-xs flex items-center justify-between">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-1.5 font-bold text-slate-800">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              gpsData ? 'bg-emerald-500' : 'bg-amber-500'
                            }`}
                          />
                          {gpsData ? 'GPS Geotag Fixed' : 'GPS Coordinates'}
                        </div>
                        {gpsData ? (
                          <p className="text-[11px] text-slate-600 font-mono">
                            {gpsData.lat}°, {gpsData.lon}° (±{gpsData.accuracy || 5}m)
                          </p>
                        ) : (
                          <p className="text-[11px] text-slate-500">
                            {gpsLoading ? 'Acquiring GPS fix...' : 'No GPS lock acquired'}
                          </p>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={captureGps}
                        disabled={gpsLoading}
                        className="text-[11px] font-bold text-teal-800 bg-white border border-slate-300 px-2 py-1 rounded shadow-sm hover:bg-slate-50"
                      >
                        {gpsLoading ? 'Locating...' : 'Refresh GPS'}
                      </button>
                    </div>

                    {gpsError && (
                      <p className="text-[11px] text-rose-600 font-medium">⚠️ {gpsError}</p>
                    )}

                    {/* Optional Note */}
                    <div>
                      <Input
                        value={photoNote}
                        onChange={(e) => setPhotoNote(e.target.value)}
                        placeholder="Caption / description (optional)"
                        className="text-xs"
                      />
                    </div>

                    <Button
                      type="button"
                      onClick={handleUploadPhoto}
                      disabled={uploadingPhoto}
                      className="w-full justify-center text-xs py-2"
                    >
                      {uploadingPhoto
                        ? 'Uploading...'
                        : effectiveOnline
                        ? 'Upload Progress Photo'
                        : '⚡ Save Photo to IndexedDB Outbox'}
                    </Button>
                  </div>
                )}
              </div>
            </Card>

            {/* ================= SECTION C: MARK RESTORATION DONE ================= */}
            <Card className="p-4 bg-gradient-to-br from-emerald-50 to-teal-50 border-2 border-emerald-400 rounded-xl shadow-sm space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-base">◆</span>
                    <h3 className="font-extrabold text-emerald-950 text-sm">
                      Mark Restoration Done
                    </h3>
                  </div>
                  <p className="text-[11px] text-emerald-800 font-medium mt-0.5">
                    Post official restoration verification evidence to mark street reinstated.
                  </p>
                </div>
                <Badge tone="neutral">Milestone</Badge>
              </div>

              <div className="bg-white/80 p-2.5 rounded-lg border border-emerald-200 text-xs text-slate-700 space-y-1">
                <p>
                  • Excavation is backfilled & asphalt/pavement is fully relaid.
                </p>
                <p>• Construction debris and barricades are removed.</p>
              </div>

              <Button
                type="button"
                onClick={() => setShowRestorationModal(true)}
                className="w-full justify-center bg-emerald-700 hover:bg-emerald-800 text-white font-extrabold text-xs py-2.5 shadow-sm"
              >
                ◆ Mark Restoration Done (Verify Site)
              </Button>
            </Card>

            {/* ================= SECTION D: SITE EVIDENCE & HISTORY ================= */}
            <div className="space-y-2 pt-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-600 px-1">
                Site Evidence & Timeline
              </h3>

              {/* Photos Gallery */}
              {selectedWork.evidence && selectedWork.evidence.length > 0 ? (
                <div className="grid grid-cols-2 gap-2">
                  {selectedWork.evidence.map((ev, i) => (
                    <div
                      key={ev.id || i}
                      className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm text-xs"
                    >
                      <div className="h-24 bg-slate-100 flex items-center justify-center overflow-hidden">
                        {ev.public_url || ev.public_path ? (
                          <img
                            src={ev.public_url || ev.public_path}
                            alt="Evidence"
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <span className="text-slate-400 text-xl">🖼</span>
                        )}
                      </div>
                      <div className="p-1.5 text-[10px] space-y-0.5">
                        <div className="font-bold text-slate-800 capitalize">
                          {ev.kind || 'Progress'}
                        </div>
                        <div className="text-slate-500">
                          {ev.taken_at ? new Date(ev.taken_at).toLocaleDateString() : 'Recent'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic px-1">
                  No public photos recorded yet.
                </p>
              )}

              {/* Recent Updates */}
              {selectedWork.updates && selectedWork.updates.length > 0 && (
                <div className="space-y-1.5 pt-2">
                  {selectedWork.updates.slice(0, 4).map((u, i) => (
                    <div
                      key={u.id || i}
                      className="p-2.5 bg-white border border-slate-200 rounded-lg text-xs space-y-0.5 shadow-2xs"
                    >
                      <p className="font-medium text-slate-800">{u.text}</p>
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>{u.at ? new Date(u.at).toLocaleDateString() : 'Just now'}</span>
                        {typeof u.pct_complete === 'number' && (
                          <span className="font-bold text-teal-800">{u.pct_complete}%</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* ================================================================ */
          /* VIEW 2: WORKS LIST (Assigned Works)                              */
          /* ================================================================ */
          <div className="space-y-3 animate-fadeIn">
            {/* Header / Filter Toolbar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-slate-900">Assigned Public Works</h2>
                  <p className="text-xs text-slate-500">
                    {isUsingCache ? '📦 Stored in IndexedDB' : '🌐 Connected to live registry'}
                  </p>
                </div>
                <Button
                  tone="secondary"
                  onClick={loadWorks}
                  disabled={loadingWorks}
                  className="text-xs py-1 px-2.5 h-auto min-h-0"
                >
                  {loadingWorks ? 'Refreshing...' : '↻ Refresh'}
                </Button>
              </div>

              {/* Search Bar */}
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search road, project, ward..."
                className="text-xs h-9 bg-white"
              />

              {/* Status Tabs */}
              <div className="flex gap-1 bg-slate-200/80 p-1 rounded-lg text-xs font-semibold">
                <button
                  onClick={() => setStatusFilter('active')}
                  className={`flex-1 py-1.5 rounded-md text-center transition ${
                    statusFilter === 'active'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Active ({works.filter((w) => ['ongoing', 'permitted', 'paused'].includes(w.status)).length})
                </button>
                <button
                  onClick={() => setStatusFilter('all')}
                  className={`flex-1 py-1.5 rounded-md text-center transition ${
                    statusFilter === 'all'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  All ({works.length})
                </button>
                <button
                  onClick={() => setStatusFilter('completed')}
                  className={`flex-1 py-1.5 rounded-md text-center transition ${
                    statusFilter === 'completed'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Completed
                </button>
              </div>
            </div>

            {/* List of Works */}
            {loadingWorks ? (
              <div className="space-y-2.5">
                {[1, 2, 3].map((n) => (
                  <Skeleton key={n} className="h-28 rounded-xl" />
                ))}
              </div>
            ) : filteredWorks.length === 0 ? (
              <Card className="text-center py-8">
                {loadError ? <div role="alert" className="space-y-3"><p>{loadError}</p><Button tone="secondary" onClick={() => void loadWorks()}>Retry</Button></div> : <EmptyState
                  title="No assigned works found"
                  detail={
                    searchQuery
                      ? 'No matches for your search term.'
                      : 'No public works currently assigned for this status.'
                  }
                  action={
                    searchQuery ? (
                      <Button tone="secondary" onClick={() => setSearchQuery('')}>
                        Clear Search
                      </Button>
                    ) : undefined
                  }
                />}
              </Card>
            ) : (
              <div className="space-y-2.5">
                {filteredWorks.map((work) => {
                  const pendingCount = queue.filter((q) => q.work_id === work.id).length;
                  return (
                    <div
                      key={work.id}
                      onClick={() => setSelectedWorkId(work.id)}
                      className="bg-white border border-slate-200 hover:border-teal-500 rounded-xl p-3.5 shadow-xs cursor-pointer transition active:scale-[0.99] space-y-2"
                    >
                      <div className="flex items-center justify-between gap-1.5">
                        <span className="text-[10px] font-extrabold uppercase tracking-wider text-teal-800 bg-teal-50 px-2 py-0.5 rounded">
                          {work.ref_no || 'WRK-2026'}
                        </span>
                        <div className="flex items-center gap-1">
                          {pendingCount > 0 && (
                            <span className="text-[10px] font-bold bg-amber-100 text-amber-900 px-1.5 py-0.5 rounded-full">
                              ⏱ {pendingCount} queued
                            </span>
                          )}
                          <StatusChip status={work.status} />
                        </div>
                      </div>

                      <div>
                        <h3 className="font-bold text-slate-900 text-sm leading-snug">
                          {work.title}
                        </h3>
                        <p className="text-xs text-slate-500 mt-0.5">
                          📍 {work.road_name || 'Road section'} · {work.ward?.name || 'Ward'}
                        </p>
                      </div>

                      {/* Progress bar preview */}
                      <div className="space-y-1 pt-1">
                        <div className="flex justify-between text-[11px] font-semibold text-slate-600">
                          <span>Progress</span>
                          <span className="text-teal-900 font-bold">
                            {work.pct_complete ?? 0}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#075e67] rounded-full transition-all"
                            style={{ width: `${Math.min(100, work.pct_complete ?? 0)}%` }}
                          />
                        </div>
                      </div>

                      <div className="pt-1 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-100">
                        <span>{work.agency?.name || 'City Agency'}</span>
                        <span className="font-bold text-teal-800">Open Detail →</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </main>

      {/* ===================== BOTTOM NAVIGATION BAR ===================== */}
      <nav className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-white border-t border-slate-200 px-4 py-2 flex items-center justify-around z-20 shadow-lg">
        <button
          onClick={() => setSelectedWorkId(null)}
          className={`flex flex-col items-center gap-0.5 text-xs font-bold transition ${
            !selectedWorkId ? 'text-[#075e67]' : 'text-slate-400 hover:text-slate-600'
          }`}
        >
          <span className="text-base">📋</span>
          <span>Works</span>
        </button>

        <button
          onClick={() => setShowQueueModal(true)}
          className="flex flex-col items-center gap-0.5 text-xs font-bold text-slate-400 hover:text-slate-600 relative transition"
        >
          <span className="text-base">📦</span>
          <span>Outbox ({queue.length})</span>
          {queue.length > 0 && (
            <span className="absolute -top-1 right-2 w-2 h-2 rounded-full bg-amber-500" />
          )}
        </button>

        <button
          onClick={() => setSimulateOffline((prev) => !prev)}
          className={`flex flex-col items-center gap-0.5 text-xs font-bold transition ${
            !effectiveOnline ? 'text-amber-600' : 'text-slate-400 hover:text-slate-600'
          }`}
        >
          <span className="text-base">{effectiveOnline ? '📶' : '⚡'}</span>
          <span>{effectiveOnline ? 'Go Offline' : 'Reconnect'}</span>
        </button>

        <button
          onClick={() => setShowAuthModal(true)}
          className="flex flex-col items-center gap-0.5 text-xs font-bold text-slate-400 hover:text-slate-600 transition"
        >
          <span className="text-base">{hasToken ? '👤' : '🔑'}</span>
          <span>{hasToken ? 'Profile' : 'Auth'}</span>
        </button>
      </nav>

      {/* ===================== RESTORATION MODAL ===================== */}
      <Modal
        open={showRestorationModal}
        title="Mark Restoration Done"
        onClose={() => setShowRestorationModal(false)}
      >
        <form onSubmit={handleMarkRestorationDone} className="space-y-3.5 text-xs">
          <div className="bg-emerald-50 border border-emerald-300 rounded-lg p-3 text-emerald-900 space-y-1">
            <p className="font-bold">Restoration Verification Check:</p>
            <p>
              Please attach proof of asphalt reinstatement and surface finishing. This will record
              evidence of kind <strong>restoration</strong> and set completion to 100%.
            </p>
          </div>

          <div>
            <label className="block font-bold text-slate-800 mb-1">
              Restoration Verification Photo *
            </label>
            <input
              ref={restorationInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleRestorationSelect}
              className="hidden"
              id="camera-restoration-input"
            />

            {!restorationPreview ? (
              <button
                type="button"
                onClick={() => restorationInputRef.current?.click()}
                className="w-full border-2 border-dashed border-emerald-400 bg-emerald-50 hover:bg-emerald-100/60 rounded-xl p-4 flex flex-col items-center justify-center gap-1.5 transition"
              >
                <div className="w-9 h-9 rounded-full bg-emerald-200 flex items-center justify-center text-emerald-900 text-lg">
                  📸
                </div>
                <span className="font-bold text-emerald-950">
                  Tap to Take Restoration Photo
                </span>
                <span className="text-[10px] text-emerald-700">
                  Captures geotag & timestamp
                </span>
              </button>
            ) : (
              <div className="space-y-1.5">
                <div className="relative rounded-lg overflow-hidden border border-slate-300 max-h-44 bg-black flex items-center justify-center">
                  <img
                    src={restorationPreview}
                    alt="Restoration Preview"
                    className="w-full object-contain max-h-40"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setRestorationFile(null);
                      setRestorationPreview(null);
                    }}
                    className="absolute top-2 right-2 bg-black/70 text-white rounded-full p-1 text-xs px-2"
                  >
                    Retake
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* GPS fix for restoration */}
          <div className="p-2.5 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-between">
            <div className="space-y-0.5">
              <span className="font-bold text-slate-800">
                {gpsData ? '✓ GPS Geotag Locked' : 'GPS Coordinates'}
              </span>
              {gpsData ? (
                <p className="text-[11px] text-slate-600 font-mono">
                  {gpsData.lat}°, {gpsData.lon}° (±{gpsData.accuracy || 5}m)
                </p>
              ) : (
                <p className="text-[11px] text-slate-500">
                  {gpsLoading ? 'Acquiring GPS fix...' : 'Tap Refresh GPS'}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={captureGps}
              disabled={gpsLoading}
              className="text-[11px] font-bold text-teal-800 bg-white border border-slate-300 px-2 py-1 rounded"
            >
              {gpsLoading ? 'Locating...' : 'Refresh GPS'}
            </button>
          </div>

          <div>
            <label className="block font-bold text-slate-800 mb-1">
              Restoration Remarks / Road Quality *
            </label>
            <Textarea
              value={restorationNote}
              onChange={(e) => setRestorationNote(e.target.value)}
              rows={2}
              required
              className="text-xs"
            />
          </div>

          <div className="pt-2 flex gap-2">
            <Button
              type="button"
              tone="secondary"
              onClick={() => setShowRestorationModal(false)}
              className="flex-1 justify-center"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submittingRestoration}
              className="flex-1 justify-center bg-emerald-700 hover:bg-emerald-800 text-white font-bold"
            >
              {submittingRestoration ? 'Saving...' : 'Confirm Restoration'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* ===================== SYNC QUEUE OUTBOX MODAL ===================== */}
      <Modal
        open={showQueueModal}
        title={`IndexedDB Outbox (${queue.length})`}
        onClose={() => setShowQueueModal(false)}
      >
        <div className="space-y-3 text-xs">
          <p className="text-slate-600">
            Pending actions queued in local IndexedDB. Items are synced to the city server in FIFO
            order once online.
          </p>

          {queue.length === 0 ? (
            <div className="text-center py-6 text-slate-400">
              <span className="text-2xl block mb-1">✓</span>
              <span>Your outbox is completely synced.</span>
            </div>
          ) : (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {queue.map((item) => (
                <div
                  key={item.id}
                  className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg space-y-1 relative"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 capitalize flex items-center gap-1">
                      <span>{item.type === 'evidence' ? '📷 Photo / Evidence' : '📝 Quick Update'}</span>
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {new Date(item.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-700">
                    Work: <strong>{item.work_ref || item.work_title || item.work_id}</strong>
                  </p>

                  {item.type === 'update' && (
                    <div className="text-[11px] text-slate-600 bg-white p-1.5 rounded border border-slate-100">
                      <p>"{ (item.payload as QueuedUpdatePayload).text }"</p>
                      <span className="text-teal-800 font-bold">
                        Progress: {(item.payload as QueuedUpdatePayload).pct_complete}%
                      </span>
                    </div>
                  )}

                  {item.type === 'evidence' && (
                    <div className="text-[11px] text-slate-600 bg-white p-1.5 rounded border border-slate-100 flex items-center justify-between">
                      <span>Kind: {(item.payload as QueuedEvidencePayload).kind}</span>
                      <span>
                        GPS:{' '}
                        {(item.payload as QueuedEvidencePayload).lat
                          ? '✓ Tagged'
                          : 'No GPS'}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-end pt-1">
                    <button
                      onClick={async () => {
                        if (item.id != null) {
                          await removeSyncItem(item.id);
                          await refreshQueue();
                          toast('Item removed from local outbox.');
                        }
                      }}
                      className="text-[10px] text-rose-700 hover:underline font-bold"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="pt-2 flex gap-2 border-t border-slate-200">
            {queue.length > 0 && (
              <Button
                tone="secondary"
                onClick={async () => {
                  if (confirm('Clear all queued offline items?')) {
                    await clearSyncQueue();
                    await refreshQueue();
                    toast('Outbox cleared.');
                  }
                }}
                className="text-xs"
              >
                Clear All
              </Button>
            )}

            <Button
              onClick={syncQueueNow}
              disabled={isSyncing || queue.length === 0 || !effectiveOnline}
              className="flex-1 justify-center text-xs"
            >
              {isSyncing ? 'Syncing...' : 'Sync Now to Server'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ===================== AUTH MODAL ===================== */}
      <Modal
        open={showAuthModal}
        title="Field Operator Login"
        onClose={() => setShowAuthModal(false)}
      >
        <div className="space-y-3.5 text-xs">
          {hasToken ? (
            <div className="space-y-3 text-center py-2">
              <div className="w-12 h-12 bg-emerald-100 text-emerald-800 rounded-full mx-auto flex items-center justify-center text-xl font-bold">
                ✓
              </div>
              <div>
                <h4 className="font-bold text-slate-900 text-sm">Authenticated Session</h4>
                <p className="text-slate-500 text-[11px] mt-0.5">
                  Your JWT access token is active in localStorage.
                </p>
              </div>
              <Button tone="secondary" onClick={handleLogout} className="w-full justify-center">
                Log Out
              </Button>
            </div>
          ) : (
            <form onSubmit={handleQuickLogin} className="space-y-3">
              <p className="text-slate-600">
                Sign in as Junior Engineer or Contractor to push live updates directly to the Demo
                City registry.
              </p>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Email</label>
                <Input
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  placeholder="je.ward1@demo.city"
                  className="text-xs"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Password</label>
                <Input
                  type="password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  placeholder="demo1234"
                  className="text-xs"
                />
              </div>

              <div className="pt-1 space-y-2">
                <Button
                  type="submit"
                  disabled={authLoading}
                  className="w-full justify-center font-bold"
                >
                  {authLoading ? 'Signing In...' : 'Quick Demo Sign In (JE Ward 1)'}
                </Button>

                <p className="text-center text-[10px] text-slate-400">
                  Or use resident login at{' '}
                  <Link href="/login" className="underline text-teal-800">
                    /login
                  </Link>
                </p>
              </div>
            </form>
          )}
        </div>
      </Modal>
    </div>
  );
}
