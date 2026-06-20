import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { filesApi, uploadFileDirect } from "@/lib/api";
export function useFiles() {
    return useQuery({
        queryKey: ["files"],
        queryFn: async () => {
            const { data } = await filesApi.list();
            return data.items;
        },
    });
}
export function useUploadFile() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (file) => uploadFileDirect(file),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["files"] }),
    });
}
export function useDeleteFile() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (id) => filesApi.delete(id),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["files"] }),
    });
}
export function useDownloadUrl(fileId) {
    return useQuery({
        queryKey: ["download-url", fileId],
        queryFn: async () => {
            const { data } = await filesApi.getDownloadUrl(fileId);
            return data.download_url;
        },
        enabled: !!fileId,
        staleTime: 0,
    });
}
