//go:build !test

package main

import (
	"encoding/json"
	"log"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// EvaluateMatch is triggered by the Worker Pool when a NATS message arrives.
// Production version uses PostgreSQL's FOR UPDATE SKIP LOCKED for safe concurrency.
func EvaluateMatch(eventData []byte) {
	var event ProductEvent
	err := json.Unmarshal(eventData, &event)
	if err != nil {
		log.Printf("Failed to unmarshal JetStream event: %v", err)
		return
	}

	wantsBytes, _ := json.Marshal(event.Wants)

	newItem := &Item{
		ID:       event.ID,
		OwnerID:  event.OwnerID,
		Category: event.Category,
		Title:    event.Emoji + " " + event.Title,
		Wants:    datatypes.JSON(wantsBytes),
		Status:   "available",
	}

	err = DB.Transaction(func(tx *gorm.DB) error {
		if err := tx.Save(newItem).Error; err != nil {
			return err
		}

		log.Printf("[Matcher] Saved Item %v [%v]. Looking for K=3 loops...", newItem.Title, newItem.Category)

		var wantsMap map[string]interface{}
		json.Unmarshal(wantsBytes, &wantsMap)
		targetCategory, _ := wantsMap["category"].(string)

		type MatchResult struct {
			B_ID string
			C_ID string
		}
		var match MatchResult

		// PostgreSQL: uses FOR UPDATE SKIP LOCKED to prevent double-matching under load
		query := `
			SELECT b.id as b_id, c.id as c_id
			FROM items b
			JOIN items c ON c.category = b.wants->>'category'
			WHERE 
				b.category = ? 
				AND ? = c.wants->>'category'
				AND b.status = 'available'
				AND c.status = 'available'
				AND b.owner_id != ? 
				AND c.owner_id != ? 
				AND b.owner_id != c.owner_id
			LIMIT 1
			FOR UPDATE SKIP LOCKED;
		`

		if err := tx.Raw(query, targetCategory, newItem.Category, newItem.OwnerID, newItem.OwnerID).Scan(&match).Error; err != nil {
			return err
		}

		if match.B_ID != "" && match.C_ID != "" {
			var bItem, cItem Item
			tx.First(&bItem, "id = ?", match.B_ID)
			tx.First(&cItem, "id = ?", match.C_ID)

			log.Printf("[Matcher] 🔥 K=3 MATCH FOUND 🔥\n  A: %v\n  B: %v\n  C: %v", newItem.Title, bItem.Title, cItem.Title)

			tx.Model(&Item{}).Where("id IN ?", []string{newItem.ID, bItem.ID, cItem.ID}).Update("status", "matched")

			proposal := TradeProposal{
				Status: "pending",
				UserA:  newItem.OwnerID,
				ItemA:  newItem.Title,
				UserB:  bItem.OwnerID,
				ItemB:  bItem.Title,
				UserC:  cItem.OwnerID,
				ItemC:  cItem.Title,
			}

			if err := tx.Create(&proposal).Error; err != nil {
				return err
			}
			log.Printf("[Matcher] TradeProposal safely logged for Match Set %d", proposal.ID)

			PublishToCentrifugo("trade_hub:proposals", map[string]interface{}{
				"event":    "new_proposal",
				"proposal": proposal,
			})
		} else {
			log.Printf("[Matcher] No loop found for %s yet.", newItem.Title)
		}

		return nil
	})

	if err != nil {
		log.Printf("[Matcher] Transaction failed: %v", err)
	}
}
