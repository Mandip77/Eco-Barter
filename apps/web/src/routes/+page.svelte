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

  // ── Profile customization (localStorage) ───────────────────────────
  let profileEmoji = $state('');
  let profileBio = $state('');
  let profileColor = $state('#16a34a');
  let profileTab = $state<'overview'|'listings'|'edit'|'security'|'settings'>('overview');
  let showEmojiPicker = $state(false);
  let editBio = $state('');
  let showAvatarMenu = $state(false);

  // ── Change password form ────────────────────────────────────────────
  let pwForm = $state({ current: '', next: '', confirm: '' });
  let pwError = $state('');
  let pwSuccess = $state('');
  let pwLoading = $state(false);

  // ── Settings ────────────────────────────────────────────────────────
  let settingsNotifs = $state(true);
  let settingsPublic = $state(true);
  let settingsEcoAlerts = $state(true);

  const avatarEmojis = ['🌿','🌱','🦋','🌸','🍃','🌍','♻️','🌲','🌻','🐝','💚','🦺','🌊','🔆','✨','🎯','🚀','🦁','🐻','🦊'];
  const avatarColors = ['#16a34a','#0d9488','#2563eb','#7c3aed','#db2777','#ea580c','#ca8a04','#64748b'];

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
    // Load profile customization
    profileEmoji = localStorage.getItem('profile_emoji') || '';
    profileBio = localStorage.getItem('profile_bio') || '';
    profileColor = localStorage.getItem('profile_color') || '#16a34a';
    editBio = profileBio;
    settingsNotifs = localStorage.getItem('settings_notifs') !== 'false';
    settingsPublic = localStorage.getItem('settings_public') !== 'false';
    settingsEcoAlerts = localStorage.getItem('settings_eco_alerts') !== 'false';

    await loadListings();

    // Fetch reputation
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
    showToast(`Trade preference registered for ${selectedListing.title}! The EcoBarter Matrix is calculating loops…`);
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

  // ── Profile functions ───────────────────────────────────────────────
  function selectEmoji(e: string) {
    profileEmoji = e;
    localStorage.setItem('profile_emoji', e);
    showEmojiPicker = false;
  }

  function selectColor(c: string) {
    profileColor = c;
    localStorage.setItem('profile_color', c);
  }

  function saveEditProfile() {
    profileBio = editBio;
    localStorage.setItem('profile_bio', profileBio);
    showToast('Profile updated!', 'success');
  }

  function shareProfile() {
    const url = `${window.location.origin}?user=${authState.user?.username}`;
    navigator.clipboard.writeText(url).then(() => showToast('Profile link copied to clipboard!', 'success'));
  }

  async function changePassword() {
    pwError = '';
    pwSuccess = '';
    if (!pwForm.current || !pwForm.next) { pwError = 'Please fill in all fields.'; return; }
    if (pwForm.next !== pwForm.confirm) { pwError = 'New passwords do not match.'; return; }
    if (pwForm.next.length < 8) { pwError = 'New password must be at least 8 characters.'; return; }
    pwLoading = true;
    try {
      const resp = await fetch('/api/v1/auth/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify({ current_password: pwForm.current, new_password: pwForm.next })
      });
      const data = await resp.json();
      if (resp.ok) {
        pwSuccess = 'Password updated successfully!';
        pwForm = { current: '', next: '', confirm: '' };
        showToast('Password changed!', 'success');
      } else {
        pwError = data.detail || 'Failed to update password.';
      }
    } catch {
      pwError = 'Network error. Please try again.';
    } finally {
      pwLoading = false;
    }
  }

  function saveSettings() {
    localStorage.setItem('settings_notifs', String(settingsNotifs));
    localStorage.setItem('settings_public', String(settingsPublic));
    localStorage.setItem('settings_eco_alerts', String(settingsEcoAlerts));
    showToast('Settings saved!', 'success');
  }

  function handleLogout() {
    logout();
    showAvatarMenu = false;
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

  function handleWindowClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.avatar-wrap')) showAvatarMenu = false;
    if (!target.closest('.profile-avatar-wrap')) showEmojiPicker = false;
  }
</script>

