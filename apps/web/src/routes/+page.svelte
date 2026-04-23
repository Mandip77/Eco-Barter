<script lang="ts">
  import { onMount } from 'svelte';
  import { authState, logout } from '$lib/auth.svelte';
  import { goto } from '$app/navigation';
  import { Centrifuge } from 'centrifuge';

  const categories = ['All','Electronics','Books & Media','Clothing','Furniture','Skills & Services','Plants & Garden','Sports & Outdoors','Food & Produce','Other'];
  const CONDITIONS = ['New', 'Like New', 'Good', 'Fair', 'Poor'];

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
  let modals = $state({ newListing: false, listingDetail: false, editListing: false });
  let newListing = $state({ title: '', cat: 'Electronics', desc: '', wants: '', emoji: '📦', condition: 'Good' });
  let selectedListing: any = $state(null);

  // ── Location ──────────────────────────────────────────────────────
  let userLocation: { lat: number; lon: number } | null = $state(null);
  let locationRadius = $state(10);
  let locationLoading = $state(false);

  // ── Saves/Watchlist ───────────────────────────────────────────────
  let savedIds = $state(new Set<string>());

  // ── Image upload ──────────────────────────────────────────────────
  let newListingImage: File | null = $state(null);
  let newListingImagePreview = $state('');

  // ── AI suggestion ─────────────────────────────────────────────────
  let aiSuggestion = $state('');
  let aiLoading = $state(false);

  // ── Reviews ───────────────────────────────────────────────────────
  let showReviewModal = $state(false);
  let reviewTarget = $state({ tradeId: 0, revieweeId: '', revieweeName: '' });
  let reviewForm = $state({ score: 5, comment: '' });
  let reviewSubmitting = $state(false);
  let userReviews = $state<any[]>([]);

  // ── Trade scheduling ──────────────────────────────────────────────
  let showScheduler = $state<number | null>(null);
  let scheduleInput = $state('');
  let scheduleLoading = $state(false);

  // ── Edit listing ──────────────────────────────────────────────────
  let editingListing: any = $state(null);
  let editForm = $state({ title: '', cat: 'Electronics', desc: '', wants: '', emoji: '📦', condition: 'Good' });
  let editImage: File | null = $state(null);
  let editImagePreview = $state('');
  let editLoading = $state(false);

  // ── Trade history ─────────────────────────────────────────────────
  let tradeHistory = $state<any[]>([]);

  // ── Counter-proposal ──────────────────────────────────────────────
  let showCounterPanel = $state<number | null>(null);
  let counterItem = $state('');

  // ── Batch propose (wishlist) ──────────────────────────────────────
  let batchSelected = $state(new Set<string>());
  let batchProposing = $state(false);

  // ── Profile customization ─────────────────────────────────────────
  let profileEmoji = $state('');
  let profileBio = $state('');
  let profileColor = $state('#16a34a');
  let profileTab = $state<'overview'|'listings'|'saved'|'history'|'edit'|'security'|'settings'>('overview');
  let showEmojiPicker = $state(false);
  let editBio = $state('');
  let showAvatarMenu = $state(false);
  let pwForm = $state({ current: '', next: '', confirm: '' });
  let pwError = $state('');
  let pwSuccess = $state('');
  let pwLoading = $state(false);
  let showDeleteModal = $state(false);
  let deletePassword = $state('');
  let deleteError = $state('');
  let deleteLoading = $state(false);
  let settingsNotifs = $state(true);
  let settingsPublic = $state(true);
  let settingsEcoAlerts = $state(true);

  const avatarEmojis = ['🌿','🌱','🦋','🌸','🍃','🌍','♻️','🌲','🌻','🐝','💚','🦺','🌊','🔆','✨','🎯','🚀','🦁','🐻','🦊'];
  const avatarColors = ['#16a34a','#0d9488','#2563eb','#7c3aed','#db2777','#ea580c','#ca8a04','#64748b'];
  const conditionColors: Record<string, string> = { 'New': '#10b981', 'Like New': '#16a34a', 'Good': '#2563eb', 'Fair': '#f59e0b', 'Poor': '#ef4444' };

  let filteredListings = $derived(listings.filter(l =>
    (activeFilter === 'All' || l.cat === activeFilter) &&
    (!searchQuery || l.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      l.desc.toLowerCase().includes(searchQuery.toLowerCase()) ||
      l.wants.toLowerCase().includes(searchQuery.toLowerCase()))
  ));
  let myItems = $derived(listings.filter(x => x.mine));
  let activeChat = $derived(activeChatId ? chats.find(c => c.id === activeChatId) : null);

  // ── Haversine distance (km) ───────────────────────────────────────
  function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLon/2)**2;
    return R * 2 * Math.asin(Math.sqrt(a));
  }

  async function loadListings() {
    isLoadingListings = true;
    listingsError = '';
    try {
      let url = '/api/v1/catalog/products';
      if (userLocation) {
        url += `?lat=${userLocation.lat}&lon=${userLocation.lon}&max_distance=${locationRadius * 1000}`;
      }
      const resp = await fetch(url);
      if (resp.ok) {
        const data = await resp.json();
        listings = data.map((dbItem: any) => {
          const coords = dbItem.location?.coordinates; // [lon, lat]
          const distKm = (userLocation && coords)
            ? haversineKm(userLocation.lat, userLocation.lon, coords[1], coords[0])
            : null;
          return {
            id: dbItem._id,
            title: dbItem.title,
            user: dbItem.owner_id === authState.user?.id ? authState.user?.username || 'You' : dbItem.owner_id,
            userInitials: dbItem.owner_id === authState.user?.id ? (authState.user?.username?.substring(0,2).toUpperCase() || 'ME') : dbItem.owner_id.substring(0,2).toUpperCase(),
            cat: dbItem.category,
            emoji: dbItem.emoji || '📦',
            desc: dbItem.description || '',
            wants: dbItem.wants?.preferences?.query || 'Open to offers',
            tags: dbItem.tags || [],
            mine: dbItem.owner_id === authState.user?.id,
            condition: dbItem.condition || 'Good',
            image_data: dbItem.image_data || null,
            location: dbItem.location || null,
            distKm,
            view_count: dbItem.view_count || 0,
            expires_at: dbItem.expires_at || null,
          };
        });
      } else {
        listingsError = `Catalog service returned an error (${resp.status}). Try refreshing.`;
      }
    } catch {
      listingsError = 'Unable to reach the catalog service. Check your connection or try again shortly.';
    } finally {
      isLoadingListings = false;
    }
  }

  // ── Location ──────────────────────────────────────────────────────
  async function getLocation() {
    if (!navigator.geolocation) { showToast('Geolocation is not supported by your browser.', 'error'); return; }
    locationLoading = true;
    try {
      const pos = await new Promise<GeolocationPosition>((res, rej) =>
        navigator.geolocation.getCurrentPosition(res, rej, { timeout: 10000 }));
      userLocation = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      localStorage.setItem('user_location', JSON.stringify(userLocation));
      await loadListings();
      showToast('Showing listings near you!', 'success');
    } catch {
      showToast('Could not get your location. Please check browser permissions.', 'error');
    } finally {
      locationLoading = false;
    }
  }

  function clearLocation() {
    userLocation = null;
    localStorage.removeItem('user_location');
    loadListings();
  }

  // ── Saves ─────────────────────────────────────────────────────────
  async function loadSaves() {
    if (!authState.user || !authState.token) return;
    try {
      const resp = await fetch('/api/v1/catalog/saves', {
        headers: { 'Authorization': `Bearer ${authState.token}` }
      });
      if (resp.ok) {
        const data = await resp.json();
        savedIds = new Set(data.saved_ids);
      }
    } catch { /* non-critical */ }
  }

  async function toggleSave(e: MouseEvent, listingId: string) {
    e.stopPropagation();
    if (!authState.user) { goto('/login'); return; }
    const isSaved = savedIds.has(listingId);
    const newSet = new Set(savedIds);
    if (isSaved) {
      newSet.delete(listingId);
      savedIds = newSet;
      await fetch(`/api/v1/catalog/saves/${listingId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authState.token}` }
      }).catch(() => {});
    } else {
      newSet.add(listingId);
      savedIds = newSet;
      await fetch(`/api/v1/catalog/saves/${listingId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authState.token}` }
      }).catch(() => {});
    }
  }

  // ── Image upload ──────────────────────────────────────────────────
  function handleImageSelect(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    if (file.size > 1024 * 1024) { showToast('Image must be under 1 MB.', 'error'); return; }
    newListingImage = file;
    const reader = new FileReader();
    reader.onload = (ev) => { newListingImagePreview = ev.target?.result as string || ''; };
    reader.readAsDataURL(file);
  }

  function handleEditImageSelect(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    if (file.size > 1024 * 1024) { showToast('Image must be under 1 MB.', 'error'); return; }
    editImage = file;
    const reader = new FileReader();
    reader.onload = (ev) => { editImagePreview = ev.target?.result as string || ''; };
    reader.readAsDataURL(file);
  }

  // ── AI suggestion ─────────────────────────────────────────────────
  async function getAISuggestion(listingId: string) {
    if (!authState.token) { goto('/login'); return; }
    aiSuggestion = '';
    aiLoading = true;
    try {
      const resp = await fetch(`/api/v1/catalog/products/${listingId}/suggest`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authState.token}` }
      });
      if (resp.ok) {
        const data = await resp.json();
        aiSuggestion = data.suggestion || 'No suggestion available.';
      } else {
        aiSuggestion = 'Could not generate a suggestion right now.';
      }
    } catch {
      aiSuggestion = 'AI service is temporarily unavailable.';
    } finally {
      aiLoading = false;
    }
  }

  // ── Edit / delete listing ─────────────────────────────────────────
  function openEditModal(l: any) {
    editingListing = l;
    editForm = { title: l.title, cat: l.cat, desc: l.desc, wants: l.wants, emoji: l.emoji || '📦', condition: l.condition || 'Good' };
    editImagePreview = l.image_data || '';
    editImage = null;
    modals.editListing = true;
  }

  async function saveEditListing() {
    if (!editForm.title.trim()) { showToast('Title is required.', 'error'); return; }
    editLoading = true;
    try {
      const payload = {
        title: editForm.title, category: editForm.cat,
        description: editForm.desc || 'No description.',
        wants: { preferences: { query: editForm.wants || 'Open to offers' } },
        emoji: editForm.emoji || '📦', condition: editForm.condition,
        tags: [editForm.cat],
        location: editingListing.location || { type: 'Point', coordinates: [-71.0589, 42.3601] }
      };
      const resp = await fetch(`/api/v1/catalog/products/${editingListing.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        if (editImage) {
          const fd = new FormData();
          fd.append('file', editImage);
          const imgResp = await fetch(`/api/v1/catalog/products/${editingListing.id}/image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authState.token}` },
            body: fd
          });
          if (imgResp.ok) { const d = await imgResp.json(); editImagePreview = d.image_data || editImagePreview; }
        }
        modals.editListing = false;
        showToast(`"${editForm.title}" updated!`, 'success');
        await loadListings();
      } else { showToast('Failed to update listing.', 'error'); }
    } catch { showToast('Network error.', 'error'); }
    finally { editLoading = false; }
  }

  async function deleteListing(e: MouseEvent, l: any) {
    e.stopPropagation();
    if (!confirm(`Delete "${l.title}"? This cannot be undone.`)) return;
    try {
      const resp = await fetch(`/api/v1/catalog/products/${l.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authState.token}` }
      });
      if (resp.status === 204) {
        listings = listings.filter(x => x.id !== l.id);
        showToast('Listing deleted.', 'success');
      } else { showToast('Failed to delete listing.', 'error'); }
    } catch { showToast('Network error.', 'error'); }
  }

  function shareListing(l: any) {
    const url = `${window.location.origin}?listing=${l.id}`;
    navigator.clipboard.writeText(url).then(() => showToast('Listing link copied!', 'success'));
  }

  async function bumpListing(e: MouseEvent, l: any) {
    e.stopPropagation();
    try {
      const resp = await fetch(`/api/v1/catalog/products/${l.id}/bump`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authState.token}` }
      });
      if (resp.ok) { showToast(`"${l.title}" bumped — active for 30 more days!`, 'success'); await loadListings(); }
      else { showToast('Bump failed.', 'error'); }
    } catch { showToast('Network error.', 'error'); }
  }

  async function submitCounter(tradeId: number) {
    if (!counterItem) { showToast('Select an item to counter with.', 'error'); return; }
    try {
      const resp = await fetch('/api/v1/trade/counter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify({ trade_id: tradeId, counter_item: counterItem })
      });
      if (resp.ok) { showCounterPanel = null; counterItem = ''; showToast('Counter-proposal sent!', 'success'); }
      else { showToast('Failed to send counter.', 'error'); }
    } catch { showToast('Network error.', 'error'); }
  }

  function toggleBatchSelect(id: string) {
    const next = new Set(batchSelected);
    if (next.has(id)) next.delete(id); else next.add(id);
    batchSelected = next;
  }

  function proposeBatch() {
    if (batchSelected.size === 0) { showToast('Select at least one listing.', 'error'); return; }
    batchProposing = true;
    const firstId = [...batchSelected][0];
    batchSelected = new Set();
    batchProposing = false;
    openListing(firstId);
  }

  // ── Reviews ───────────────────────────────────────────────────────
  async function loadReviews() {
    if (!authState.user) return;
    try {
      const resp = await fetch(`/api/v1/reputation/reviews/${authState.user.username}`);
      if (resp.ok) {
        const data = await resp.json();
        userReviews = data.reviews || [];
      }
    } catch { /* non-critical */ }
  }

  function openReviewModal(tradeId: number, revieweeId: string, revieweeName: string) {
    reviewTarget = { tradeId, revieweeId, revieweeName };
    reviewForm = { score: 5, comment: '' };
    showReviewModal = true;
  }

  async function submitReview() {
    reviewSubmitting = true;
    try {
      const resp = await fetch('/api/v1/reputation/reviews', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify({
          trade_id: reviewTarget.tradeId,
          reviewee_id: reviewTarget.revieweeId,
          score: reviewForm.score,
          comment: reviewForm.comment,
        })
      });
      if (resp.ok) {
        showReviewModal = false;
        showToast('Review submitted! Thank you.', 'success');
        await loadReviews();
      } else {
        showToast('Failed to submit review.', 'error');
      }
    } catch {
      showToast('Network error.', 'error');
    } finally {
      reviewSubmitting = false;
    }
  }

  // ── Trade scheduling ──────────────────────────────────────────────
  async function scheduleTrade(tradeId: number) {
    if (!scheduleInput) { showToast('Please select a date and time.', 'error'); return; }
    scheduleLoading = true;
    try {
      const isoDate = new Date(scheduleInput).toISOString();
      const resp = await fetch('/api/v1/trade/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify({ trade_id: tradeId, scheduled_at: isoDate })
      });
      if (resp.ok) {
        const data = await resp.json();
        const idx = chats.findIndex(c => c.id === tradeId);
        if (idx > -1) {
          chats[idx].scheduledAt = data.proposal?.scheduled_at;
          chats = [...chats];
        }
        showScheduler = null;
        showToast('Meetup scheduled!', 'success');
      } else {
        showToast('Failed to schedule meetup.', 'error');
      }
    } catch {
      showToast('Network error.', 'error');
    } finally {
      scheduleLoading = false;
    }
  }

  // ── Profile helpers ───────────────────────────────────────────────
  function selectEmoji(e: string) { profileEmoji = e; localStorage.setItem('profile_emoji', e); showEmojiPicker = false; }
  function selectColor(c: string) { profileColor = c; localStorage.setItem('profile_color', c); }
  function saveEditProfile() { profileBio = editBio; localStorage.setItem('profile_bio', profileBio); showToast('Profile updated!', 'success'); }
  function shareProfile() {
    navigator.clipboard.writeText(`${window.location.origin}?user=${authState.user?.username}`)
      .then(() => showToast('Profile link copied!', 'success'));
  }
  async function changePassword() {
    pwError = ''; pwSuccess = '';
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
      if (resp.ok) { pwSuccess = 'Password updated!'; pwForm = { current: '', next: '', confirm: '' }; showToast('Password changed!', 'success'); }
      else { pwError = data.detail || 'Failed to update password.'; }
    } catch { pwError = 'Network error.'; }
    finally { pwLoading = false; }
  }
  async function deleteAccount() {
    deleteError = '';
    if (!deletePassword) { deleteError = 'Please enter your password to confirm.'; return; }
    deleteLoading = true;
    try {
      const resp = await fetch('/api/v1/auth/account', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify({ password: deletePassword })
      });
      if (resp.status === 204) { localStorage.clear(); logout(); goto('/login'); }
      else { const d = await resp.json().catch(() => ({})); deleteError = d.detail || 'Failed to delete account.'; }
    } catch { deleteError = 'Network error.'; }
    finally { deleteLoading = false; }
  }
  function saveSettings() {
    localStorage.setItem('settings_notifs', String(settingsNotifs));
    localStorage.setItem('settings_public', String(settingsPublic));
    localStorage.setItem('settings_eco_alerts', String(settingsEcoAlerts));
    showToast('Settings saved!', 'success');
  }
  function handleLogout() { logout(); showAvatarMenu = false; }

  // ── Listings ──────────────────────────────────────────────────────
  function setPage(page: string) { currentPage = page; if (page === 'chat') pendingMatchCount = 0; }
  function setFilter(cat: string) { activeFilter = cat; }
  function handleSearch(e: Event) { searchQuery = (e.target as HTMLInputElement).value; }
  function openListing(id: string) {
    selectedListing = listings.find(x => x.id === id);
    selectedOfferItem = null;
    aiSuggestion = '';
    modals.listingDetail = true;
  }
  function selectOffer(id: string) { selectedOfferItem = id; }
  function proposeTrade() {
    if (!selectedOfferItem) { showToast('Please select a listing to offer'); return; }
    showToast(`Trade preference registered for ${selectedListing.title}! The EcoBarter Matrix is calculating loops…`);
    modals.listingDetail = false;
  }

  async function addListing() {
    if (!authState.user) { goto('/login'); return; }
    if (!newListing.title.trim()) { showToast('Please enter a title.'); return; }
    if (!newListingImage) { showToast('Please add a photo of your item before posting.', 'error'); return; }
    try {
      const payload = {
        title: newListing.title, category: newListing.cat,
        description: newListing.desc || 'No description.',
        wants: { preferences: { query: newListing.wants || 'Open to offers' } },
        emoji: newListing.emoji || '📦', condition: newListing.condition,
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
        // Upload image if selected
        let imageData: string | null = null;
        if (newListingImage) {
          const fd = new FormData();
          fd.append('file', newListingImage);
          const imgResp = await fetch(`/api/v1/catalog/products/${dbItem._id}/image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authState.token}` },
            body: fd
          });
          if (imgResp.ok) { const imgData = await imgResp.json(); imageData = imgData.image_data || null; }
        }
        listings = [{
          id: dbItem._id, title: dbItem.title,
          user: authState.user?.username || 'You',
          userInitials: authState.user?.username?.substring(0,2).toUpperCase() || 'ME',
          cat: dbItem.category, emoji: dbItem.emoji, desc: dbItem.description,
          wants: dbItem.wants?.preferences?.query || 'Open to offers',
          tags: dbItem.tags, mine: true,
          condition: dbItem.condition || 'Good',
          image_data: imageData,
          distKm: null,
        }, ...listings];
        modals.newListing = false;
        showToast(`"${newListing.title}" listed!`, 'success');
        newListing = { title: '', cat: 'Electronics', desc: '', wants: '', emoji: '📦', condition: 'Good' };
        newListingImage = null;
        newListingImagePreview = '';
      } else { showToast('Failed to post listing.', 'error'); }
    } catch { showToast('Network error.', 'error'); }
  }

  async function sendChatMsg() {
    if (!chatInput.trim() || !activeChatId || !authState.user) return;
    try {
      const resp = await fetch('/api/v1/trade/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authState.token}` },
        body: JSON.stringify({ trade_id: activeChatId, text: chatInput })
      });
      if (resp.ok) { chatInput = ''; scrollToBottom(); }
      else { showToast('Failed to send message.', 'error'); }
    } catch { showToast('Network error.', 'error'); }
  }

  function handleChatKey(e: KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMsg(); } }

  function acceptTrade(id: number) {
    const i = chats.findIndex(c => c.id === id);
    chats[i].proposal = null;
    chats[i].messages = [...chats[i].messages, {
      from: 'me', text: '✅ Trade accepted! Let\'s coordinate the swap pickup.',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }];
    chats = [...chats];
    showToast('Trade accepted! Eco Score updated.', 'success');
    // Prompt review for the other participants
    const chat = chats[i];
    if (chat.with) openReviewModal(id, chat.with.split(',')[0].trim(), chat.with.split(',')[0].trim());
  }

  function scrollToBottom() {
    setTimeout(() => { const el = document.querySelector('.chat-messages'); if (el) el.scrollTop = el.scrollHeight; }, 50);
  }

  function showToast(msg: string, type: string = '') {
    toastMsg = msg; toastType = type;
    setTimeout(() => { toastMsg = ''; toastType = ''; }, 4000);
  }

  function closeModals(e: MouseEvent) {
    if ((e.target as HTMLElement).classList.contains('modal-overlay')) {
      modals.newListing = false; modals.listingDetail = false; modals.editListing = false;
    }
  }

  function handleWindowClick(e: MouseEvent) {
    const t = e.target as HTMLElement;
    if (!t.closest('.avatar-wrap')) showAvatarMenu = false;
    if (!t.closest('.profile-avatar-wrap')) showEmojiPicker = false;
  }

  onMount(async () => {
    // Restore profile customization
    profileEmoji = localStorage.getItem('profile_emoji') || '';
    profileBio = localStorage.getItem('profile_bio') || '';
    profileColor = localStorage.getItem('profile_color') || '#16a34a';
    editBio = profileBio;
    settingsNotifs = localStorage.getItem('settings_notifs') !== 'false';
    settingsPublic = localStorage.getItem('settings_public') !== 'false';
    settingsEcoAlerts = localStorage.getItem('settings_eco_alerts') !== 'false';

    // Restore saved location
    const storedLoc = localStorage.getItem('user_location');
    if (storedLoc) { try { userLocation = JSON.parse(storedLoc); } catch { /* ignore */ } }

    await loadListings();

    if (authState.user) {
      await Promise.all([
        loadSaves(),
        loadReviews(),
        fetch(`/api/v1/reputation/${authState.user.username}`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d) { userReputation = d.eigentrust_score ?? 10.0; userRank = d.rank ?? 'Novice'; } })
          .catch(() => {}),
      ]);
    }

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
          const active = proposals.filter((p: any) => p.status !== 'completed' && p.status !== 'cancelled');
          tradeHistory = proposals
            .filter((p: any) => p.status === 'completed' || p.status === 'cancelled')
            .map((p: any) => ({
              id: p.id, with: [p.user_a, p.user_b, p.user_c, p.user_d].filter(Boolean).join(', '),
              item: `Match Loop #${p.id}`, status: p.status, created_at: p.created_at,
            }));
          chats = active.map((p: any) => ({
            id: p.id, with: [p.user_a, p.user_b, p.user_c, p.user_d].filter(Boolean).join(', '),
            initials: 'TR', item: `Match Loop #${p.id}`, online: true, messages: [],
            proposal: { me: [p.item_a], them: [p.item_b, p.item_c, p.user_d ? p.item_d : null].filter(Boolean) },
            scheduledAt: p.scheduled_at || null,
          }));
          active.forEach((p: any) => {
            const ch = `chat_${p.id}`;
            if (!chatSubscriptions[ch]) {
              const sub = centrifuge!.newSubscription(ch);
              sub.on('publication', (ctx) => {
                const ind = chats.findIndex(c => c.id === p.id);
                if (ind > -1) chats[ind].messages = [...chats[ind].messages, {
                  from: ctx.data.from === authState.user?.username ? 'me' : ctx.data.from,
                  text: ctx.data.text,
                  time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                }];
              });
              sub.subscribe();
              chatSubscriptions[ch] = sub;
            }
          });
        }
      } catch { /* non-critical */ }

      const hubSub = centrifuge!.newSubscription('trade_hub:proposals');
      hubSub.on('publication', (ctx) => {
        const p = ctx.data?.proposal;
        if (!p) return;
        const isParticipant = [p.user_a, p.user_b, p.user_c, p.user_d].includes(authState.user?.username);
        if (isParticipant) {
          if (p.status === 'pending' && !chats.find((c: any) => c.id === p.id)) {
            chats = [{ id: p.id, with: [p.user_a,p.user_b,p.user_c,p.user_d].filter(Boolean).join(', '), initials: 'TR', item: `Match Loop #${p.id}`, online: true, messages: [], proposal: { me: [p.item_a||'?'], them: [p.item_b,p.item_c,p.user_d?p.item_d:null].filter(Boolean) }, scheduledAt: null }, ...chats];
            if (currentPage !== 'chat') { pendingMatchCount++; showToast('New trade loop matched!', 'match'); }
          } else if (p.status === 'completed') {
            showToast(`Trade Loop #${p.ID} completed! +5 kg CO₂ saved.`, 'success');
          }
        }
      });
      hubSub.subscribe();
    }
  });
