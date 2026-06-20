export type Block =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "callout"; text: string }
  | { type: "code"; text: string };

export interface QuizQuestion {
  question: string;
  options: string[];
  answerIndex: number;
  explanation?: string;
}

export interface Chapter {
  id: string;
  title: string;
  objective?: string;
  blocks: Block[];
  quiz: QuizQuestion[];
}

export interface Concept {
  title: string;
  description: string;
  companyName?: string;
  primaryColor?: string;
  chapters: Chapter[];
}
