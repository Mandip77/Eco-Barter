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

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
{@render children()}
