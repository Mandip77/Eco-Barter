<script lang="ts">
  import { authState, login } from "$lib/auth.svelte";
  import { goto } from "$app/navigation";

  let isLogin = $state(true);
  let email = $state("");
  let password = $state("");
  let username = $state("");
  let errorMsg = $state("");
  let loading = $state(false);

  // If already logged in, redirect
  $effect(() => {
    if (authState.user) {
      goto("/");
    }
  });

  async function handleSubmit(e: Event) {
    e.preventDefault();
    errorMsg = "";

    if (!email || !password || (!isLogin && !username)) {
      errorMsg = "Please fill out all fields.";
      return;
    }

    loading = true;
    try {
      if (isLogin) {
        const resp = await fetch("/api/v1/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        if (!resp.ok) {
          const dt = await resp.json();
          throw new Error(dt.detail || "Failed to login");
        }

        const data = await resp.json();
        login(data.access_token);
      } else {
        const resp = await fetch("/api/v1/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, username }),
        });

        if (!resp.ok) {
          const dt = await resp.json();
          throw new Error(dt.detail || "Failed to register");
        }

        // Auto login after register
        const loginResp = await fetch("/api/v1/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        if (loginResp.ok) {
          const data = await loginResp.json();
          login(data.access_token);
        }
      }
    } catch (e: any) {
      errorMsg = e.message || "An error occurred";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Sign In - EcoBarter</title>
  <meta
    name="description"
    content="Sign in or create your free EcoBarter account to start trading sustainably - no money needed."
  />
  <meta property="og:title" content="Sign In - EcoBarter" />
  <meta
    property="og:description"
    content="Join EcoBarter - the sustainable marketplace where you trade what you have for what you need."
  />
  <meta name="twitter:title" content="Sign In - EcoBarter" />
  <meta
    name="twitter:description"
    content="Join EcoBarter and start trading sustainably today. Free to join."
  />
</svelte:head>

<div
  class="min-h-screen flex items-center justify-center p-6 relative overflow-hidden"
>
  <!-- Decorative background elements -->
  <div
    class="absolute -top-24 -left-24 w-96 h-96 bg-green-500/10 rounded-full blur-3xl"
  ></div>
  <div
    class="absolute -bottom-24 -right-24 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl"
  ></div>

  <div class="w-full max-w-lg relative z-10">
    <div class="text-center mb-12">
      <button
        class="text-5xl font-black tracking-tighter text-[var(--accent)] cursor-pointer hover:scale-105 transition-transform bg-transparent border-none"
        onclick={() => goto("/")}
      >
        EcoBarter
      </button>
      <p class="text-[var(--text2)] mt-4 text-lg font-medium opacity-80">
        The future of sustainable trading
      </p>
    </div>

    <div
      class="bg-white/80 backdrop-blur-xl rounded-[32px] p-10 md:p-12 border border-white shadow-[var(--shadow-premium)]"
    >
      <h2
        class="text-3xl font-extrabold mb-10 text-[var(--text)] text-center tracking-tight"
      >
        {isLogin ? "Welcome back" : "Join the movement"}
      </h2>

      {#if errorMsg}
        <div
          class="bg-red-500/10 border border-red-500/20 text-red-600 px-5 py-4 rounded-xl mb-8 text-sm flex items-center gap-3 animate-in fade-in slide-in-from-top-2"
        >
          <svg
            class="w-5 h-5 shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            ><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            ></path></svg
          >
          {errorMsg}
        </div>
      {/if}

      <form onsubmit={handleSubmit} class="flex flex-col gap-6">
        {#if !isLogin}
          <div class="flex flex-col gap-2.5">
            <label
              class="text-xs font-bold uppercase tracking-widest text-[var(--text3)] ml-1"
              for="username">Username</label
            >
            <input
              bind:value={username}
              type="text"
              id="username"
              placeholder="ecowarrior23"
              class="w-full bg-[var(--surface2)]/50 border border-[var(--border)] rounded-2xl px-5 py-4 text-[var(--text)] focus:outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent)]/5 transition-all placeholder:text-[var(--text3)]"
            />
          </div>
        {/if}

        <div class="flex flex-col gap-2.5">
          <label
            class="text-xs font-bold uppercase tracking-widest text-[var(--text3)] ml-1"
            for="email">Email Address</label
          >
          <input
            bind:value={email}
            type="email"
            id="email"
            placeholder="you@example.com"
            class="w-full bg-[var(--surface2)]/50 border border-[var(--border)] rounded-2xl px-5 py-4 text-[var(--text)] focus:outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent)]/5 transition-all placeholder:text-[var(--text3)]"
          />
        </div>

        <div class="flex flex-col gap-2.5">
          <div class="flex items-center justify-between">
            <label
              class="text-xs font-bold uppercase tracking-widest text-[var(--text3)] ml-1"
              for="password">Password</label
            >
          </div>
          <input
            bind:value={password}
            type="password"
            id="password"
            placeholder="••••••••"
            class="w-full bg-[var(--surface2)]/50 border border-[var(--border)] rounded-2xl px-5 py-4 text-[var(--text)] focus:outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent)]/5 transition-all placeholder:text-[var(--text3)]"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          class="w-full bg-[var(--accent)] hover:bg-[var(--accent2)] text-white font-bold px-6 py-4.5 rounded-2xl shadow-lg shadow-green-500/20 transition-all hover:-translate-y-0.5 active:translate-y-0 mt-4 disabled:opacity-70 flex items-center justify-center gap-2 text-lg"
        >
          {#if loading}
            <svg
              class="animate-spin h-5 w-5 text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              ><circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle><path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path></svg
            >
            Processing...
          {:else}
            {isLogin ? "Sign In" : "Create Account"}
          {/if}
        </button>
      </form>

      <div class="mt-10 text-center text-base text-[var(--text2)] font-medium">
        {isLogin ? "Don't have an account?" : "Already have an account?"}
        <button
          onclick={() => {
            isLogin = !isLogin;
            errorMsg = "";
          }}
          class="font-bold text-[var(--accent)] hover:text-[var(--accent2)] ml-2 transition-colors decoration-2 hover:underline underline-offset-4"
        >
          {isLogin ? "Join now" : "Log in here"}
        </button>
      </div>
    </div>
  </div>
</div>
