<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { initializeAuth } from '$lib/auth.svelte';

	let { children } = $props();

	import { onMount } from 'svelte';
	onMount(() => {
		initializeAuth();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<meta name="theme-color" content="#16a34a" />
	<meta name="application-name" content="EcoBarter" />
	<meta property="og:site_name" content="EcoBarter" />
	<meta property="og:type" content="website" />
	<meta property="og:image" content="/og-image.png" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:image" content="/og-image.png" />
</svelte:head>

{@render children()}
