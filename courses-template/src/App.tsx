import { useEffect, useMemo, useState } from "react";
import type { Concept, NormChapter, QuizQuestion } from "./types";
import { BlockView } from "./blocks";
import {
  announceReady,
  onInit,
  postProgress,
  reportElementSelected,
  setupSelectMode,
} from "./progress";

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function normalize(concept: Concept): NormChapter[] {
  return concept.chapters.map((ch) => ({
    ...ch,
    pages: ch.pages && ch.pages.length ? ch.pages : [{ blocks: ch.blocks || [] }],
  }));
}

/** End-of-chapter quiz with an 80% gate and unlimited retries (options reshuffle
 * on each attempt). Calls `onPass` with the score once the threshold is met. */
function ChapterQuiz({
  quiz,
  passingScore,
  onPass,
  chapterIndex,
}: {
  quiz: QuizQuestion[];
  passingScore: number;
  onPass: (score: number) => void;
  chapterIndex: number;
}) {
  const [attempt, setAttempt] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);

  // Reset when the chapter changes.
  useEffect(() => {
    setAttempt(0);
    setAnswers({});
    setSubmitted(false);
  }, [chapterIndex]);

  // Shuffle option order per attempt while tracking the original index.
  const shuffled = useMemo(
    () =>
      quiz.map((q) => ({
        q,
        opts: shuffle(q.options.map((text, originalIndex) => ({ text, originalIndex }))),
      })),
    [quiz, attempt],
  );

  const answered = Object.keys(answers).length === quiz.length;
  const score = useMemo(() => {
    if (!quiz.length) return 100;
    let correct = 0;
    quiz.forEach((q, i) => {
      if (answers[i] === q.answerIndex) correct += 1;
    });
    return Math.round((correct / quiz.length) * 100);
  }, [answers, quiz]);

  const passed = submitted && score >= passingScore;
  const failed = submitted && score < passingScore;

  const retry = () => {
    setAttempt((a) => a + 1);
    setAnswers({});
    setSubmitted(false);
  };

  return (
    <div className="quiz">
      <div className="quiz-head">
        <h3>Chapter checkpoint</h3>
        <span className="quiz-gate">Pass {passingScore}% to continue</span>
      </div>
      {shuffled.map(({ q, opts }, qi) => {
        const chosen = answers[qi];
        return (
          <div className="q" key={qi}>
            <strong>{q.question}</strong>
            <div className="q-opts">
              {opts.map((opt, oi) => {
                let cls = "q-opt";
                if (submitted) {
                  if (opt.originalIndex === q.answerIndex) cls += " correct";
                  else if (opt.originalIndex === chosen) cls += " wrong";
                } else if (chosen === opt.originalIndex) {
                  cls += " selected";
                }
                return (
                  <button
                    key={oi}
                    className={cls}
                    disabled={submitted}
                    onClick={() => setAnswers((a) => ({ ...a, [qi]: opt.originalIndex }))}
                  >
                    {opt.text}
                  </button>
                );
              })}
            </div>
            {submitted && q.explanation ? <p className="explain">{q.explanation}</p> : null}
          </div>
        );
      })}

      {!submitted ? (
        <button className="btn" disabled={!answered} onClick={() => setSubmitted(true)}>
          Submit answers
        </button>
      ) : null}

      {passed ? (
        <div className="quiz-result pass">
          <span>You scored {score}% — chapter unlocked! ✓</span>
          <button className="btn" onClick={() => onPass(score)}>
            Continue ›
          </button>
        </div>
      ) : null}

      {failed ? (
        <div className="quiz-result fail">
          <span>
            You scored {score}%. You need {passingScore}% — review and try again.
          </span>
          <button className="btn" onClick={retry}>
            Try again ↻
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function App() {
  const [concept, setConcept] = useState<Concept | null>(null);
  const [chapters, setChapters] = useState<NormChapter[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [current, setCurrent] = useState(0); // chapter index
  const [page, setPage] = useState(0); // page index within chapter
  const [onQuiz, setOnQuiz] = useState(false);
  const [unlocked, setUnlocked] = useState(0); // highest unlocked chapter
  const [completed, setCompleted] = useState<Set<number>>(new Set());
  const [scores, setScores] = useState<Record<number, number>>({});
  const [selectMode, setSelectMode] = useState(false);

  useEffect(() => {
    fetch("./concept.json")
      .then((r) => {
        if (!r.ok) throw new Error(`concept.json ${r.status}`);
        return r.json();
      })
      .then((data: Concept) => {
        setConcept(data);
        setChapters(normalize(data));
        if (data.primaryColor) {
          document.documentElement.style.setProperty("--brand", data.primaryColor);
        }
        document.title = data.title;
      })
      .catch((e) => setError(String(e)));

    onInit((state) => {
      if (typeof state.current_chapter === "number") {
        setCurrent(state.current_chapter);
        setUnlocked((u) => Math.max(u, state.current_chapter ?? 0));
      }
    });
    setupSelectMode(setSelectMode);
    announceReady();
  }, []);

  const total = chapters.length;
  const allDone = total > 0 && completed.size === total;
  const progressPct = total ? Math.round((completed.size / total) * 100) : 0;
  const avgScore = useMemo(() => {
    const vals = Object.values(scores);
    return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0;
  }, [scores]);

  useEffect(() => {
    if (!concept) return;
    postProgress({
      status: allDone ? "completed" : "in_progress",
      progress_pct: progressPct,
      current_chapter: current,
      score: allDone ? avgScore : null,
    });
  }, [concept, completed, current, progressPct, avgScore, allDone]);

  if (error) {
    return (
      <div className="done-card">
        <h1>Course unavailable</h1>
        <p style={{ color: "var(--muted)" }}>This course is still being prepared. ({error})</p>
      </div>
    );
  }
  if (!concept) {
    return <div className="done-card"><p>Loading course…</p></div>;
  }

  const chapter = chapters[current];
  const pages = chapter.pages;
  const lastPage = page >= pages.length - 1;

  const goChapter = (i: number) => {
    if (i > unlocked) return;
    setCurrent(i);
    setPage(0);
    setOnQuiz(false);
  };

  const nextPage = () => {
    if (!lastPage) setPage((p) => p + 1);
    else setOnQuiz(true);
  };

  const onQuizPass = (score: number) => {
    setScores((s) => ({ ...s, [current]: score }));
    setCompleted((prev) => new Set(prev).add(current));
    const next = current + 1;
    setUnlocked((u) => Math.max(u, Math.min(next, total - 1)));
    if (next < total) {
      setCurrent(next);
      setPage(0);
      setOnQuiz(false);
    } else {
      setOnQuiz(false);
    }
  };

  return (
    <div className={`app${selectMode ? " select-mode" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-badge">{(concept.companyName || "C").charAt(0)}</span>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{concept.companyName || "Course"}</div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>Coursive</div>
          </div>
        </div>
        <div className="progress-rail">
          <div className="progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <ul className="chapter-nav">
          {chapters.map((ch, i) => {
            const locked = i > unlocked;
            return (
              <li key={ch.id}>
                <button
                  className={`${i === current ? "active" : ""}${locked ? " locked" : ""}`}
                  onClick={() => goChapter(i)}
                  disabled={locked}
                >
                  <span className={`dot${completed.has(i) ? " done" : ""}`}>
                    {completed.has(i) ? "✓" : locked ? "🔒" : i + 1}
                  </span>
                  {ch.title}
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      <main className="main">
        {allDone ? (
          <div className="content done-card">
            <p className="eyebrow">Complete</p>
            <h1>{concept.title}</h1>
            <p className="objective">
              You finished every chapter. Average quiz score: <strong>{avgScore}%</strong>.
            </p>
            <button className="btn" onClick={() => { setCurrent(0); setPage(0); setOnQuiz(false); }}>
              Review from start
            </button>
          </div>
        ) : (
          <div
            className="content"
            onClickCapture={(e) => {
              if (!selectMode) return;
              const el = (e.target as HTMLElement).closest("[data-block-id]");
              if (el) {
                e.preventDefault();
                e.stopPropagation();
                reportElementSelected(
                  el.getAttribute("data-block-id") || "",
                  el.textContent || "",
                );
              }
            }}
          >
            <p className="eyebrow">
              Chapter {current + 1} of {total}
              {!onQuiz ? ` · Page ${page + 1} of ${pages.length}` : " · Checkpoint"}
            </p>
            <h1 data-block-id={`${current}:title`}>{chapter.title}</h1>
            {chapter.objective && page === 0 && !onQuiz ? (
              <p className="objective">{chapter.objective}</p>
            ) : null}

            {!onQuiz ? (
              <>
                {pages[page].title ? <h2 className="page-title">{pages[page].title}</h2> : null}
                {pages[page].blocks.map((b, i) => (
                  <BlockView key={`${current}:${page}:${i}`} block={b} id={`${current}:${page}:${i}`} />
                ))}
                <div className="footer-nav">
                  <button
                    className="btn ghost"
                    disabled={page === 0}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                  >
                    Back
                  </button>
                  <button className="btn" onClick={nextPage}>
                    {lastPage ? "Take the checkpoint ›" : "Continue ›"}
                  </button>
                </div>
              </>
            ) : (
              <ChapterQuiz
                key={current}
                chapterIndex={current}
                quiz={chapter.quiz}
                passingScore={chapter.passingScore || 80}
                onPass={onQuizPass}
              />
            )}
          </div>
        )}
      </main>
    </div>
  );
}
