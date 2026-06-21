import { type ReactNode, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Bar, Line, Pie } from "react-chartjs-2";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import type {
  Block,
  ConversationTurn,
  FillInBlankData,
  MatchingGameData,
  MinigameData,
  MinigamePair,
  MinigameQuestion,
  MinigameSortItem,
  Persona,
  SortingChallengeData,
  WordCloudData,
} from "./types";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Tooltip,
  Legend,
);

type Resolve = (link?: string) => string | undefined;

/** Parse inline markdown bold (`**text**`) into React nodes. */
function renderInlineMarkdown(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/);
  if (parts.length === 1) return text;
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function MediaImage({ src, alt }: { src?: string; alt?: string }) {
  if (!src) return null;
  return (
    <motion.img
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      src={src}
      alt={alt ?? ""}
      className="w-full rounded-xl border border-black/5 shadow-sm"
    />
  );
}

// â”€â”€ Conversation (avatars left/right, click-through bubbles, per-bubble TTS) â”€â”€

// Local "cartoon avatar library": a parametric flat-illustration person, drawn
// deterministically from a seed string so each persona keeps the same face. A
// persona `avatar` like "f-2"/"m-5" is the seed; a "/..." or "http..." value is
// treated as a real image instead.
const SKIN = ["#F8D2B0", "#F0C09A", "#E0A878", "#C68A5E", "#9C6B43", "#6F4A2E"];
const HAIR = ["#2B1B12", "#5A3825", "#8A5A2B", "#C99B4B", "#9AA0A6", "#1F2937", "#D14B3D", "#E6E0D4"];
const SHIRT = ["#5145E5", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4", "#8b5cf6", "#ec4899", "#0ea5e9"];

function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function isAssetRef(v?: string): boolean {
  return !!v && (v.startsWith("/") || v.startsWith("http"));
}

function speakWithBrowser(text?: string): boolean {
  if (!text || typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = document.documentElement.lang || navigator.language || "en";
  utterance.rate = 1;
  window.speechSynthesis.speak(utterance);
  return true;
}

function HairStyle({ kind, hair }: { kind: number; hair: string }) {
  // A crown/cap that covers the forehead, plus per-style extras.
  const cap = "M27,42 Q27,16 50,16 Q73,16 73,42 Q73,28 50,28 Q27,28 27,42 Z";
  switch (kind) {
    case 1: // long: side panels down to the shoulders
      return (
        <>
          <rect x="26" y="34" width="9" height="34" rx="4" fill={hair} />
          <rect x="65" y="34" width="9" height="34" rx="4" fill={hair} />
          <path d={cap} fill={hair} />
        </>
      );
    case 2: // bun on top
      return (
        <>
          <circle cx="50" cy="14" r="7" fill={hair} />
          <path d={cap} fill={hair} />
        </>
      );
    case 3: // short / buzz: thinner cap
      return <path d="M29,40 Q29,22 50,22 Q71,22 71,40 Q71,31 50,31 Q29,31 29,40 Z" fill={hair} />;
    default: // tidy short
      return <path d={cap} fill={hair} />;
  }
}

function Avatar({ seed, size = 56 }: { seed: string; size?: number }) {
  const clip = useId();
  const h = hashSeed(seed || "x");
  const skin = SKIN[h % SKIN.length];
  const hair = HAIR[(h >> 3) % HAIR.length];
  const shirt = SHIRT[(h >> 6) % SHIRT.length];
  const style = (h >> 9) % 4;
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label="avatar">
      <defs>
        <clipPath id={clip}>
          <circle cx="50" cy="50" r="50" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clip})`}>
        <rect width="100" height="100" fill="#eef2f7" />
        <path d="M12,100 Q14,68 50,68 Q86,68 88,100 Z" fill={shirt} />
        <rect x="44" y="56" width="12" height="14" rx="5" fill={skin} />
        <circle cx="50" cy="40" r="22" fill={skin} />
        <HairStyle kind={style} hair={hair} />
        <circle cx="42.5" cy="41" r="2.1" fill="#1f2937" />
        <circle cx="57.5" cy="41" r="2.1" fill="#1f2937" />
        <path
          d="M43,48 Q50,53 57,48"
          stroke="#1f2937"
          strokeWidth="1.7"
          fill="none"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
}

function PersonaAvatar({
  persona,
  size,
  resolve,
}: {
  persona?: Persona;
  size: number;
  resolve: Resolve;
}) {
  const av = persona?.avatar;
  if (isAssetRef(av)) {
    const src = resolve(av);
    if (src)
      return (
        <img
          src={src}
          alt={persona?.name ?? ""}
          style={{ width: size, height: size }}
          className="rounded-full object-cover"
        />
      );
  }
  return <Avatar seed={av || persona?.id || persona?.name || "x"} size={size} />;
}

function PersonaStage({
  persona,
  active,
  resolve,
}: {
  persona?: Persona;
  active: boolean;
  resolve: Resolve;
}) {
  return (
    <div
      className={`flex flex-col items-center text-center transition-all duration-300 ${
        active ? "opacity-100" : "opacity-40 grayscale"
      }`}
    >
      <motion.div
        animate={{ scale: active ? 1.06 : 0.94 }}
        className={`rounded-full ${active ? "ring-4 ring-[var(--brand)]/30" : ""}`}
      >
        <PersonaAvatar persona={persona} size={64} resolve={resolve} />
      </motion.div>
      <div className="mt-1.5 text-xs font-semibold">{persona?.name}</div>
      {persona?.role ? <div className="text-[10px] text-gray-400">{persona.role}</div> : null}
    </div>
  );
}

function normalizeConversation(data?: Record<string, unknown>): {
  personas: Persona[];
  turns: ConversationTurn[];
} {
  const turns = (data?.turns as ConversationTurn[]) ?? [];
  let personas = (data?.personas as Persona[]) ?? [];
  if (!personas.length) {
    // Legacy `dialogue` shape: derive personas from distinct speakers.
    const names = Array.from(
      new Set(turns.map((t) => t.speaker || t.persona || "Speaker")),
    );
    personas = names.map((n, i): Persona => ({
      id: n,
      name: n,
      side: i % 2 === 0 ? "left" : "right",
    }));
  }
  return { personas, turns };
}

function personaOf(turn: ConversationTurn, personas: Persona[]): Persona {
  const key = turn.persona ?? turn.speaker;
  return (
    personas.find((p) => p.id === key || p.name === key) ??
    personas[0] ?? { name: turn.speaker, side: "left" }
  );
}

// --- Dialogue Graph types (real shape for conversation/dialogue blocks) ---

interface DialogueChoice {
  text: string;
  next_node: string | null;
}

interface DialogueNode {
  id: string;
  text: string;
  choices?: DialogueChoice[];
}

interface DialogueGraphData {
  speaker?: string;
  dialogue_nodes: DialogueNode[];
}

function isDialogueGraph(d: Record<string, unknown>): boolean {
  return Array.isArray(d.dialogue_nodes);
}

function DialogueGraph({ data }: { data: Record<string, unknown> }) {
  const reduced = useReducedMotion();
  const raw = data as unknown as DialogueGraphData;
  const nodes = raw.dialogue_nodes;
  const speakerName = typeof raw.speaker === "string" ? raw.speaker : "Speaker";
  const nodeMap = useMemo(() => {
    const m = new Map<string, DialogueNode>();
    for (const n of nodes) m.set(n.id, n);
    return m;
  }, [nodes]);

  const firstNode = nodes[0];
  const [transcript, setTranscript] = useState<{ role: "speaker" | "learner"; text: string }[]>(
    firstNode ? [{ role: "speaker", text: firstNode.text }] : [],
  );
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(firstNode?.id ?? null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const currentNode = currentNodeId ? nodeMap.get(currentNodeId) : undefined;
  const choices = currentNode?.choices ?? [];
  const isTerminal = !currentNode || choices.length === 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  }, [transcript.length, reduced]);

  const pickChoice = useCallback((choice: DialogueChoice) => {
    setTranscript((prev) => [...prev, { role: "learner", text: choice.text }]);
    if (choice.next_node && nodeMap.has(choice.next_node)) {
      const nextNode = nodeMap.get(choice.next_node)!;
      setCurrentNodeId(choice.next_node);
      setTranscript((prev) => [...prev, { role: "speaker", text: nextNode.text }]);
    } else {
      setCurrentNodeId(null);
    }
  }, [nodeMap]);

  const restart = useCallback(() => {
    setTranscript(firstNode ? [{ role: "speaker", text: firstNode.text }] : []);
    setCurrentNodeId(firstNode?.id ?? null);
  }, [firstNode]);

  if (!nodes.length) {
    return (
      <div className="rounded-xl border border-black/5 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No dialogue available.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-black/5 bg-gradient-to-b from-gray-50 to-white" role="region" aria-label="Interactive dialogue">
      <div className="border-b border-black/5 px-4 py-3">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Dialogue</span>
        <div className="text-sm font-semibold text-gray-700">{speakerName}</div>
      </div>

      <div className="max-h-[400px] overflow-y-auto p-4">
        <div className="space-y-2.5" role="log" aria-label="Conversation transcript" aria-live="polite">
          {transcript.map((entry, i) => {
            const isLearner = entry.role === "learner";
            return (
              <motion.div
                key={i}
                initial={reduced ? { opacity: 1 } : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${isLearner ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[78%] rounded-2xl px-3.5 py-2 text-sm ${
                    isLearner
                      ? "bg-[var(--brand)] text-white"
                      : "border border-black/5 bg-white"
                  }`}
                >
                  <div className={`mb-0.5 text-[11px] font-semibold ${isLearner ? "text-white/85" : "opacity-70"}`}>
                    {isLearner ? "You" : speakerName}
                  </div>
                  <div>{entry.text}</div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Choice buttons */}
        {!isTerminal && choices.length > 0 ? (
          <div className="mt-3 space-y-1.5">
            {choices.map((choice, ci) => (
              <button
                key={ci}
                type="button"
                onClick={() => pickChoice(choice)}
                className="block w-full rounded-xl border border-[var(--brand)]/30 bg-[var(--brand)]/5 px-3 py-2 text-left text-sm font-medium text-[var(--brand)] transition hover:bg-[var(--brand)]/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
              >
                {choice.text}
              </button>
            ))}
          </div>
        ) : null}

        <div ref={bottomRef} />
      </div>

      <div className="flex items-center justify-between border-t border-black/5 px-4 py-3">
        <span className="text-xs text-gray-400">
          {isTerminal && transcript.length > 0 ? "Conversation complete" : `${transcript.length} messages`}
        </span>
        <button
          type="button"
          onClick={restart}
          className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
        >
          Restart
        </button>
      </div>
    </div>
  );
}

