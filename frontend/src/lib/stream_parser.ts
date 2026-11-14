/**
 * Line-Buffered SSE Stream Parser with 60fps requestAnimationFrame Throttling
 * and Markdown Fence Auto-Healing.
 */

export interface ParsedEvent {
  event: string;
  data: string;
}

export class SseStreamParser {
  private buffer = '';
  private currentEvent = 'message';
  private currentData = '';

  /**
   * Feed new text chunk into the line buffer and yield complete SSE events.
   */
  *feed(chunk: string): Generator<ParsedEvent, void, unknown> {
    this.buffer += chunk;
    const lines = this.buffer.split(/\r\n|\r|\n/);
    // Keep incomplete trailing line in buffer
    this.buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        // Empty line indicates event boundary
        if (this.currentData) {
          yield { event: this.currentEvent, data: this.currentData };
          this.currentEvent = 'message';
          this.currentData = '';
        }
        continue;
      }

      // Standard SSE: comment lines start with ':' and must be ignored without resetting state
      if (trimmed.startsWith(':')) {
        continue;
      }

      if (line.startsWith('event:')) {
        let ev = line.slice(6);
        if (ev.startsWith(' ')) ev = ev.slice(1);
        this.currentEvent = ev.trim();
      } else if (line.startsWith('data:')) {
        let dataPart = line.slice(5);
        if (dataPart.startsWith(' ')) dataPart = dataPart.slice(1);
        this.currentData = this.currentData ? `${this.currentData}\n${dataPart}` : dataPart;
      }
    }
  }

  flush(): ParsedEvent | null {
    if (this.currentData) {
      const evt = { event: this.currentEvent, data: this.currentData };
      this.currentEvent = 'message';
      this.currentData = '';
      this.buffer = '';
      return evt;
    }
    if (this.buffer.startsWith('data:')) {
      let data = this.buffer.slice(5);
      if (data.startsWith(' ')) data = data.slice(1);
      this.buffer = '';
      return { event: this.currentEvent || 'message', data };
    }
    this.buffer = '';
    return null;
  }
}

/**
 * Throttles high-velocity token updates via requestAnimationFrame to guarantee 60fps render.
 */
export class RafTokenBatcher {
  private pendingTokens: string[] = [];
  private rafId: number | null = null;
  private onFlush: (flushedText: string) => void;

  constructor(onFlush: (flushedText: string) => void) {
    this.onFlush = onFlush;
  }

  push(token: string) {
    this.pendingTokens.push(token);
    if (this.rafId === null) {
      this.rafId = requestAnimationFrame(() => {
        const combined = this.pendingTokens.join('');
        this.pendingTokens = [];
        this.rafId = null;
        this.onFlush(combined);
      });
    }
  }

  flushImmediate() {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    if (this.pendingTokens.length > 0) {
      const combined = this.pendingTokens.join('');
      this.pendingTokens = [];
      this.onFlush(combined);
    }
  }
}

/**
 * Auto-heals unclosed markdown fences (code blocks, inline code, and structural tables)
 * so partial token streams render safely without corrupting UI layout (ADR-10).
 */
export function healMarkdownFences(markdown: string): string {
  if (!markdown) return '';

  let healed = markdown;

  // 1. Detect and close unclosed code blocks (``` or ~~~)
  const codeBlockMatches = healed.match(/```/g) || [];
  if (codeBlockMatches.length % 2 !== 0) {
    healed = `${healed}\n\`\`\``;
  } else {
    const tildeMatches = healed.match(/~~~/g) || [];
    if (tildeMatches.length % 2 !== 0) {
      healed = `${healed}\n~~~`;
    }
  }

  // 2. Detect and heal unclosed structural markdown tables
  const lines = healed.split(/\r?\n/);
  const lastLine = lines[lines.length - 1];
  const trimmedLast = lastLine.trim();
  if (trimmedLast.startsWith('|') && !trimmedLast.endsWith('|')) {
    healed = `${healed} |`;
  }

  // 3. Heal unclosed single backtick inline code spans outside code blocks
  const isInsideCodeBlock = (healed.match(/```/g) || []).length % 2 !== 0;
  if (!isInsideCodeBlock) {
    const textOutsideFences = healed.replace(/```[\s\S]*?```/g, '');
    const singleBackticks = (textOutsideFences.match(/`/g) || []).length;
    if (singleBackticks % 2 !== 0) {
      healed = `${healed}\``;
    }
  }

  return healed;
}

