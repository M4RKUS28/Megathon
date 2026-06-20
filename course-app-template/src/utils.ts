import type { Course } from "./types";

/** Percentage score for a set of answers against a quiz answer key. */
export function scorePct(answerKey: number[], answers: Record<number, number>): number {
  if (answerKey.length === 0) return 100;
  const correct = answerKey.filter((a, i) => answers[i] === a).length;
  return Math.round((correct / answerKey.length) * 100);
}

/** Whether a score passes the chapter gate (default 80%). */
export function hasPassed(score: number, passingPct = 80): boolean {
  return score >= passingPct;
}

/** Validate that a parsed course has the minimum shape to render. */
export function isRenderable(course: Course | null): course is Course {
  return !!course && Array.isArray(course.chapters) && course.chapters.length > 0;
}