</script>

<svelte:window onclick={handleWindowClick} />

<svelte:head>
  <title>EcoBarter — Trade Sustainably, Live Freely</title>
  <meta name="description" content="EcoBarter is a sustainable marketplace where goods and skills flow freely — no money needed." />
</svelte:head>

<!-- NAV -->
<nav>
  <button class="logo" onclick={() => setPage('browse')}>🌿 EcoBarter</button>
  <div class="nav-links">
    <button class="nav-btn {currentPage==='browse'?'active':''}" onclick={() => setPage('browse')}>Browse</button>
    <button class="nav-btn {currentPage==='chat'?'active':''}" onclick={() => setPage('chat')}>
      Negotiation {#if pendingMatchCount > 0}<span class="badge">{pendingMatchCount}</span>{/if}
    </button>
    <button class="nav-btn {currentPage==='profile'?'active':''}" onclick={() => setPage('profile')}>Profile</button>
  </div>
  <div class="nav-right">
    {#if authState.user}
      <button class="btn btn-primary btn-sm" onclick={() => modals.newListing = true}>+ New Listing</button>
      <div class="avatar-wrap">
        <button class="avatar {showAvatarMenu?'active':''}" onclick={(e)=>{e.stopPropagation();showAvatarMenu=!showAvatarMenu;}} style="background:linear-gradient(135deg,{profileColor},{profileColor}cc)">
          {#if profileEmoji}<span style="font-size:1.05rem;line-height:1">{profileEmoji}</span>{:else}{authState.user.username.substring(0,2).toUpperCase()}{/if}
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
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='overview'; showAvatarMenu=false; }}><span class="menu-icon">👤</span> View Profile</button>
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='edit'; showAvatarMenu=false; }}><span class="menu-icon">✏️</span> Edit Profile</button>
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='security'; showAvatarMenu=false; }}><span class="menu-icon">🔒</span> Change Password</button>
            <button class="avatar-menu-item" onclick={() => { setPage('profile'); profileTab='settings'; showAvatarMenu=false; }}><span class="menu-icon">⚙️</span> Settings</button>
            <div class="avatar-menu-sep"></div>
            <button class="avatar-menu-item danger" onclick={handleLogout}><span class="menu-icon">🚪</span> Sign Out</button>
          </div>
        {/if}
      </div>
    {:else}
      <button class="btn btn-primary btn-sm" onclick={() => goto('/login')}>Sign In</button>
    {/if}
  </div>
