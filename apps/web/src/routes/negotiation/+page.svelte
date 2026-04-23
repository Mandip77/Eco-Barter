<script lang="ts">
    import { onMount } from 'svelte';
    import { Centrifuge } from 'centrifuge';
    import QRCode from 'qrcode';
    import { authState } from '$lib/auth.svelte';

    let connected = $state(false);
    let tradeProposals = $state<any[]>([]);
    let currentUser = $derived(authState.user?.username || null);

    let showScanModal = $state(false);
    let qrDataUrl = $state('');
    let activeTrade = $state<any>(null);
    let verifyNode = $state('');
    let mockScanValue = $state('');
    let isVerifying = $state(false);
    let toastMsg = $state('');
    let toastType = $state('');

    function showToast(msg: string, type: string = '') {
        toastMsg = msg;
        toastType = type;
        setTimeout(() => { toastMsg = ''; toastType = ''; }, 4000);
    }

    onMount(async () => {
        const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const centrifuge = new Centrifuge(`${wsProto}//${window.location.host}/connection/websocket`);

        centrifuge.on('connected', () => connected = true);
        centrifuge.on('disconnected', () => connected = false);

        const sub = centrifuge.newSubscription('trade_hub:proposals');
        sub.on('publication', (ctx) => {
            // Update an existing proposal or add a new one
            const updated = ctx.data.proposal;
            const index = tradeProposals.findIndex(p => p.ID === updated.ID);
            if(index > -1) {
                tradeProposals[index] = updated;
            } else {
                tradeProposals = [...tradeProposals, updated];
            }
        });

        sub.subscribe();
        centrifuge.connect();

        // Fetch initial state
        try {
            const resp = await fetch('/api/v1/trade/proposals', {
                headers: {
                    'Authorization': `Bearer ${authState.token}`
                }
            });
            if (resp.ok) {
                tradeProposals = await resp.json();
            }
        } catch(e) {
            console.error("Could not fetch trace proposals:", e);
        }
    });

    const triggerQR = async (trade: any, targetIdentity: string) => {
        try {
            activeTrade = trade;
            verifyNode = targetIdentity;
            const payload = JSON.stringify({ trade_id: trade.ID, target_user: targetIdentity });
            qrDataUrl = await QRCode.toDataURL(payload, { 
                color: { dark: '#042f2e', light: '#f0fdf4' },
                margin: 2, scale: 8
            });
            showScanModal = true;
        } catch (e) {
            console.error('Failed to generate QR:', e);
        }
    };

    const submitMockScan = async () => {
        isVerifying = true;
        try {
            const parsed = JSON.parse(mockScanValue || '{}');
            const resp = await fetch('/api/v1/trade/verify', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authState.token}`
                },
                body: JSON.stringify(parsed)
            });
            if (resp.ok) {
                showToast('Hand-off verified! Item exchange confirmed.', 'success');
                showScanModal = false;
                mockScanValue = '';
            } else {
                showToast('Scan rejected — invalid trade parameters.', 'error');
            }
        } catch (e) {
            showToast('Invalid QR code format. Please try again.', 'error');
        }
        isVerifying = false;
    };
</script>

<svelte:head>
    <title>Trade Loop Coordinator — EcoBarter</title>
    <meta name="description" content="Coordinate, verify, and lock your EcoBarter circular trade exchanges with QR-based physical handoff confirmation." />
    <meta property="og:title" content="Trade Loop Coordinator — EcoBarter" />
    <meta property="og:description" content="Coordinate K-way circular trade loops and verify physical item exchanges on EcoBarter." />
</svelte:head>

<div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-6 md:p-12">
    <header class="flex justify-between items-center mb-12">
        <div>
            <h1 class="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 to-teal-200 bg-clip-text text-transparent">
                Negotiation Matrix
            </h1>
            <p class="text-slate-400 mt-2 font-medium">Coordinate, verify, and lock physical exchanges.</p>
        </div>
        
        <div class="flex items-center gap-6">
            <div class="flex items-center gap-3 bg-slate-900 px-4 py-2 rounded-full border border-slate-800">
                <div class="w-3 h-3 rounded-full {connected ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' : 'bg-rose-500'} animate-pulse"></div>
                <span class="text-sm font-semibold tracking-wide uppercase text-slate-300">Live Sync</span>
            </div>
            
            <div class="flex items-center gap-2">
                {#if currentUser}
                    <span class="text-sm font-medium text-emerald-400">Authenticated as {currentUser}</span>
                {:else}
                    <a href="/login" class="text-sm border border-emerald-500 text-emerald-400 px-3 py-1.5 rounded-lg hover:bg-emerald-500/10 transition-colors font-semibold">Log In First</a>
                {/if}
            </div>
        </div>
    </header>

    <main class="grid gap-6">
        {#if tradeProposals.length === 0}
            <div class="p-12 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/50 backdrop-blur-sm">
                <div class="text-slate-500 font-medium">No live trade proposals found. Wait for the engine to match a K=3 loop.</div>
            </div>
        {:else}
            {#each tradeProposals as trade}
                <div class="group bg-slate-900 border border-slate-800 rounded-2xl p-6 transition-all hover:border-emerald-500/50 hover:shadow-[0_0_30px_rgba(16,185,129,0.05)]">
                    
                    <div class="flex justify-between items-start mb-6">
                        <div class="flex items-center gap-3">
                            <span class="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-bold uppercase tracking-wider rounded-full border border-emerald-500/20">Loop #{trade.ID}</span>
                            <span class="text-sm text-slate-500 font-mono">Status: <span class="capitalize text-slate-300">{trade.status || 'Pending'}</span></span>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <!-- Node A -->
                        <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col justify-between {currentUser === trade.user_a ? 'ring-1 ring-emerald-500/30' : ''}">
                            <div>
                                <div class="text-sm font-medium text-slate-500 mb-1">Owner: {trade.user_a}</div>
                                <div class="text-lg font-bold text-slate-200">{trade.item_a}</div>
                            </div>
                            <div class="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center">
                                <span class="text-xs font-bold uppercase {trade.verified_a ? 'text-emerald-400' : 'text-slate-600'} flex items-center gap-1">
                                    {trade.verified_a ? '✓ Verified' : '⌚ Awaiting Handoff'}
                                </span>
                                {#if currentUser === trade.user_a && !trade.verified_a}
                                    <button onclick={() => triggerQR(trade, trade.user_a)} class="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg transition-colors font-semibold">Generate Tag</button>
                                {/if}
                            </div>
                        </div>

                        <!-- Node B -->
                        <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col justify-between {currentUser === trade.user_b ? 'ring-1 ring-emerald-500/30' : ''}">
                            <div>
                                <div class="text-sm font-medium text-slate-500 mb-1">Owner: {trade.user_b}</div>
                                <div class="text-lg font-bold text-slate-200">{trade.item_b}</div>
                            </div>
                            <div class="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center">
                                <span class="text-xs font-bold uppercase {trade.verified_b ? 'text-emerald-400' : 'text-slate-600'} flex items-center gap-1">
                                    {trade.verified_b ? '✓ Verified' : '⌚ Awaiting Handoff'}
                                </span>
                                {#if currentUser === trade.user_b && !trade.verified_b}
                                    <button onclick={() => triggerQR(trade, trade.user_b)} class="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg transition-colors font-semibold">Generate Tag</button>
                                {/if}
                            </div>
                        </div>

                        <!-- Node C -->
                        <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col justify-between {currentUser === trade.user_c ? 'ring-1 ring-emerald-500/30' : ''}">
                            <div>
                                <div class="text-sm font-medium text-slate-500 mb-1">Owner: {trade.user_c}</div>
                                <div class="text-lg font-bold text-slate-200">{trade.item_c}</div>
                            </div>
                            <div class="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center">
                                <span class="text-xs font-bold uppercase {trade.verified_c ? 'text-emerald-400' : 'text-slate-600'} flex items-center gap-1">
                                    {trade.verified_c ? '✓ Verified' : '⌚ Awaiting Handoff'}
                                </span>
                                {#if currentUser === trade.user_c && !trade.verified_c}
                                    <button onclick={() => triggerQR(trade, trade.user_c)} class="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg transition-colors font-semibold">Generate Tag</button>
                                {/if}
                            </div>
                        </div>
                    </div>
                </div>
            {/each}
        {/if}
    </main>
</div>

<!-- Modal -->
{#if showScanModal}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div class="w-full max-w-md bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl relative">
            <button onclick={() => showScanModal = false} aria-label="Close" class="absolute top-4 right-4 text-slate-400 hover:text-slate-200 transition-colors">
                <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
            
            <h2 class="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-teal-300 mb-6 text-center">Scan Validated Exchange</h2>
            
            <div class="flex justify-center mb-6">
                <!-- QR Code Display -->
                <div class="p-3 bg-white rounded-2xl shadow-[0_0_40px_rgba(16,185,129,0.15)]">
                    <img src={qrDataUrl} alt="QR Code" class="w-48 h-48" />
                </div>
            </div>

            <p class="text-sm text-center text-slate-400 mb-6 leading-relaxed">
                Provide this QR code to the recipient when you physically hand off your item.
            </p>

            <div class="mt-8 pt-8 border-t border-slate-800">
                <p class="text-xs text-slate-500 uppercase font-bold tracking-widest text-center mb-4">Webcam Prototype Fallback</p>
                <div class="flex flex-col gap-3">
                    <input type="text" bind:value={mockScanValue} placeholder={`{"trade_id": ${activeTrade?.ID}, "target_user": "${verifyNode}"}`} class="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-sm font-mono text-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/50" />
                    <button onclick={submitMockScan} disabled={isVerifying} class="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-lg transition-colors flex items-center justify-center gap-2">
                        {isVerifying ? 'Verifying...' : 'Simulate Physical Scan'}
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

{#if toastMsg}
    <div style="position:fixed;bottom:24px;right:24px;padding:13px 22px;border-radius:14px;font-size:0.88rem;font-weight:600;z-index:9999;max-width:360px;line-height:1.45;pointer-events:none;animation:toastIn 0.3s cubic-bezier(0.34,1.56,0.64,1);box-shadow:0 8px 28px rgba(0,0,0,0.3);{toastType === 'success' ? 'background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;' : toastType === 'error' ? 'background:linear-gradient(135deg,#e11d48,#be123c);color:#fff;' : 'background:#0f172a;color:#fff;'}">
        {toastMsg}
    </div>
{/if}

<style>
    @keyframes toastIn { from{transform:translateY(22px) scale(0.94);opacity:0} to{transform:translateY(0) scale(1);opacity:1} }
</style>
