//go:build !test

package main

import (
	"encoding/json"
	"log"

	"gorm.io/gorm"
)

// EvaluateMatch is triggered by the Worker Pool when a NATS message arrives.
// Tries K=2 (direct swap), then K=3 (3-way loop), then K=4 (4-way loop).
// Production version uses PostgreSQL's FOR UPDATE SKIP LOCKED for safe concurrency.
func EvaluateMatch(eventData []byte) {
	var event ProductEvent
	if err := json.Unmarshal(eventData, &event); err != nil {
		log.Printf("Failed to unmarshal JetStream event: %v", err)
		return
	}

	wantsBytes, _ := json.Marshal(event.Wants)

	newItem := &Item{
		ID:       event.ID,
		OwnerID:  event.OwnerID,
		Category: event.Category,
		Title:    event.Emoji + " " + event.Title,
		Wants:    json.RawMessage(wantsBytes),
		Status:   "available",
	}

	err := DB.Transaction(func(tx *gorm.DB) error {
		if err := tx.Save(newItem).Error; err != nil {
			return err
		}

		var wantsMap map[string]interface{}
		json.Unmarshal(wantsBytes, &wantsMap)
		targetCategory, _ := wantsMap["category"].(string)

		log.Printf("[Matcher] Saved Item %v [%v]. Searching K=2,3,4 loops...", newItem.Title, newItem.Category)

		if matched, err := tryK2Match(tx, newItem, targetCategory); err != nil {
			return err
		} else if matched {
			return nil
		}

		if matched, err := tryK3Match(tx, newItem, targetCategory); err != nil {
			return err
		} else if matched {
			return nil
		}

		if matched, err := tryK4Match(tx, newItem, targetCategory); err != nil {
			return err
		} else if matched {
			return nil
		}

		log.Printf("[Matcher] No loop found for %s yet.", newItem.Title)
		return nil
	})

	if err != nil {
		log.Printf("[Matcher] Transaction failed: %v", err)
	}
}

func tryK2Match(tx *gorm.DB, a *Item, targetCategory string) (bool, error) {
	var bID string
	// B has targetCategory (what A wants) AND wants A's category
	query := `
		SELECT id FROM items
		WHERE category = ?
		  AND wants->>'category' = ?
		  AND status = 'available'
		  AND owner_id != ?
		LIMIT 1
		FOR UPDATE SKIP LOCKED
	`
	tx.Raw(query, targetCategory, a.Category, a.OwnerID).Scan(&bID)
	if bID == "" {
		return false, nil
	}

	var bItem Item
	tx.First(&bItem, "id = ?", bID)
	log.Printf("[Matcher] ✅ K=2 MATCH\n  A: %v\n  B: %v", a.Title, bItem.Title)

	tx.Model(&Item{}).Where("id IN ?", []string{a.ID, bItem.ID}).Update("status", "matched")

	proposal := TradeProposal{
		K:      2,
		Status: "pending",
		UserA:  a.OwnerID, ItemA: a.Title,
		UserB: bItem.OwnerID, ItemB: bItem.Title,
	}
	if err := tx.Create(&proposal).Error; err != nil {
		return false, err
	}
	log.Printf("[Matcher] K=2 TradeProposal #%d created", proposal.ID)
	PublishToCentrifugo("trade_hub:proposals", map[string]interface{}{
		"event": "new_proposal", "proposal": proposal,
	})
	return true, nil
}

