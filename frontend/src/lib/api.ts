/**
 * High-Performance API Client with Native Web Crypto SHA-256 Hashing,
 * SigV4 OAC Compatibility, SSE ReadableStream Processing, and S3 Presigned I/O.
 */
import { auth } from './auth.svelte';
import { computeSha256, generateIdempotencyKey } from './crypto';
import { RafTokenBatcher, SseStreamParser } from './stream_parser';
import type { Attachment, WorkflowRequest, WorkflowState } from './types';

export interface StreamCallbacks {
  onToken?: (delta: string) => void;
  onState?: (state: WorkflowState) => void;
  onError?: (err: Error) => void;
  onComplete?: () => void;
  onRateLimit?: (retryAfterSeconds: number) => void;
}

export class ApiClient {
  private activeAbortController: AbortController | null = null;

  cancelActiveStream() {
    if (this.activeAbortController) {
      this.activeAbortController.abort();
      this.activeAbortController = null;
    }
  }

  /**
   * Executes an SSE streaming request to /api/stream/workflow with OAC SigV4 hashing.
   */
  async streamWorkflow(
    req: WorkflowRequest,
    callbacks: StreamCallbacks
  ): Promise<void> {
    this.cancelActiveStream();
    this.activeAbortController = new AbortController();

    const token = await auth.getValidToken();
    const serializedBody = JSON.stringify(req);
    const contentSha256 = await computeSha256(serializedBody);
    const idempotencyKey = generateIdempotencyKey();

    const parser = new SseStreamParser();
    const batcher = new RafTokenBatcher((flushedTokens) => {
      callbacks.onToken?.(flushedTokens);
    });

    try {
      const response = await fetch('/api/stream/workflow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'x-amz-content-sha256': contentSha256,
          'x-idempotency-key': idempotencyKey,
        },
        body: serializedBody,
        signal: this.activeAbortController.signal,
      });

