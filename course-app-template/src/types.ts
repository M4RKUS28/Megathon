export interface Block {
  type: string;
  text?: string;
  items?: string[];
  asset?: string;
  data?: Record<string, unknown>;
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

export type AssetMap = Record<string, string>;
