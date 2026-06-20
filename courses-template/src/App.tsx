import { useEffect, useMemo, useState } from "react";
import type { Block, Concept } from "./types";
import {
  announceReady,
  onInit,
  postProgress,
  reportElementSelected,
  setupSelectMode,
} from "./progress";

function BlockView({ block, id }: { block: Block; id: string }) {
  switch (block.type) {
    case "heading":
      return <h2 data-block-id={id} style={{ marginTop: 28 }}>{block.text}</h2>;
    case "paragraph":
      return <p data-block-id={id} className="block-p">{block.text}</p>;
    case "list":
      return (
        <ul data-block-id={id} className="block-list">
          {block.items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      );
    case "callout":
      return <div data-block-id={id} className="callout">{block.text}</div>;
    case "code":
      return <pre data-block-id={id} className="code">{block.text}</pre>;
    default:
      return null;
  }
}

export function App() {
  const [concept, setConcept] = useState<Concept | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);
  const [completed, setCompleted] = useState<Set<number>>(new Set());
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [selectMode, setSelectMode] = useState(false);

  useEffect(() => {
    fetch("./concept.json")
      .then((r) => {
        if (!r.ok) throw new Error(`concept.json ${r.status}`);
        return r.json();
      })
      .then((data: Concept) => {
        setConcept(data);
        if (data.primaryColor) {
          document.documentElement.style.setProperty("--brand", data.primaryColor);
        }
        document.title = data.title;
      })
      .catch((e) => setError(String(e)));

    onInit((state) => {
      if (typeof state.current_chapter === "number") setCurrent(state.current_chapter);
    });
    setupSelectMode(setSelectMode);
    announceReady();
  }, []);

  const total = concept?.chapters.length ?? 0;
  const progressPct = total ? Math.round((completed.size / total) * 100) : 0;

  const score = useMemo(() => {
    if (!concept) return 0;
    let correct = 0;
    let asked = 0;
    concept.chapters.forEach((ch, ci) =>
      ch.quiz.forEach((q, qi) => {
        asked += 1;
        if (answers[`${ci}:${qi}`] === q.answerIndex) correct += 1;
      }),
    );
    return asked ? Math.round((correct / asked) * 100) : 0;
  }, [concept, answers]);

  useEffect(() => {
    if (!concept) return;
    const done = completed.size === total && total > 0;
    postProgress({
      status: done ? "completed" : "in_progress",
      progress_pct: progressPct,
      current_chapter: current,
      score: done ? score : null,
    });
  }, [concept, completed, current, progressPct, score, total]);

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

  const allDone = completed.size === total;
  const chapter = concept.chapters[current];

  const handleBlockClick = (blockId: string, text: string) => {
    if (selectMode) reportElementSelected(blockId, text);
  };

  const completeChapter = () => {
    setCompleted((prev) => new Set(prev).add(current));
    if (current < total - 1) setCurrent(current + 1);
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
          {concept.chapters.map((ch, i) => (
            <li key={ch.id}>
              <button
                className={i === current ? "active" : ""}
                onClick={() => setCurrent(i)}
              >
                <span className={`dot${completed.has(i) ? " done" : ""}`}>
                  {completed.has(i) ? "✓" : i + 1}
                </span>
                {ch.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="main">
        {allDone ? (
          <div className="content done-card">
            <p className="eyebrow">Complete</p>
            <h1>{concept.title}</h1>
            <p className="objective">
              You finished every chapter. Final score: <strong>{score}%</strong>.
            </p>
            <button className="btn" onClick={() => setCurrent(0)}>
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
                handleBlockClick(
                  el.getAttribute("data-block-id") || "",
                  el.textContent || "",
                );
              }
            }}
          >
            <p className="eyebrow">
              Chapter {current + 1} of {total}
            </p>
            <h1 data-block-id={`${current}:title`}>{chapter.title}</h1>
            {chapter.objective ? <p className="objective">{chapter.objective}</p> : null}

            {chapter.blocks.map((b, i) => (
              <BlockView key={i} block={b} id={`${current}:block:${i}`} />
            ))}

            {chapter.quiz.length > 0 ? (
              <div className="quiz">
                <h3>Check your understanding</h3>
                {chapter.quiz.map((q, qi) => {
                  const key = `${current}:${qi}`;
                  const chosen = answers[key];
                  return (
                    <div className="q" key={qi}>
                      <strong>{q.question}</strong>
                      {q.options.map((opt, oi) => {
                        let cls = "q-opt";
                        if (chosen !== undefined) {
                          if (oi === q.answerIndex) cls += " correct";
                          else if (oi === chosen) cls += " wrong";
                        }
                        return (
                          <button
                            key={oi}
                            className={cls}
                            disabled={chosen !== undefined}
                            onClick={() => setAnswers((a) => ({ ...a, [key]: oi }))}
                          >
                            {opt}
                          </button>
                        );
                      })}
                      {chosen !== undefined && q.explanation ? (
                        <p className="explain">{q.explanation}</p>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : null}

            <div className="footer-nav">
              <button
                className="btn ghost"
                disabled={current === 0}
                onClick={() => setCurrent(current - 1)}
              >
                Back
              </button>
              <button className="btn" onClick={completeChapter}>
                {current === total - 1 ? "Finish course" : "Mark complete & continue"}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