function Conversation({ data, resolve }: { data?: Record<string, unknown>; resolve: Resolve }) {
  // Real shape: dialogue_nodes graph
  if (data && isDialogueGraph(data)) {
    return <DialogueGraph data={data} />;
  }

  // Legacy shape: linear turns + personas
  const { personas, turns } = useMemo(() => normalizeConversation(data), [data]);
  const [shown, setShown] = useState(1);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fallbackSpeechRef = useRef<string>("");

  const left = personas.find((p) => p.side !== "right") ?? personas[0];
  const right = personas.find((p) => p.side === "right") ?? personas[1] ?? personas[0];

  const play = useCallback(
    (link?: string, text?: string) => {
      const src = resolve(link);
      const el = audioRef.current;
      fallbackSpeechRef.current = text ?? "";
      if (!src || !el) {
        speakWithBrowser(text);
        return;
      }
      el.src = src;
      el.currentTime = 0;
      void el.play().catch(() => {});
    },
    [resolve],
  );

  useEffect(() => {
    if (!turns.length) return;
    const turn = turns[shown - 1];
    play(turn?.audio, turn?.text);
  }, [shown, turns, play]);

  if (!turns.length) return null;

  const active = personaOf(turns[shown - 1] ?? {}, personas);
  const done = shown >= turns.length;
  const advance = () => setShown((s) => Math.min(s + 1, turns.length));

  return (
    <div className="rounded-2xl border border-black/5 bg-gradient-to-b from-gray-50 to-white p-4" role="region" aria-label="Conversation">
      <audio
        ref={audioRef}
        className="hidden"
        onLoadedMetadata={(e) => {
          if (fallbackSpeechRef.current && e.currentTarget.duration <= 3.2) {
            e.currentTarget.pause();
            speakWithBrowser(fallbackSpeechRef.current);
          }
        }}
        onError={() => speakWithBrowser(fallbackSpeechRef.current)}
      />
      <div className="mb-4 flex items-end justify-between gap-2">
        <PersonaStage persona={left} active={left === active} resolve={resolve} />
        <span className="pb-7 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
          Conversation
        </span>
        <PersonaStage persona={right} active={right === active} resolve={resolve} />
      </div>

      <div className="space-y-2.5" role="log" aria-label="Conversation transcript" aria-live="polite">
        {turns.slice(0, shown).map((t, i) => {
          const p = personaOf(t, personas);
          const mine = p?.side === "right";
          const isLast = i === shown - 1;
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex items-end gap-2 ${mine ? "flex-row-reverse" : ""}`}
            >
              <PersonaAvatar persona={p} size={30} resolve={resolve} />
              <div
                className={`max-w-[78%] rounded-2xl px-3.5 py-2 text-sm ${
                  mine ? "bg-[var(--brand)] text-white" : "border border-black/5 bg-white"
                } ${isLast ? "ring-2 ring-[var(--brand)]/30" : ""}`}
              >
                <div
                  className={`mb-0.5 flex items-center gap-1.5 text-[11px] font-semibold ${
                    mine ? "text-white/85" : "opacity-70"
                  }`}
                >
                  {p?.name}
                  {p?.role ? <span className="font-normal opacity-70">{String.fromCharCode(183)} {p.role}</span> : null}
                </div>
                <div>{t.text}</div>
                {t.audio ? (
                  <button
                    type="button"
                    onClick={() => play(t.audio, t.text)}
                    className={`mt-1 inline-flex items-center gap-1 text-[11px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)] ${
                      mine ? "text-white/85" : "text-[var(--brand)]"
                    }`}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v7a4.49 4.49 0 002.5-3.5z"/>
                    </svg>
                    Replay
                  </button>
                ) : null}
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          {Math.min(shown, turns.length)} / {turns.length}
        </span>
        {done ? (
          <button
            type="button"
            onClick={() => setShown(1)}
            className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
          >
            Replay conversation
          </button>
        ) : (
          <button
            type="button"
            onClick={advance}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}


function shuffle<T>(items: T[]): T[] {
  return [...items]
    .map((value) => ({ value, order: Math.random() }))
    .sort((a, b) => a.order - b.order)
    .map(({ value }) => value);
}

function GameShell({
  title,
  prompt,
  score,
  total,
  onReset,
  children,
}: {
  title: string;
  prompt?: string;
  score: number;
  total: number;
  onReset: () => void;
  children: ReactNode;
}) {
  const pct = total ? Math.round((score / total) * 100) : 0;
  return (
    <div className="overflow-hidden rounded-2xl border border-black/5 bg-white shadow-sm">
      <div className="border-b border-black/5 bg-[var(--brand)]/5 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">
              Minigame
            </div>
            <h4 className="mt-0.5 text-base font-bold text-gray-900">{title}</h4>
            {prompt ? <p className="mt-1 text-sm text-gray-600">{prompt}</p> : null}
          </div>
          <div className="rounded-xl border border-black/5 bg-white px-3 py-2 text-right shadow-sm">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
              Score
            </div>
            <div className="text-lg font-bold text-[var(--brand)]">
              {score}/{total}
            </div>
          </div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/10">
          <motion.div
            animate={{ width: `${pct}%` }}
            className="h-full rounded-full bg-[var(--brand)]"
          />
        </div>
      </div>
      <div className="p-4">{children}</div>
      <div className="flex justify-end border-t border-black/5 bg-gray-50 px-4 py-3">
        <button
          type="button"
          onClick={onReset}
          className="rounded-lg border border-black/10 bg-white px-3 py-1.5 text-xs font-medium"
        >
          Replay
        </button>
      </div>
    </div>
  );
}

function QuizMinigame({ data }: { data: MinigameData }) {
  const questions = data.questions ?? [];
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const score = questions.reduce(
    (sum, q, i) => sum + (answers[i] === q.answerIndex ? 1 : 0),
    0,
  );

  return (
    <GameShell
      title={data.title ?? "Quick challenge"}
      prompt={data.prompt}
      score={score}
      total={questions.length}
      onReset={() => setAnswers({})}
    >
      <div className="space-y-4">
        {questions.map((q: MinigameQuestion, qi) => {
          const picked = answers[qi];
          const answered = picked !== undefined;
          return (
            <div key={qi} className="rounded-xl border border-black/5 bg-gray-50 p-3">
              <div className="text-sm font-semibold text-gray-900">{q.question}</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {q.options.map((option, oi) => {
                  const correct = oi === q.answerIndex;
                  const active = picked === oi;
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setAnswers((s) => ({ ...s, [qi]: oi }))}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                        answered && correct
                          ? "border-emerald-500 bg-emerald-50"
                          : active
                            ? "border-red-400 bg-red-50"
                            : "border-black/10 bg-white hover:border-[var(--brand)]"
                      }`}
                    >
                      <span className="mr-2 font-bold">
                        {answered && correct ? "OK" : answered && active ? "X" : ""}
                      </span>
                      {option}
                    </button>
                  );
                })}
              </div>
              {answered && q.explanation ? (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-3 rounded-lg bg-white p-2 text-xs text-gray-600"
                >
                  {q.explanation}
                </motion.div>
              ) : null}
            </div>
          );
        })}
      </div>
    </GameShell>
  );
}

