// Bridge that reports learner progress to the embedding platform via postMessage.

export interface ProgressState {
  status?: string;
  progress_pct?: number;
  current_chapter?: number;
  current_page?: number;
  score?: number;
  quiz_attempts?: number;
}

export function postProgress(state: ProgressState): void {
  try {
    window.parent?.postMessage({ type: "coursive:progress", ...state }, "*");
  } catch {
    /* embedding may be cross-origin without a parent listener */
  }
}

export function announceReady(): void {
  try {
    window.parent?.postMessage({ type: "coursive:ready" }, "*");
  } catch {
    /* no-op */
  }
}
