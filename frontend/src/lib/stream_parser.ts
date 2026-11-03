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

      if (trimmed.startsWith('event:')) {
        this.currentEvent = trimmed.slice(6).trim();
      } else if (trimmed.startsWith('data:')) {
        const dataPart = trimmed.slice(5).trim();
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
      const data = this.buffer.slice(5).trim();
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
 * Auto-heals unclosed markdown code blocks so partial streams render cleanly without breaking syntax.
 */
export function healMarkdownFences(markdown: string): string {
  const codeBlockMatches = markdown.match(/```/g);
  if (codeBlockMatches && codeBlockMatches.length % 2 !== 0) {
    return `${markdown}\n\`\`\``;
  }
  return markdown;
}

