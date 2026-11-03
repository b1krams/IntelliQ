<script lang="ts">
  import { api } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { workflowStore } from '../lib/stores.svelte';
  import type { Attachment } from '../lib/types';

  let isUploading = $state(false);
  let uploadProgress = $state(0);
  let fileInputRef: HTMLInputElement | null = null;
  let isDragOver = $state(false);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;

    if (!auth.isAuthenticated) {
      workflowStore.showToast('Please sign in to upload documents.', true);
      return;
    }

    const file = files[0];

    if (file.size > 50 * 1024 * 1024) {
      workflowStore.showToast('File exceeds 50MB size limit.', true);
      return;
    }

    isUploading = true;
    uploadProgress = 0;
    try {
      const att = await api.uploadFileToS3(file, (p) => {
        uploadProgress = p;
      });
      workflowStore.stagedAttachments = [...workflowStore.stagedAttachments, att];
      workflowStore.showToast(`Uploaded ${file.name}`);
    } catch (err: any) {
      workflowStore.showToast(`Upload failed: ${err.message}`, true);
    } finally {
      isUploading = false;
      uploadProgress = 0;
      if (fileInputRef) fileInputRef.value = '';
    }
  }

  function removeAttachment(id: string) {
    workflowStore.stagedAttachments = workflowStore.stagedAttachments.filter((a) => a.id !== id);
    workflowStore.showToast('Document removed.');
  }

  function addSampleTranscript() {
    const sampleText = `=== DISCOVERY MEETING TRANSCRIPT ===
Project: OmniLogistics Fleet Telematics & Dynamic Route Optimization
Participants:
- Rachel Vance (VP of Supply Chain & Fleet Operations)
- Dave Kowalski (Fleet Logistics Director)
- Priya Patel (Lead Cloud Architect)

Rachel: Our dispatchers currently face major delivery delays because route calculations do not incorporate real-time highway congestion and weather disruptions. We have 450 regional delivery vans across 12 distribution centers.
Dave: Right now, dispatch assigns static routes at 5:00 AM. When a driver encounters an accident on I-95, they have no automatic rerouting. We need continuous GPS telemetry from OBD-II vehicle dongles streaming every 15 seconds.
Priya: We should ingest the telemetry into a real-time event pipeline and calculate dynamic ETAs.
Rachel: Exactly. And customers must receive an SMS alert when the vehicle is within 10 minutes of their delivery address with a live tracking link.
Key Requirements:
1. Vehicle OBD-II GPS telemetry ingestion (sub-15s interval, geofence enter/exit events).
2. Dynamic route recalculation engine prioritizing fuel efficiency and delivery time windows.
3. Customer SMS notification dispatch with expiring secure tracking web view.
4. Driver mobile tablet app for digital proof of delivery (signature + photo capture).
5. Strict regulatory compliance with FMCSA Hours of Service (HOS) rules and tamper-proof audit trail.`;

    const sampleAttachment: Attachment = {
      id: crypto.randomUUID(),
      name: 'OmniLogistics_Discovery_Transcript.txt',
      mime_type: 'text/plain',
      s3_key: 'uploads/sample_discovery_notes.txt',
      size_bytes: sampleText.length,
      text_content: sampleText,
      base64_data: btoa(sampleText),
    };
    workflowStore.stagedAttachments = [...workflowStore.stagedAttachments, sampleAttachment];
    workflowStore.showToast('Sample Discovery Notes added.');
  }
</script>

<div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 space-y-4 shadow-xs">
  <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
    <h4 class="text-xs font-extrabold font-display uppercase tracking-wider text-neutral-950 dark:text-white flex items-center gap-2">
      <span class="w-2.5 h-2.5 bg-neutral-950 dark:bg-white inline-block"></span>
      Project Documents
    </h4>
    <button
      type="button"
      onclick={addSampleTranscript}
      class="text-xs font-bold text-[#4c750b] dark:text-[#86BC25] hover:underline cursor-pointer"
    >
      + Add Sample Notes
    </button>
  </div>

  <p class="text-xs text-neutral-600 dark:text-neutral-400">
    Upload meeting recordings, interview transcripts, architectural diagrams, or specification documents.
  </p>

  <!-- Dropzone -->
  <div
    role="button"
    tabindex="0"
    class="p-6 border-2 border-dashed {isDragOver
      ? 'border-[#86BC25] bg-emerald-50/20'
      : 'border-neutral-400 dark:border-neutral-600'} hover:border-black dark:hover:border-[#86BC25] bg-neutral-50 dark:bg-neutral-950 text-center transition-colors cursor-pointer select-none"
    ondragover={(e) => {
      e.preventDefault();
      isDragOver = true;
    }}
    ondragleave={() => (isDragOver = false)}
    ondrop={(e) => {
      e.preventDefault();
      isDragOver = false;
      handleFiles(e.dataTransfer?.files || null);
    }}
    onclick={() => fileInputRef?.click()}
    onkeydown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') fileInputRef?.click();
    }}
  >
    <input
      type="file"
      bind:this={fileInputRef}
      class="hidden"
      accept=".txt,.vtt,.docx,.pdf,.png,.jpg,.jpeg,.csv"
      onchange={(e) => handleFiles((e.target as HTMLInputElement).files)}
    />
    <div class="text-2xl mb-1 text-neutral-700 dark:text-neutral-300 font-black">⬆</div>
    <p class="text-xs font-bold text-neutral-900 dark:text-neutral-100 font-display">
      Drag & drop files here, or <span class="text-[#4c750b] dark:text-[#86BC25] underline">browse files</span>
    </p>
    <p class="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
      Supported: TXT, PDF, PNG, JPG, DOCX (Max 50MB)
    </p>
  </div>

  <!-- Upload Progress Bar -->
  {#if isUploading}
    <div class="space-y-1.5 pt-1">
      <div class="flex justify-between text-xs font-bold">
        <span>Uploading document...</span>
        <span>{uploadProgress}%</span>
      </div>
      <div class="w-full h-2 bg-neutral-200 dark:bg-neutral-800 border border-neutral-400">
        <div class="bg-[#86BC25] h-full transition-all duration-150" style="width: {uploadProgress}%"></div>
      </div>
    </div>
  {/if}

  <!-- Staged Upload File List -->
  {#if workflowStore.stagedAttachments.length > 0}
    <div class="space-y-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
      <span class="text-xs font-bold text-neutral-600 dark:text-neutral-400 uppercase block">
        Attached Files ({workflowStore.stagedAttachments.length})
      </span>
      {#each workflowStore.stagedAttachments as att}
        <div class="flex items-center justify-between p-2.5 bg-neutral-100 dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700">
          <div class="flex items-center gap-2 min-w-0">
            <div class="w-6 h-6 bg-black text-white dark:bg-white dark:text-black font-bold text-[10px] flex items-center justify-center shrink-0">
              {att.name.split('.').pop()?.toUpperCase() || 'DOC'}
            </div>
            <div class="min-w-0">
              <p class="text-xs font-bold text-neutral-900 dark:text-neutral-100 truncate">
                {att.name}
              </p>
              <p class="text-[10px] text-neutral-500 dark:text-neutral-400">
                {(att.size_bytes ? att.size_bytes / 1024 : 12).toFixed(1)} KB
              </p>
            </div>
          </div>
          <button
            type="button"
            onclick={() => removeAttachment(att.id)}
            aria-label="Remove attached file"
            class="text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-1 font-bold text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>
