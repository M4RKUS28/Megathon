import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, Maximize, Minimize } from "lucide-react";
import { useLearningCourse, useReportProgress } from "@/hooks/useLearning";
import { useFullscreen } from "@/hooks/useFullscreen";

export function CoursePlayerPage() {
  const { id } = useParams<{ id: string }>();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { ref: frameWrapRef, isFullscreen, toggle: toggleFullscreen } =
    useFullscreen<HTMLDivElement>();
  const { data: course } = useLearningCourse(id);
  const reportProgress = useReportProgress(id!);

  const enrollment = course?.enrollment;

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const d = e.data;
      if (!d || typeof d !== "object" || typeof d.type !== "string") return;
      if (!d.type.startsWith("coursive:")) return;

      if (d.type === "coursive:ready") {
        // Send saved progress so the course can resume where the learner left off.
        iframeRef.current?.contentWindow?.postMessage(
          {
            type: "coursive:init",
            state: {
              status: enrollment?.status ?? "not_started",
              progress_pct: enrollment?.progress_pct ?? 0,
              current_chapter: enrollment?.current_chapter ?? 0,
              score: enrollment?.score ?? null,
            },
          },
          "*",
        );
      }

      if (d.type === "coursive:progress") {
        reportProgress.mutate({
          status: d.status,
          progress_pct: d.progress_pct,
          current_chapter: d.current_chapter,
          current_page: d.current_page,
          score: d.score,
          time_spent_seconds: d.time_spent_seconds,
          quiz_attempts: d.quiz_attempts,
          drop_off_point: d.drop_off_point,
          engagement_score: d.engagement_score,
        });
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrollment?.status, enrollment?.progress_pct, id]);

  if (!course) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link
          to="/learn"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> My Learning
        </Link>
        {enrollment ? (
          <span className="text-sm text-muted-foreground">
            {enrollment.status === "completed"
              ? `Completed${enrollment.score != null ? ` · ${enrollment.score}%` : ""}`
              : `${enrollment.progress_pct}% complete`}
          </span>
        ) : null}
      </div>

      <h1 className="text-xl font-bold tracking-tight">{course.title}</h1>

      {course.host_url ? (
        <div ref={frameWrapRef} className="relative bg-background shadow-neu rounded-xl">
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
            className="absolute right-3 top-3 z-10 inline-flex items-center gap-1.5 rounded-lg border border-border bg-background/90 px-3 py-1.5 text-sm font-medium text-muted-foreground shadow-neu-sm backdrop-blur hover:text-foreground"
          >
            {isFullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
            {isFullscreen ? "Exit" : "Fullscreen"}
          </button>
          <iframe
            ref={iframeRef}
            src={course.host_url}
            title={course.title}
            className={`w-full bg-white ${
              isFullscreen ? "h-screen" : "h-[78vh] rounded-xl border border-border"
            }`}
          />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">This course is not available yet.</p>
      )}
    </div>
  );
}