function OrderMinigame({ data }: { data: MinigameData }) {
  const steps = data.steps ?? [];
  const [order, setOrder] = useState<string[]>(() => shuffle(steps));
  const score = order.reduce((sum, step, i) => sum + (step === steps[i] ? 1 : 0), 0);

  const move = (from: number, to: number) => {
    if (to < 0 || to >= order.length) return;
    setOrder((current) => {
      const next = [...current];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  };

  return (
    <GameShell
      title={data.title ?? "Put it in order"}
      prompt={data.prompt}
      score={score}
      total={steps.length}
      onReset={() => setOrder(shuffle(steps))}
    >
      <div className="space-y-2">
        {order.map((step, i) => {
          const correct = step === steps[i];
          return (
            <motion.div
              layout
              key={step}
              className={`flex items-center gap-2 rounded-xl border p-2 ${
                correct ? "border-emerald-500 bg-emerald-50" : "border-black/10 bg-gray-50"
              }`}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-sm font-bold">
                {i + 1}
              </div>
              <div className="flex-1 text-sm">{step}</div>
              <button
                type="button"
                onClick={() => move(i, i - 1)}
                className="rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
              >
                Up
              </button>
              <button
                type="button"
                onClick={() => move(i, i + 1)}
                className="rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
              >
                Down
              </button>
            </motion.div>
          );
        })}
      </div>
    </GameShell>
  );
}

function SortMinigame({ data }: { data: MinigameData }) {
  const items = data.items ?? [];
  const categories =
    data.categories && data.categories.length
      ? data.categories
      : Array.from(new Set(items.map((item) => item.category)));
  const [picks, setPicks] = useState<Record<number, string>>({});
  const score = items.reduce((sum, item, i) => sum + (picks[i] === item.category ? 1 : 0), 0);

  return (
    <GameShell
      title={data.title ?? "Sort the cards"}
      prompt={data.prompt}
      score={score}
      total={items.length}
      onReset={() => setPicks({})}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item: MinigameSortItem, i) => {
          const picked = picks[i];
          const correct = picked === item.category;
          return (
            <div
              key={`${item.text}-${i}`}
              className={`rounded-xl border p-3 ${
                picked
                  ? correct
                    ? "border-emerald-500 bg-emerald-50"
                    : "border-red-400 bg-red-50"
                  : "border-black/10 bg-gray-50"
              }`}
            >
              <div className="text-sm font-medium">{item.text}</div>
              <select
                value={picked ?? ""}
                onChange={(e) => setPicks((s) => ({ ...s, [i]: e.target.value }))}
                className="mt-2 w-full rounded-lg border border-black/10 bg-white px-2 py-1.5 text-sm"
              >
                <option value="">Choose category</option>
                {categories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>
    </GameShell>
  );
}

type MemoryCard = {
  id: string;
  pair: number;
  text: string;
};

function MemoryMinigame({ data }: { data: MinigameData }) {
  const pairs = data.pairs ?? [];
  const [cards, setCards] = useState<MemoryCard[]>(() =>
    shuffle(
      pairs.flatMap((pair: MinigamePair, i) => [
        { id: `${i}-a`, pair: i, text: pair.a },
        { id: `${i}-b`, pair: i, text: pair.b },
      ]),
    ),
  );
  const [open, setOpen] = useState<string[]>([]);
  const [matched, setMatched] = useState<Record<number, boolean>>({});
  const score = Object.values(matched).filter(Boolean).length;

  const reset = () => {
    setCards(
      shuffle(
        pairs.flatMap((pair: MinigamePair, i) => [
          { id: `${i}-a`, pair: i, text: pair.a },
          { id: `${i}-b`, pair: i, text: pair.b },
        ]),
      ),
    );
    setOpen([]);
    setMatched({});
  };

  const flip = (card: MemoryCard) => {
    if (matched[card.pair] || open.includes(card.id) || open.length >= 2) return;
    const nextOpen = [...open, card.id];
    setOpen(nextOpen);
    if (nextOpen.length === 2) {
      const first = cards.find((c) => c.id === nextOpen[0]);
      if (first?.pair === card.pair) {
        setMatched((s) => ({ ...s, [card.pair]: true }));
        setOpen([]);
      } else {
        window.setTimeout(() => setOpen([]), 800);
      }
    }
  };

  return (
    <GameShell
      title={data.title ?? "Memory match"}
      prompt={data.prompt}
      score={score}
      total={pairs.length}
      onReset={reset}
    >
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {cards.map((card) => {
          const visible = matched[card.pair] || open.includes(card.id);
          return (
            <button
              key={card.id}
              type="button"
              onClick={() => flip(card)}
              className={`min-h-[82px] rounded-xl border p-3 text-sm font-medium transition ${
                matched[card.pair]
                  ? "border-emerald-500 bg-emerald-50"
                  : visible
                    ? "border-[var(--brand)] bg-[var(--brand)]/5"
                    : "border-black/10 bg-gray-100"
              }`}
            >
              {visible ? card.text : "?"}
            </button>
          );
        })}
      </div>
    </GameShell>
  );
}

function Minigame({ data }: { data?: Record<string, unknown> }) {
  const game = (data ?? {}) as unknown as MinigameData;
  switch (game.game) {
    case "quiz":
      return <QuizMinigame data={game} />;
    case "order":
      return <OrderMinigame data={game} />;
    case "sort":
      return <SortMinigame data={game} />;
    case "memory":
      return <MemoryMinigame data={game} />;
    default:
      return (
        <GameShell
          title={game.title ?? "Practice challenge"}
          prompt={game.prompt ?? "This minigame type is not supported by the fallback renderer yet."}
          score={0}
          total={0}
          onReset={() => {}}
        >
          <div className="rounded-xl bg-gray-50 p-3 text-sm text-gray-600">
            Custom game: {game.game || "unknown"}
          </div>
        </GameShell>
      );
  }
}

function Flashcards({ data }: { data?: Record<string, unknown> }) {
  const allCards = useMemo(() => (data?.cards as { front: string; back: string }[]) ?? [], [data]);
  const [order, setOrder] = useState<number[]>(() => allCards.map((_, i) => i));
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  const [firstFlipCorrect, setFirstFlipCorrect] = useState<Set<number>>(new Set());
  const [showCelebration, setShowCelebration] = useState(false);

  const cards = useMemo(() => order.map((i) => ({ ...allCards[i], _idx: i })), [order, allCards]);
  const revealed = Object.keys(flipped).filter((k) => flipped[Number(k)]).length;
  const total = allCards.length;

  const shuffle = useCallback(() => {
    setOrder((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [next[i], next[j]] = [next[j], next[i]];
      }
      return next;
    });
    setFlipped({});
  }, []);

  const flip = (idx: number) => {
    const wasFlipped = !!flipped[idx];
    setFlipped((f) => ({ ...f, [idx]: !f[idx] }));
    if (!wasFlipped) {
      setFirstFlipCorrect((s) => new Set(s).add(idx));
      if (revealed + 1 === total && !showCelebration) {
        setShowCelebration(true);
        setTimeout(() => setShowCelebration(false), 2500);
      }
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500">
          {revealed} / {total} revealed
        </span>
        <button
          type="button"
          onClick={shuffle}
          className="rounded-lg border border-black/10 px-3 py-1 text-xs font-medium hover:bg-black/5"
        >
          Shuffle
        </button>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-[var(--brand)] transition-all"
          style={{ width: `${total ? (revealed / total) * 100 : 0}%` }}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {cards.map((c) => (
          <button
            key={c._idx}
            onClick={() => flip(c._idx)}
            className={`min-h-[96px] rounded-xl border p-4 text-left shadow-sm transition hover:shadow-md ${
              flipped[c._idx]
                ? "border-[var(--brand)]/30 bg-[var(--brand)]/5"
                : "border-black/5 bg-white"
            }`}
          >
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--brand)]">
              {flipped[c._idx] ? "Answer" : "Card"}
            </div>
            <div className="mt-1 text-sm">{flipped[c._idx] ? c.back : c.front}</div>
          </button>
        ))}
      </div>
      {showCelebration && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-center"
        >
          <div className="text-lg font-bold text-emerald-700">All cards revealed!</div>
          <div className="text-sm text-emerald-600">
            {firstFlipCorrect.size} / {total} seen on first pass
          </div>
        </motion.div>
      )}
    </div>
  );
}

// --- DragDrop types ---

interface DragDropItemReal {
  id: string;
  text: string;
  category: string;
}

interface DragDropCategoryReal {
  id: string;
  title: string;
}

interface DragDropNormalized {
  prompt?: string;
  items: { id: string; text: string; correctBin: string }[];
  bins: { id: string; title: string }[];
}

function normalizeDragDropData(data?: Record<string, unknown>): DragDropNormalized {
  if (!data) return { items: [], bins: [] };
  // Real shape: { items, categories }
  if (Array.isArray(data.items) && Array.isArray(data.categories)) {
    const rawItems = data.items as DragDropItemReal[];
    const rawCats = data.categories as DragDropCategoryReal[];
    return {
      prompt: typeof data.prompt === "string" ? data.prompt : undefined,
      items: rawItems.map((it, i) => ({
        id: it.id ?? `item-${i}`,
        text: it.text,
        correctBin: it.category,
      })),
      bins: rawCats.map((c) => ({ id: c.id, title: c.title })),
    };
  }
  // Legacy shape: { prompt, pairs: [{ left, right }] }
  const pairs = (data.pairs as { left: string; right: string }[]) ?? [];
  const uniqueRights = Array.from(new Set(pairs.map((p) => p.right)));
  return {
    prompt: typeof data.prompt === "string" ? data.prompt : undefined,
    items: pairs.map((p, i) => ({
      id: `item-${i}`,
      text: p.left,
      correctBin: p.right,
    })),
    bins: uniqueRights.map((r) => ({ id: r, title: r })),
  };
}

function DragDrop({ data }: { data?: Record<string, unknown> }) {
  const pairs = (data?.pairs as { left: string; right: string }[]) ?? [];
  const rights = useMemo(() => pairs.map((p) => p.right).sort(), [pairs]);
  const [picks, setPicks] = useState<Record<number, string>>({});
  const [checked, setChecked] = useState(false);
  const [shakeIdx, setShakeIdx] = useState<number | null>(null);

  const allFilled = pairs.every((_, i) => !!picks[i]);
  const correctCount = pairs.filter((p, i) => picks[i] === p.right).length;
  const allCorrect = checked && correctCount === pairs.length;

  const checkAll = () => {
    setChecked(true);
    // Shake the first wrong answer
    const wrongIdx = pairs.findIndex((p, i) => picks[i] !== p.right);
    if (wrongIdx >= 0) {
      setShakeIdx(wrongIdx);
      setTimeout(() => setShakeIdx(null), 600);
    }
  };

  const reset = () => {
    setPicks({});
    setChecked(false);
    setShakeIdx(null);
  };

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {data?.prompt ? <p className="mb-3 text-sm font-medium">{String(data.prompt)}</p> : null}
      <div className="space-y-2">
        {pairs.map((p, i) => {
          const correct = picks[i] === p.right;
          const isShaking = shakeIdx === i;
          return (
            <motion.div
              key={i}
              animate={isShaking ? { x: [0, -6, 6, -4, 4, 0] } : {}}
              transition={{ duration: 0.4 }}
              className="flex items-center gap-3"
            >
              <span className="w-28 shrink-0 text-sm font-medium">{p.left}</span>
              <select
                value={picks[i] ?? ""}
                disabled={checked && correct}
                onChange={(e) => {
                  setPicks((s) => ({ ...s, [i]: e.target.value }));
                  setChecked(false);
                }}
                className={`flex-1 rounded-lg border px-2 py-1.5 text-sm transition-all ${
                  checked
                    ? correct
                      ? "border-emerald-500 bg-emerald-50"
                      : "border-red-400 bg-red-50"
                    : picks[i]
                      ? "border-[var(--brand)] bg-[var(--brand)]/5"
                      : "border-black/10"
                }`}
              >
                <option value="">Selectâ€¦</option>
                {rights.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              {checked && (
                <span className={`text-sm font-bold ${correct ? "text-emerald-600" : "text-red-500"}`}>
                  {correct ? "✓" : "✗"}
                </span>
              )}
            </motion.div>

          );
        })}
      </div>
      <div className="mt-4 flex items-center gap-3">
        {!checked ? (
          <button
            type="button"
            disabled={!allFilled}
            onClick={checkAll}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            Check All
          </button>
        ) : allCorrect ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 text-sm font-medium text-emerald-600"
          >
            <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white text-xs">✓</span>
            All correct!
          </motion.div>
        ) : (
          <>
            <span className="text-sm font-medium text-red-600">
              {correctCount} / {pairs.length} correct
            </span>
            <button
              type="button"
              onClick={reset}
              className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium"
            >
              Try again
            </button>
          </>
        )}
      </div>
    </div>
  );
}