func tryK3Match(tx *gorm.DB, a *Item, targetCategory string) (bool, error) {
	type Result struct{ B_ID, C_ID string }
	var match Result
	// A→B→C→A circular loop using PostgreSQL FOR UPDATE SKIP LOCKED
	query := `
		SELECT b.id AS b_id, c.id AS c_id
		FROM items b
		JOIN items c ON c.category = b.wants->>'category'
		WHERE b.category = ?
		  AND ? = c.wants->>'category'
		  AND b.status = 'available' AND c.status = 'available'
		  AND b.owner_id != ? AND c.owner_id != ?
		  AND b.owner_id != c.owner_id
		LIMIT 1
		FOR UPDATE SKIP LOCKED
	`
	tx.Raw(query, targetCategory, a.Category, a.OwnerID, a.OwnerID).Scan(&match)
	if match.B_ID == "" {
		return false, nil
	}

	var bItem, cItem Item
	tx.First(&bItem, "id = ?", match.B_ID)
	tx.First(&cItem, "id = ?", match.C_ID)
	log.Printf("[Matcher] 🔥 K=3 MATCH\n  A: %v\n  B: %v\n  C: %v", a.Title, bItem.Title, cItem.Title)

	tx.Model(&Item{}).Where("id IN ?", []string{a.ID, bItem.ID, cItem.ID}).Update("status", "matched")

	proposal := TradeProposal{
		K:      3,
		Status: "pending",
		UserA:  a.OwnerID, ItemA: a.Title,
		UserB:  bItem.OwnerID, ItemB: bItem.Title,
		UserC:  cItem.OwnerID, ItemC: cItem.Title,
	}
	if err := tx.Create(&proposal).Error; err != nil {
		return false, err
	}
	log.Printf("[Matcher] K=3 TradeProposal #%d created", proposal.ID)
	PublishToCentrifugo("trade_hub:proposals", map[string]interface{}{
		"event": "new_proposal", "proposal": proposal,
	})
	return true, nil
}

func tryK4Match(tx *gorm.DB, a *Item, targetCategory string) (bool, error) {
	type Result struct{ B_ID, C_ID, D_ID string }
	var match Result
	// A→B→C→D→A circular loop
	query := `
		SELECT b.id AS b_id, c.id AS c_id, d.id AS d_id
		FROM items b
		JOIN items c ON c.category = b.wants->>'category'
		JOIN items d ON d.category = c.wants->>'category'
		WHERE b.category = ?
		  AND ? = d.wants->>'category'
		  AND b.status = 'available' AND c.status = 'available' AND d.status = 'available'
		  AND b.owner_id != ? AND c.owner_id != ? AND d.owner_id != ?
		  AND b.owner_id != c.owner_id
		  AND b.owner_id != d.owner_id
		  AND c.owner_id != d.owner_id
		LIMIT 1
		FOR UPDATE SKIP LOCKED
	`
	tx.Raw(query, targetCategory, a.Category, a.OwnerID, a.OwnerID, a.OwnerID).Scan(&match)
	if match.B_ID == "" {
		return false, nil
	}

	var bItem, cItem, dItem Item
	tx.First(&bItem, "id = ?", match.B_ID)
	tx.First(&cItem, "id = ?", match.C_ID)
	tx.First(&dItem, "id = ?", match.D_ID)
	log.Printf("[Matcher] 💫 K=4 MATCH\n  A: %v\n  B: %v\n  C: %v\n  D: %v",
		a.Title, bItem.Title, cItem.Title, dItem.Title)

	tx.Model(&Item{}).Where("id IN ?", []string{a.ID, bItem.ID, cItem.ID, dItem.ID}).Update("status", "matched")

	proposal := TradeProposal{
		K:      4,
		Status: "pending",
		UserA:  a.OwnerID, ItemA: a.Title,
		UserB:  bItem.OwnerID, ItemB: bItem.Title,
		UserC:  cItem.OwnerID, ItemC: cItem.Title,
		UserD:  dItem.OwnerID, ItemD: dItem.Title,
	}
	if err := tx.Create(&proposal).Error; err != nil {
		return false, err
	}
	log.Printf("[Matcher] K=4 TradeProposal #%d created", proposal.ID)
	PublishToCentrifugo("trade_hub:proposals", map[string]interface{}{
		"event": "new_proposal", "proposal": proposal,
	})
	return true, nil
}
