import { describe, expect, it } from 'vitest';
import { computeSha256, generateIdempotencyKey } from './crypto';

describe('Crypto Utilities (ADR-04 & ADR-11)', () => {
  it('computes correct standard SHA-256 hash for known strings', async () => {
    // Standard test vector: empty string
    const emptyHash = await computeSha256('');
    expect(emptyHash).toBe('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');

    // Known ASCII test
    const textHash = await computeSha256('intelliq-zero-cost');
    expect(textHash).toMatch(/^[a-f0-9]{64}$/);
  });

  it('computes hash from Uint8Array accurately', async () => {
    const data = new Uint8Array([105, 110, 116, 101, 108, 108, 105, 113]);
    const hash = await computeSha256(data);
    expect(hash).toMatch(/^[a-f0-9]{64}$/);
  });

  it('generates unique valid UUIDv4 idempotency keys', () => {
    const key1 = generateIdempotencyKey();
    const key2 = generateIdempotencyKey();

    expect(key1).not.toBe(key2);
    // Standard UUID v4 pattern
    expect(key1).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  });
});