// --- Scenario types ---

interface ScenarioOption {
  text: string;
  feedback: string;
  next_step?: string | null;
  correct?: boolean;
}

interface ScenarioStep {
  id: string;
  question: string;
  options: ScenarioOption[];
}

interface ScenarioNormalized {
  prompt?: string;
  steps: ScenarioStep[];
}

function normalizeScenarioData(data?: Record<string, unknown>): ScenarioNormalized {
  if (!data) return { steps: [] };
  // Real shape: { steps: [{ id, question, options: [{ text, feedback, next_step }] }] }
  if (Array.isArray(data.steps)) {
    const steps = (data.steps as { id?: string; question?: string; options?: { text: string; feedback?: string; next_step?: string | null; correct?: boolean }[] }[]).map(
      (s, i) => ({
        id: typeof s.id === "string" ? s.id : `step-${i}`,
        question: typeof s.question === "string" ? s.question : `Decision ${i + 1}`,
        options: (s.options ?? []).map((o) => ({
          text: o.text,
          feedback: typeof o.feedback === "string" ? o.feedback : "",
          next_step: o.next_step ?? null,
          correct: typeof o.correct === "boolean" ? o.correct : undefined,
        })),
      }),
    );
    return { prompt: typeof data.prompt === "string" ? data.prompt : undefined, steps };
  }
  // Legacy shape: { prompt, branches: [{ choice, outcome }] }
  const branches = (data.branches as { choice: string; outcome: string }[]) ?? [];
  const singleStep: ScenarioStep = {
    id: "step-0",
    question: typeof data.prompt === "string" ? data.prompt : "Make your choice:",
    options: branches.map((b) => ({
      text: b.choice,
      feedback: b.outcome,
      next_step: null,
    })),
  };
  return { prompt: undefined, steps: branches.length ? [singleStep] : [] };
}

