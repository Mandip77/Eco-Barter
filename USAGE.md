# EcoBarter — User Guide

EcoBarter is a sustainable marketplace where you trade goods and skills directly with other people — no money involved. This guide walks you through every feature from account creation to completing your first trade.

**Live site:** https://ecobarter.man-dip.dev

---

## Table of Contents

1. [Creating an Account](#1-creating-an-account)
2. [Browsing Listings](#2-browsing-listings)
3. [Listing an Item or Skill](#3-listing-an-item-or-skill)
4. [Proposing a Trade](#4-proposing-a-trade)
5. [Negotiating in Chat](#5-negotiating-in-chat)
6. [Scheduling the Handoff](#6-scheduling-the-handoff)
7. [Completing the Trade with QR Verification](#7-completing-the-trade-with-qr-verification)
8. [Leaving a Review](#8-leaving-a-review)
9. [Your Profile and Reputation](#9-your-profile-and-reputation)
10. [Account Settings](#10-account-settings)
11. [Using on Mobile](#11-using-on-mobile)
12. [Tips for a Successful Trade](#12-tips-for-a-successful-trade)

---

## 1. Creating an Account

1. Go to **https://ecobarter.man-dip.dev** (or `http://localhost:5173` if running locally).
2. Click **Sign In** in the top-right corner (or the **Sign In** tab in the bottom navigation on mobile).
3. Switch to the **Register** tab.
4. Enter:
   - A **username** (publicly visible)
   - Your **email address**
   - A **password** — minimum 8 characters, must contain at least one letter and one digit
5. Click **Create Account**.

You are logged in immediately after registering. Your session lasts 24 hours, after which you will be asked to sign in again.

> **Already have an account?** Use the **Login** tab and enter your email and password.

---

## 2. Browsing Listings

The **Browse** page is the main marketplace view.

### Searching and filtering

- **Search bar** — Type any keyword to filter listings by title, description, or what the owner wants.
- **Category chips** — Click a category (Electronics, Books & Media, Clothing, Furniture, Skills & Services, Plants & Garden, Sports & Outdoors, Food & Produce) to show only that type.
- **Near me** — Click the location button to filter listings within a chosen radius (1 km, 5 km, 10 km, 25 km, or 50 km) of your current location. Your browser will ask for permission.

### Reading a listing card

Each card shows:
- The item's emoji or uploaded photo
- Title, owner username, and condition badge (New / Like New / Good / Fair / Poor)
- Tags and a short description
- What the owner is looking for in exchange
- Distance from you (if location is enabled)
- An expiry indicator if the listing is about to expire

### Saving a listing

Click the **bookmark icon** (top-left of any card) to save it to your watchlist. You can view saved listings later from your Profile → Saved tab.

### Viewing a listing in detail

Click any card to open a full-detail modal with the complete description, condition, owner profile, and a **Propose Trade** button.

---

## 3. Listing an Item or Skill

1. Click **+ New Listing** in the navigation bar (or the **+** button in the mobile bottom bar).
   - You must be signed in. If not, you will be redirected to the login page.
2. Fill in the form:
   - **Title** — Short, descriptive name (e.g. "Vintage Kodak film camera")
   - **Category** — Pick the most relevant category
   - **Condition** — How worn or new is the item?
   - **Description** — Describe condition, size, age, any defects
   - **What I want** — Describe what you are looking for in return. Be specific — the matching engine uses this to find you a partner (e.g. "Looking for a bicycle repair kit or any gardening tools")
   - **Emoji** — Pick an emoji to represent your item if you are not uploading a photo
   - **Photo** (optional) — Upload a JPEG, PNG, WebP, or GIF up to 1 MB
3. Click **Post Listing**.

Your listing is now live in the marketplace and the trade engine will begin looking for matches immediately.

> **AI Suggestion:** After posting, you can open your listing and click **Get AI Suggestion** to receive an AI-generated description of what a good exchange partner might look like.

### Editing or deleting a listing

Go to **Profile → My Listings**, find the listing, and click the edit (✏️) or delete (🗑️) icon.

---

## 4. Proposing a Trade

EcoBarter matches trades automatically, but you can also propose directly:

### Manual proposal

1. Open any listing you are interested in.
2. Click **Propose Trade**.
3. Select one of your own listings as the item you are offering in return.
4. Click **Send Proposal**.

The other user will receive a notification and can accept, counter, or decline.

### Automatic matching

The trade engine runs in the background and checks for matches every time a listing is created or updated. It finds:

- **2-way swaps** — You have what they want; they have what you want
- **3-way rings** — A → B → C → A (your item goes to B, B's item goes to C, C's item comes back to you)
- **4-way chains** — A → B → C → D → A

When a match is found, all participants are notified instantly via a real-time alert, and a conversation thread is opened automatically in the **Negotiation** tab.

---

## 5. Negotiating in Chat

The **Negotiation** tab (💬 on mobile) shows all your active trade conversations.

### Chat basics

- Click a conversation in the sidebar to open it.
- Type a message in the input box at the bottom and press **Enter** or click **Send**.
- Messages are delivered in real time to all participants.

### Counter-proposal

If you want to offer a different item than the one originally matched:

1. Click **Counter-offer** in the chat header.
2. Select one of your listings from the picker.
3. Click **Send Counter** — the other participant(s) will see your revised offer in the chat.

### Batch propose (wishlist)

On a user's profile or from the listings page, you can select multiple items and propose them all at once as a bundle offer. Hold/long-tap a listing card and tick the checkboxes, then click **Batch Propose**.

---

## 6. Scheduling the Handoff

Once all parties agree to the trade:

1. In the chat header, click **📅 Schedule**.
2. Enter a date, time, and meeting point (e.g. "Saturday 3pm, Central Park south entrance").
3. Click **Confirm Schedule**.

The scheduled time appears in the conversation preview in the sidebar so everyone can see it at a glance. To change it, click **📅 Reschedule** and submit a new time.

---

## 7. Completing the Trade with QR Verification

Physical handoffs are verified with QR codes to confirm that goods actually changed hands.

### At the swap point

1. Go to the **Negotiation** page and open the active trade.
2. Click **Start Handoff / Show QR**.
3. Your QR code is displayed on screen — it contains your verification token for this trade.
4. Each participant scans the other's QR code with their phone camera (or the in-app scanner).
5. Once your code is scanned by the other party, your leg of the trade is marked **Verified** ✓.

For 3-way or 4-way trades, every participant must scan and be scanned before the trade is marked **Completed**.

> **Tip:** Open the QR page before you leave home so you are not scrambling at the meetup point.

---

## 8. Leaving a Review

After a trade is marked **Completed**, you can leave a review for the other participant(s):

1. Go to **Profile → Trade History**.
2. Find the completed trade and click **Leave Review**.
3. Select a star rating (1–5) and optionally add a comment.
4. Click **Submit Review**.

Reviews feed directly into the EigenTrust reputation score. You can only review someone once per trade, and you must have participated in the trade yourself.

---

## 9. Your Profile and Reputation

Access your profile by clicking your avatar in the top-right corner → **View Profile**, or tapping the **👤 Profile** tab on mobile.

### Overview tab

- **EigenTrust score** and rank tier (Novice / Trusted / Eco-Champion)
- **CO₂ saved** — estimated kilograms of emissions offset by your completed trades
- **Trade count** and review summary
- Recent reviews left by your trade partners

### Reputation tiers

| Tier | Score range | What it means |
|---|---|---|
| Novice | 0–19 | Just getting started |
| Trusted | 20–50 | Established track record |
| Eco-Champion | 50+ | Highly trusted, active trader |

Scores decay gradually if you stop trading — a dormant account loses half its trust score every 90 days. Stay active to maintain your rank.

### My Listings tab

All your active listings. Edit or delete any of them here.

### Saved tab

All listings you have bookmarked for later.

### Trade History tab

Every completed, pending, and cancelled trade you have been part of.

### Customising your profile

Go to **Profile → Edit Profile**:

- Change your **display emoji** and **avatar colour**
- Update your **bio**

---

## 10. Account Settings

Access settings from your avatar menu → **Settings**, or **Profile → Settings** tab.

| Setting | What it does |
|---|---|
| Notifications | Toggle trade match and message alerts |
| Public profile | Show or hide your profile from other users |
| Eco alerts | Receive reminders about expiring listings |

### Changing your password

Avatar menu → **Change Password** → enter your current password and a new one (min 8 characters, at least one letter and one digit).

### Deleting your account

Avatar menu → **Settings** → **Delete Account** at the bottom. You will be asked to confirm with your password. This action is permanent and removes all your listings and trade history.

---

## 11. Using on Mobile

EcoBarter works fully on mobile browsers — no app download required.

- Open the site in your mobile browser and **add it to your home screen** for an app-like experience (Share → Add to Home Screen on iOS, or the browser menu on Android).
- The **bottom navigation bar** gives quick access to Browse, Negotiate, Post, and Profile.
- The **+ Post** button in the bottom bar opens the new listing form.
- In the **Negotiate** tab, tap a conversation to open it full-screen. Use the **← Back** button to return to the conversation list.
- Modals (listing detail, new listing form) slide up from the bottom of the screen.

---

## 12. Tips for a Successful Trade

**Write a specific "what I want" description.** The matching engine uses this text to find compatible partners. "Looking for a beginner guitar or ukulele, any condition" works much better than "open to anything".

**Upload a photo.** Listings with photos get more attention and convey item condition much more clearly than text alone.

**Respond quickly.** Once a match is found, the other party may be chatting with multiple potential partners. A fast reply increases your chances of locking in the trade.

**Be honest about condition.** If an item has a scratch or missing part, say so. Accurate descriptions lead to higher review scores and a better reputation.

**Meet in a public place.** Choose a well-lit, busy location for physical handoffs. A library lobby, café, or community centre is ideal.

**Use the scheduler.** Confirming a specific time in the chat reduces no-shows and gives everyone a clear commitment.

**Leave a review.** Reviews are how the community builds trust. Even a short 5-star review with no comment helps the other person's reputation.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| "Identity service is temporarily unreachable" | The backend is starting up. Wait 30 seconds and refresh. |
| Listings are not loading | Check your internet connection. The catalog service may be restarting. |
| QR code won't scan | Make sure both phones have good lighting and the screen brightness is turned up. |
| I can't find a match | Add more detail to your "what I want" field, or broaden the item category. |
| I was logged out unexpectedly | Sessions last 24 hours. Sign in again — your listings and history are preserved. |
| Location filter not working | Allow location access in your browser settings and try again. |

---

*For bugs or feature requests, open an issue at [github.com/Mandip77/Eco-Barter/issues](https://github.com/Mandip77/Eco-Barter/issues).*
