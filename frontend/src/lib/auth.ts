import Keycloak from "keycloak-js";

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: import.meta.env.VITE_KEYCLOAK_REALM,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
});

let initPromise: Promise<boolean> | null = null;

export async function initKeycloak(): Promise<boolean> {
  if (initPromise) return initPromise;
  initPromise = keycloak.init({
    onLoad: "check-sso",
    silentCheckSsoRedirectUri: window.location.origin + "/silent-check-sso.html",
    pkceMethod: "S256",
  });
  return initPromise;
}

export async function login(redirectUri?: string) {
  await keycloak.login(redirectUri ? { redirectUri } : undefined);
}

export async function register(redirectUri?: string) {
  // Redirects to Keycloak's hosted registration form (requires
  // registrationAllowed=true on the realm).
  await keycloak.register(redirectUri ? { redirectUri } : undefined);
}

export async function logout() {
  await keycloak.logout({ redirectUri: window.location.origin });
}

export function getToken(): string | undefined {
  return keycloak.token;
}

export async function getValidToken(): Promise<string> {
  await keycloak.updateToken(30);
  if (!keycloak.token) throw new Error("Not authenticated");
  return keycloak.token;
}

export function getUserInfo() {
  const p = keycloak.tokenParsed;
  if (!p) return null;
  return {
    id: p.sub as string,
    email: p.email as string,
    username: p.preferred_username as string,
    roles: (p.realm_access?.roles ?? []) as string[],
  };
}

export function isAuthenticated(): boolean {
  return keycloak.authenticated ?? false;
}

export { keycloak };
