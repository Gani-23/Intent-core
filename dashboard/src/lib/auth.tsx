import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

const STORAGE_KEY = "lsa-dashboard-auth-session";
const OAUTH_BASE_URL = (import.meta.env.VITE_OAUTH_BASE_URL || "https://oauth4-0.onrender.com").replace(/\/$/, "");

export const FEATURE_APPS = {
  adminConsole: "admin-console",
  platform: "lsa-platform",
  reports: "lsa-reports-read",
  targets: "lsa-targets-access",
  reviews: "lsa-reviews-read",
} as const;

export type AuthPermission = "reports" | "targets" | "reviews" | "admin" | "workspace";

export type OAuthSession = {
  accessToken: string;
  username: string;
  role: string;
  apps: string[];
  appId: string | null;
};

type OAuthLoginResponse = {
  success: boolean;
  accessToken: string;
  app_id?: string;
  user: {
    username: string;
    role: string;
    apps?: string[];
    projects?: string[];
  };
};

type OAuthValidateResponse = {
  success: boolean;
  valid: boolean;
  user: {
    username: string;
    role: string;
  };
  apps: string[];
  tokenAppId?: string | null;
};

type AuthContextValue = {
  session: OAuthSession | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  oauthFetch: <T>(path: string, init?: RequestInit) => Promise<T>;
  hasPermission: (permission: AuthPermission) => boolean;
  hasAnySession: boolean;
  isAdmin: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function normalizeApps(apps: string[] | undefined | null) {
  return [...new Set((apps || []).map((item) => String(item || "").trim().toLowerCase()).filter(Boolean))];
}

function buildSession(payload: OAuthLoginResponse | OAuthValidateResponse, accessToken: string): OAuthSession {
  const user = payload.user;
  const embeddedApps = "apps" in user ? (user.apps || user.projects || []) : [];
  const apps = normalizeApps("apps" in payload ? payload.apps : embeddedApps);
  return {
    accessToken,
    username: String(user.username || "").trim().toLowerCase(),
    role: String(user.role || "user").trim().toLowerCase(),
    apps,
    appId: ("app_id" in payload ? payload.app_id : null) || ("tokenAppId" in payload ? payload.tokenAppId : null) || null,
  };
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return JSON.parse(text) as T;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<OAuthSession | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as OAuthSession) : null;
    } catch {
      return null;
    }
  });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!session) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }, [session]);

  const logout = useCallback(() => {
    setSession(null);
  }, []);

  const oauthFetch = useCallback(
    async <T,>(path: string, init: RequestInit = {}) => {
      if (!session?.accessToken) {
        throw new Error("Sign in required.");
      }
      const headers = new Headers(init.headers || {});
      headers.set("Authorization", `Bearer ${session.accessToken}`);
      if (!headers.has("Content-Type") && init.body) {
        headers.set("Content-Type", "application/json");
      }
      const response = await fetch(`${OAUTH_BASE_URL}/api/users${path}`, {
        ...init,
        headers,
      });
      if (response.status === 401) {
        setSession(null);
      }
      return readJson<T>(response);
    },
    [session],
  );

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      if (!session?.accessToken) {
        setReady(true);
        return;
      }
      try {
        const response = await fetch(`${OAUTH_BASE_URL}/api/users/licenses/validate`, {
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
          },
        });
        if (!response.ok) {
          throw new Error("Session expired");
        }
        const payload = await readJson<OAuthValidateResponse>(response);
        if (!cancelled) {
          setSession(buildSession(payload, session.accessToken));
        }
      } catch {
        if (!cancelled) {
          setSession(null);
        }
      } finally {
        if (!cancelled) {
          setReady(true);
        }
      }
    };
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const attempts: Array<{ appId?: string }> = [
      {},
      { appId: FEATURE_APPS.platform },
    ];
    let lastError = "Unable to sign in.";
    for (const attempt of attempts) {
      const response = await fetch(`${OAUTH_BASE_URL}/api/users/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          ...(attempt.appId ? { appId: attempt.appId } : {}),
        }),
      });
      if (response.ok) {
        const payload = await readJson<OAuthLoginResponse>(response);
        setSession(buildSession(payload, payload.accessToken));
        return;
      }
      lastError = (await response.text()) || lastError;
    }
    throw new Error(lastError);
  }, []);

  const hasPermission = useCallback(
    (permission: AuthPermission) => {
      if (!session) {
        return false;
      }
      if (session.role === "admin") {
        return true;
      }
      const apps = new Set(normalizeApps(session.apps));
      if (permission === "admin") {
        return false;
      }
      if (permission === "workspace") {
        return apps.has(FEATURE_APPS.platform);
      }
      if (permission === "reports") {
        return apps.has(FEATURE_APPS.reports);
      }
      if (permission === "targets") {
        return apps.has(FEATURE_APPS.targets);
      }
      if (permission === "reviews") {
        return apps.has(FEATURE_APPS.reviews);
      }
      return false;
    },
    [session],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      ready,
      login,
      logout,
      oauthFetch,
      hasPermission,
      hasAnySession: Boolean(session),
      isAdmin: session?.role === "admin",
    }),
    [session, ready, login, logout, oauthFetch, hasPermission],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("AuthContext missing");
  }
  return value;
}
