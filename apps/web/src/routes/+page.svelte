<script lang="ts">
  import { onMount } from 'svelte';
  import { authState, logout } from '$lib/auth.svelte';
  import { goto } from '$app/navigation';
  import { Centrifuge } from 'centrifuge';

  const categories = ['All','Electronics','Books & Media','Clothing','Furniture','Skills & Services','Plants & Garden','Sports & Outdoors','Food & Produce','Other'];
  let listings: any[] = $state([]);
  let chats = $state<any[]>([]);

  let isLoadingListings = $state(true);
  let listingsError = $state('');
  let toastMsg = $state('');
  let toastType = $state('');
  let chatInput = $state('');
  let pendingMatchCount = $state(0);

  let userReputation = $state(10.0);
  let userRank = $state('Novice');
  let centrifuge: Centrifuge | null = null;
  let chatSubscriptions: Record<string, any> = {};

  let currentPage = $state('browse');
  let activeFilter = $state('All');
  let searchQuery = $state('');

  let activeChatId: number | null = $state(null);
  let selectedOfferItem: number | null = $state(null);

  let modals = $state({ newListing: false, listingDetail: false });
  let newListing = $state({ title: '', cat: 'Electronics', desc: '', wants: '', emoji: '📦' });
  let selectedListing: any = $state(null);

  let filteredListings = $derived(listings.filter(l =>
    (activeFilter === 'All' || l.cat === activeFilter) &&
    (!searchQuery || l.title.toLowerCase().includes(searchQuery.toLowerCase()) || l.desc.toLowerCase().includes(searchQuery.toLowerCase()) || l.wants.toLowerCase().includes(searchQuery.toLowerCase()))
  ));

  let myItems = $derived(listings.filter(x => x.mine));
  let activeChat = $derived(activeChatId ? chats.find(c => c.id === activeChatId) : null);

  async function loadListings() {
    isLoadingListings = true;
    listingsError = '';
    try {
      const resp = await fetch('/api/v1/catalog/products');
      if (resp.ok) {
        const data = await resp.json();
        listings = data.map((dbItem: any) => ({
          id: dbItem._id,
          title: dbItem.title,
          user: dbItem.owner_id === authState.user?.id ? authState.user?.username || 'You' : dbItem.owner_id,
          userInitials: dbItem.owner_id === authState.user?.id ? (authState.user?.username?.substring(0,2).toUpperCase() || 'ME') : dbItem.owner_id.substring(0,2).toUpperCase(),
          cat: dbItem.category,
          emoji: dbItem.emoji || '📦',
          desc: dbItem.description || '',
          wants: dbItem.wants?.preferences?.query || 'Open to offers',
          tags: dbItem.tags || [],
          mine: dbItem.owner_id === authState.user?.id
        }));
      } else {
        listingsError = `Catalog service returned an error (${resp.status}). Try refreshing.`;
      }
    } catch {
      listingsError = 'Unable to reach the catalog service. Check your connection or try again shortly.';
    } finally {
      isLoadingListings = false;
    }
  }

  onMount(async () => {
    await loadListings();

    // Fetch Reputation
    if (authState.user) {
      try {
        const repResp = await fetch(`/api/v1/reputation/${authState.user.username}`);
        if (repResp.ok) {
          const repData = await repResp.json();
          userReputation = repData.eigentrust_score ?? repData.score ?? 10.0;
          userRank = repData.rank ?? 'Novice';
        }
      } catch { /* non-critical */ }
    }

    // Centrifuge — real-time hub
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    centrifuge = new Centrifuge(`${wsProto}//${window.location.host}/connection/websocket`);
    centrifuge.connect();

    if (authState.user) {
      try {
        const propResp = await fetch('/api/v1/trade/proposals', {
          headers: { 'Authorization': `Bearer ${authState.token}` }
        });
        if (propResp.ok) {
          const proposals = await propResp.json();
          chats = proposals.map((p: any) => ({
            id: p.ID,
            with: [p.user_a, p.user_b, p.user_c, p.user_d].filter(Boolean).join(', '),
            initials: 'TR',
            item: `Match Loop #${p.ID}`,
            online: true,
            messages: [],
            proposal: { me: [p.item_a], them: [p.item_b, p.item_c, p.user_d ? p.item_d : null].filter(Boolean) }
          }));

          proposals.forEach((p: any) => {
            const ch = `chat_${p.ID}`;
            if (!chatSubscriptions[ch]) {
              const sub = centrifuge!.newSubscription(ch);
              sub.on('publication', (ctx) => {
                const ind = chats.findIndex(c => c.id === p.ID);
                if (ind > -1) {
                  chats[ind].messages = [...chats[ind].messages, {
                    from: ctx.data.from === authState.user?.username ? 'me' : ctx.data.from,
                    text: ctx.data.text,
                    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  }];
                }
              });
              sub.subscribe();
              chatSubscriptions[ch] = sub;
            }
          });
        }
      } catch { /* proposals non-critical */ }

      // Subscribe to global trade hub for new-match alerts
      const hubSub = centrifuge!.newSubscription('trade_hub:proposals');
      hubSub.on('publication', (ctx) => {
        const payload = ctx.data;
        if (payload?.event === 'proposal_updated' && payload?.proposal) {
          const p = payload.proposal;
          const isParticipant =
            p.user_a === authState.user?.username ||
            p.user_b === authState.user?.username ||
            p.user_c === authState.user?.username ||
            p.user_d === authState.user?.username;

          if (isParticipant) {
            if (p.status === 'pending' && !chats.find((c: any) => c.id === p.ID)) {
              chats = [{
                id: p.ID,
                with: [p.user_a, p.user_b, p.user_c, p.user_d].filter(Boolean).join(', '),
                initials: 'TR',
                item: `Match Loop #${p.ID}`,
                online: true,
                messages: [],
                proposal: { me: [p.item_a || '?'], them: [p.item_b, p.item_c, p.user_d ? p.item_d : null].filter(Boolean) }
              }, ...chats];
              if (currentPage !== 'chat') {
                pendingMatchCount++;
                showToast('New trade loop matched! Open Negotiation to coordinate.', 'match');
              }
            } else if (p.status === 'completed') {
              showToast(`Trade Loop #${p.ID} completed! +5 kg CO₂ saved.`, 'success');
            }
          }
        }
      });
      hubSub.subscribe();
    }
  });

  function setPage(page: string) {
    currentPage = page;
    if (page === 'chat') pendingMatchCount = 0;
  }

  function setFilter(cat: string) { activeFilter = cat; }
  function handleSearch(e: Event) { searchQuery = (e.target as HTMLInputElement).value; }

  function openListing(id: number) {
    selectedListing = listings.find(x => x.id === id);
    selectedOfferItem = null;
    modals.listingDetail = true;
  }

  function selectOffer(id: number) { selectedOfferItem = id; }

  function proposeTrade() {
    if (!selectedOfferItem) { showToast('Please select a listing to offer'); return; }
    showToast(`Trade preference registered for ${selectedListing.title}! The EcoBarter Matrix is calculating loops...`);
    modals.listingDetail = false;
  }

  async function sendChatMsg() {
    if (!chatInput.trim() || !activeChatId || !authState.user) return;
    const payload = { trade_id: activeChatId, text: chatInput };
    try {
      const resp = await fetch('/api/v1/trade/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        chatInput = '';
        scrollToBottom();
      } else {
        showToast('Failed to send message.', 'error');
      }
    } catch {
      showToast('Network error — message not sent.', 'error');
    }
  }

  function handleChatKey(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMsg(); }
  }

  function acceptTrade(id: number) {
    const chatIndex = chats.findIndex(c => c.id === id);
    chats[chatIndex].proposal = null;
    chats[chatIndex].messages = [...chats[chatIndex].messages, {
      from: 'me',
      text: '✅ Trade accepted! Let\'s coordinate the swap pickup.',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }];
    chats = [...chats];
    showToast('Trade accepted! Eco Score updated.', 'success');
  }

  async function getAISuggestion(_id: number) {
    showToast('AI trade suggestions coming soon.');
  }

  function scrollToBottom() {
    setTimeout(() => {
      const el = document.querySelector('.chat-messages');
      if (el) el.scrollTop = el.scrollHeight;
    }, 50);
  }

  async function addListing() {
    if (!authState.user) { goto('/login'); return; }
    if (!newListing.title.trim()) { showToast('Please enter a title.'); return; }
    try {
      const payload = {
        title: newListing.title,
        category: newListing.cat,
        description: newListing.desc || 'No description.',
        wants: { preferences: { query: newListing.wants || 'Open to offers' } },
        emoji: newListing.emoji || '📦',
        tags: [newListing.cat],
        location: { type: 'Point', coordinates: [-71.0589, 42.3601] }
      };
      const resp = await fetch('/api/v1/catalog/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        const dbItem = await resp.json();
        listings = [{
          id: dbItem._id, title: dbItem.title,
          user: authState.user?.username || 'You',
          userInitials: authState.user?.username?.substring(0,2).toUpperCase() || 'ME',
          cat: dbItem.category, emoji: dbItem.emoji,
          desc: dbItem.description,
          wants: dbItem.wants?.preferences?.query || 'Open to offers',
          tags: dbItem.tags, mine: true
        }, ...listings];
        modals.newListing = false;
        showToast(`"${newListing.title}" listed!`, 'success');
        newListing = { title: '', cat: 'Electronics', desc: '', wants: '', emoji: '📦' };
      } else {
        showToast('Failed to post listing. Please try again.', 'error');
      }
    } catch {
      showToast('Network error — listing not posted.', 'error');
    }
  }

  function showToast(msg: string, type: string = '') {
    toastMsg = msg;
    toastType = type;
    setTimeout(() => { toastMsg = ''; toastType = ''; }, 4000);
  }

  function closeModals(e: MouseEvent) {
    if ((e.target as HTMLElement).classList.contains('modal-overlay')) {
      modals.newListing = false;
      modals.listingDetail = false;
    }
  }
