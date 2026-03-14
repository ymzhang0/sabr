export const DEFAULT_PROJECT_CODE_DIRECTORY = "codes";
export const DEFAULT_PROJECT_DATA_DIRECTORY = "data";

const ACTION_RULES: Array<{ pattern: RegExp; value: string }> = [
  { pattern: /\b(submit|launch|run workchain|run calculation|prepare submission)\b/i, value: "submit" },
  { pattern: /\b(analy[sz]e|inspect|diagnos)\w*\b/i, value: "analyze" },
  { pattern: /\b(plot|chart|visuali[sz]e|band structure|dos)\b/i, value: "plot" },
  { pattern: /\b(test|benchmark|check|validate)\b/i, value: "test" },
  { pattern: /\b(relax|optimi[sz]e|optimize)\b/i, value: "relax" },
];

const SUBJECT_RULES: Array<{ pattern: RegExp; value: string }> = [
  { pattern: /\b(silicon|^si$|\bsi\b)/i, value: "si" },
  { pattern: /\b(iron|^fe$|\bfe\b)/i, value: "fe" },
  { pattern: /\b(equation of state|state of equation|eos)\b/i, value: "eos" },
  { pattern: /\b(bands?|band structure)\b/i, value: "bands" },
  { pattern: /\b(density of states|dos)\b/i, value: "dos" },
  { pattern: /\b(co2)\b/i, value: "co2" },
  { pattern: /\b(adsorption|surface)\b/i, value: "adsorption" },
  { pattern: /\b(convergence|converge|ecutwfc|cutoff)\b/i, value: "convergence" },
  { pattern: /\b(bcc)\b/i, value: "bcc" },
  { pattern: /\b(magnetic|ferromagnetic|non-magnetic|nonmagnetic)\b/i, value: "magnetic" },
];

const STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "into",
  "that",
  "this",
  "then",
  "using",
  "use",
  "workflow",
  "project",
  "aiida",
  "quantum",
  "espresso",
  "plugin",
  "code",
  "script",
  "python",
  "please",
  "help",
  "generate",
]);

function toAsciiSlug(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[^\x00-\x7F]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
}

function formatDateStamp(date: Date): string {
  const year = String(date.getFullYear()).padStart(4, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function detectAction(intent: string): string {
  for (const rule of ACTION_RULES) {
    if (rule.pattern.test(intent)) {
      return rule.value;
    }
  }
  return "submit";
}

function detectSubjects(intent: string): string[] {
  const detected: string[] = [];
  const seen = new Set<string>();

  for (const rule of SUBJECT_RULES) {
    if (!rule.pattern.test(intent) || seen.has(rule.value)) {
      continue;
    }
    seen.add(rule.value);
    detected.push(rule.value);
  }

  const asciiWords = intent
    .normalize("NFKD")
    .replace(/[^\x00-\x7F]/g, " ")
    .toLowerCase()
    .match(/[a-z0-9]+/g) ?? [];

  for (const word of asciiWords) {
    if (STOP_WORDS.has(word) || seen.has(word) || /^\d+$/.test(word)) {
      continue;
    }
    seen.add(word);
    detected.push(word);
    if (detected.length >= 3) {
      break;
    }
  }

  return detected.slice(0, 3);
}

function ensurePythonFilename(filename: string): string {
  const cleaned = String(filename || "").trim().replace(/\\/g, "/");
  const base = cleaned.split("/").filter(Boolean).pop() || "script";
  const stem = toAsciiSlug(base.replace(/\.py$/i, "")) || "script";
  return `${stem}.py`;
}

export function normalizeProjectScriptRelativePath(inputPath: string): string {
  const cleaned = String(inputPath || "").trim().replace(/\\/g, "/");
  const segments = cleaned.split("/").filter(Boolean);
  const safeSegments = segments.map((segment, index) => {
    const sanitized = toAsciiSlug(segment.replace(/\.py$/i, ""));
    if (index === segments.length - 1) {
      return `${sanitized || "script"}.py`;
    }
    return sanitized || "folder";
  });

  if (safeSegments.length === 0) {
    return `${DEFAULT_PROJECT_CODE_DIRECTORY}/script.py`;
  }

  if (safeSegments[0] !== DEFAULT_PROJECT_CODE_DIRECTORY) {
    safeSegments.unshift(DEFAULT_PROJECT_CODE_DIRECTORY);
  }

  return safeSegments.join("/");
}

export function suggestScriptFilename(intent: string, date = new Date()): string {
  const normalizedIntent = String(intent || "").trim();
  const action = detectAction(normalizedIntent);
  const subjects = detectSubjects(normalizedIntent);
  const base = [action, ...subjects].filter(Boolean).slice(0, 4).join("_") || "submit_script";
  return `${base}_${formatDateStamp(date)}.py`;
}

export function buildProjectScriptSaveTarget(args: {
  projectPath?: string | null;
  intent?: string | null;
  filename?: string | null;
}): {
  filename: string;
  relativePath: string;
  absolutePathHint: string | null;
} {
  const filename = args.filename?.trim()
    ? ensurePythonFilename(args.filename)
    : suggestScriptFilename(String(args.intent || ""));
  const relativePath = normalizeProjectScriptRelativePath(`${DEFAULT_PROJECT_CODE_DIRECTORY}/${filename}`);
  const normalizedProjectPath = String(args.projectPath || "").trim().replace(/\\/g, "/").replace(/\/+$/g, "");
  return {
    filename,
    relativePath,
    absolutePathHint: normalizedProjectPath ? `${normalizedProjectPath}/${relativePath}` : null,
  };
}

export function buildProjectLayoutSystemPrompt(): string {
  return `Standard project layout: save reusable Python scripts under ${DEFAULT_PROJECT_CODE_DIRECTORY}/ and exported results under ${DEFAULT_PROJECT_DATA_DIRECTORY}/. When suggesting a save location, explicitly recommend ${DEFAULT_PROJECT_CODE_DIRECTORY}/<filename>.py.`;
}

export function buildScriptSaveRecommendation(relativePath: string): string {
  const cleaned = String(relativePath || "").trim() || `${DEFAULT_PROJECT_CODE_DIRECTORY}/script.py`;
  return `I have prepared the script and recommend saving it under ${cleaned}.`;
}
