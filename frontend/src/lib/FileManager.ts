export const DEFAULT_PROJECT_CODE_DIRECTORY = "codes";
export const DEFAULT_PROJECT_DATA_DIRECTORY = "data";
const PYTHON_CODE_BLOCK_REGEX = /```python\s*([\s\S]*?)```/gi;
const GENERIC_CODE_BLOCK_REGEX = /```(?:py|python)?\s*([\s\S]*?)```/gi;
const BACKTICK_PYTHON_PATH_REGEX = /`([^`\n]+\.py)`/g;
const PLAIN_PYTHON_PATH_REGEX = /(?:^|[\s:(])((?:codes\/)?[A-Za-z0-9._/-]+\.py)(?=$|[\s`),.:;])/g;

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

function extractLastRegexGroup(regex: RegExp, text: string): string | null {
  const source = String(text || "");
  let match: RegExpExecArray | null = null;
  let lastValue: string | null = null;
  regex.lastIndex = 0;
  while ((match = regex.exec(source)) !== null) {
    const candidate = String(match[1] || "").trim();
    if (candidate) {
      lastValue = candidate;
    }
  }
  regex.lastIndex = 0;
  return lastValue;
}

function extractAssistantScriptContent(text: string): string | null {
  const pythonBlock = extractLastRegexGroup(PYTHON_CODE_BLOCK_REGEX, text);
  if (pythonBlock) {
    return pythonBlock;
  }
  const genericBlock = extractLastRegexGroup(GENERIC_CODE_BLOCK_REGEX, text);
  if (!genericBlock) {
    return null;
  }
  const normalized = genericBlock.trim();
  if (!normalized) {
    return null;
  }
  if (!/(^|\n)\s*(from|import|def|class|if __name__ == [\"'])/m.test(normalized)) {
    return null;
  }
  return normalized;
}

function extractSuggestedScriptPath(text: string): string | null {
  const backtickPath = extractLastRegexGroup(BACKTICK_PYTHON_PATH_REGEX, text);
  if (backtickPath) {
    return backtickPath;
  }
  const plainPath = extractLastRegexGroup(PLAIN_PYTHON_PATH_REGEX, text);
  return plainPath;
}

export type AssistantScriptArtifact = {
  filename: string;
  relativePath: string;
  content: string;
};

export function extractAssistantScriptArtifact(args: {
  text: string;
  intent?: string | null;
  projectPath?: string | null;
}): AssistantScriptArtifact | null {
  const text = String(args.text || "");
  const content = extractAssistantScriptContent(text);
  if (!content) {
    return null;
  }

  const suggestedPath = extractSuggestedScriptPath(text);
  const hasExplicitSaveSignal =
    Boolean(suggestedPath)
    || /recommended script|推荐脚本|save(?:d| it)? under|saving it under|建议将其保存至|建议保存至/i.test(text);
  if (!hasExplicitSaveSignal) {
    return null;
  }

  const target = buildProjectScriptSaveTarget({
    projectPath: args.projectPath,
    intent: args.intent,
    filename: suggestedPath,
  });

  return {
    filename: target.filename,
    relativePath: suggestedPath
      ? normalizeProjectScriptRelativePath(suggestedPath)
      : target.relativePath,
    content: content.endsWith("\n") ? content : `${content}\n`,
  };
}