      if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('Retry-After') || '60', 10);
        callbacks.onRateLimit?.(retryAfter);
        throw new Error(`Rate limit exceeded. Lockout active for ${retryAfter}s.`);
      }

      if (response.status === 401) {
        auth.logout();
        auth.authModalOpen = true;
        throw new Error('Authentication session expired. Please sign in again.');
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Stream error (HTTP ${response.status}): ${errorText}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported or empty body');
      }

      // ADR-07: Stream consumption using TextDecoderStream and reader
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          if (value) {
            for (const eventItem of parser.feed(value)) {
              if (eventItem.event === 'token') {
                try {
                  const parsed = JSON.parse(eventItem.data);
                  batcher.push(parsed.chunk || '');
                } catch {
                  batcher.push(eventItem.data);
                }
              } else if (eventItem.event === 'state') {
                batcher.flushImmediate();
                try {
                  const stateObj = JSON.parse(eventItem.data);
                  callbacks.onState?.(stateObj);
                } catch (e) {
                  console.warn('Failed to parse state frame:', e);
                }
              } else if (eventItem.event === 'error') {
                batcher.flushImmediate();
                let errMsg = eventItem.data;
                try {
                  const errObj = JSON.parse(eventItem.data);
                  errMsg = errObj.error || eventItem.data;
                } catch {
                  // Raw error string
                }
                callbacks.onError?.(new Error(errMsg));
              } else if (eventItem.event === 'done') {
                batcher.flushImmediate();
                callbacks.onComplete?.();
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.info('Stream cleanly aborted by user.');
      } else {
        callbacks.onError?.(err);
      }
    } finally {
      batcher.flushImmediate();
      this.activeAbortController = null;
    }
  }

  /**
   * Uploads file directly to S3 via Presigned PUT with reactive progress tracking.
   */
  async uploadFileToS3(
    file: File,
    sessionIdOrProgress?: string | ((percent: number) => void),
    onProgressParam?: (percent: number) => void
  ): Promise<Attachment> {
    let sessionId: string | undefined = undefined;
    let onProgress = onProgressParam;
    if (typeof sessionIdOrProgress === 'function') {
      onProgress = sessionIdOrProgress;
    } else if (typeof sessionIdOrProgress === 'string') {
      sessionId = sessionIdOrProgress;
    }

    const token = await auth.getValidToken();
    if (!token) {
      auth.authModalOpen = true;
      throw new Error('Authentication required: Please sign in with AWS Cognito before uploading files to S3.');
    }

    // 1. Determine accurate MIME type
    const ext = file.name.split('.').pop()?.toLowerCase();
    let mimeType = file.type || '';
    if (!mimeType || mimeType === 'application/octet-stream') {
      switch (ext) {
        case 'txt': mimeType = 'text/plain'; break;
        case 'md': mimeType = 'text/markdown'; break;
        case 'csv': mimeType = 'text/csv'; break;
        case 'json': mimeType = 'application/json'; break;
        case 'vtt': mimeType = 'text/vtt'; break;
        case 'pdf': mimeType = 'application/pdf'; break;
        case 'png': mimeType = 'image/png'; break;
        case 'jpg':
        case 'jpeg': mimeType = 'image/jpeg'; break;
        case 'webp': mimeType = 'image/webp'; break;
        case 'docx': mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'; break;
        default: mimeType = 'application/octet-stream'; break;
      }
    }

    const presignReq = JSON.stringify({
      filename: file.name,
      mime_type: mimeType,
      session_id: sessionId,
    });
    const presignSha = await computeSha256(presignReq);

    const presignRes = await fetch('/api/upload/presign', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'x-amz-content-sha256': presignSha,
      },
      body: presignReq,
    });

    if (!presignRes.ok) {
      const errData = await presignRes.json().catch(() => ({ error: 'Upload presign failed' }));
      if (presignRes.status === 401) {
        auth.authModalOpen = true;
      }
      throw new Error(errData.error || `Presign request failed with status ${presignRes.status}`);
    }

    const { upload_url, s3_key } = await presignRes.json();

    // 2. Direct S3 upload using XHR for reliable onprogress
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('PUT', upload_url);
      xhr.setRequestHeader('Content-Type', mimeType);

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (evt) => {
          if (evt.lengthComputable) {
            onProgress(Math.round((evt.loaded / evt.total) * 100));
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`S3 upload failed with status ${xhr.status}: ${xhr.statusText}`));
        }
      };

      xhr.onerror = () => reject(new Error(`S3 upload network error (status ${xhr.status || 'aborted'}). Please verify CORS or network connectivity.`));
      xhr.send(file);
    });

    // 3. Directly extract text for text-based documentation
    let textContent: string | undefined = undefined;
    const isTextDoc = mimeType.startsWith('text/') || ['txt', 'md', 'csv', 'json', 'vtt', 'tsv', 'log'].includes(ext || '');
    if (file.size <= 5 * 1024 * 1024 && isTextDoc) {
      try {
        textContent = await file.text();
      } catch (e) {
        console.warn('Could not read text content directly:', e);
      }
    }

    // 4. Fast chunked base64 extraction for multi-modal (<5MB)
    let base64Data: string | undefined = undefined;
    if (file.size <= 5 * 1024 * 1024) {
      try {
        const buffer = await file.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = '';
        const len = bytes.byteLength;
        const chunkSize = 0x8000; // 32KB chunking
        for (let i = 0; i < len; i += chunkSize) {
          binary += String.fromCharCode.apply(
            null,
            bytes.subarray(i, Math.min(i + chunkSize, len)) as any
          );
        }
        base64Data = btoa(binary);
      } catch (e) {
        console.warn('Could not read base64 inline data:', e);
      }
    }

    return {
      id: crypto.randomUUID(),
      name: file.name,
      mime_type: mimeType,
      s3_key: s3_key,
      size_bytes: file.size,
      base64_data: base64Data,
      text_content: textContent,
    };
  }

  /**
   * Fetches full workflow state, decompressing offloaded gzip payloads if necessary.
   */
  async getWorkflow(workflowId: string): Promise<WorkflowState> {
    const token = await auth.getValidToken();
    const res = await fetch(`/api/workflows/${workflowId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      throw new Error(`Failed to load workflow ${workflowId}`);
    }

    // Check if response is gzipped S3 artifact
    const contentEncoding = res.headers.get('content-encoding');
    if (contentEncoding === 'gzip' && res.body && 'DecompressionStream' in window) {
      const decompressedStream = res.body.pipeThrough(new (window as any).DecompressionStream('gzip'));
      const text = await new Response(decompressedStream).text();
      return JSON.parse(text);
    }

    return await res.json();
  }

  /**
   * Retrieves list of stored sessions for the authenticated user.
   */
  async listWorkflows(): Promise<any[]> {
    const token = await auth.getValidToken();
    const res = await fetch('/api/workflows', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.workflows || [];
  }

  /**
   * Generates and triggers download of JIRA-compatible Excel package.
   */
  async exportJiraExcel(workflowId: string): Promise<{ filename: string; size_bytes: number }> {
    const token = await auth.getValidToken();
    const idempotencyKey = generateIdempotencyKey();
    const emptySha = await computeSha256('');

    const res = await fetch(`/api/workflows/${workflowId}/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'x-amz-content-sha256': emptySha,
        'x-idempotency-key': idempotencyKey,
      },
      body: JSON.stringify({}),
    });

    if (!res.ok) {
      throw new Error(`Failed to generate JIRA Excel: ${await res.text()}`);
    }

    const data = await res.json();
    const binary = atob(data.content_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    const blob = new Blob([bytes], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = data.filename || 'intelliq_jira_package.xlsx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    return { filename: data.filename, size_bytes: data.size_bytes };
  }
}

export const api = new ApiClient();

