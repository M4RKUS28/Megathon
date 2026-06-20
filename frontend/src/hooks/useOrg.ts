import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { departmentApi, peopleApi, type Person } from "@/lib/api";

export function usePeople() {
  return useQuery({
    queryKey: ["people"],
    queryFn: async () => (await peopleApi.list()).data,
  });
}

export function useUpdatePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: { id: string } & Partial<Pick<Person, "role" | "department_id" | "manager_id">>) =>
      peopleApi.update(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["people"] }),
  });
}

export function useDepartments() {
  return useQuery({
    queryKey: ["departments"],
    queryFn: async () => (await departmentApi.list()).data,
  });
}

export function useCreateDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; parent_id?: string | null }) => departmentApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
}

export function useDeleteDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => departmentApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
}
