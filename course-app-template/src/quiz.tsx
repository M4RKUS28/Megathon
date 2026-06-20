import { useState } from "react";
import type { Quiz } from "./types";

export function QuizView({
  quiz,
  onPass,
}: {
  quiz: Quiz;
  onPass: (scorePct: number, attempts: number) => void;
}) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [active, setActive] = useState(0);

  const total = quiz.questions.length;
  const correct = quiz.questions.filter((q, i) => answers[i] === q.answerIndex).length;
  const scorePct = total ? Math.round((correct / total) * 100) : 100;
  const passing = quiz.passing_pct || 80;
  const passed = submitted && scorePct >= passing;
  const current = quiz.questions[active];
  const answered = Object.keys(answers).length;

  const submit = () => {
    const n = attempts + 1;
    setAttempts(n);
    setSubmitted(true);
    if (total === 0 || scorePct >= passing) onPass(scorePct, n);
  };

  const retry = () => {
    setAnswers({});
    setSubmitted(false);
    setActive(0);
  };

  return (
    <div className="rounded-2xl border border-black/5 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold">Knowledge check</h3>
          <p className="text-sm text-gray-500">You need {passing}% to unlock the next chapter.</p>
        </div>
        <div className="rounded-lg bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-500">
          {answered}/{total} answered
        </div>
      </div>

      <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
        {quiz.questions.map((q, qi) => {
          const hasAnswer = answers[qi] !== undefined;
          const isActive = qi === active;
          const isCorrect = submitted && answers[qi] === q.answerIndex;
          const isWrong = submitted && hasAnswer && !isCorrect;
          return (
            <button
              key={qi}
              type="button"
              onClick={() => setActive(qi)}
              className={`flex h-9 min-w-9 items-center justify-center rounded-lg border px-3 text-sm font-semibold transition ${
                isActive
                  ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                  : isCorrect
                    ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                    : isWrong
                      ? "border-red-400 bg-red-50 text-red-700"
                      : hasAnswer
                        ? "border-[var(--brand)]/40 bg-[var(--brand)]/10 text-[var(--brand)]"
                        : "border-black/10 bg-white text-gray-500"
              }`}
              aria-label={`Question ${qi + 1}${hasAnswer ? ", answered" : ""}`}
            >
              {qi + 1}
            </button>
          );
        })}
      </div>

      {current ? (
        <div className="mt-5 rounded-xl border border-black/5 bg-gray-50 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">
              Question {active + 1} of {total}
            </p>
          </div>
          <p className="mb-3 font-medium">{current.question}</p>
          <div className="space-y-2">
            {current.options.map((opt, oi) => {
              const chosen = answers[active];
              let cls = "border-black/10 bg-white";
              if (submitted) {
                if (oi === current.answerIndex) cls = "border-emerald-500 bg-emerald-50";
                else if (oi === chosen) cls = "border-red-400 bg-red-50";
              } else if (chosen === oi) {
                cls = "border-[var(--brand)] bg-[var(--brand)]/10";
              }
              return (
                <button
                  key={oi}
                  type="button"
                  disabled={submitted}
                  onClick={() => setAnswers((a) => ({ ...a, [active]: oi }))}
                  className={`block w-full rounded-lg border px-3 py-2 text-left text-sm ${cls}`}
                >
                  {opt}
                </button>
              );
            })}
          </div>
          {submitted && current.explanation ? (
            <p className="mt-3 rounded-lg bg-white p-2 text-xs text-gray-500">
              {current.explanation}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="mt-5 rounded-xl border border-black/5 bg-gray-50 p-4 text-sm text-gray-500">
          This quiz has no questions.
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={active === 0}
          onClick={() => setActive((i) => Math.max(0, i - 1))}
          className="rounded-lg border border-black/10 px-3 py-1.5 text-sm font-medium disabled:opacity-40"
        >
          Previous question
        </button>
        {active < total - 1 ? (
          <button
            type="button"
            onClick={() => setActive((i) => Math.min(total - 1, i + 1))}
            className="rounded-lg border border-black/10 px-3 py-1.5 text-sm font-medium"
          >
            Next question
          </button>
        ) : null}
        {!submitted ? (
          <button
            type="button"
            onClick={submit}
            disabled={answered < total}
            className="ml-auto rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Submit
          </button>
        ) : passed ? (
          <span className="text-sm font-medium text-emerald-600">Passed — {scorePct}%</span>
        ) : (
          <>
            <span className="text-sm font-medium text-red-600">
              {scorePct}% — below {passing}%.
            </span>
            {quiz.retryable ? (
              <button
                type="button"
                onClick={retry}
                className="rounded-lg border border-black/10 px-3 py-1.5 text-sm font-medium"
              >
                Try again
              </button>
            ) : null}
          </>
        )}
        {attempts > 0 ? (
          <span className="text-xs text-gray-400">Attempts: {attempts}</span>
        ) : null}
      </div>
    </div>
  );
}
