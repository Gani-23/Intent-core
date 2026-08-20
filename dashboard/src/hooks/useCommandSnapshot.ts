import { useCallback, useEffect, useMemo, useState } from "react";

import { useBackendApi } from "../lib/api";
import type {
  AlertRecord,
  AnalyticsResponse,
  HealthResponse,
  IncidentNarrativeResponse,
  OwnerTeamQueue,
  ReadinessResponse,
  RuntimeReviewQueue,
  TrustScoreResponse,
} from "../lib/types";

type SnapshotState = {
  health: HealthResponse | null;
  readiness: ReadinessResponse | null;
  analytics: AnalyticsResponse | null;
  trust: TrustScoreResponse | null;
  narrative: IncidentNarrativeResponse | null;
  reviews: RuntimeReviewQueue | null;
  ownerQueue: OwnerTeamQueue | null;
  alerts: AlertRecord[];
};

const initialState: SnapshotState = {
  health: null,
  readiness: null,
  analytics: null,
  trust: null,
  narrative: null,
  reviews: null,
  ownerQueue: null,
  alerts: [],
};

export function useCommandSnapshot() {
  const api = useBackendApi();
  const [snapshot, setSnapshot] = useState<SnapshotState>(initialState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    const [health, readiness, analytics, trust, narrative, reviews, ownerQueue, alerts] = await Promise.all([
      api.getHealth(),
      api.getReadiness(),
      api.getAnalytics(14),
      api.getTrustScore(),
      api.getIncidentNarrative(),
      api.getRuntimeReviewQueue(),
      api.getOwnerTeamQueue(),
      api.getAlerts(10),
    ]);
    setSnapshot({ health, readiness, analytics, trust, narrative, reviews, ownerQueue, alerts });
  }, [api]);

  useEffect(() => {
    load()
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.hidden) {
        return;
      }
      load().catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  const runAction = useCallback(
    async (label: string, action: () => Promise<unknown>) => {
      setActionState(`${label}...`);
      setError(null);
      try {
        await action();
        await load();
        setActionState(`${label} done`);
        window.setTimeout(() => setActionState(null), 2200);
      } catch (err) {
        setActionState(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [load],
  );

  return useMemo(
    () => ({
      api,
      snapshot,
      loading,
      error,
      actionState,
      setError,
      load,
      runAction,
    }),
    [actionState, api, error, load, loading, runAction, snapshot],
  );
}