function Scenario({ data }: { data?: Record<string, unknown> }) {
  const branches = (data?.branches as { choice: string; outcome: string; explanation?: string }[]) ?? [];
  const [picked, setPicked] = useState<number | null>(null);
  const [showAll, setShowAll] = useState(false);
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {data?.prompt ? <p className="mb-3 text-sm font-medium">{String(data.prompt)}</p> : null}
      <div className="flex flex-wrap gap-2">
        {branches.map((b, i) => (
          <button
            key={i}
            onClick={() => { setPicked(i); setShowAll(false); }}
            className={`rounded-lg border px-3 py-1.5 text-sm transition-all ${
              picked === i
                ? "border-[var(--brand)] bg-[var(--brand)]/10 font-medium"
                : picked !== null
                  ? "border-black/5 opacity-60"
                  : "border-black/10 hover:border-[var(--brand)]/50"
            }`}
          >
            {b.choice}
          </button>
        ))}
      </div>
    );
  }

  const totalSteps = steps.length;
  const completedSteps = history.length;
  const correctCount = history.filter((h) => h.option.correct === true).length;
  const hasCorrectness = history.some((h) => h.option.correct !== undefined);

  return (
    <div className="overflow-hidden rounded-xl border border-black/5 bg-white" role="region" aria-label="Decision scenario">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-black/5 bg-gray-50 px-4 py-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">Scenario</div>
          {prompt ? <p className="mt-0.5 text-sm text-gray-600">{prompt}</p> : null}
        </div>
        <span className="text-xs text-gray-400">
          Step {Math.min(completedSteps + 1, totalSteps)}/{totalSteps}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-gray-100">
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 space-y-2"
        >
          <div className="rounded-lg bg-[var(--brand)]/5 border border-[var(--brand)]/10 p-3 text-sm">
            <div className="font-medium text-[var(--brand)] mb-1">Your choice: {branches[picked].choice}</div>
            {branches[picked].outcome}
          </div>
          {!showAll && branches.some((b) => b.explanation) && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="text-xs font-medium text-[var(--brand)] hover:underline"
            >
              Why were the other options different?
            </button>
          )}
          {showAll && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-1.5"
            >
              {branches.map((b, i) => {
                if (i === picked || !b.explanation) return null;
                return (
                  <div key={i} className="rounded-lg bg-gray-50 p-2.5 text-sm">
                    <span className="font-medium text-gray-700">{b.choice}:</span>{" "}
                    <span className="text-gray-500">{b.explanation}</span>
                  </div>
                );
              })}
            </motion.div>
          )}
        </motion.div>
      ) : null}
    </div>
  );
}

