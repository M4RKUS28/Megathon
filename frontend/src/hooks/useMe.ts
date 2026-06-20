import { useQuery } from "@tanstack/react-query";
import { meApi } from "@/lib/api";

export function useMe(enabled = true) {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => (await meApi.get()).data,
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}