</script>

<svelte:head>
  <title>EcoBarter — Trade Sustainably, Live Freely</title>
  <meta name="description" content="EcoBarter is a sustainable marketplace where goods and skills flow freely — no money needed. Discover circular trade loops powered by smart matching." />
  <meta property="og:title" content="EcoBarter — Trade Sustainably, Live Freely" />
  <meta property="og:description" content="A sustainable marketplace where goods and skills flow freely — no money needed. Discover circular K-way trade loops." />
  <meta name="twitter:title" content="EcoBarter — Trade Sustainably, Live Freely" />
  <meta name="twitter:description" content="Discover circular trade loops powered by smart matching. No money needed." />
</svelte:head>

<nav>
  <button class="logo" onclick={() => setPage('browse')}>🌿 EcoBarter</button>
  <div class="nav-links">
    <button class="nav-btn {currentPage === 'browse' ? 'active' : ''}" onclick={() => setPage('browse')}>Browse</button>
    <button class="nav-btn {currentPage === 'chat' ? 'active' : ''}" onclick={() => setPage('chat')}>
      Negotiation
      {#if pendingMatchCount > 0}<span class="badge">{pendingMatchCount}</span>{/if}
    </button>
    <button class="nav-btn {currentPage === 'profile' ? 'active' : ''}" onclick={() => setPage('profile')}>Profile</button>
  </div>
  <div class="nav-right">
    {#if authState.user}
      <button class="btn btn-primary btn-sm" onclick={() => modals.newListing = true}>+ New Listing</button>
      <button class="avatar" onclick={() => logout()} title="Logout">{authState.user.username.substring(0,2).toUpperCase()}</button>
    {:else}
      <button class="btn btn-primary btn-sm" onclick={() => goto('/login')}>Sign In</button>
    {/if}
  </div>
</nav>

{#if authState.serviceError}
<div class="service-error-banner">
  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
  Identity service is temporarily unreachable — account features are limited. Your session is preserved.
</div>
{/if}

<!-- BROWSE -->
<div class="page {currentPage === 'browse' ? 'active' : ''}" id="page-browse">
  <div class="hero">
    <h1>Trade What You Have,<br><span>Get What You Need</span></h1>
    <p>EcoBarter is a sustainable marketplace where goods and skills flow freely — no money needed.</p>
    <div class="hero-btns">
      <button class="btn btn-primary" onclick={() => authState.user ? modals.newListing = true : goto('/login')}>List Something</button>
      <button class="btn btn-outline" onclick={() => document.getElementById('listings-section')?.scrollIntoView({behavior:'smooth'})}>Browse Swaps</button>
    </div>
  </div>
  <div id="listings-section">
    <div class="section-header">
      <div class="section-title">Available Swaps</div>
      {#if !isLoadingListings && !listingsError}
        <span style="font-size:0.82rem;color:var(--text3)">{filteredListings.length} listings</span>
      {/if}
    </div>
    <div class="filters">
      <input type="text" class="search-input" placeholder="Search listings…" oninput={handleSearch}>
      <div style="display:flex;gap:7px;flex-wrap:wrap">
        {#each categories as cat}
          <button class="filter-chip {activeFilter === cat ? 'active' : ''}" onclick={() => setFilter(cat)}>{cat}</button>
        {/each}
      </div>
    </div>

    {#if isLoadingListings}
      <div class="card-grid">
        {#each Array(6) as _}
          <div class="skeleton-card">
            <div class="skeleton" style="height:188px;border-radius:0;"></div>
            <div style="padding:20px 22px 22px;display:flex;flex-direction:column;gap:10px;">
              <div class="skeleton" style="height:18px;width:65%;"></div>
              <div class="skeleton" style="height:13px;width:40%;"></div>
              <div class="skeleton" style="height:13px;width:55%;"></div>
            </div>
          </div>
        {/each}
      </div>
    {:else if listingsError}
      <div style="background:rgba(239,68,68,0.06);border:1.5px solid rgba(239,68,68,0.18);border-radius:var(--radius-sm);padding:16px 20px;display:flex;align-items:center;gap:12px;font-size:0.88rem;color:#dc2626;">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
        <span style="flex:1">{listingsError}</span>
        <button onclick={loadListings} style="font-weight:700;text-decoration:underline;background:none;border:none;cursor:pointer;color:inherit;font-size:inherit;white-space:nowrap;">Retry</button>
      </div>
    {:else}
      <div class="card-grid">
        {#each filteredListings as l}
          <button class="listing-card" onclick={() => openListing(l.id)}>
            <div class="listing-img">{l.emoji}</div>
            <div class="listing-body">
              <div class="listing-title">{l.title}</div>
              <div class="listing-user">by {l.user}{#if l.mine} <span class="badge" style="background:var(--surface2);color:var(--text2);border:1px solid var(--border)">You</span>{/if}</div>
              <div class="listing-tags">
                {#each l.tags as t}
                  <span class="tag {t === 'Eco-friendly' ? 'green' : ''}">{t}</span>
                {/each}
              </div>
              <div class="listing-wants">Wants: <strong>{l.wants.split(',')[0]}…</strong></div>
            </div>
          </button>
        {/each}
        {#if filteredListings.length === 0}
          <div style="grid-column:1/-1;text-align:center;padding:60px 20px;color:var(--text3);font-size:0.95rem;">
            No listings match your search. Try a different filter or <button onclick={() => authState.user ? modals.newListing = true : goto('/login')} style="color:var(--accent);font-weight:600;background:none;border:none;cursor:pointer;text-decoration:underline;">be the first to list</button>.
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<!-- CHAT -->
<div class="page {currentPage === 'chat' ? 'active' : ''}" id="page-chat">
  <div class="chat-layout">
    <div class="chat-sidebar">
      <div class="chat-sidebar-header">Negotiations</div>
      {#each chats as c}
        <button class="chat-item {c.id === activeChatId ? 'active' : ''}" onclick={() => { activeChatId = c.id; scrollToBottom(); }}>
          <div class="chat-item-avatar">{c.initials}</div>
          <div class="chat-item-info">
            <div class="chat-item-name">{c.with}</div>
            <div class="chat-item-preview">{c.item}</div>
          </div>
          {#if c.online}<div class="online-dot"></div>{/if}
        </button>
      {/each}
      {#if chats.length === 0}
        <div style="padding:24px;font-size:0.84rem;color:var(--text3);text-align:center;line-height:1.55;">No active trade loops yet.<br>Browse listings and propose a trade to start.</div>
      {/if}
    </div>
    <div class="chat-main" id="chat-main">
      {#if activeChatId && activeChat}
        <div class="chat-header">
          <div class="chat-item-avatar">{activeChat.initials}</div>
          <div>
            <div style="font-weight:700;font-size:0.95rem">{activeChat.with}</div>
            <div class="text-sm text-muted">{activeChat.item}</div>
          </div>
          <button class="btn btn-outline btn-sm" style="margin-left:auto" onclick={() => getAISuggestion(activeChatId as number)}>🤖 AI Help</button>
        </div>
        <div class="chat-messages">
          {#if activeChat.proposal}
            <div class="proposal-bar">
              <span style="color:var(--accent);font-weight:700;font-size:0.84rem;flex-shrink:0">📦 Proposal</span>
              <div class="proposal-items">
                {#each activeChat.proposal.me as i}
                  <div class="proposal-item"><span>{i.split(' ')[0]}</span>{i.split(' ').slice(1).join(' ')}</div>
                {/each}
              </div>
              <span class="arrow">⇄</span>
              <div class="proposal-items">
                {#each activeChat.proposal.them as i}
                  <div class="proposal-item"><span>{i.split(' ')[0]}</span>{i.split(' ').slice(1).join(' ')}</div>
                {/each}
              </div>
              <button class="btn btn-primary btn-sm" onclick={() => acceptTrade(activeChatId as number)}>Accept</button>
              <button class="btn btn-outline btn-sm" onclick={() => showToast('Counter-proposal coming soon.')}>Counter</button>
            </div>
          {/if}
          {#each activeChat.messages as m}
            <div class="msg {m.from === 'me' ? 'mine' : ''} {m.from === 'ai' ? 'ai' : ''}">
              <div class="msg-avatar" style="{m.from === 'me' ? 'background:var(--accent);color:#fff;border-color:var(--accent)' : m.from === 'ai' ? 'background:#fefce8;color:#b45309;border-color:#fde68a' : ''}">{m.from === 'me' ? 'Me' : m.from === 'ai' ? '🤖' : activeChat.initials}</div>
              <div><div class="msg-bubble">{m.text}</div><div class="msg-time">{m.time}</div></div>
            </div>
          {/each}
        </div>
        <div class="chat-input-area">
          <textarea class="chat-input" bind:value={chatInput} placeholder="Type a message…" rows="1" onkeydown={handleChatKey}></textarea>
          <button class="btn btn-primary" onclick={sendChatMsg}>Send</button>
        </div>
      {:else}
        <div style="flex:1;display:flex;align-items:center;justify-content:center;color:var(--text3);font-size:0.9rem">Select a negotiation to start</div>
      {/if}
    </div>
  </div>
</div>

<!-- PROFILE -->
<div class="page {currentPage === 'profile' ? 'active' : ''}" id="page-profile">
  <div class="profile-header">
    <div class="profile-avatar">{authState.user ? authState.user.username.substring(0,2).toUpperCase() : 'AJ'}</div>
    <div class="profile-info">
      <h2>{authState.user ? authState.user.username : 'Guest'}</h2>
      <p>Earth Region · {userRank}</p>
      <div class="stars" style="color:{userReputation > 50 ? '#10b981' : '#f59e0b'}">★★★★★</div>
      <div class="stat-row">
        <div class="stat"><div class="stat-val">{myItems.length}</div><div class="stat-label">Listings</div></div>
        <div class="stat"><div class="stat-val">{userReputation.toFixed(1)}</div><div class="stat-label">Trust Score</div></div>
        <div class="stat"><div class="stat-val">{chats.length}</div><div class="stat-label">Active Nodes</div></div>
      </div>
      <div style="margin-top:14px"><span class="eco-score">🌱 84 kg CO₂ saved</span></div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
    <div>
      <div class="section-header"><div class="section-title">My Listings</div></div>
      {#each myItems as l}
        <div class="card" style="margin-bottom:9px;display:flex;align-items:center;gap:12px;padding:16px 18px;">
          <div style="font-size:1.8rem;background:var(--surface2);width:44px;height:44px;border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center">{l.emoji}</div>
          <div style="flex:1"><div style="font-weight:600;font-size:0.92rem">{l.title}</div><div class="text-sm text-muted">{l.cat}</div></div>
          <button class="btn btn-outline btn-sm">Edit</button>
        </div>
      {/each}
      {#if myItems.length === 0}
        <div style="color:var(--text3);font-size:0.88rem;padding:16px 0">No listings yet. <button onclick={() => modals.newListing = true} style="color:var(--accent);font-weight:600;background:none;border:none;cursor:pointer;text-decoration:underline">Add one</button>.</div>
      {/if}
    </div>
    <div>
      <div class="section-header"><div class="section-title">Recent Reviews</div></div>
      <div class="review-card"><div class="stars" style="font-size:0.82rem">★★★★★</div><p class="text-sm" style="margin-top:8px;line-height:1.6">"Super smooth trade! Alex was communicative and the vintage lamp was exactly as described."</p><p class="text-sm text-muted" style="margin-top:6px">— Morgan T. · 3 days ago</p></div>
      <div class="review-card"><div class="stars" style="font-size:0.82rem">★★★★★</div><p class="text-sm" style="margin-top:8px;line-height:1.6">"Great swap, would trade again. Showed up on time with the board games as promised."</p><p class="text-sm text-muted" style="margin-top:6px">— Priya K. · 1 week ago</p></div>
      <div class="review-card"><div class="stars" style="font-size:0.82rem">★★★★☆</div><p class="text-sm" style="margin-top:8px;line-height:1.6">"Friendly and honest. The guitar had a small scratch not mentioned, but we worked it out."</p><p class="text-sm text-muted" style="margin-top:6px">— Sam R. · 2 weeks ago</p></div>
    </div>
  </div>
</div>

<!-- NEW LISTING MODAL -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay {modals.newListing ? 'open' : ''}" onclick={closeModals}>
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title">New Listing</div>
      <button class="close-btn" onclick={() => modals.newListing = false}>×</button>
    </div>
    <div class="form-group"><label for="nl-title">Item / Service Name</label><input id="nl-title" type="text" bind:value={newListing.title} placeholder="e.g. Vintage Polaroid Camera"></div>
    <div class="form-group"><label for="nl-cat">Category</label><select id="nl-cat" bind:value={newListing.cat}>
      {#each categories.filter(c => c !== 'All') as c}<option>{c}</option>{/each}
    </select></div>
    <div class="form-group"><label for="nl-desc">Description</label><textarea id="nl-desc" bind:value={newListing.desc} placeholder="Describe condition, details, etc."></textarea></div>
    <div class="form-group"><label for="nl-wants">Looking to trade for…</label><input id="nl-wants" type="text" bind:value={newListing.wants} placeholder="e.g. Camera lenses, or open to offers"></div>
    <div class="form-group"><label for="nl-emoji">Emoji Icon</label><input id="nl-emoji" type="text" bind:value={newListing.emoji} placeholder="📷" maxlength="4" style="width:80px"></div>
    <button class="btn btn-primary w-full" onclick={addListing}>Post Listing</button>
  </div>
</div>

<!-- LISTING DETAIL MODAL -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay {modals.listingDetail && selectedListing ? 'open' : ''}" onclick={closeModals}>
  {#if selectedListing}
    <div class="modal" style="max-width:600px">
      <div class="modal-header">
        <div class="modal-title">{selectedListing.title}</div>
        <button class="close-btn" onclick={() => modals.listingDetail = false}>×</button>
      </div>
      <div style="font-size:4.5rem;text-align:center;padding:24px;background:linear-gradient(135deg,var(--accent-light),var(--surface2));border-radius:var(--radius-sm);margin-bottom:16px">{selectedListing.emoji}</div>
      <div style="display:flex;gap:16px;margin-bottom:14px;align-items:flex-start">
        <div style="flex:1"><p class="text-sm" style="line-height:1.65;margin-bottom:10px;color:var(--text2)">{selectedListing.desc}</p><div class="listing-tags">{#each selectedListing.tags as t}<span class="tag {t==='Eco-friendly'?'green':''}">{t}</span>{/each}</div></div>
        <div style="text-align:right;flex-shrink:0"><div class="text-sm text-muted">Listed by</div><div style="font-weight:700;margin-top:2px">{selectedListing.user}</div><div class="stars" style="font-size:0.8rem">★★★★★</div></div>
      </div>
      <div style="background:var(--surface2);border:1.5px solid var(--border);border-radius:var(--radius-sm);padding:12px 14px;margin-bottom:16px">
        <div class="text-muted text-sm" style="margin-bottom:3px">Looking for:</div>
        <div style="font-weight:700;color:var(--text)">{selectedListing.wants}</div>
      </div>
      <hr class="divider">
      <div class="section-header" style="margin-bottom:8px"><div class="section-title">Propose a Trade</div></div>
      <p class="text-sm text-muted" style="margin-bottom:12px">Select one of your listings to offer in exchange:</p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">
        {#each myItems as i}
          <button class="proposal-item" style="cursor:pointer; {selectedOfferItem === i.id ? 'border-color:var(--accent);background:var(--accent-light);color:var(--accent2);' : ''}" onclick={() => selectOffer(i.id)}>
            <span>{i.emoji}</span>{i.title}
          </button>
        {/each}
        {#if myItems.length === 0}
          <span class="text-muted text-sm">No listings yet — <button onclick={() => { modals.listingDetail = false; modals.newListing = true; }} style="color:var(--accent);font-weight:600;background:none;border:none;cursor:pointer;text-decoration:underline">add one first</button>.</span>
        {/if}
      </div>
      <button class="btn btn-primary w-full" style={selectedListing.mine ? 'opacity:0.4' : ''} disabled={selectedListing.mine} onclick={proposeTrade}>
        {selectedListing.mine ? 'This is your listing' : 'Send Trade Proposal & Open Chat'}
      </button>
    </div>
  {/if}
</div>

{#if toastMsg}
  <div class="toast {toastType ? `toast-${toastType}` : ''}">{toastMsg}</div>
{/if}
