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

  const total = quiz.questions.length;
  const correct = quiz.questions.filter((q, i) => answers[i] === q.answerIndex).length;
  const scorePct = total ? Math.round((correct / total) * 100) : 100;
  const passing = quiz.passing_pct || 80;
  const passed = submitted && scorePct >= passing;

  const submit = () => {
    const n = attempts + 1;
    setAttempts(n);
    setSubmitted(true);
    if (total === 0 || scorePct >= passing) onPass(scorePct, n);
  };

  const retry = () => {
    setAnswers({});
    setSubmitted(false);
  };

  return (
    <div className="rounded-2xl border border-black/5 bg-white p-5">
      <h3 className="text-lg font-bold">Knowledge check</h3>
      <p className="mb-4 text-sm text-gray-500">
        You need {passing}% to unlock the next chapter.
      </p>
      <div className="space-y-5">
        {quiz.questions.map((q, qi) => {
          const chosen = answers[qi];
          return (
            <div key={qi}>
              <p className="mb-2 font-medium">{q.question}</p>
              <div className="space-y-2">
                {q.options.map((opt, oi) => {
                  let cls = "border-black/10";
                  if (submitted) {
                    if (oi === q.answerIndex) cls = "border-emerald-500 bg-emerald-50";
                    else if (oi === chosen) cls = "border-red-400 bg-red-50";
                  } else if (chosen === oi) {
                    cls = "border-[var(--brand)] bg-[var(--brand)]/10";
                  }
                  return (
                    <button
                      key={oi}
                      disabled={submitted}
                      onClick={() => setAnswers((a) => ({ ...a, [qi]: oi }))}
                      className={`block w-full rounded-lg border px-3 py-2 text-left text-sm ${cls}`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
              {submitted && q.explanation ? (
                <p className="mt-1.5 text-xs text-gray-500">{q.explanation}</p>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="mt-5 flex items-center gap-3">
        {!submitted ? (
          <button
            onClick={submit}
            disabled={Object.keys(answers).length < total}
            className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
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
                onClick={retry}
                className="rounded-lg border border-black/10 px-3 py-1.5 text-sm font-medium"
              >
                Try again
              </button>
            ) : null}
          </>
        )}
        {attempts > 0 ? (
          <span className="ml-auto text-xs text-gray-400">Attempts: {attempts}</span>
        ) : null}
      </div>
    </div>
  );
}
