<script lang="ts">
  import { auth } from '../lib/auth.svelte';
  import { workflowStore } from '../lib/stores.svelte';

  type AuthTab = 'signin' | 'new_password';

  let currentTab = $state<AuthTab>('signin');
  let email = $state('');
  let password = $state('');
  let challengeSession = $state('');
  let newPassword = $state('');
  let confirmNewPassword = $state('');
  let isSubmitting = $state(false);
  let errorMessage = $state('');
  let successMessage = $state('');

  async function handleSignIn(e: SubmitEvent) {
    e.preventDefault();
    if (!email || !password) {
      errorMessage = 'Email and password are required.';
      return;
    }
    isSubmitting = true;
    errorMessage = '';
    successMessage = '';

    const res = await auth.login(email, password);
    isSubmitting = false;
    if (res.success) {
      workflowStore.showToast(`Signed in as ${email}`);
    } else if (res.challenge === 'NEW_PASSWORD_REQUIRED') {
      challengeSession = res.session || '';
      currentTab = 'new_password';
      errorMessage = '';
      successMessage = 'First-time login detected. You must set a new permanent password to continue.';
    } else {
      errorMessage = res.error || 'Authentication failed. Please verify your credentials.';
    }
  }

  async function handleNewPasswordSubmit(e: SubmitEvent) {
    e.preventDefault();
    if (!newPassword || !confirmNewPassword) {
      errorMessage = 'Please enter and confirm your new permanent password.';
      return;
    }
    if (newPassword !== confirmNewPassword) {
      errorMessage = 'Passwords do not match. Please re-enter.';
      return;
    }
    if (newPassword.length < 8) {
      errorMessage = 'Password must be at least 8 characters long.';
      return;
    }

    isSubmitting = true;
    errorMessage = '';
    successMessage = '';

    const res = await auth.completeNewPassword(email, newPassword, challengeSession);
    isSubmitting = false;
    if (res.success) {
      workflowStore.showToast(`Permanent password updated. Signed in as ${email}`);
    } else {
      errorMessage = res.error || 'Failed to set permanent password. Please ensure it contains uppercase, lowercase, number, and symbol.';
    }
  }
</script>

{#if auth.authModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4">
    <div class="bg-white dark:bg-neutral-900 border-2 border-black dark:border-white p-6 max-w-md w-full shadow-2xl space-y-5">
      <div class="flex items-center justify-between pb-3 border-b-2 border-neutral-300 dark:border-neutral-700">
        <div class="flex items-center gap-2">
          <div class="w-3 h-3 bg-[#86BC25]"></div>
          <h3 class="text-sm font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            {currentTab === 'signin' ? 'Sign In' : 'Set Permanent Password'}
          </h3>
        </div>
        <button
          type="button"
          onclick={() => (auth.authModalOpen = false)}
          class="text-neutral-500 hover:text-black dark:hover:text-white font-mono font-bold text-sm cursor-pointer"
        >
          ✕
        </button>
      </div>

      {#if errorMessage}
        <div class="p-3 bg-red-50 dark:bg-red-950/60 border border-red-500 text-xs font-bold text-red-700 dark:text-red-300 break-words">
          ✕ {errorMessage}
        </div>
      {/if}

      {#if successMessage}
        <div class="p-3 bg-green-50 dark:bg-green-950/60 border border-[#86BC25] text-xs font-bold text-[#628f14] dark:text-[#86BC25] break-words">
          ✓ {successMessage}
        </div>
      {/if}

      {#if currentTab === 'signin'}
        <!-- SIGN IN FORM -->
        <form onsubmit={handleSignIn} class="space-y-4">
          <div class="flex flex-col gap-1.5">
            <label for="signin-email" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
              Cognito Email <span class="text-[#628f14] dark:text-[#86BC25] font-black">*</span>
            </label>
            <input
              id="signin-email"
              type="email"
              required
              bind:value={email}
              placeholder="user@example.com"
              class="w-full px-4 py-2.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-400 dark:border-neutral-600 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="signin-password" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
              Password <span class="text-[#628f14] dark:text-[#86BC25] font-black">*</span>
            </label>
            <input
              id="signin-password"
              type="password"
              required
              bind:value={password}
              placeholder="••••••••••••"
              class="w-full px-4 py-2.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-400 dark:border-neutral-600 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <div class="pt-2 flex gap-3">
            <button
              type="button"
              onclick={() => (auth.authModalOpen = false)}
              class="flex-1 py-2.5 bg-neutral-200 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 text-xs font-bold font-display uppercase tracking-wider hover:bg-neutral-300 dark:hover:bg-neutral-700 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              class="flex-1 py-2.5 bg-black text-white hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black font-display uppercase tracking-wider transition-colors cursor-pointer border border-black disabled:opacity-50"
            >
              {isSubmitting ? 'Authenticating...' : 'Sign In'}
            </button>
          </div>
        </form>

      {:else}
        <!-- FORCE CHANGE PASSWORD FORM (FIRST TIME LOGIN) -->
        <form onsubmit={handleNewPasswordSubmit} class="space-y-4">
          <div class="p-2.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-400 dark:border-amber-600 text-[11px] font-bold text-amber-800 dark:text-amber-200">
            ⚠️ Security Notice: An administrator added your account with a temporary password. You must establish a permanent password before continuing.
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="newpwd-email" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
              Email Account
            </label>
            <input
              id="newpwd-email"
              type="email"
              readonly
              bind:value={email}
              class="w-full px-4 py-2 bg-neutral-100 dark:bg-neutral-800 border-2 border-neutral-300 dark:border-neutral-700 text-sm font-mono text-neutral-600 dark:text-neutral-300"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="newpwd-input" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
              New Permanent Password <span class="text-[#628f14] dark:text-[#86BC25] font-black">*</span>
            </label>
            <input
              id="newpwd-input"
              type="password"
              required
              bind:value={newPassword}
              placeholder="Min 8 chars, 1 upper, 1 lower, 1 number, 1 symbol"
              class="w-full px-4 py-2.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-400 dark:border-neutral-600 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="newpwd-confirm" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
              Confirm New Password <span class="text-[#628f14] dark:text-[#86BC25] font-black">*</span>
            </label>
            <input
              id="newpwd-confirm"
              type="password"
              required
              bind:value={confirmNewPassword}
              placeholder="Re-enter permanent password"
              class="w-full px-4 py-2.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-400 dark:border-neutral-600 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <div class="pt-2 flex gap-3">
            <button
              type="button"
              onclick={() => { currentTab = 'signin'; }}
              class="flex-1 py-2.5 bg-neutral-200 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 text-xs font-bold font-display uppercase tracking-wider hover:bg-neutral-300 dark:hover:bg-neutral-700 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              class="flex-1 py-2.5 bg-black text-white hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black font-display uppercase tracking-wider transition-colors cursor-pointer border border-black disabled:opacity-50"
            >
              {isSubmitting ? 'Setting Password...' : 'Save & Sign In'}
            </button>
          </div>
        </form>
      {/if}
    </div>
  </div>
{/if}
