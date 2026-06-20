export interface Block {
  type: string;
  text?: string;
  items?: string[];
  asset?: string;
  data?: Record<string, unknown>;
}

// `conversation` block payload (data). Avatars come from the local cartoon
// library keyed by `avatar` (e.g. "f-2"/"m-5"), or an asset link to a real image.
export interface Persona {
  id?: string;
  name?: string;
  role?: string;
  side?: "left" | "right";
  avatar?: string;
}

export interface ConversationTurn {
  persona?: string; // persona id
  speaker?: string; // legacy `dialogue` shape
  text?: string;
  audio?: string; // per-bubble TTS asset link
}

export interface Page {
  id: string;
  title?: string;
  blocks: Block[];
}

export interface QuizQuestion {
  question: string;
  options: string[];
  answerIndex: number;
  explanation?: string;
}

export interface Quiz {
  passing_pct: number;
  retryable: boolean;
  questions: QuizQuestion[];
}

export interface Chapter {
  id: string;
  title: string;
  objective?: string;
  pages: Page[];
  quiz: Quiz;
}

export interface Course {
  title: string;
  description?: string;
  companyName?: string;
  primaryColor?: string;
  language?: string;
  passing_pct?: number;
  chapters: Chapter[];
}

// ── New interactive block data shapes ─────────────────────────────────────────

export interface MatchingGameData {
  pairs: { term: string; definition: string }[];
}

export interface SortingChallengeData {
  prompt: string;
  items: string[];
  correctOrder: number[];
}

export interface FillInBlankData {
  sentences: {
    text: string;
    blanks: { position: number; answer: string; options: string[] }[];
  }[];
}

export interface WordCloudData {
  words: { text: string; weight: number }[];
}

export type AssetMap = Record<string, string>;
