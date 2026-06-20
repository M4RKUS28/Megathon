// Progress bridge between the embedded course and the Coursive platform.
// All messages are namespaced with a `coursive:` prefix.

export interface ProgressState {
  status: "in_progress" | "completed";
  progress_pct: number;
  current_chapter: number;
  score?: number | null;
}

const NS = "coursive:";

export function postToHost(type: string, payload: Record<string, unknown> = {}) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({ type: NS + type, ...payload }, "*");
  }
}

export function postProgress(state: ProgressState) {
  postToHost("progress", { ...state });
}

export function announceReady() {
  postToHost("ready");
}

/** Resume support: host may reply to `ready` with a saved state. */
export function onInit(cb: (state: Partial<ProgressState>) => void) {
  window.addEventListener("message", (e) => {
    const data = e.data;
    if (data && typeof data === "object" && data.type === NS + "init") {
      cb(data.state ?? {});
    }
  });
}

/**
 * Edit-loop support: the host can switch the course into "select mode", in which
 * clicking a content block reports its id and text to the host instead of
 * interacting normally.
 */
export function setupSelectMode(onToggle: (enabled: boolean) => void) {
  window.addEventListener("message", (e) => {
    const data = e.data;
    if (data && typeof data === "object" && data.type === NS + "select-mode") {
      onToggle(Boolean(data.enabled));
    }
  });
}

export function reportElementSelected(blockId: string, text: string) {
  postToHost("element-selected", { blockId, text });
}