</nav>

<nav class="bottom-nav" aria-label="Mobile navigation">
  <button class="bottom-nav-btn {currentPage==='browse'?'active':''}" onclick={() => setPage('browse')}>
    <span class="bn-icon">🏪</span>Browse
  </button>
  <button class="bottom-nav-btn {currentPage==='chat'?'active':''}" onclick={() => setPage('chat')}>
    <span class="bn-icon">💬</span>Negotiate
    {#if pendingMatchCount > 0}<span class="badge">{pendingMatchCount}</span>{/if}
  </button>
  <button class="bottom-nav-btn" onclick={() => authState.user ? (setPage('browse'), modals.newListing=true) : goto('/login')}>
    <span class="bn-icon" style="background:var(--accent);color:#fff;border-radius:50%;width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:1.1rem">+</span>
    Post
  </button>
  <button class="bottom-nav-btn {currentPage==='profile'?'active':''}" onclick={() => setPage('profile')}>
    <span class="bn-icon">👤</span>Profile
  </button>
</nav>

{#if authState.serviceError}
<div class="service-error-banner">
  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
  Identity service is temporarily unreachable — account features are limited.
</div>
{/if}

<!-- BROWSE -->
<div class="page {currentPage==='browse'?'active':''}" id="page-browse">
  <div class="hero">
    <h1>Trade What You Have,<br><span>Get What You Need</span></h1>
    <p>EcoBarter is a sustainable marketplace where goods and skills flow freely — no money needed.</p>
    <div class="hero-btns">
      <button class="btn btn-primary" onclick={() => authState.user ? modals.newListing=true : goto('/login')}>List Something</button>
      <button class="btn btn-outline" onclick={() => document.getElementById('listings-section')?.scrollIntoView({behavior:'smooth'})}>Browse Swaps</button>
    </div>
  </div>

  <div id="listings-section">
    <div class="section-header">
      <div class="section-title">Available Swaps</div>
      {#if !isLoadingListings && !listingsError}
        <span style="font-size:0.82rem;color:var(--text3)">{filteredListings.length} listings{userLocation ? ` within ${locationRadius} km` : ''}</span>
      {/if}
    </div>

    <!-- Location + search filters -->
    <div class="filters">
      <input type="text" class="search-input" placeholder="Search listings…" oninput={handleSearch}>

      <!-- Location bar -->
      {#if userLocation}
        <div class="location-bar active">
          <span>📍 Near you</span>
          <select class="location-radius-select" bind:value={locationRadius} onchange={() => loadListings()}>
            {#each [1,5,10,25,50] as r}<option value={r}>{r} km</option>{/each}
          </select>
          <button class="location-clear-btn" onclick={clearLocation} title="Clear location">×</button>
        </div>
      {:else}
        <button class="location-bar" onclick={getLocation} disabled={locationLoading}>
          {#if locationLoading}
            <span class="loc-spinner"></span> Getting location…
          {:else}
            📍 Near me
          {/if}
        </button>
      {/if}

      <div style="display:flex;gap:7px;flex-wrap:wrap">
        {#each categories as cat}
          <button class="filter-chip {activeFilter===cat?'active':''}" onclick={() => setFilter(cat)}>{cat}</button>
        {/each}
      </div>
    </div>

    {#if isLoadingListings}
      <div class="card-grid">
        {#each Array(6) as _}
          <div class="skeleton-card"><div class="skeleton" style="height:188px;border-radius:0;"></div><div style="padding:20px 22px 22px;display:flex;flex-direction:column;gap:10px;"><div class="skeleton" style="height:18px;width:65%;"></div><div class="skeleton" style="height:13px;width:40%;"></div><div class="skeleton" style="height:13px;width:55%;"></div></div></div>
        {/each}
      </div>
    {:else if listingsError}
      <div style="background:rgba(239,68,68,0.06);border:1.5px solid rgba(239,68,68,0.18);border-radius:var(--radius-sm);padding:16px 20px;display:flex;align-items:center;gap:12px;font-size:0.88rem;color:#dc2626;">
        <span style="flex:1">{listingsError}</span>
        <button onclick={loadListings} style="font-weight:700;text-decoration:underline;background:none;border:none;cursor:pointer;color:inherit;">Retry</button>
      </div>
    {:else}
      <div class="card-grid">
        {#each filteredListings as l}
          <button class="listing-card" onclick={() => openListing(l.id)}>
            <div class="listing-img" style={l.image_data ? 'padding:0;overflow:hidden' : ''}>
              {#if l.image_data}
                <img src={l.image_data} alt={l.title} style="width:100%;height:100%;object-fit:cover;display:block;" />
              {:else}
                {l.emoji}
              {/if}
              <!-- Bookmark (div avoids button-inside-button invalid HTML) -->
              <!-- svelte-ignore a11y_interactive_supports_focus -->
              <div
                role="button"
                tabindex="0"
                class="bookmark-btn {savedIds.has(l.id) ? 'saved' : ''}"
                onclick={(e) => toggleSave(e, l.id)}
                onkeydown={(e) => e.key === 'Enter' && toggleSave(e as unknown as MouseEvent, l.id)}
                title={savedIds.has(l.id) ? 'Remove from saved' : 'Save listing'}
              >
                {savedIds.has(l.id) ? '🔖' : '🏷️'}
              </div>
              <!-- Distance badge -->
              {#if l.distKm !== null}
                <span class="distance-badge">{l.distKm < 1 ? `${(l.distKm*1000).toFixed(0)} m` : `${l.distKm.toFixed(1)} km`}</span>
              {/if}
            </div>
            <div class="listing-body">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
                <div class="listing-title" style="flex:1;margin:0">{l.title}</div>
                <span class="condition-badge" style="background:{conditionColors[l.condition]}18;color:{conditionColors[l.condition]};border-color:{conditionColors[l.condition]}44">{l.condition}</span>
              </div>
              <div class="listing-user">by {l.user}{#if l.mine} <span class="badge" style="background:var(--surface2);color:var(--text2);border:1px solid var(--border)">You</span>{/if}{#if l.view_count > 0}<span style="margin-left:6px;font-size:0.74rem;color:var(--text3)">👁 {l.view_count}</span>{/if}</div>
              <div class="listing-tags">{#each l.tags as t}<span class="tag {t==='Eco-friendly'?'green':''}">{t}</span>{/each}</div>
              <div class="listing-wants">Wants: <strong>{l.wants.split(',')[0]}…</strong></div>
            </div>
          </button>
        {/each}
        {#if filteredListings.length === 0}
          <div style="grid-column:1/-1;text-align:center;padding:60px 20px;color:var(--text3);font-size:0.95rem;">
            No listings match{userLocation ? ' near your location' : ''}. <button onclick={() => authState.user ? modals.newListing=true : goto('/login')} style="color:var(--accent);font-weight:600;background:none;border:none;cursor:pointer;text-decoration:underline;">Be the first to list</button>.
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<!-- CHAT -->
<div class="page {currentPage==='chat'?'active':''}" id="page-chat">
  <div class="chat-layout {activeChatId ? 'has-active-chat' : ''}">
    <div class="chat-sidebar">
      <div class="chat-sidebar-header">Negotiations</div>
      {#each chats as c}
        <button class="chat-item {c.id===activeChatId?'active':''}" onclick={() => { activeChatId=c.id; showScheduler=null; scrollToBottom(); }}>
          <div class="chat-item-avatar">{c.initials}</div>
          <div class="chat-item-info">
            <div class="chat-item-name">{c.with}</div>
            <div class="chat-item-preview">
              {#if c.scheduledAt}📅 {new Date(c.scheduledAt).toLocaleDateString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}{:else}{c.item}{/if}
            </div>
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
          <button class="btn btn-outline btn-sm" onclick={() => activeChatId = null} style="display:none" aria-label="Back" id="chat-back-btn">← Back</button>
          <div class="chat-item-avatar">{activeChat.initials}</div>
          <div>
            <div style="font-weight:700;font-size:0.95rem">{activeChat.with}</div>
            <div class="text-sm text-muted">{activeChat.item}</div>
          </div>
          <div class="chat-header-actions" style="margin-left:auto;display:flex;gap:8px">
            <button class="btn btn-outline btn-sm" onclick={() => showScheduler = showScheduler === activeChatId ? null : activeChatId}>
              📅 {activeChat.scheduledAt ? 'Reschedule' : 'Schedule'}
            </button>
            <button class="btn btn-outline btn-sm" onclick={() => {}}>🤖 AI Help</button>
          </div>
        </div>

        <!-- Counter-proposal panel -->
        {#if showCounterPanel === activeChatId}
          <div class="counter-panel">
            <div style="font-weight:700;font-size:0.88rem;margin-bottom:10px">🔄 Counter-Offer — pick your item</div>
            <div style="display:flex;flex-wrap:wrap;gap:7px;margin-bottom:10px">
              {#each myItems as i}
                <button class="proposal-item" style="{counterItem===i.title?'border-color:var(--accent);background:var(--accent-light);color:var(--accent2)':''}" onclick={() => counterItem=i.title}>
                  <span>{i.emoji}</span>{i.title}
                </button>
              {/each}
              {#if myItems.length===0}<span class="text-muted text-sm">No listings to offer — add one first.</span>{/if}
            </div>
            <div style="display:flex;gap:8px">
              <button class="btn btn-primary btn-sm" onclick={() => submitCounter(activeChatId as number)} disabled={!counterItem}>Send Counter</button>
              <button class="btn btn-outline btn-sm" onclick={() => { showCounterPanel=null; counterItem=''; }}>Cancel</button>
            </div>
          </div>
        {/if}

        <!-- Schedule meetup panel -->
        {#if showScheduler === activeChatId}
          <div class="schedule-panel">
            <div style="font-weight:700;font-size:0.88rem;margin-bottom:8px">📅 Schedule a Meetup</div>
            {#if activeChat.scheduledAt}
              <div style="font-size:0.83rem;color:var(--accent);margin-bottom:8px">Currently: {new Date(activeChat.scheduledAt).toLocaleString()}</div>
            {/if}
            <div style="display:flex;gap:8px;align-items:center">
              <input type="datetime-local" bind:value={scheduleInput} style="flex:1;font-size:0.85rem;padding:7px 10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);background:var(--surface2);color:var(--text);outline:none;">
              <button class="btn btn-primary btn-sm" onclick={() => scheduleTrade(activeChatId as number)} disabled={scheduleLoading}>
                {scheduleLoading ? '…' : 'Confirm'}
              </button>
              <button class="btn btn-outline btn-sm" onclick={() => showScheduler=null}>Cancel</button>
            </div>
          </div>
        {/if}

        <div class="chat-messages">
          {#if activeChat.proposal}
            <div class="proposal-bar">
              <span style="color:var(--accent);font-weight:700;font-size:0.84rem;flex-shrink:0">📦 Proposal</span>
              <div class="proposal-items">{#each activeChat.proposal.me as i}<div class="proposal-item"><span>{i.split(' ')[0]}</span>{i.split(' ').slice(1).join(' ')}</div>{/each}</div>
              <span class="arrow">⇄</span>
              <div class="proposal-items">{#each activeChat.proposal.them as i}<div class="proposal-item"><span>{i.split(' ')[0]}</span>{i.split(' ').slice(1).join(' ')}</div>{/each}</div>
              <button class="btn btn-primary btn-sm" onclick={() => acceptTrade(activeChatId as number)}>Accept</button>
              <button class="btn btn-outline btn-sm" onclick={() => { showCounterPanel = showCounterPanel === activeChatId ? null : activeChatId; counterItem=''; }}>🔄 Counter</button>
            </div>
          {/if}
          {#each activeChat.messages as m}
            <div class="msg {m.from==='me'?'mine':''} {m.from==='ai'?'ai':''}">
              <div class="msg-avatar" style="{m.from==='me'?'background:var(--accent);color:#fff;border-color:var(--accent)':m.from==='ai'?'background:#fefce8;color:#b45309;border-color:#fde68a':''}">{m.from==='me'?'Me':m.from==='ai'?'🤖':activeChat.initials}</div>
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
<div class="page {currentPage==='profile'?'active':''}" id="page-profile">
  {#if !authState.user}
    <div style="text-align:center;padding:80px 20px">
      <div style="font-size:3.5rem;margin-bottom:16px">🌿</div>
      <h2 style="font-family:'Outfit',sans-serif;font-size:1.6rem;margin-bottom:8px">Sign in to view your profile</h2>
      <button class="btn btn-primary" onclick={() => goto('/login')}>Sign In</button>
    </div>
  {:else}
    <div class="profile-card-new">
      <div class="profile-banner-new"></div>
      <div class="profile-card-body-new">
        <div class="profile-avatar-wrap">
          <button class="profile-avatar-xl" style="background:linear-gradient(135deg,{profileColor},{profileColor}cc)" onclick={(e)=>{e.stopPropagation();showEmojiPicker=!showEmojiPicker;}} title="Change avatar">
            {#if profileEmoji}<span style="font-size:2.6rem;line-height:1">{profileEmoji}</span>{:else}{authState.user.username.substring(0,2).toUpperCase()}{/if}
            <div class="avatar-edit-badge">✏️</div>
          </button>
          {#if showEmojiPicker}
            <div class="emoji-picker-panel" onclick={(e)=>e.stopPropagation()}>
              <div class="picker-section-title">Pick an avatar</div>
              <div class="emoji-grid">{#each avatarEmojis as e}<button class="emoji-opt {profileEmoji===e?'selected':''}" onclick={() => selectEmoji(e)}>{e}</button>{/each}</div>
              <div class="picker-section-title" style="margin-top:12px">Color</div>
              <div class="color-grid">{#each avatarColors as c}<button class="color-opt {profileColor===c?'selected':''}" style="background:{c}" onclick={() => selectColor(c)}></button>{/each}</div>
              {#if profileEmoji}<button class="btn btn-outline btn-sm" style="margin-top:10px;width:100%;font-size:0.78rem" onclick={() => { profileEmoji=''; localStorage.removeItem('profile_emoji'); showEmojiPicker=false; }}>Reset to initials</button>{/if}
            </div>
          {/if}
        </div>
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px">
            <h2 style="font-size:1.65rem;font-weight:900;letter-spacing:-0.6px;font-family:'Outfit',sans-serif">{authState.user.username}</h2>
            <span class="rank-pill">{userRank}</span>
          </div>
          <p style="font-size:0.85rem;color:var(--text3);margin-bottom:8px">{authState.user.email}</p>
          {#if profileBio}<p style="font-size:0.93rem;color:var(--text2);line-height:1.6;max-width:500px;margin-bottom:12px">{profileBio}</p>
          {:else}<p style="font-size:0.85rem;color:var(--text3);font-style:italic;margin-bottom:12px">No bio yet — <button onclick={() => profileTab='edit'} style="color:var(--accent);background:none;border:none;cursor:pointer;text-decoration:underline;font-size:inherit;font-style:normal">add one</button></p>{/if}
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-outline btn-sm" onclick={shareProfile}>Share Profile</button>
            <button class="btn btn-outline btn-sm" onclick={() => profileTab='edit'}>Edit Profile</button>
          </div>
        </div>
      </div>
      <div class="profile-stats-row">
        <div class="profile-stat-item"><div class="profile-stat-val">{myItems.length}</div><div class="profile-stat-lbl">Listings</div></div>
        <div class="profile-stat-div"></div>
        <div class="profile-stat-item"><div class="profile-stat-val" style="color:var(--accent)">{userReputation.toFixed(1)}</div><div class="profile-stat-lbl">Trust Score</div></div>
        <div class="profile-stat-div"></div>
        <div class="profile-stat-item"><div class="profile-stat-val">{chats.length}</div><div class="profile-stat-lbl">Active Trades</div></div>
        <div class="profile-stat-div"></div>
        <div class="profile-stat-item"><div class="profile-stat-val" style="color:#10b981">{savedIds.size}</div><div class="profile-stat-lbl">Saved</div></div>
        <div class="profile-stat-div"></div>
        <div class="profile-stat-item"><div class="profile-stat-val" style="color:#10b981">{chats.length * 5} kg</div><div class="profile-stat-lbl">CO₂ Saved</div></div>
      </div>
    </div>

    <div class="profile-subtabs">
      {#each [['overview','Overview'],['listings','My Listings'],['saved','Wishlist'],['history','History'],['edit','Edit Profile'],['security','Security'],['settings','Settings']] as [tab, label]}
        <button class="profile-subtab {profileTab===tab?'active':''}" onclick={() => profileTab = tab as typeof profileTab}>{label}</button>
      {/each}
    </div>

    {#if profileTab === 'overview'}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="card" style="padding:22px 24px">
          <div class="section-title" style="margin-bottom:18px">🌱 Eco Impact</div>
          <div style="display:flex;flex-direction:column;gap:16px">
            <div><div class="eco-bar-row" style="margin-bottom:7px"><span style="font-size:0.83rem;color:var(--text2);font-weight:600">CO₂ Saved</span><span style="font-size:0.83rem;font-weight:700;color:#10b981">{chats.length*5} kg</span></div><div class="eco-progress-track"><div class="eco-progress-fill" style="width:{Math.min(chats.length*12,100)}%"></div></div></div>
            <div class="eco-bar-row"><span style="font-size:0.83rem;color:var(--text2);font-weight:600">Items Diverted from Landfill</span><span style="font-size:0.83rem;font-weight:700;color:var(--accent)">{myItems.length+chats.length}</span></div>
            <div class="eco-bar-row"><span style="font-size:0.83rem;color:var(--text2);font-weight:600">Trust Rank</span><span class="rank-pill" style="font-size:0.73rem;padding:2px 10px">{userRank}</span></div>
            <div class="eco-bar-row"><span style="font-size:0.83rem;color:var(--text2);font-weight:600">EigenTrust Score</span><span style="font-size:0.83rem;font-weight:700">{userReputation.toFixed(1)} / 100</span></div>
          </div>
        </div>
        <div>
          <div class="section-header"><div class="section-title">Reviews ({userReviews.length})</div></div>
          {#if userReviews.length > 0}
            {#each userReviews.slice(0,3) as r}
              <div class="review-card">
                <div class="stars" style="font-size:0.82rem">{'★'.repeat(r.score)}{'☆'.repeat(5-r.score)}</div>
                {#if r.comment}<p class="text-sm" style="margin-top:8px;line-height:1.6">"{r.comment}"</p>{/if}
                <p class="text-sm text-muted" style="margin-top:6px">— Trade #{r.trade_id} · {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}</p>
              </div>
            {/each}
          {:else}
            <div class="review-card"><p class="text-sm text-muted" style="text-align:center;padding:8px 0">No reviews yet. Complete trades to earn reviews.</p></div>
          {/if}
        </div>
      </div>

    {:else if profileTab === 'listings'}
      <div class="card" style="padding:0;overflow:hidden">
        <div style="padding:18px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between"><div class="section-title">My Listings</div><button class="btn btn-primary btn-sm" onclick={() => modals.newListing=true}>+ New Listing</button></div>
        {#each myItems as l}
          <div style="display:flex;align-items:center;gap:14px;padding:14px 24px;border-bottom:1px solid var(--border)">
            <div style="width:46px;height:46px;background:var(--accent-light);border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center;flex-shrink:0;overflow:hidden">
              {#if l.image_data}<img src={l.image_data} alt={l.title} style="width:100%;height:100%;object-fit:cover">{:else}<span style="font-size:1.9rem">{l.emoji}</span>{/if}
            </div>
            <div style="flex:1;min-width:0">
              <div style="font-weight:700;font-size:0.93rem">{l.title}</div>
              <div class="text-sm text-muted" style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">
                {l.cat} · {l.condition}
                {#if l.expires_at}
                  <span class="expiry-badge {new Date(l.expires_at) < new Date(Date.now()+3*86400000)?'expiring':''}">
                    expires {new Date(l.expires_at).toLocaleDateString([],{month:'short',day:'numeric'})}
                  </span>
                {/if}
              </div>
            </div>
            <span class="tag green" style="flex-shrink:0">Active</span>
            {#if l.expires_at}<button class="btn btn-outline btn-sm" onclick={(e)=>bumpListing(e,l)}>Bump</button>{/if}
            <button class="btn btn-outline btn-sm" onclick={() => openEditModal(l)}>Edit</button>
            <button class="btn btn-outline btn-sm" style="color:var(--warn);border-color:rgba(225,29,72,0.3)" onclick={(e) => deleteListing(e, l)}>Delete</button>
          </div>
        {/each}
        {#if myItems.length === 0}<div style="text-align:center;padding:52px 24px;color:var(--text3)"><div style="font-size:2.8rem;margin-bottom:12px">📦</div><p style="font-size:0.9rem;margin-bottom:16px">No listings yet.</p><button class="btn btn-primary btn-sm" onclick={() => modals.newListing=true}>Create First Listing</button></div>{/if}
      </div>

    {:else if profileTab === 'saved'}
      <div class="card" style="padding:0;overflow:hidden">
        <div style="padding:18px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">
          <div class="section-title">Wishlist ({savedIds.size})</div>
          {#if batchSelected.size > 0}
            <div style="display:flex;gap:8px;align-items:center">
              <span style="font-size:0.82rem;color:var(--text2)">{batchSelected.size} selected</span>
              <button class="btn btn-primary btn-sm" onclick={proposeBatch} disabled={batchProposing}>Propose Selected</button>
              <button class="btn btn-outline btn-sm" onclick={() => batchSelected=new Set()}>Clear</button>
            </div>
          {:else}
            <span style="font-size:0.78rem;color:var(--text3)">Tap ☐ to multi-select</span>
          {/if}
        </div>
        {#each listings.filter(l => savedIds.has(l.id)) as l}
          <!-- svelte-ignore a11y_interactive_supports_focus -->
          <div class="listing-row {batchSelected.has(l.id)?'selected':''}" role="button" tabindex="0" onclick={() => openListing(l.id)} onkeydown={(e)=>e.key==='Enter'&&openListing(l.id)}>
            <button class="batch-check" onclick={(e)=>{e.stopPropagation();toggleBatchSelect(l.id);}} style="background:none;border:1.5px solid {batchSelected.has(l.id)?'var(--accent)':'var(--border)'};border-radius:6px;width:22px;height:22px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:0.85rem;cursor:pointer;color:{batchSelected.has(l.id)?'var(--accent)':'var(--text3)'}">
              {batchSelected.has(l.id)?'✓':''}
            </button>
            <div style="width:40px;height:40px;background:var(--accent-light);border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center;flex-shrink:0;overflow:hidden">
              {#if l.image_data}<img src={l.image_data} alt={l.title} style="width:100%;height:100%;object-fit:cover">{:else}<span style="font-size:1.5rem">{l.emoji}</span>{/if}
            </div>
            <div style="flex:1;min-width:0">
              <div style="font-weight:700;font-size:0.93rem">{l.title}</div>
              <div class="text-sm text-muted">by {l.user} · {l.condition}{#if l.view_count>0} · 👁 {l.view_count}{/if}</div>
            </div>
            <span class="condition-badge" style="background:{conditionColors[l.condition]}18;color:{conditionColors[l.condition]};border-color:{conditionColors[l.condition]}44">{l.condition}</span>
            <button class="btn btn-primary btn-sm" onclick={(e) => { e.stopPropagation(); openListing(l.id); }}>Propose Trade</button>
            <button class="btn btn-outline btn-sm" onclick={(e) => toggleSave(e, l.id)}>Unsave</button>
          </div>
        {/each}
        {#if savedIds.size === 0}<div style="text-align:center;padding:52px 24px;color:var(--text3)"><div style="font-size:2.8rem;margin-bottom:12px">🏷️</div><p>No saved listings yet. Tap 🏷️ on any listing to save it.</p></div>{/if}
      </div>

    {:else if profileTab === 'history'}
      <div class="card" style="padding:0;overflow:hidden">
        <div style="padding:18px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">
          <div class="section-title">Trade History ({tradeHistory.length})</div>
          {#if tradeHistory.length > 0}<span style="font-size:0.82rem;color:var(--text3)">{tradeHistory.filter(t=>t.status==='completed').length} completed · {tradeHistory.filter(t=>t.status==='cancelled').length} cancelled</span>{/if}
        </div>
        {#each tradeHistory as t}
          <div class="trade-hist-item">
            <div class="chat-item-avatar" style="border-radius:12px;font-size:0.72rem">{t.status==='completed'?'✅':'❌'}</div>
            <div style="flex:1;min-width:0">
              <div style="font-weight:700;font-size:0.93rem">{t.item}</div>
              <div class="text-sm text-muted">with {t.with}{t.created_at ? ` · ${new Date(t.created_at).toLocaleDateString([],{month:'short',day:'numeric',year:'numeric'})}` : ''}</div>
            </div>
            <span class="tag {t.status==='completed'?'green':''}" style="flex-shrink:0;text-transform:capitalize">{t.status}</span>
            {#if t.status==='completed'}<span style="font-size:0.78rem;color:#10b981;font-weight:600;white-space:nowrap">+5 kg CO₂</span>{/if}
          </div>
        {/each}
        {#if tradeHistory.length === 0}
          <div style="text-align:center;padding:52px 24px;color:var(--text3)">
            <div style="font-size:2.8rem;margin-bottom:12px">📋</div>
            <p style="font-size:0.9rem">No completed or cancelled trades yet.</p>
          </div>
        {/if}
      </div>

    {:else if profileTab === 'edit'}
      <div class="card" style="max-width:560px;padding:28px">
        <div class="section-title" style="margin-bottom:20px">Edit Profile</div>
        <div class="form-group"><label for="edit-username">Username</label><input id="edit-username" type="text" value={authState.user.username} disabled style="opacity:0.55;cursor:not-allowed"><p style="font-size:0.76rem;color:var(--text3);margin-top:5px">Username cannot be changed.</p></div>
        <div class="form-group"><label for="edit-email">Email</label><input id="edit-email" type="email" value={authState.user.email} disabled style="opacity:0.55;cursor:not-allowed"></div>
        <div class="form-group"><label for="edit-bio">Bio</label><textarea id="edit-bio" bind:value={editBio} placeholder="Tell the community about yourself…" rows="4" style="min-height:100px"></textarea></div>
        <div style="display:flex;gap:10px"><button class="btn btn-primary" onclick={saveEditProfile}>Save Changes</button><button class="btn btn-outline" onclick={() => { editBio=profileBio; }}>Cancel</button></div>
      </div>

    {:else if profileTab === 'security'}
      <div class="card" style="max-width:460px;padding:28px">
        <div class="section-title" style="margin-bottom:6px">Change Password</div>
        <p style="font-size:0.84rem;color:var(--text3);margin-bottom:22px">At least 8 characters, different from your current password.</p>
        {#if pwError}<div class="alert-error">{pwError}</div>{/if}
        {#if pwSuccess}<div class="alert-success">{pwSuccess}</div>{/if}
        <div class="form-group"><label for="pw-current">Current Password</label><input id="pw-current" type="password" bind:value={pwForm.current} autocomplete="current-password"></div>
        <div class="form-group"><label for="pw-new">New Password</label><input id="pw-new" type="password" bind:value={pwForm.next} autocomplete="new-password"></div>
        <div class="form-group"><label for="pw-confirm">Confirm New Password</label><input id="pw-confirm" type="password" bind:value={pwForm.confirm} autocomplete="new-password"></div>
        <button class="btn btn-primary" onclick={changePassword} disabled={pwLoading}>{pwLoading?'Updating…':'Update Password'}</button>
        <div style="margin-top:36px;padding-top:24px;border-top:1px solid var(--border)">
          <div style="font-weight:700;font-size:0.92rem;color:var(--warn);margin-bottom:6px">Danger Zone</div>
          <p style="font-size:0.82rem;color:var(--text3);margin-bottom:14px">Permanently delete your account and all data. Cannot be undone.</p>
          <button class="btn btn-danger btn-sm" onclick={() => { showDeleteModal=true; deletePassword=''; deleteError=''; }}>Delete Account</button>
        </div>
      </div>

    {:else if profileTab === 'settings'}
      <div class="card" style="max-width:520px;padding:28px">
        <div class="section-title" style="margin-bottom:22px">Preferences</div>
        <div class="settings-row"><div><div style="font-weight:600;font-size:0.92rem">Trade Match Notifications</div><div style="font-size:0.8rem;color:var(--text3);margin-top:3px">Get notified when a K-way loop matches</div></div><button class="toggle {settingsNotifs?'on':''}" onclick={() => { settingsNotifs=!settingsNotifs; saveSettings(); }}><span></span></button></div>
        <div class="settings-row"><div><div style="font-weight:600;font-size:0.92rem">Public Profile</div><div style="font-size:0.8rem;color:var(--text3);margin-top:3px">Allow others to view your profile and reputation</div></div><button class="toggle {settingsPublic?'on':''}" onclick={() => { settingsPublic=!settingsPublic; saveSettings(); }}><span></span></button></div>
        <div class="settings-row"><div><div style="font-weight:600;font-size:0.92rem">Eco Impact Alerts</div><div style="font-size:0.8rem;color:var(--text3);margin-top:3px">Weekly CO₂ savings and eco milestones</div></div><button class="toggle {settingsEcoAlerts?'on':''}" onclick={() => { settingsEcoAlerts=!settingsEcoAlerts; saveSettings(); }}><span></span></button></div>
        <div style="margin-top:30px;padding-top:22px;border-top:1px solid var(--border)">
          <div class="section-title" style="font-size:0.9rem;margin-bottom:14px">Account Info</div>
          <div style="display:flex;flex-direction:column;gap:10px">
            <div class="info-row"><span>User ID</span><code style="font-size:0.79rem;background:var(--surface2);padding:3px 9px;border-radius:6px;color:var(--text3)">{authState.user.id}</code></div>
            <div class="info-row"><span>Email</span><span style="color:var(--text2)">{authState.user.email}</span></div>
          </div>
        </div>
        <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--border)">
          <button class="btn btn-outline btn-sm" style="color:var(--warn);border-color:rgba(225,29,72,0.3)" onclick={handleLogout}>Sign Out</button>
        </div>
      </div>
    {/if}
  {/if}
</div>

<!-- NEW LISTING MODAL -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay {modals.newListing?'open':''}" onclick={closeModals}>
  <div class="modal">
    <div class="modal-header"><div class="modal-title">New Listing</div><button class="close-btn" onclick={() => modals.newListing=false}>×</button></div>

    <!-- Image upload -->
    <div class="form-group">
      <label>Photo (optional, max 1 MB)</label>
      <div class="image-upload-area" onclick={() => document.getElementById('nl-image')?.click()}>
        {#if newListingImagePreview}
          <img src={newListingImagePreview} alt="preview" style="width:100%;height:100%;object-fit:cover;border-radius:var(--radius-sm)">
          <button class="image-clear-btn" onclick={(e) => { e.stopPropagation(); newListingImage=null; newListingImagePreview=''; }}>×</button>
        {:else}
          <div style="text-align:center;color:var(--text3)">
            <div style="font-size:2rem;margin-bottom:6px">📷</div>
            <div style="font-size:0.82rem">Click to upload a photo</div>
          </div>
        {/if}
      </div>
      <input id="nl-image" type="file" accept="image/*" onchange={handleImageSelect} style="display:none">
    </div>

    <div class="form-group"><label for="nl-title">Item / Service Name</label><input id="nl-title" type="text" bind:value={newListing.title} placeholder="e.g. Vintage Polaroid Camera"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="form-group"><label for="nl-cat">Category</label><select id="nl-cat" bind:value={newListing.cat}>{#each categories.filter(c=>c!=='All') as c}<option>{c}</option>{/each}</select></div>
      <div class="form-group"><label for="nl-cond">Condition</label><select id="nl-cond" bind:value={newListing.condition}>{#each CONDITIONS as c}<option>{c}</option>{/each}</select></div>
    </div>
    <div class="form-group"><label for="nl-desc">Description</label><textarea id="nl-desc" bind:value={newListing.desc} placeholder="Describe condition, details, etc."></textarea></div>
    <div class="form-group"><label for="nl-wants">Looking to trade for…</label><input id="nl-wants" type="text" bind:value={newListing.wants} placeholder="e.g. Camera lenses, or open to offers"></div>
    <div class="form-group"><label for="nl-emoji">Emoji Icon</label><input id="nl-emoji" type="text" bind:value={newListing.emoji} placeholder="📷" maxlength="4" style="width:80px"></div>
    <button class="btn btn-primary w-full" onclick={addListing}>Post Listing</button>
  </div>
</div>

<!-- EDIT LISTING MODAL -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay {modals.editListing?'open':''}" onclick={closeModals}>
  <div class="modal">
    <div class="modal-header"><div class="modal-title">Edit Listing</div><button class="close-btn" onclick={() => modals.editListing=false}>×</button></div>

    <div class="form-group">
      <label>Photo</label>
      <div class="image-upload-area" onclick={() => document.getElementById('el-image')?.click()}>
        {#if editImagePreview}
          <img src={editImagePreview} alt="preview" style="width:100%;height:100%;object-fit:cover;border-radius:var(--radius-sm)">
          <button class="image-clear-btn" onclick={(e) => { e.stopPropagation(); editImage=null; editImagePreview=''; }}>×</button>
        {:else}
          <div style="text-align:center;color:var(--text3)">
            <div style="font-size:2rem;margin-bottom:6px">📷</div>
            <div style="font-size:0.82rem">Click to replace photo</div>
          </div>
        {/if}
      </div>
      <input id="el-image" type="file" accept="image/*" onchange={handleEditImageSelect} style="display:none">
    </div>

    <div class="form-group"><label for="el-title">Item / Service Name</label><input id="el-title" type="text" bind:value={editForm.title}></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="form-group"><label for="el-cat">Category</label><select id="el-cat" bind:value={editForm.cat}>{#each categories.filter(c=>c!=='All') as c}<option>{c}</option>{/each}</select></div>
      <div class="form-group"><label for="el-cond">Condition</label><select id="el-cond" bind:value={editForm.condition}>{#each CONDITIONS as c}<option>{c}</option>{/each}</select></div>
    </div>
    <div class="form-group"><label for="el-desc">Description</label><textarea id="el-desc" bind:value={editForm.desc}></textarea></div>
    <div class="form-group"><label for="el-wants">Looking to trade for…</label><input id="el-wants" type="text" bind:value={editForm.wants}></div>
    <div class="form-group"><label for="el-emoji">Emoji Icon</label><input id="el-emoji" type="text" bind:value={editForm.emoji} maxlength="4" style="width:80px"></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-primary w-full" onclick={saveEditListing} disabled={editLoading}>{editLoading ? 'Saving…' : 'Save Changes'}</button>
      <button class="btn btn-outline" onclick={() => modals.editListing=false}>Cancel</button>
    </div>
  </div>
</div>

<!-- LISTING DETAIL MODAL -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay {modals.listingDetail&&selectedListing?'open':''}" onclick={closeModals}>
  {#if selectedListing}
    <div class="modal" style="max-width:600px">
      <div class="modal-header">
        <div>
          <div class="modal-title">{selectedListing.title}</div>
          {#if selectedListing.view_count > 0}<div style="font-size:0.76rem;color:var(--text3);margin-top:2px">👁 {selectedListing.view_count} views</div>{/if}
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="btn btn-outline btn-sm" onclick={() => shareListing(selectedListing)} title="Copy link">🔗 Share</button>
          <button class="close-btn" onclick={() => modals.listingDetail=false}>×</button>
        </div>
      </div>

      <div style="position:relative;font-size:4.5rem;text-align:center;padding:24px;background:linear-gradient(135deg,var(--accent-light),var(--surface2));border-radius:var(--radius-sm);margin-bottom:16px;overflow:hidden">
        {#if selectedListing.image_data}
          <img src={selectedListing.image_data} alt={selectedListing.title} style="width:100%;height:200px;object-fit:cover;border-radius:var(--radius-sm);display:block;">
        {:else}
          {selectedListing.emoji}
        {/if}
        <span class="condition-badge" style="position:absolute;top:10px;right:10px;background:{conditionColors[selectedListing.condition]}18;color:{conditionColors[selectedListing.condition]};border-color:{conditionColors[selectedListing.condition]}44;font-size:0.8rem">{selectedListing.condition}</span>
      </div>

      <div style="display:flex;gap:16px;margin-bottom:14px;align-items:flex-start">
        <div style="flex:1"><p class="text-sm" style="line-height:1.65;margin-bottom:10px;color:var(--text2)">{selectedListing.desc}</p><div class="listing-tags">{#each selectedListing.tags as t}<span class="tag {t==='Eco-friendly'?'green':''}">{t}</span>{/each}</div></div>
        <div style="text-align:right;flex-shrink:0"><div class="text-sm text-muted">Listed by</div><div style="font-weight:700;margin-top:2px">{selectedListing.user}</div><div class="stars" style="font-size:0.8rem">★★★★★</div></div>
      </div>

      <div style="background:var(--surface2);border:1.5px solid var(--border);border-radius:var(--radius-sm);padding:12px 14px;margin-bottom:12px">
        <div class="text-muted text-sm" style="margin-bottom:3px">Looking for:</div>
        <div style="font-weight:700;color:var(--text)">{selectedListing.wants}</div>
      </div>

      <!-- AI Suggestion -->
      {#if !selectedListing.mine}
        <div style="margin-bottom:16px">
          <button class="btn btn-outline btn-sm" onclick={() => getAISuggestion(selectedListing.id)} disabled={aiLoading} style="width:100%">
            {aiLoading ? '🤖 Thinking…' : '🤖 AI: What should I offer?'}
          </button>
          {#if aiSuggestion}
            <div class="ai-suggestion-box">{aiSuggestion}</div>
          {/if}
        </div>
      {/if}

      <hr class="divider">
      <div class="section-header" style="margin-bottom:8px"><div class="section-title">Propose a Trade</div></div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">
        {#each myItems as i}
          <button class="proposal-item" style="cursor:pointer;{selectedOfferItem===i.id?'border-color:var(--accent);background:var(--accent-light);color:var(--accent2);':''}" onclick={() => selectOffer(i.id)}>
            <span>{i.emoji}</span>{i.title}
          </button>
        {/each}
        {#if myItems.length===0}<span class="text-muted text-sm">No listings yet — <button onclick={() => { modals.listingDetail=false; modals.newListing=true; }} style="color:var(--accent);font-weight:600;background:none;border:none;cursor:pointer;text-decoration:underline">add one first</button>.</span>{/if}
      </div>
      <button class="btn btn-primary w-full" style={selectedListing.mine?'opacity:0.4':''} disabled={selectedListing.mine} onclick={proposeTrade}>
        {selectedListing.mine ? 'This is your listing' : 'Send Trade Proposal & Open Chat'}
      </button>
    </div>
  {/if}
</div>

<!-- REVIEW MODAL -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay {showReviewModal?'open':''}" onclick={(e) => { if ((e.target as HTMLElement).classList.contains('modal-overlay')) showReviewModal=false; }}>
  <div class="modal" style="max-width:440px">
    <div class="modal-header"><div class="modal-title">Leave a Review</div><button class="close-btn" onclick={() => showReviewModal=false}>×</button></div>
    <p style="font-size:0.88rem;color:var(--text3);margin-bottom:18px">How was your trade with <strong style="color:var(--text)">{reviewTarget.revieweeName}</strong>?</p>
    <div class="form-group">
      <label>Rating</label>
      <div style="display:flex;gap:8px;margin-top:6px">
        {#each [1,2,3,4,5] as s}
          <button onclick={() => reviewForm.score=s} style="font-size:1.6rem;background:none;border:none;cursor:pointer;opacity:{reviewForm.score>=s?1:0.25};transition:opacity 0.15s">★</button>
        {/each}
      </div>
    </div>
    <div class="form-group"><label for="review-comment">Comment (optional)</label><textarea id="review-comment" bind:value={reviewForm.comment} placeholder="Describe how the trade went…" rows="3"></textarea></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-primary" style="flex:1" onclick={submitReview} disabled={reviewSubmitting}>{reviewSubmitting?'Submitting…':'Submit Review'}</button>
      <button class="btn btn-outline" onclick={() => showReviewModal=false}>Skip</button>
    </div>
  </div>
</div>

<!-- DELETE ACCOUNT MODAL -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay {showDeleteModal?'open':''}" onclick={(e) => { if ((e.target as HTMLElement).classList.contains('modal-overlay')) showDeleteModal=false; }}>
  <div class="modal" style="max-width:460px">
    <div class="modal-header"><div class="modal-title" style="color:var(--warn)">Delete Account</div><button class="close-btn" onclick={() => showDeleteModal=false}>×</button></div>
    <div style="background:rgba(225,29,72,0.06);border:1.5px solid rgba(225,29,72,0.2);border-radius:var(--radius-sm);padding:14px 16px;margin-bottom:20px">
      <div style="font-weight:700;font-size:0.88rem;color:var(--warn);margin-bottom:6px">⚠ This action is permanent and cannot be undone</div>
      <ul style="font-size:0.82rem;color:#dc2626;line-height:1.7;padding-left:18px;margin:0">
        <li>Your account and login credentials will be deleted</li>
        <li>All your listings will be removed</li>
        <li>Your reputation score and trade history will be erased</li>
      </ul>
    </div>
    {#if deleteError}<div class="alert-error">{deleteError}</div>{/if}
    <div class="form-group"><label for="delete-confirm-pw">Enter your password to confirm</label><input id="delete-confirm-pw" type="password" bind:value={deletePassword} autocomplete="current-password" style="border-color:rgba(225,29,72,0.35)"></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-danger" style="flex:1;{deleteLoading?'opacity:0.7;cursor:not-allowed':''}" onclick={deleteAccount} disabled={deleteLoading}>{deleteLoading?'Deleting…':'Permanently Delete My Account'}</button>
      <button class="btn btn-outline" onclick={() => showDeleteModal=false}>Cancel</button>
    </div>
  </div>
</div>

{#if toastMsg}
  <div class="toast {toastType?`toast-${toastType}`:''}">{toastMsg}</div>
{/if}
