import axios from "axios";

const isNativePlatform = typeof window !== "undefined" && (
  window.Capacitor?.isNativePlatform?.() ||
  window.location?.protocol === "capacitor:" ||
  (window.location?.protocol === "https:" && window.location?.hostname === "localhost" && !window.location?.port)
);

export const renderProductionUrl = import.meta.env.VITE_API_URL || "https://jwl-whatsapp-crm.onrender.com";

export function getApiBaseUrl() {
  return localStorage.getItem("mg_custom_api_url") ||
    import.meta.env.VITE_API_URL ||
    (isNativePlatform ? renderProductionUrl : "");
}

const api = axios.create({ baseURL: getApiBaseUrl() });

export function setApiBaseUrl(url) {
  api.defaults.baseURL = url;
  axios.defaults.baseURL = url;
}

// Automatically attach Bearer token to every outbound request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Also attach to global axios instance for legacy calls
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// In-flight refresh promise to prevent duplicate concurrent refresh calls
let refreshPromise = null;

export async function silentRefreshToken() {
  const currentToken = localStorage.getItem("token");
  if (!currentToken) {
    return null;
  }

  if (refreshPromise) {
    return refreshPromise;
  }

  const baseUrl = getApiBaseUrl();
  const refreshUrl = `${baseUrl.replace(/\/+$/, "")}/api/auth/refresh`;

  refreshPromise = axios
    .post(
      refreshUrl,
      {},
      {
        withCredentials: true,
        headers: {
          Authorization: `Bearer ${currentToken}`,
        },
      }
    )
    .then((res) => {
      const newToken = res.data?.access_token;
      if (newToken) {
        localStorage.setItem("token", newToken);
        api.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
        axios.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
        window.dispatchEvent(
          new CustomEvent("auth:token-updated", { detail: { token: newToken } })
        );
        return newToken;
      }
      return null;
    })
    .catch((err) => {
      const status = err.response?.status;
      if (status === 401 || status === 400) {
        localStorage.removeItem("token");
        localStorage.removeItem("username");
        delete api.defaults.headers.common["Authorization"];
        delete axios.defaults.headers.common["Authorization"];
        window.dispatchEvent(new Event("auth:unauthorized"));
      }
      throw err;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

// Proactive refresh timer: refresh every 12 minutes (720,000 ms) while logged in
if (typeof window !== "undefined") {
  setInterval(() => {
    if (localStorage.getItem("token")) {
      silentRefreshToken().catch(() => {
        // Handled in catch block of silentRefreshToken
      });
    }
  }, 12 * 60 * 1000);

  // When tab becomes visible again after sleep/background, refresh token proactively
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && localStorage.getItem("token")) {
      silentRefreshToken().catch(() => {});
    }
  });
}

function handle401Response(error, axiosInstance) {
  const originalRequest = error.config;
  if (!error.response || error.response.status !== 401 || !originalRequest) {
    return Promise.reject(error);
  }

  const url = originalRequest.url || "";
  // Do not attempt refresh on login, register, or refresh endpoints
  if (
    url.includes("/api/auth/token") ||
    url.includes("/api/auth/login") ||
    url.includes("/api/auth/register") ||
    url.includes("/api/auth/refresh")
  ) {
    return Promise.reject(error);
  }

  if (originalRequest._retry) {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    delete api.defaults.headers.common["Authorization"];
    delete axios.defaults.headers.common["Authorization"];
    window.dispatchEvent(new Event("auth:unauthorized"));
    return Promise.reject(error);
  }

  originalRequest._retry = true;

  return silentRefreshToken()
    .then((newToken) => {
      if (newToken) {
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return axiosInstance(originalRequest);
      }
      return Promise.reject(error);
    })
    .catch((refreshErr) => {
      return Promise.reject(refreshErr);
    });
}

api.interceptors.response.use(
  (response) => response,
  (error) => handle401Response(error, api)
);

axios.interceptors.response.use(
  (response) => response,
  (error) => handle401Response(error, axios)
);

export default api;
