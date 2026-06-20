import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { coursesApi, reportingApi, type CourseBriefInput, type CoursePlan } from "@/lib/api";

export function useCourses() {
  return useQuery({
    queryKey: ["courses"],
    queryFn: async () => (await coursesApi.list()).data,
  });
}

export function useCourse(id: string | undefined, poll = false) {
  return useQuery({
    queryKey: ["course", id],
    queryFn: async () => (await coursesApi.get(id!)).data,
    enabled: !!id,
    refetchInterval: poll ? 3000 : false,
  });
}

export function useCourseJobs(id: string | undefined, poll = false) {
  return useQuery({
    queryKey: ["course-jobs", id],
    queryFn: async () => (await coursesApi.jobs(id!)).data,
    enabled: !!id,
    refetchInterval: poll ? 3000 : false,
  });
}

export function useCreateCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description: string; brief: CourseBriefInput }) =>
      coursesApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses"] }),
  });
}

export function useApprovePlan(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (plan?: CoursePlan) => coursesApi.approvePlan(id, plan),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["course", id] });
      qc.invalidateQueries({ queryKey: ["course-jobs", id] });
    },
  });
}

export function useManagerDashboard() {
  return useQuery({
    queryKey: ["manager-dashboard"],
    queryFn: async () => (await reportingApi.managerDashboard()).data,
  });
}

export function useCourseEdits(id: string | undefined, poll = false) {
  return useQuery({
    queryKey: ["course-edits", id],
    queryFn: async () => (await coursesApi.edits.list(id!)).data,
    enabled: !!id,
    refetchInterval: poll ? 3000 : false,
  });
}

export function useCreateEdit(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { prompt: string; target_selector?: string; target_text?: string }) =>
      coursesApi.edits.create(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["course-edits", id] }),
  });
}

export function useAcceptEdit(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (editId: string) => coursesApi.edits.accept(id, editId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["course", id] });
      qc.invalidateQueries({ queryKey: ["course-edits", id] });
    },
  });
}

export function useRejectEdit(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (editId: string) => coursesApi.edits.reject(id, editId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["course-edits", id] }),
  });
}
