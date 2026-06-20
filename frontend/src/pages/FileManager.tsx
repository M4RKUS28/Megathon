import { useRef, useState } from "react";
import { useDeleteFile, useFiles, useUploadFile } from "@/hooks/useFiles";
import { filesApi, type FileRecord } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

export function FileManagerPage() {
  const { data: files, isLoading } = useFiles();
  const upload = useUploadFile();
  const del = useDeleteFile();
  const inputRef = useRef<HTMLInputElement>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    upload.mutate(file);
    e.target.value = "";
  }

  async function handleDownload(record: FileRecord) {
    setDownloading(record.id);
    try {
      const { data } = await filesApi.getDownloadUrl(record.id);
      window.open(data.download_url, "_blank");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Files</h1>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={upload.isPending}
          className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
        >
          {upload.isPending ? "Uploading..." : "Upload file"}
        </button>
        <input ref={inputRef} type="file" className="hidden" onChange={handleFileChange} />
      </div>

      {upload.isError && (
        <div className="rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
          Upload failed. Please try again.
        </div>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}

      {!isLoading && files?.length === 0 && (
        <div className="rounded-xl border border-dashed border-border py-16 text-center text-muted-foreground">
          No files yet. Click "Upload file" to get started.
        </div>
      )}

      <div className="divide-y divide-border rounded-xl border border-border bg-card">
        {files?.map((f) => (
          <div key={f.id} className="flex items-center justify-between px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{f.filename}</p>
              <p className="text-xs text-muted-foreground">
                {formatBytes(f.size_bytes)} &middot; {new Date(f.created_at).toLocaleDateString()}
              </p>
            </div>
            <div className="ml-4 flex shrink-0 gap-2">
              <button
                onClick={() => handleDownload(f)}
                disabled={downloading === f.id}
                className="rounded-md px-3 py-1.5 text-xs text-primary hover:bg-accent disabled:opacity-50"
              >
                {downloading === f.id ? "..." : "Download"}
              </button>
              <button
                onClick={() => del.mutate(f.id)}
                className="rounded-md px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
