export type Block =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "callout"; text: string; variant?: string }
  | { type: "code"; text: string; language?: string }
  | { type: "image"; url?: string; prompt?: string; alt?: string; caption?: string }
  | { type: "video"; url?: string; poster?: string; prompt?: string; caption?: string }
  | { type: "audio"; url?: string; say?: string; caption?: string }
  | {
      type: "dialogue";
      title?: string;
      speakers: DialogueSpeaker[];
      steps: DialogueStep[];
    }
  | { type: "dragdrop"; instructions?: string; pairs: DragPair[] }
  | { type: "ordering"; instructions?: string; items: string[] }
  | { type: "hotspot"; instructions?: string; imageUrl?: string; imagePrompt?: string; spots: Hotspot[] }
  | { type: "flipcards"; title?: string; cards: FlipCard[] }
  | { type: "chart"; title?: string; chartType?: string; labels: string[]; series: ChartSeries[] };

export interface DialogueSpeaker {
  name: string;
  role?: string;
  avatarPrompt?: string;
  avatarUrl?: string;
}

export interface DialogueStep {
  speaker: string;
  text: string;
}

export interface DragPair {
  term: string;
  match: string;
}

export interface Hotspot {
  x: number;
  y: number;
  label: string;
  text: string;
}

export interface FlipCard {
  front: string;
  back: string;
}

export interface ChartSeries {
  label: string;
  data: number[];
}

export interface QuizQuestion {
  question: string;
  options: string[];
  answerIndex: number;
  explanation?: string;
}

export interface Page {
  id?: string;
  title?: string;
  blocks: Block[];
}

export interface Chapter {
  id: string;
  title: string;
  objective?: string;
  passingScore?: number;
  pages?: Page[];
  /** Legacy (v1) flat block list — normalized into a single page at load. */
  blocks?: Block[];
  quiz: QuizQuestion[];
}

export interface Concept {
  title: string;
  description: string;
  companyName?: string;
  primaryColor?: string;
  chapters: Chapter[];
}

/** A chapter guaranteed to have `pages` (after normalization). */
export interface NormChapter extends Chapter {
  pages: Page[];
}
