import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { companyApi } from "@/lib/api";

export function useCompanies() {
  return useQuery({
    queryKey: ["companies"],
    queryFn: async () => (await companyApi.list()).data,
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; slug: string }) => companyApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}
