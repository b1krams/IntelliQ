/**
 * Native Web Crypto API SHA-256 computation helper.
 * Strictly satisfies CloudFront OAC SigV4 x-amz-content-sha256 header requirements.
 */

export async function computeSha256(data: string | ArrayBuffer | Uint8Array): Promise<string> {
  let buffer: ArrayBuffer;
  if (typeof data === 'string') {
    buffer = new TextEncoder().encode(data).buffer as ArrayBuffer;
  } else if (data instanceof Uint8Array) {
    buffer = data.buffer as ArrayBuffer;
  } else {
    buffer = data;
  }

  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function generateIdempotencyKey(): string {
  return crypto.randomUUID();
}