// ── New interactive block types ───────────────────────────────────────────────

function MatchingGame({ data }: { data?: Record<string, unknown> }) {
  const pairs = ((data as MatchingGameData | undefined)?.pairs) ?? [];
  const total = pairs.length;

  // Build a grid of 2*N cards (term + definition), shuffled once
  const gridCards = useMemo(() => {
    const cards: { id: number; text: string; pairIdx: number; kind: "term" | "def" }[] = [];
    pairs.forEach((p, i) => {
      cards.push({ id: i * 2, text: p.term, pairIdx: i, kind: "term" });
      cards.push({ id: i * 2 + 1, text: p.definition, pairIdx: i, kind: "def" });
    });
    for (let i = cards.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [cards[i], cards[j]] = [cards[j], cards[i]];
    }
    return cards;
  }, [pairs]);

  const [flipped, setFlipped] = useState<Set<number>>(new Set());
  const [matched, setMatched] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<number | null>(null);
  const [wrong, setWrong] = useState<Set<number>>(new Set());
  const [moves, setMoves] = useState(0);

  const handleClick = (cardId: number) => {
    if (matched.has(cardId) || flipped.has(cardId) || wrong.size > 0) return;
    const card = gridCards.find((c) => c.id === cardId);
    if (!card) return;

    if (selected === null) {
      setSelected(cardId);
      setFlipped((s) => new Set(s).add(cardId));
      return;
    }

    const prev = gridCards.find((c) => c.id === selected);
    if (!prev) return;
    setFlipped((s) => new Set(s).add(cardId));
    setMoves((m) => m + 1);

    if (prev.pairIdx === card.pairIdx && prev.kind !== card.kind) {
      // Match!
      setMatched((s) => { const n = new Set(s); n.add(prev.id); n.add(card.id); return n; });
      setSelected(null);
    } else {
      // No match — briefly show both, then hide
      setWrong(new Set([prev.id, card.id]));
      setTimeout(() => {
        setFlipped((s) => { const n = new Set(s); n.delete(prev.id); n.delete(card.id); return n; });
        setWrong(new Set());
        setSelected(null);
      }, 800);
    }
  };

  const allMatched = matched.size === gridCards.length && gridCards.length > 0;
  const cols = total <= 3 ? "grid-cols-3" : total <= 4 ? "grid-cols-4" : "grid-cols-4";

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold">Memory Match</h4>
        <span className="text-xs text-gray-400">{matched.size / 2} / {total} matched · {moves} moves</span>
      </div>
      <div className={`grid ${cols} gap-2`}>
        {gridCards.map((card) => {
          const isFlipped = flipped.has(card.id) || matched.has(card.id);
          const isMatched = matched.has(card.id);
          const isWrong = wrong.has(card.id);
          return (
            <button
              key={card.id}
              onClick={() => handleClick(card.id)}
              disabled={isMatched}
              className={`min-h-[72px] rounded-lg border p-2.5 text-xs text-center transition-all ${
                isMatched
                  ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                  : isWrong
                    ? "border-red-400 bg-red-50"
                    : isFlipped
                      ? "border-[var(--brand)] bg-[var(--brand)]/5"
                      : "border-black/10 bg-gray-50 hover:bg-gray-100 cursor-pointer"
              }`}
            >
              {isFlipped ? (
                <span>{card.text}</span>
              ) : (
                <span className="text-gray-400 text-lg">?</span>
              )}
            </button>
          );
        })}
      </div>
      {allMatched && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mt-3 rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-center"
        >
          <div className="font-bold text-emerald-700">All pairs matched!</div>
          <div className="text-xs text-emerald-600">Completed in {moves} moves</div>
        </motion.div>
      )}
    </div>
  );
}