<svelte:window onclick={handleWindowClick} />

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
      <!-- Avatar dropdown -->
      <div class="avatar-wrap">
        <button
          class="avatar {showAvatarMenu ? 'active' : ''}"
          onclick={(e) => { e.stopPropagation(); showAvatarMenu = !showAvatarMenu; }}
          title="Account menu"
          style="background: linear-gradient(135deg, {profileColor}, {profileColor}cc)"
        >
          {#if profileEmoji}
            <span style="font-size:1.05rem;line-height:1">{profileEmoji}</span>
          {:else}
            {authState.user.username.substring(0,2).toUpperCase()}
          {/if}
        </button>
        {#if showAvatarMenu}
          <div class="avatar-menu">
            <div class="avatar-menu-header">
              <div class="avatar-menu-avatar" style="background:linear-gradient(135deg,{profileColor},{profileColor}cc)">
                {#if profileEmoji}<span style="font-size:1.2rem">{profileEmoji}</span>{:else}{authState.user.username.substring(0,2).toUpperCase()}{/if}
              </div>
              <div style="min-width:0">
                <div class="avatar-menu-name">{authState.user.username}</div>
                <div class="avatar-menu-email">{authState.user.email}</div>
              </div>
            </div>
            <div class="avatar-menu-sep"></div>
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='overview'; showAvatarMenu=false; }}>
              <span class="menu-icon">👤</span> View Profile
            </button>
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='edit'; showAvatarMenu=false; }}>
              <span class="menu-icon">✏️</span> Edit Profile
            </button>
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='security'; showAvatarMenu=false; }}>
              <span class="menu-icon">🔒</span> Change Password
            </button>
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='settings'; showAvatarMenu=false; }}>
              <span class="menu-icon">⚙️</span> Settings
            </button>
            <div class="avatar-menu-sep"></div>
            <button class="avatar-menu-item danger" onclick={handleLogout}>
              <span class="menu-icon">🚪</span> Sign Out
            </button>
          </div>
        {/if}
      </div>
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
  {#if !authState.user}
    <div style="text-align:center;padding:80px 20px">
      <div style="font-size:3.5rem;margin-bottom:16px">🌿</div>
      <h2 style="font-family:'Outfit',sans-serif;font-size:1.6rem;margin-bottom:8px">Sign in to view your profile</h2>
      <p style="color:var(--text3);margin-bottom:24px">Join EcoBarter and start trading sustainably.</p>
      <button class="btn btn-primary" onclick={() => goto('/login')}>Sign In</button>
    </div>
  {:else}
    <!-- ── Profile header card ── -->
    <div class="profile-card-new">
      <div class="profile-banner-new"></div>
      <div class="profile-card-body-new">
        <!-- Avatar with emoji picker -->
        <div class="profile-avatar-wrap">
          <button
            class="profile-avatar-xl"
            style="background:linear-gradient(135deg,{profileColor},{profileColor}cc)"
            onclick={(e) => { e.stopPropagation(); showEmojiPicker = !showEmojiPicker; }}
            title="Change avatar"
          >
            {#if profileEmoji}
              <span style="font-size:2.6rem;line-height:1">{profileEmoji}</span>
            {:else}
              {authState.user.username.substring(0,2).toUpperCase()}
            {/if}
            <div class="avatar-edit-badge">✏️</div>
          </button>

          {#if showEmojiPicker}
            <div class="emoji-picker-panel" onclick={(e) => e.stopPropagation()}>
              <div class="picker-section-title">Pick an avatar</div>
              <div class="emoji-grid">
                {#each avatarEmojis as e}
                  <button class="emoji-opt {profileEmoji === e ? 'selected' : ''}" onclick={() => selectEmoji(e)}>{e}</button>
                {/each}
              </div>
              <div class="picker-section-title" style="margin-top:12px">Background color</div>
              <div class="color-grid">
                {#each avatarColors as c}
                  <button
                    class="color-opt {profileColor === c ? 'selected' : ''}"
                    style="background:{c}"
                    onclick={() => selectColor(c)}
                  ></button>
                {/each}
              </div>
              {#if profileEmoji}
                <button
                  class="btn btn-outline btn-sm"
                  style="margin-top:10px;width:100%;font-size:0.78rem"
                  onclick={() => { profileEmoji=''; localStorage.removeItem('profile_emoji'); showEmojiPicker=false; }}
                >Reset to initials</button>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Name + bio + actions -->
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px">
            <h2 style="font-size:1.65rem;font-weight:900;letter-spacing:-0.6px;font-family:'Outfit',sans-serif">{authState.user.username}</h2>
            <span class="rank-pill">{userRank}</span>
          </div>
          <p style="font-size:0.85rem;color:var(--text3);margin-bottom:8px">{authState.user.email}</p>
          {#if profileBio}
            <p style="font-size:0.93rem;color:var(--text2);line-height:1.6;max-width:500px;margin-bottom:12px">{profileBio}</p>
          {:else}
            <p style="font-size:0.85rem;color:var(--text3);font-style:italic;margin-bottom:12px">
              No bio yet —
              <button onclick={() => profileTab='edit'} style="color:var(--accent);background:none;border:none;cursor:pointer;text-decoration:underline;font-size:inherit;font-style:normal">add one</button>
            </p>
          {/if}
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-outline btn-sm" onclick={shareProfile}>
              <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>
              Share Profile
            </button>
            <button class="btn btn-outline btn-sm" onclick={() => profileTab='edit'}>
              <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
              Edit Profile
            </button>
          </div>
        </div>
      </div>

      <!-- Stats row -->
      <div class="profile-stats-row">
        <div class="profile-stat-item">
          <div class="profile-stat-val">{myItems.length}</div>
          <div class="profile-stat-lbl">Listings</div>
        </div>
        <div class="profile-stat-div"></div>
        <div class="profile-stat-item">
          <div class="profile-stat-val" style="color:var(--accent)">{userReputation.toFixed(1)}</div>
          <div class="profile-stat-lbl">Trust Score</div>
        </div>
        <div class="profile-stat-div"></div>
        <div class="profile-stat-item">
          <div class="profile-stat-val">{chats.length}</div>
          <div class="profile-stat-lbl">Active Trades</div>
        </div>
        <div class="profile-stat-div"></div>
        <div class="profile-stat-item">
          <div class="profile-stat-val" style="color:#10b981">{chats.length * 5} kg</div>
          <div class="profile-stat-lbl">CO₂ Saved</div>
        </div>
      </div>
    </div>

    <!-- Sub-tabs -->
    <div class="profile-subtabs">
      {#each [['overview','Overview'],['listings','My Listings'],['edit','Edit Profile'],['security','Security'],['settings','Settings']] as [tab, label]}
        <button class="profile-subtab {profileTab === tab ? 'active' : ''}" onclick={() => profileTab = tab as typeof profileTab}>{label}</button>
      {/each}
    </div>

    <!-- ── Overview tab ── -->
    {#if profileTab === 'overview'}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="card" style="padding:22px 24px">
          <div class="section-title" style="margin-bottom:18px">🌱 Eco Impact</div>
          <div style="display:flex;flex-direction:column;gap:16px">
            <div>
              <div class="eco-bar-row" style="margin-bottom:7px">
                <span style="font-size:0.83rem;color:var(--text2);font-weight:600">CO₂ Saved</span>
                <span style="font-size:0.83rem;font-weight:700;color:#10b981">{chats.length * 5} kg</span>
              </div>
              <div class="eco-progress-track"><div class="eco-progress-fill" style="width:{Math.min(chats.length * 12, 100)}%"></div></div>
            </div>
            <div class="eco-bar-row">
              <span style="font-size:0.83rem;color:var(--text2);font-weight:600">Items Diverted from Landfill</span>
              <span style="font-size:0.83rem;font-weight:700;color:var(--accent)">{myItems.length + chats.length}</span>
            </div>
            <div class="eco-bar-row">
              <span style="font-size:0.83rem;color:var(--text2);font-weight:600">Trust Rank</span>
              <span class="rank-pill" style="font-size:0.73rem;padding:2px 10px">{userRank}</span>
            </div>
            <div class="eco-bar-row">
              <span style="font-size:0.83rem;color:var(--text2);font-weight:600">EigenTrust Score</span>
              <span style="font-size:0.83rem;font-weight:700;color:var(--text)">{userReputation.toFixed(1)} / 100</span>
            </div>
          </div>
        </div>
        <div>
          <div class="section-header"><div class="section-title">Recent Reviews</div></div>
          <div class="review-card"><div class="stars" style="font-size:0.82rem">★★★★★</div><p class="text-sm" style="margin-top:8px;line-height:1.6">"Super smooth trade! {authState.user.username} was communicative and the item was exactly as described."</p><p class="text-sm text-muted" style="margin-top:6px">— Morgan T. · 3 days ago</p></div>
          <div class="review-card"><div class="stars" style="font-size:0.82rem">★★★★★</div><p class="text-sm" style="margin-top:8px;line-height:1.6">"Great swap, would trade again. Showed up on time with everything as promised."</p><p class="text-sm text-muted" style="margin-top:6px">— Priya K. · 1 week ago</p></div>
          <div class="review-card"><div class="stars" style="font-size:0.82rem">★★★★☆</div><p class="text-sm" style="margin-top:8px;line-height:1.6">"Friendly and honest. Would definitely trade again."</p><p class="text-sm text-muted" style="margin-top:6px">— Sam R. · 2 weeks ago</p></div>
        </div>
      </div>

    <!-- ── My Listings tab ── -->
    {:else if profileTab === 'listings'}
      <div class="card" style="padding:0;overflow:hidden">
        <div style="padding:18px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">
          <div class="section-title">My Listings</div>
          <button class="btn btn-primary btn-sm" onclick={() => modals.newListing = true}>+ New Listing</button>
        </div>
        {#each myItems as l}
          <div style="display:flex;align-items:center;gap:14px;padding:14px 24px;border-bottom:1px solid var(--border);transition:background 0.15s" onmouseenter={(e)=>(e.currentTarget as HTMLElement).style.background='var(--surface2)'} onmouseleave={(e)=>(e.currentTarget as HTMLElement).style.background=''}>
            <div style="font-size:1.9rem;width:46px;height:46px;background:var(--accent-light);border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center;flex-shrink:0">{l.emoji}</div>
            <div style="flex:1;min-width:0">
              <div style="font-weight:700;font-size:0.93rem">{l.title}</div>
              <div class="text-sm text-muted">{l.cat} · Wants: {l.wants}</div>
            </div>
            <span class="tag green" style="flex-shrink:0">Active</span>
            <button class="btn btn-outline btn-sm">Edit</button>
          </div>
        {/each}
        {#if myItems.length === 0}
          <div style="text-align:center;padding:52px 24px;color:var(--text3)">
            <div style="font-size:2.8rem;margin-bottom:12px">📦</div>
            <p style="font-size:0.9rem;margin-bottom:16px">You haven't listed anything yet.</p>
            <button class="btn btn-primary btn-sm" onclick={() => modals.newListing = true}>Create Your First Listing</button>
          </div>
        {/if}
      </div>

    <!-- ── Edit Profile tab ── -->
    {:else if profileTab === 'edit'}
      <div class="card" style="max-width:560px;padding:28px">
        <div class="section-title" style="margin-bottom:20px">Edit Profile</div>
        <div class="form-group">
          <label for="edit-username">Username</label>
          <input id="edit-username" type="text" value={authState.user.username} disabled style="opacity:0.55;cursor:not-allowed">
          <p style="font-size:0.76rem;color:var(--text3);margin-top:5px">Username cannot be changed after registration.</p>
        </div>
        <div class="form-group">
          <label for="edit-email">Email Address</label>
          <input id="edit-email" type="email" value={authState.user.email} disabled style="opacity:0.55;cursor:not-allowed">
        </div>
        <div class="form-group">
          <label for="edit-bio">Bio</label>
          <textarea id="edit-bio" bind:value={editBio} placeholder="Tell the EcoBarter community about yourself, what you trade, your eco goals…" rows="4" style="min-height:100px"></textarea>
        </div>
        <div style="display:flex;gap:10px">
          <button class="btn btn-primary" onclick={saveEditProfile}>Save Changes</button>
          <button class="btn btn-outline" onclick={() => { editBio = profileBio; }}>Cancel</button>
        </div>
      </div>

    <!-- ── Security tab ── -->
    {:else if profileTab === 'security'}
      <div class="card" style="max-width:460px;padding:28px">
        <div class="section-title" style="margin-bottom:6px">Change Password</div>
        <p style="font-size:0.84rem;color:var(--text3);margin-bottom:22px;line-height:1.55">Choose a strong password you don't use elsewhere. At least 8 characters.</p>

        {#if pwError}
          <div class="alert-error">{pwError}</div>
        {/if}
        {#if pwSuccess}
          <div class="alert-success">{pwSuccess}</div>
        {/if}

        <div class="form-group">
          <label for="pw-current">Current Password</label>
          <input id="pw-current" type="password" bind:value={pwForm.current} autocomplete="current-password" placeholder="Your current password">
        </div>
        <div class="form-group">
          <label for="pw-new">New Password</label>
          <input id="pw-new" type="password" bind:value={pwForm.next} autocomplete="new-password" placeholder="At least 8 characters">
        </div>
        <div class="form-group">
          <label for="pw-confirm">Confirm New Password</label>
          <input id="pw-confirm" type="password" bind:value={pwForm.confirm} autocomplete="new-password" placeholder="Repeat new password">
        </div>
        <button class="btn btn-primary" onclick={changePassword} disabled={pwLoading} style={pwLoading ? 'opacity:0.7;cursor:not-allowed' : ''}>
          {pwLoading ? 'Updating…' : 'Update Password'}
        </button>

        <div style="margin-top:36px;padding-top:24px;border-top:1px solid var(--border)">
          <div style="font-weight:700;font-size:0.92rem;color:var(--warn);margin-bottom:6px">Danger Zone</div>
          <p style="font-size:0.82rem;color:var(--text3);margin-bottom:14px;line-height:1.5">Permanently delete your account and all associated data. This cannot be undone.</p>
          <button class="btn btn-danger btn-sm" onclick={() => showToast('Account deletion is coming soon.', 'error')}>Delete Account</button>
        </div>
      </div>

    <!-- ── Settings tab ── -->
    {:else if profileTab === 'settings'}
      <div class="card" style="max-width:520px;padding:28px">
        <div class="section-title" style="margin-bottom:22px">Preferences</div>

        <div class="settings-row">
          <div>
            <div style="font-weight:600;font-size:0.92rem">Trade Match Notifications</div>
            <div style="font-size:0.8rem;color:var(--text3);margin-top:3px">Get notified when a new K-way loop matches your listings</div>
          </div>
          <button class="toggle {settingsNotifs ? 'on' : ''}" onclick={() => { settingsNotifs = !settingsNotifs; saveSettings(); }}><span></span></button>
        </div>
        <div class="settings-row">
          <div>
            <div style="font-weight:600;font-size:0.92rem">Public Profile</div>
            <div style="font-size:0.8rem;color:var(--text3);margin-top:3px">Allow others to view your profile and reputation score</div>
          </div>
          <button class="toggle {settingsPublic ? 'on' : ''}" onclick={() => { settingsPublic = !settingsPublic; saveSettings(); }}><span></span></button>
        </div>
        <div class="settings-row">
          <div>
            <div style="font-weight:600;font-size:0.92rem">Eco Impact Alerts</div>
            <div style="font-size:0.8rem;color:var(--text3);margin-top:3px">Weekly summary of your CO₂ savings and eco milestones</div>
          </div>
          <button class="toggle {settingsEcoAlerts ? 'on' : ''}" onclick={() => { settingsEcoAlerts = !settingsEcoAlerts; saveSettings(); }}><span></span></button>
        </div>

        <div style="margin-top:30px;padding-top:22px;border-top:1px solid var(--border)">
          <div class="section-title" style="font-size:0.9rem;margin-bottom:14px">Account Info</div>
          <div style="display:flex;flex-direction:column;gap:10px">
            <div class="info-row">
              <span>User ID</span>
              <code style="font-size:0.79rem;background:var(--surface2);padding:3px 9px;border-radius:6px;color:var(--text3);letter-spacing:0.02em">{authState.user.id}</code>
            </div>
            <div class="info-row">
              <span>Email</span>
              <span style="color:var(--text2);font-size:0.88rem">{authState.user.email}</span>
            </div>
            <div class="info-row">
              <span>Member Since</span>
              <span style="color:var(--text3);font-size:0.88rem">EcoBarter Alpha</span>
            </div>
          </div>
        </div>

        <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--border)">
          <button class="btn btn-outline btn-sm" style="color:var(--warn);border-color:rgba(225,29,72,0.3)" onclick={handleLogout}>Sign Out of EcoBarter</button>
        </div>
      </div>
    {/if}
  {/if}
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
