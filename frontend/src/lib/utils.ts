import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const UNICODE_ESCAPE_PATTERN = /\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})/g;
const SURROGATE_PAIR_ESCAPE_PATTERN = /\\u([dD][89ABab][0-9a-fA-F]{2})\\u([dD][C-Fc-f][0-9a-fA-F]{2})/g;

export function decodeEscapedUnicode(value: string): string {
  if (!value.includes("\\") || !/\\u(?:\{[0-9a-fA-F]{1,6}\}|[0-9a-fA-F]{4})|\\x[0-9a-fA-F]{2}/.test(value)) {
    return value;
  }

  const withSurrogatesDecoded = value.replace(SURROGATE_PAIR_ESCAPE_PATTERN, (match, high, low) => {
    const highCode = Number.parseInt(high, 16);
    const lowCode = Number.parseInt(low, 16);
    const codePoint = ((highCode - 0xd800) << 10) + (lowCode - 0xdc00) + 0x10000;
    try {
      return String.fromCodePoint(codePoint);
    } catch {
      return match;
    }
  });

  return withSurrogatesDecoded.replace(UNICODE_ESCAPE_PATTERN, (match, braceHex, unicodeHex, byteHex) => {
    const rawCodePoint = braceHex ?? unicodeHex ?? byteHex;
    if (!rawCodePoint) {
      return match;
    }

    const codePoint = Number.parseInt(rawCodePoint, 16);
    if (!Number.isFinite(codePoint)) {
      return match;
    }

    try {
      return String.fromCodePoint(codePoint);
    } catch {
      return match;
    }
  });
}

export function decodeEscapedUnicodeDeep<T>(value: T): T {
  const seen = new WeakMap<object, unknown>();

  const walk = (current: unknown): unknown => {
    if (typeof current === "string") {
      return decodeEscapedUnicode(current);
    }
    if (Array.isArray(current)) {
      return current.map((entry) => walk(entry));
    }
    if (!current || typeof current !== "object") {
      return current;
    }
    if (seen.has(current)) {
      return seen.get(current);
    }

    const result: Record<string, unknown> = {};
    seen.set(current, result);
    Object.entries(current).forEach(([key, entry]) => {
      result[key] = walk(entry);
    });
    return result;
  };

  return walk(value) as T;
}
