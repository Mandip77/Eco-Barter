//go:build test

package main

import (
	"encoding/json"
	"log"

	"gorm.io/datatypes"
)

// EvaluateMatch — test build.
// Uses SQLite-compatible queries without FOR UPDATE SKIP LOCKED.
// Avoids wrapping raw SQL Scan inside DB.Transaction() which causes
// SQLITE_MISUSE(21) with glebarez/sqlite on a single-connection pool.
func EvaluateMatch(eventData []byte) {
	var event ProductEvent
	if err := json.Unmarshal(eventData, &event); err != nil {
		log.Printf("Failed to unmarshal JetStream event: %v", err)
		return
	}

	wantsBytes, _ := json.Marshal(event.Wants)
	var wantsMap map[string]interface{}
	json.Unmarshal(wantsBytes, &wantsMap)
	targetCategory, _ := wantsMap["category"].(string)

	// 1. Upsert the new item
	newItem := &Item{
		ID:       event.ID,
		OwnerID:  event.OwnerID,
		Category: event.Category,
		Title:    event.Emoji + " " + event.Title,
		Wants:    datatypes.JSON(wantsBytes),
		Status:   "available",
	}
	if err := DB.Save(newItem).Error; err != nil {
		log.Printf("[Matcher] Failed to save item: %v", err)
		return
	}
	log.Printf("[Matcher] Saved Item %v [%v]. Looking for K=3 loops...", newItem.Title, newItem.Category)

	// 2. Find all available items that have targetCategory (what A wants)
	var bCandidates []Item
	DB.Where("category = ? AND status = ? AND owner_id != ?", targetCategory, "available", newItem.OwnerID).Find(&bCandidates)

	// 3. For each B candidate, find a C that completes the loop
	for _, bItem := range bCandidates {
		var bWants map[string]interface{}
		json.Unmarshal(bItem.Wants, &bWants)
		bWantsCategory, _ := bWants["category"].(string)

		// C must: have bWantsCategory, want A's category, different owner from A and B
		var cCandidates []Item
		DB.Where(
			"category = ? AND status = ? AND owner_id != ? AND owner_id != ?",
			bWantsCategory, "available", newItem.OwnerID, bItem.OwnerID,
		).Find(&cCandidates)

		for _, cItem := range cCandidates {
			var cWants map[string]interface{}
			json.Unmarshal(cItem.Wants, &cWants)
			cWantsCategory, _ := cWants["category"].(string)

			// C must want what A has (A's category) to complete the loop
			if cWantsCategory == newItem.Category {
				log.Printf("[Matcher] 🔥 K=3 MATCH FOUND 🔥\n  A: %v\n  B: %v\n  C: %v",
					newItem.Title, bItem.Title, cItem.Title)

				// Mark all three as matched
				DB.Model(&Item{}).
					Where("id IN ?", []string{newItem.ID, bItem.ID, cItem.ID}).
					Update("status", "matched")

				// Create trade proposal
				proposal := TradeProposal{
					Status: "pending",
					UserA:  newItem.OwnerID,
					ItemA:  newItem.Title,
					UserB:  bItem.OwnerID,
					ItemB:  bItem.Title,
					UserC:  cItem.OwnerID,
					ItemC:  cItem.Title,
				}
				if err := DB.Create(&proposal).Error; err != nil {
					log.Printf("[Matcher] Failed to create proposal: %v", err)
					return
				}
				log.Printf("[Matcher] TradeProposal logged for Match Set %d", proposal.ID)
				log.Printf("[Matcher] (test) Would publish to trade_hub:proposals")
				return // One match per event is enough
			}
		}
	}

	log.Printf("[Matcher] No loop found for %s yet.", newItem.Title)
}