function SortingChallenge({ data }: { data?: Record<string, unknown> }) {
  const raw = data as SortingChallengeData | undefined;
  const prompt = raw?.prompt ?? "Put these items in the correct order:";
  const items = useMemo(() => raw?.items ?? [], [raw]);
  const correctOrder = useMemo(() => raw?.correctOrder ?? items.map((_, i) => i), [raw, items]);

  const [order, setOrder] = useState<number[]>(() => {
    const indices = items.map((_, i) => i);
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    return indices;
  });
  const [checked, setChecked] = useState(false);

  const moveUp = (pos: number) => {
    if (pos === 0) return;
    setOrder((o) => { const n = [...o]; [n[pos], n[pos - 1]] = [n[pos - 1], n[pos]]; return n; });
    setChecked(false);
  };

  const moveDown = (pos: number) => {
    if (pos >= order.length - 1) return;
    setOrder((o) => { const n = [...o]; [n[pos], n[pos + 1]] = [n[pos + 1], n[pos]]; return n; });
    setChecked(false);
  };

  const isCorrect = order.every((idx, pos) => idx === correctOrder[pos]);

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      <p className="mb-3 text-sm font-medium">{prompt}</p>
      <div className="space-y-1.5">
        {order.map((itemIdx, pos) => {
          const posCorrect = checked && itemIdx === correctOrder[pos];
          const posWrong = checked && itemIdx !== correctOrder[pos];
          return (
            <motion.div
              key={itemIdx}
              layout
              className={`flex items-center gap-2 rounded-lg border p-2.5 text-sm transition-all ${
                posCorrect
                  ? "border-emerald-300 bg-emerald-50"
                  : posWrong
                    ? "border-red-300 bg-red-50"
                    : "border-black/10 bg-white"
              }`}
            >
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gray-100 text-xs font-bold text-gray-500">
                {pos + 1}
              </span>
              <span className="flex-1">{items[itemIdx]}</span>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => moveUp(pos)}
                  disabled={pos === 0 || (checked && isCorrect)}
                  className="rounded px-1.5 py-0.5 text-xs hover:bg-black/5 disabled:opacity-30"
                >
                  ▲
                </button>
                <button
                  type="button"
                  onClick={() => moveDown(pos)}
                  disabled={pos >= order.length - 1 || (checked && isCorrect)}
                  className="rounded px-1.5 py-0.5 text-xs hover:bg-black/5 disabled:opacity-30"
                >
                  ▼
                </button>
              </div>
              {checked && (
                <span className={`text-sm font-bold ${posCorrect ? "text-emerald-600" : "text-red-500"}`}>
                  {posCorrect ? "✓" : "✗"}
                </span>
              )}
            </motion.div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center gap-3">
        {!checked ? (
          <button
            type="button"
            onClick={() => setChecked(true)}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white"
          >
            Check Order
          </button>
        ) : isCorrect ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 text-sm font-medium text-emerald-600"
          >
            <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white text-xs">✓</span>
            Correct order!
          </motion.div>
        ) : (
          <button
            type="button"
            onClick={() => setChecked(false)}
            className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

function FillInBlank({ data }: { data?: Record<string, unknown> }) {
  const raw = data as FillInBlankData | undefined;
  const sentences = raw?.sentences ?? [];
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);

  let totalBlanks = 0;
  let correctBlanks = 0;
  sentences.forEach((s, si) =>
    s.blanks.forEach((b, bi) => {
      totalBlanks++;
      if (answers[`${si}-${bi}`] === b.answer) correctBlanks++;
    }),
  );
  const allFilled = Object.keys(answers).length >= totalBlanks;
  const allCorrect = checked && correctBlanks === totalBlanks;

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4 space-y-4">
      <h4 className="text-sm font-semibold">Fill in the blanks</h4>
      {sentences.map((s, si) => {
        // Split text at blank positions and interleave with dropdowns
        const parts: (string | { blankIdx: number })[] = [];
        let lastPos = 0;
        const sortedBlanks = [...s.blanks].sort((a, b) => a.position - b.position);
        sortedBlanks.forEach((blank, bi) => {
          if (blank.position > lastPos) {
            parts.push(s.text.slice(lastPos, blank.position));
          }
          parts.push({ blankIdx: bi });
          // Skip past the blank placeholder (assume "___" or similar)
          const afterBlank = s.text.indexOf(" ", blank.position + 1);
          lastPos = afterBlank > blank.position ? afterBlank : blank.position + 3;
        });
        if (lastPos < s.text.length) parts.push(s.text.slice(lastPos));

        return (
          <div key={si} className="text-sm leading-loose flex flex-wrap items-center gap-1">
            {parts.map((part, pi) => {
              if (typeof part === "string") {
                return <span key={pi}>{part}</span>;
              }
              const blank = s.blanks[part.blankIdx];
              const key = `${si}-${part.blankIdx}`;
              const val = answers[key];
              const correct = val === blank.answer;
              return (
                <select
                  key={pi}
                  value={val ?? ""}
                  disabled={checked && correct}
                  onChange={(e) => {
                    setAnswers((a) => ({ ...a, [key]: e.target.value }));
                    setChecked(false);
                  }}
                  className={`inline-block rounded-md border px-2 py-1 text-sm min-w-[120px] ${
                    checked
                      ? correct
                        ? "border-emerald-500 bg-emerald-50"
                        : "border-red-400 bg-red-50"
                      : val
                        ? "border-[var(--brand)] bg-[var(--brand)]/5"
                        : "border-black/10"
                  }`}
                >
                  <option value="">Choose…</option>
                  {blank.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              );
            })}
          </div>
        );
      })}
      <div className="flex items-center gap-3">
        {!checked ? (
          <button
            type="button"
            disabled={!allFilled}
            onClick={() => setChecked(true)}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            Check Answers
          </button>
        ) : allCorrect ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 text-sm font-medium text-emerald-600"
          >
            <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white text-xs">✓</span>
            All blanks correct!
          </motion.div>
        ) : (
          <>
            <span className="text-sm text-red-600 font-medium">{correctBlanks} / {totalBlanks} correct</span>
            <button
              type="button"
              onClick={() => setChecked(false)}
              className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium"
            >
              Try again
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function WordCloud({ data }: { data?: Record<string, unknown> }) {
  const raw = data as WordCloudData | undefined;
  const words = raw?.words ?? [];
  const maxWeight = Math.max(...words.map((w) => w.weight), 1);

  return (
    <div className="rounded-xl border border-black/5 bg-gradient-to-br from-gray-50 to-white p-5">
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
        {words.map((w, i) => {
          const ratio = w.weight / maxWeight;
          const size = 12 + ratio * 24; // 12px to 36px
          const opacity = 0.4 + ratio * 0.6;
          return (
            <motion.span
              key={i}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity, scale: 1 }}
              transition={{ delay: i * 0.04 }}
              style={{ fontSize: `${size}px` }}
              className="font-semibold text-[var(--brand)] cursor-default select-none"
              title={`Weight: ${w.weight}`}
            >
              {w.text}
            </motion.span>
          );
        })}
      </div>
    </div>
  );
}

// Detect fabricated / placeholder chart data that shouldn't be rendered as a
// real chart. Generic quarter labels with linearly increasing values are a
// strong signal that the data is filler, not meaningful metrics.
function looksLikePlaceholder(labels: string[], datasets: { data: number[] }[]): boolean {
  const GENERIC = /^(q[1-4]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|month\s*\d|week\s*\d|step\s*\d|year\s*\d)/i;
  const genericCount = labels.filter((l) => GENERIC.test(l.trim())).length;
  if (genericCount < labels.length * 0.6) return false;
  for (const ds of datasets) {
    if (!ds.data || ds.data.length < 3) continue;
    let monotone = true;
    for (let i = 1; i < ds.data.length; i++) {
      if (ds.data[i] < ds.data[i - 1]) { monotone = false; break; }
    }
    if (monotone) return true;
  }
  return false;
}

function ChartBlock({ data }: { data?: Record<string, unknown> }) {
  const chartType = (data?.chartType as string) ?? "bar";
  const labels = (data?.labels as string[]) ?? [];
  const datasets = (data?.datasets as { label: string; data: number[] }[]) ?? [];
  const title = data?.title ? String(data.title) : undefined;

  // If the data looks fabricated, render a styled info card instead of a chart
  if (looksLikePlaceholder(labels, datasets)) {
    return (
      <div className="rounded-xl border border-black/5 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-5">
        <div className="flex items-center gap-2 mb-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--brand)]/10 text-[var(--brand)] text-sm">
            📊
          </span>
          {title ? (
            <h4 className="text-sm font-semibold">{title}</h4>
          ) : (
            <h4 className="text-sm font-semibold">Data Visualization</h4>
          )}
        </div>
        <p className="text-sm text-gray-500">
          This visualization will be populated with real metrics once data is available.
        </p>
        {datasets.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {datasets.map((ds, i) => (
              <span
                key={i}
                className="rounded-full bg-white px-3 py-1 text-xs font-medium text-gray-600 border border-black/5"
              >
                {ds.label}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  const coloredDatasets = datasets.map((d, i) => ({
    ...d,
    backgroundColor: ["#5145E5", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4"][i % 5],
    borderColor: "#5145E5",
  }));
  const chartData = { labels, datasets: coloredDatasets };
  const opts = { responsive: true, plugins: { legend: { position: "bottom" as const } } };
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {title ? <h4 className="mb-2 text-sm font-semibold">{title}</h4> : null}
      {chartType === "line" ? (
        <Line data={chartData} options={opts} />
      ) : chartType === "pie" ? (
        <Pie data={chartData} options={opts} />
      ) : (
        <Bar data={chartData} options={opts} />
      )}
    </div>
  );
}

function AudioBlock({ block, resolve }: { block: Block; resolve: Resolve }) {
  const src = resolve(block.asset);
  const [open, setOpen] = useState(false);
  const [useBrowserVoice, setUseBrowserVoice] = useState(!src && !!block.text);
  if (!src && !block.text) return null;

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-black/5 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--brand)]">
          <span aria-hidden="true">AUDIO</span>
          Listen to this page
        </div>
        {block.text ? (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="flex h-7 w-7 items-center justify-center rounded-full border border-black/10 bg-gray-50 text-xs font-bold text-gray-700"
            aria-label="Show spoken text"
            title="Show spoken text"
          >
            i
          </button>
        ) : null}
      </div>
      {src && !useBrowserVoice ? (
        <audio
          controls
          className="w-full"
          src={src}
          onLoadedMetadata={(e) => {
            if (block.text && e.currentTarget.duration <= 3.2) {
              e.currentTarget.pause();
              setUseBrowserVoice(true);
            }
          }}
          onError={() => {
            if (block.text) setUseBrowserVoice(true);
          }}
        />
      ) : null}
      {block.text && useBrowserVoice ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="text-xs text-amber-800">
            Generated audio is unavailable. Using your browser voice for this transcript.
          </div>
          <button
            type="button"
            onClick={() => speakWithBrowser(block.text)}
            className="mt-2 rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white"
          >
            Play spoken text
          </button>
        </div>
      ) : null}
      {open && block.text ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="max-h-[80vh] w-full max-w-lg overflow-auto rounded-2xl bg-white p-5 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label="Spoken text"
          >
            <div className="flex items-start justify-between gap-3">
              <h4 className="text-base font-bold text-gray-900">Spoken text</h4>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg border border-black/10 px-2 py-1 text-xs font-medium"
              >
                Close
              </button>
            </div>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
              {block.text}
            </p>
          </motion.div>
        </div>
      ) : null}
    </div>
  );
}

function labelize(key: string): string {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function StructuredValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span>{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc space-y-1 pl-5">
        {value.map((item, i) => (
          <li key={i}>
            <StructuredValue value={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    return (
      <div className="space-y-2">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key}>
            <span className="font-semibold text-gray-800">{labelize(key)}: </span>
            <StructuredValue value={item} />
          </div>
        ))}
      </div>
    );
  }
  return null;
}

function StructuredData({ data }: { data?: Record<string, unknown> }) {
  if (!data || !Object.keys(data).length) return null;
  return (
    <div className="rounded-xl border border-black/5 bg-gray-50 p-3 text-sm leading-relaxed text-gray-700">
      <StructuredValue value={data} />
    </div>
  );
}

export function BlockView({ block, resolve }: { block: Block; resolve: Resolve }) {
  switch (block.type) {
    case "heading":
      return <h3 className="mt-2 text-xl font-bold">{block.text ? renderInlineMarkdown(block.text) : null}</h3>;
    case "paragraph":
      return <p className="text-[15px] leading-relaxed text-gray-700">{block.text ? renderInlineMarkdown(block.text) : null}</p>;
    case "list":
      return (
        <ul className="list-disc space-y-1 pl-5 text-[15px] text-gray-700">
          {(block.items ?? []).map((it, i) => (
            <li key={i}>{renderInlineMarkdown(it)}</li>
          ))}
        </ul>
      );
    case "callout":
      return (
        <div className="rounded-xl border-l-4 border-[var(--brand)] bg-[var(--brand)]/5 p-4 text-sm">
          {block.text ? renderInlineMarkdown(block.text) : null}
        </div>
      );
    case "image":
      return <MediaImage src={resolve(block.asset)} alt={block.text} />;
    case "video": {
      const src = resolve(block.asset);
      return src ? (
        <video controls className="w-full rounded-xl border border-black/5">
          <source src={src} />
        </video>
      ) : null;
    }
    case "audio": {
      return <AudioBlock block={block} resolve={resolve} />;
    }
    case "conversation":
    case "dialogue":
      return <Conversation data={block.data} resolve={resolve} />;
    case "minigame":
      return <Minigame data={block.data} />;
    case "flashcards":
      return <Flashcards data={block.data} />;
    case "dragdrop":
      return <DragDrop data={block.data} />;
    case "hotspot":
      return <Hotspot data={block.data} resolve={resolve} />;
    case "timeline":
      return <Timeline data={block.data} />;
    case "accordion":
      return <Accordion data={block.data} />;
    case "scenario":
      return <Scenario data={block.data} />;
    case "chart":
      return <ChartBlock data={block.data} />;
    case "matching_game":
      return <MatchingGame data={block.data} />;
    case "sorting_challenge":
      return <SortingChallenge data={block.data} />;
    case "fill_in_blank":
      return <FillInBlank data={block.data} />;
    case "word_cloud":
      return <WordCloud data={block.data} />;
    default: {
      // Unknown / custom block type. The design is intentionally free, so rather
      // than dropping the block, surface whatever content it carries (text, list
      // items, data and any referenced image). This is the fallback renderer used when
      // the implementation agent isn't building a bespoke app.
      const img = resolve(block.asset);
      if (!block.text && !(block.items && block.items.length) && !block.data && !img) return null;
      return (
        <div className="space-y-2">
          {block.text ? (
            <p className="text-[15px] leading-relaxed text-gray-700">{renderInlineMarkdown(block.text)}</p>
          ) : null}
          {block.items && block.items.length ? (
            <ul className="list-disc space-y-1 pl-5 text-[15px] text-gray-700">
              {block.items.map((it, i) => (
                <li key={i}>{renderInlineMarkdown(it)}</li>
              ))}
            </ul>
          ) : null}
          <StructuredData data={block.data} />
          {img ? <MediaImage src={img} alt={block.text} /> : null}
        </div>
      );
    }
  }
}
