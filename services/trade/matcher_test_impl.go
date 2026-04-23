//go:build test

package main

import (
	"encoding/json"
	"log"
)

// EvaluateMatch — test build.
// Uses SQLite-compatible queries (no FOR UPDATE SKIP LOCKED, no JOINs on JSON).
// Tries K=2, K=3, K=4 loop matching via in-memory iteration.
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

	newItem := &Item{
		ID:       event.ID,
		OwnerID:  event.OwnerID,
		Category: event.Category,
		Title:    event.Emoji + " " + event.Title,
		Wants:    json.RawMessage(wantsBytes),
		Status:   "available",
	}
	if err := DB.Save(newItem).Error; err != nil {
		log.Printf("[Matcher] Failed to save item: %v", err)
		return
	}
	log.Printf("[Matcher] Saved Item %v [%v]. Searching K=2,3,4 loops...", newItem.Title, newItem.Category)

	// K=2: direct swap — B has targetCategory and wants A's category
	var bCandidates []Item
	DB.Where("category = ? AND status = ? AND owner_id != ?", targetCategory, "available", newItem.OwnerID).Find(&bCandidates)
	for _, bItem := range bCandidates {
		var bWants map[string]interface{}
		json.Unmarshal(bItem.Wants, &bWants)
		if bWants["category"] == newItem.Category {
			log.Printf("[Matcher] ✅ K=2 MATCH\n  A: %v\n  B: %v", newItem.Title, bItem.Title)
			DB.Model(&Item{}).Where("id IN ?", []string{newItem.ID, bItem.ID}).Update("status", "matched")
			proposal := TradeProposal{
				K: 2, Status: "pending",
				UserA: newItem.OwnerID, ItemA: newItem.Title,
				UserB: bItem.OwnerID, ItemB: bItem.Title,
			}
			if err := DB.Create(&proposal).Error; err != nil {
				log.Printf("[Matcher] Failed to create K=2 proposal: %v", err)
				return
			}
			log.Printf("[Matcher] K=2 TradeProposal #%d created", proposal.ID)
			return
		}
	}

	// K=3: A→B→C→A
	for _, bItem := range bCandidates {
		var bWants map[string]interface{}
		json.Unmarshal(bItem.Wants, &bWants)
		bWantsCategory, _ := bWants["category"].(string)

		var cCandidates []Item
		DB.Where("category = ? AND status = ? AND owner_id != ? AND owner_id != ?",
			bWantsCategory, "available", newItem.OwnerID, bItem.OwnerID).Find(&cCandidates)

		for _, cItem := range cCandidates {
			var cWants map[string]interface{}
			json.Unmarshal(cItem.Wants, &cWants)
			if cWants["category"] == newItem.Category {
				log.Printf("[Matcher] 🔥 K=3 MATCH\n  A: %v\n  B: %v\n  C: %v",
					newItem.Title, bItem.Title, cItem.Title)
				DB.Model(&Item{}).Where("id IN ?", []string{newItem.ID, bItem.ID, cItem.ID}).Update("status", "matched")
				proposal := TradeProposal{
					K: 3, Status: "pending",
					UserA: newItem.OwnerID, ItemA: newItem.Title,
					UserB: bItem.OwnerID, ItemB: bItem.Title,
					UserC: cItem.OwnerID, ItemC: cItem.Title,
				}
				if err := DB.Create(&proposal).Error; err != nil {
					log.Printf("[Matcher] Failed to create K=3 proposal: %v", err)
					return
				}
				log.Printf("[Matcher] K=3 TradeProposal #%d created", proposal.ID)
				return
			}
		}
	}

	// K=4: A→B→C→D→A
	for _, bItem := range bCandidates {
		var bWants map[string]interface{}
		json.Unmarshal(bItem.Wants, &bWants)
		bWantsCategory, _ := bWants["category"].(string)

		var cCandidates []Item
		DB.Where("category = ? AND status = ? AND owner_id != ? AND owner_id != ?",
			bWantsCategory, "available", newItem.OwnerID, bItem.OwnerID).Find(&cCandidates)

		for _, cItem := range cCandidates {
			var cWants map[string]interface{}
			json.Unmarshal(cItem.Wants, &cWants)
			cWantsCategory, _ := cWants["category"].(string)

			var dCandidates []Item
			DB.Where("category = ? AND status = ? AND owner_id != ? AND owner_id != ? AND owner_id != ?",
				cWantsCategory, "available", newItem.OwnerID, bItem.OwnerID, cItem.OwnerID).Find(&dCandidates)

			for _, dItem := range dCandidates {
				var dWants map[string]interface{}
				json.Unmarshal(dItem.Wants, &dWants)
				if dWants["category"] == newItem.Category {
					log.Printf("[Matcher] 💫 K=4 MATCH\n  A: %v\n  B: %v\n  C: %v\n  D: %v",
						newItem.Title, bItem.Title, cItem.Title, dItem.Title)
					DB.Model(&Item{}).Where("id IN ?",
						[]string{newItem.ID, bItem.ID, cItem.ID, dItem.ID}).Update("status", "matched")
					proposal := TradeProposal{
						K: 4, Status: "pending",
						UserA: newItem.OwnerID, ItemA: newItem.Title,
						UserB: bItem.OwnerID, ItemB: bItem.Title,
						UserC: cItem.OwnerID, ItemC: cItem.Title,
						UserD: dItem.OwnerID, ItemD: dItem.Title,
					}
					if err := DB.Create(&proposal).Error; err != nil {
						log.Printf("[Matcher] Failed to create K=4 proposal: %v", err)
						return
					}
					log.Printf("[Matcher] K=4 TradeProposal #%d created", proposal.ID)
					return
				}
			}
		}
	}

	log.Printf("[Matcher] No loop found for %s yet.", newItem.Title)
}
