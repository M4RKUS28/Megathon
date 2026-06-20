import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignmentsApi, learningApi, type ProgressUpdate } from "@/lib/api";

export function useMyLearning() {
  return useQuery({
    queryKey: ["learning"],
    queryFn: async () => (await learningApi.list()).data,
  });
}

export function useLearningCourse(id: string | undefined) {
  return useQuery({
    queryKey: ["learning", id],
    queryFn: async () => (await learningApi.get(id!)).data,
    enabled: !!id,
  });
}

export function useReportProgress(id: string) {
  return useMutation({
    mutationFn: (body: ProgressUpdate) => learningApi.progress(id, body),
  });
}

export function useAssignments(courseId: string | undefined) {
  return useQuery({
    queryKey: ["assignments", courseId],
    queryFn: async () => (await assignmentsApi.list(courseId!)).data,
    enabled: !!courseId,
  });
}

export function useCreateAssignment(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { user_id?: string; department_id?: string; mandatory?: boolean }) =>
      assignmentsApi.create(courseId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assignments", courseId] }),
  });
}

export function useRemoveAssignment(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => assignmentsApi.remove(courseId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assignments", courseId] }),
  });
}

export function useCourseReport(courseId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["report", courseId],
    queryFn: async () => (await assignmentsApi.report(courseId!)).data,
    enabled: !!courseId && enabled,
  });
}
