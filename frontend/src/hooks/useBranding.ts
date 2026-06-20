import { useQuery } from "@tanstack/react-query";
import { brandingApi } from "@/lib/api";

/** Branding for the current authenticated tenant. */
export function useMyBranding(enabled = true) {
  return useQuery({
    queryKey: ["branding", "mine"],
    queryFn: async () => (await brandingApi.mine()).data,
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

/** Public branding by slug (no auth) — used to theme the shell before login. */
export function usePublicBranding(slug: string | null) {
  return useQuery({
    queryKey: ["branding", "public", slug],
    queryFn: async () => (await brandingApi.public(slug as string)).data,
    enabled: !!slug,
    staleTime: 5 * 60 * 1000,
  });
}
