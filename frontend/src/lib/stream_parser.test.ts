import { describe, expect, it, vi } from 'vitest';
import { healMarkdownFences, RafTokenBatcher, SseStreamParser } from './stream_parser';

describe('SseStreamParser (ADR-10 & ADR-11)', () => {
  it('correctly processes complete SSE events split across chunks', () => {
    const parser = new SseStreamParser();

    // Chunk 1: partial event and data line
    const events1 = Array.from(parser.feed('event: token\ndata: Hello'));
    expect(events1).toHaveLength(0);

    // Chunk 2: rest of data line and event delimiter
    const events2 = Array.from(parser.feed(' World\n\n'));
    expect(events2).toHaveLength(1);
    expect(events2[0]).toEqual({ event: 'token', data: 'Hello World' });
  });

  it('handles multi-line data events and comments', () => {
    const parser = new SseStreamParser();
    const payload = ': comment ping\nevent: delta\ndata: line 1\ndata: line 2\n\n';
    const events = Array.from(parser.feed(payload));

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ event: 'delta', data: 'line 1\nline 2' });
  });

  it('flushes trailing buffered data', () => {
    const parser = new SseStreamParser();
    Array.from(parser.feed('event: done\ndata: finished'));
    const flushed = parser.flush();

    expect(flushed).toEqual({ event: 'done', data: 'finished' });
  });

  it('processes synthetic high-velocity stream chunks without dropping tokens', () => {
    const parser = new SseStreamParser();
    const tokens = ['The ', 'quick ', 'brown ', 'fox ', 'jumps ', 'over ', 'the ', 'lazy ', 'dog.'];
    const collected: string[] = [];

    // Simulate single characters arriving across multiple packet bursts
    for (const token of tokens) {
      for (const char of token) {
        const events = Array.from(parser.feed(`event: token\ndata: ${char}\n\n`));
        for (const evt of events) {
          collected.push(evt.data);
        }
      }
    }

    expect(collected.join('')).toBe('The quick brown fox jumps over the lazy dog.');
  });
});

describe('healMarkdownFences (ADR-10 Markdown Healing)', () => {
  it('auto-closes unclosed code blocks with triple backticks', () => {
    const broken = 'Here is code:\n```typescript\nconst a = 1;';
    const healed = healMarkdownFences(broken);
    expect(healed).toBe('Here is code:\n```typescript\nconst a = 1;\n```');
  });

  it('leaves already closed code blocks intact', () => {
    const valid = 'Here is code:\n```typescript\nconst a = 1;\n```';
    const healed = healMarkdownFences(valid);
    expect(healed).toBe(valid);
  });

  it('auto-closes unclosed tilde code blocks', () => {
    const broken = '~~~bash\nnpm install';
    const healed = healMarkdownFences(broken);
    expect(healed).toBe('~~~bash\nnpm install\n~~~');
  });

  it('auto-heals unclosed structural markdown tables', () => {
    const brokenTable = '| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2';
    const healed = healMarkdownFences(brokenTable);
    expect(healed).toBe('| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2 |');
  });

  it('auto-closes unclosed inline code spans outside code blocks', () => {
    const brokenInline = 'Please run `npm run check before deploying.';
    const healed = healMarkdownFences(brokenInline);
    expect(healed).toBe('Please run `npm run check before deploying.`');
  });
});

describe('RafTokenBatcher (ADR-10 60fps Batching)', () => {
  it('batches multiple token pushes into immediate flush', () => {
    const flushedTokens: string[] = [];
    const batcher = new RafTokenBatcher((text) => {
      flushedTokens.push(text);
    });

    batcher.push('Alpha');
    batcher.push(' ');
    batcher.push('Beta');
    batcher.flushImmediate();

    expect(flushedTokens).toEqual(['Alpha Beta']);
  });
});
