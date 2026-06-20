import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { AssetMap, Course } from "./types";
import { BlockView } from "./blocks";
import { QuizView } from "./quiz";
import { announceReady, postProgress } from "./progress";

export function App() {
  const [course, setCourse] = useState<Course | null>(null);
  const [assetMap, setAssetMap] = useState<AssetMap>({});
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);
  const [unlocked, setUnlocked] = useState(1);
  const [passed, setPassed] = useState<Set<number>>(new Set());
  const [scores, setScores] = useState<Record<number, number>>({});
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    Promise.all([
      fetch("./course.json").then((r) => {
        if (!r.ok) throw new Error(`course.json ${r.status}`);
        return r.json();
      }),
      fetch("./asset_map.json")
        .then((r) => (r.ok ? r.json() : {}))
        .catch(() => ({})),
    ])
      .then(([c, m]: [Course, AssetMap]) => {
        setCourse(c);
        setAssetMap(m ?? {});
        if (c.primaryColor) document.documentElement.style.setProperty("--brand", c.primaryColor);
        document.title = c.title;
      })
      .catch((e) => setError(String(e)));
    announceReady();
  }, []);

  const total = course?.chapters.length ?? 0;
  const progressPct = total ? Math.round((passed.size / total) * 100) : 0;

  const resolve = useMemo(
    () => (link?: string) => (link ? assetMap[link] ?? link : undefined),
    [assetMap],
  );

  useEffect(() => {
    if (!course) return;
    const done = passed.size === total && total > 0;
    const avg = Object.values(scores);
    postProgress({
      status: done ? "completed" : "in_progress",
      progress_pct: progressPct,
      current_chapter: current,
      score: avg.length ? Math.round(avg.reduce((a, b) => a + b, 0) / avg.length) : undefined,
      quiz_attempts: attempts,
    });
  }, [course, passed, current, progressPct, scores, attempts, total]);

  if (error)
    return (
      <div className="grid h-full place-items-center p-8 text-center">
        <div>
          <h1 className="text-xl font-bold">Course unavailable</h1>
          <p className="mt-2 text-sm text-gray-500">It is still being prepared. ({error})</p>
        </div>
      </div>
    );
  if (!course) return <div className="grid h-full place-items-center">Loading course…</div>;

  const chapter = course.chapters[current];
  const allDone = passed.size === total;

  const onPass = (scorePct: number, n: number) => {
    setPassed((p) => new Set(p).add(current));
    setScores((s) => ({ ...s, [current]: scorePct }));
    setAttempts((a) => a + n);
    setUnlocked((u) => Math.max(u, current + 2));
  };

  return (
    <div className="mx-auto flex min-h-full max-w-6xl gap-6 p-4 md:p-6">
      <aside className="hidden w-64 shrink-0 md:block">
        <div className="sticky top-6 space-y-4">
          <div>
            <div className="text-sm font-semibold">{course.companyName ?? "Course"}</div>
            <div className="text-[11px] uppercase tracking-wide text-gray-400">Coursive</div>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-[var(--brand)] transition-all"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <nav className="space-y-1">
            {course.chapters.map((ch, i) => {
              const locked = i >= unlocked;
              return (
                <button
                  key={ch.id}
                  disabled={locked}
                  onClick={() => setCurrent(i)}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm ${
                    i === current ? "bg-[var(--brand)]/10 font-medium" : "hover:bg-black/5"
                  } ${locked ? "opacity-40" : ""}`}
                >
                  <span
                    className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] ${
                      passed.has(i) ? "bg-emerald-500 text-white" : "bg-gray-200"
                    }`}
                  >
                    {passed.has(i) ? "✓" : locked ? "🔒" : i + 1}
                  </span>
                  <span className="truncate">{ch.title}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        {allDone ? (
          <div className="grid h-full place-items-center rounded-2xl border border-black/5 bg-white p-10 text-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">
                Complete
              </p>
              <h1 className="mt-1 text-2xl font-bold">{course.title}</h1>
              <p className="mt-2 text-gray-500">
                You passed every chapter. Average score:{" "}
                <strong>
                  {Math.round(
                    Object.values(scores).reduce((a, b) => a + b, 0) /
                      Math.max(1, Object.values(scores).length),
                  )}
                  %
                </strong>
                .
              </p>
              <button
                onClick={() => setCurrent(0)}
                className="mt-4 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white"
              >
                Review from start
              </button>
            </div>
          </div>
        ) : (
          <motion.div
            key={current}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-5"
          >
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">
                Chapter {current + 1} of {total}
              </p>
              <h1 className="mt-1 text-2xl font-bold">{chapter.title}</h1>
              {chapter.objective ? <p className="mt-1 text-gray-500">{chapter.objective}</p> : null}
            </div>

            {chapter.pages.map((page) => (
              <section key={page.id} className="space-y-4">
                {page.blocks.map((b, i) => (
                  <BlockView key={i} block={b} resolve={resolve} />
                ))}
              </section>
            ))}

            <QuizView quiz={chapter.quiz} onPass={onPass} />

            <div className="flex items-center justify-between pt-2">
              <button
                disabled={current === 0}
                onClick={() => setCurrent(current - 1)}
                className="rounded-lg border border-black/10 px-4 py-2 text-sm font-medium disabled:opacity-40"
              >
                Back
              </button>
              <button
                disabled={!passed.has(current) || current >= total - 1}
                onClick={() => setCurrent(current + 1)}
                className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
              >
                Next chapter
              </button>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}
