<script lang="ts">
  import { auth } from '../lib/auth.svelte';
  import { workflowStore } from '../lib/stores.svelte';

  type AuthMode = 'signin' | 'new_password';

  let mode = $state<AuthMode>('signin');
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
      errorMessage = 'Please enter your email and password.';
      return;
    }
    isSubmitting = true;
    errorMessage = '';
    successMessage = '';

    const res = await auth.login(email, password);
    isSubmitting = false;
    if (res.success) {
      workflowStore.showToast(`Welcome back, ${email}`);
    } else if (res.challenge === 'NEW_PASSWORD_REQUIRED') {
      challengeSession = res.session || '';
      mode = 'new_password';
      errorMessage = '';
      successMessage = 'First-time login detected. Please create your permanent password.';
    } else {
      errorMessage = res.error || 'Invalid email or password. Please try again.';
    }
  }

  async function handleNewPasswordSubmit(e: SubmitEvent) {
    e.preventDefault();
    if (!newPassword || !confirmNewPassword) {
      errorMessage = 'Please enter and confirm your new permanent password.';
      return;
    }
    if (newPassword !== confirmNewPassword) {
      errorMessage = 'Passwords do not match.';
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
      workflowStore.showToast(`Password updated. Welcome, ${email}!`);
    } else {
      errorMessage = res.error || 'Password does not meet complexity requirements.';
    }
  }
</script>

<div class="min-h-screen flex flex-col justify-center items-center bg-[#F4F4F6] dark:bg-[#0c0c0e] px-4 py-12 transition-colors relative">
  <!-- Theme Toggle in Top Right -->
  <div class="absolute top-4 right-4 md:top-6 md:right-6">
    <button
      type="button"
      onclick={() => workflowStore.toggleTheme()}
      title="Toggle Light/Dark Theme"
      aria-label="Toggle Theme"
      class="w-9 h-9 flex items-center justify-center bg-white dark:bg-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-800 dark:text-white border-2 border-neutral-300 dark:border-neutral-700 transition-colors cursor-pointer shadow-xs"
    >
      {#if workflowStore.theme === 'dark'}
        <svg class="w-4 h-4 text-amber-300 fill-current" viewBox="0 0 20 20" aria-hidden="true">
          <path
            fill-rule="evenodd"
            d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
            clip-rule="evenodd"
          />
        </svg>
      {:else}
        <svg class="w-4 h-4 text-neutral-700 fill-current" viewBox="0 0 20 20" aria-hidden="true">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      {/if}
    </button>
  </div>

  <!-- Brand & Card Container -->
  <div class="w-full max-w-md space-y-6">
    <!-- Header Logo & Tagline -->
    <div class="text-center space-y-2">
      <div class="inline-flex items-center gap-1 font-display tracking-tight text-3xl font-black text-neutral-950 dark:text-white">
        <span>INTELLIQ</span>
        <span class="w-3 h-3 bg-[#86BC25] inline-block ml-0.5"></span>
      </div>
      <p class="text-xs uppercase tracking-wider font-extrabold text-neutral-600 dark:text-neutral-400 font-display">
        Requirements & Test Management
      </p>
    </div>

    <!-- Main Auth Card -->
    <div class="bg-white dark:bg-neutral-900 border-2 border-neutral-300 dark:border-neutral-700 shadow-xl p-8 space-y-6">
      <!-- Title -->
      <div class="border-b-2 border-neutral-200 dark:border-neutral-800 pb-3">
        <h2 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white">
          {mode === 'signin' ? 'Sign In' : 'Set Permanent Password'}
        </h2>
      </div>

      <!-- Feedback Messages -->
      {#if errorMessage}
        <div class="p-3 bg-red-50 dark:bg-red-950/60 border border-red-500 text-xs font-bold text-red-700 dark:text-red-300">
          ✕ {errorMessage}
        </div>
      {/if}

      {#if successMessage}
        <div class="p-3 bg-green-50 dark:bg-green-950/60 border border-[#86BC25] text-xs font-bold text-[#4c750b] dark:text-[#86BC25]">
          ✓ {successMessage}
        </div>
      {/if}

      {#if mode === 'signin'}
        <!-- SIGN IN -->
        <form onsubmit={handleSignIn} class="space-y-4">
          <div class="space-y-1.5">
            <label for="signin-email" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 block">
              Work Email
            </label>
            <input
              id="signin-email"
              type="email"
              required
              bind:value={email}
              placeholder="name@company.com"
              class="w-full px-4 py-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <div class="space-y-1.5">
            <label for="signin-password" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 block">
              Password
            </label>
            <input
              id="signin-password"
              type="password"
              required
              bind:value={password}
              placeholder="••••••••••••"
              class="w-full px-4 py-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            class="w-full py-3.5 bg-black text-white hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider transition-colors cursor-pointer disabled:opacity-50 mt-2"
          >
            {isSubmitting ? 'Signing In...' : 'Sign In'}
          </button>
        </form>

      {:else}
        <!-- SET NEW PASSWORD -->
        <form onsubmit={handleNewPasswordSubmit} class="space-y-4">
          <div class="p-3 bg-neutral-100 dark:bg-neutral-800 text-xs text-neutral-700 dark:text-neutral-300 font-medium">
            Please choose a new permanent password to secure your account.
          </div>

          <div class="space-y-1.5">
            <label for="newpwd" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 block">
              New Password
            </label>
            <input
              id="newpwd"
              type="password"
              required
              bind:value={newPassword}
              placeholder="Min 8 characters"
              class="w-full px-4 py-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <div class="space-y-1.5">
            <label for="confirmpwd" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 block">
              Confirm New Password
            </label>
            <input
              id="confirmpwd"
              type="password"
              required
              bind:value={confirmNewPassword}
              placeholder="Re-enter new password"
              class="w-full px-4 py-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-sm font-sans focus:border-black dark:focus:border-[#86BC25] text-neutral-950 dark:text-white"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            class="w-full py-3.5 bg-black text-white hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider transition-colors cursor-pointer disabled:opacity-50 mt-2"
          >
            {isSubmitting ? 'Saving Password...' : 'Save & Sign In'}
          </button>
        </form>
      {/if}
    </div>

    <!-- Footnote -->
    <p class="text-center text-[11px] text-neutral-500 font-medium">
      Secure, private enterprise workspace.
    </p>
  </div>
</div>
