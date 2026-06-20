import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef, useState } from "react";
import { useDeleteFile, useFiles, useUploadFile } from "@/hooks/useFiles";
import { filesApi } from "@/lib/api";
import { formatBytes } from "@/lib/utils";
export function FileManagerPage() {
    const { data: files, isLoading } = useFiles();
    const upload = useUploadFile();
    const del = useDeleteFile();
    const inputRef = useRef(null);
    const [downloading, setDownloading] = useState(null);
    function handleFileChange(e) {
        const file = e.target.files?.[0];
        if (!file)
            return;
        upload.mutate(file);
        e.target.value = "";
    }
    async function handleDownload(record) {
        setDownloading(record.id);
        try {
            const { data } = await filesApi.getDownloadUrl(record.id);
            window.open(data.download_url, "_blank");
        }
        finally {
            setDownloading(null);
        }
    }
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h1", { className: "text-2xl font-bold", children: "Files" }), _jsx("button", { onClick: () => inputRef.current?.click(), disabled: upload.isPending, className: "rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50", children: upload.isPending ? "Uploading..." : "Upload file" }), _jsx("input", { ref: inputRef, type: "file", className: "hidden", onChange: handleFileChange })] }), upload.isError && (_jsx("div", { className: "rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive", children: "Upload failed. Please try again." })), isLoading && _jsx("p", { className: "text-sm text-muted-foreground", children: "Loading..." }), !isLoading && files?.length === 0 && (_jsx("div", { className: "rounded-xl border border-dashed border-border py-16 text-center text-muted-foreground", children: "No files yet. Click \"Upload file\" to get started." })), _jsx("div", { className: "divide-y divide-border rounded-xl border border-border bg-card", children: files?.map((f) => (_jsxs("div", { className: "flex items-center justify-between px-4 py-3", children: [_jsxs("div", { className: "min-w-0", children: [_jsx("p", { className: "truncate text-sm font-medium", children: f.filename }), _jsxs("p", { className: "text-xs text-muted-foreground", children: [formatBytes(f.size_bytes), " \u00B7 ", new Date(f.created_at).toLocaleDateString()] })] }), _jsxs("div", { className: "ml-4 flex shrink-0 gap-2", children: [_jsx("button", { onClick: () => handleDownload(f), disabled: downloading === f.id, className: "rounded-md px-3 py-1.5 text-xs text-primary hover:bg-accent disabled:opacity-50", children: downloading === f.id ? "..." : "Download" }), _jsx("button", { onClick: () => del.mutate(f.id), className: "rounded-md px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10", children: "Delete" })] })] }, f.id))) })] }));
}
