package main

import (
	"time"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// ProductEvent is the struct matching the JSON payload emitted by the Catalog Service to NATS
type ProductEvent struct {
	ID        string                 `json:"_id"`
	OwnerID   string                 `json:"owner_id"`
	Title     string                 `json:"title"`
	Emoji     string                 `json:"emoji"`
	Category  string                 `json:"category"`
	Wants     map[string]interface{} `json:"wants"`
	Tags      []string               `json:"tags"`
	CreatedAt time.Time              `json:"created_at"`
}

// Item represents a mirrored entry dynamically persisting events inside PostgreSQL cleanly.
type Item struct {
	ID        string         `gorm:"primaryKey" json:"id"`
	OwnerID   string         `gorm:"index" json:"owner_id"`
	Category  string         `gorm:"index" json:"category"`
	Title     string         `json:"title"`
	Wants     datatypes.JSON `json:"wants"`
	Status    string         `gorm:"default:'available'" json:"status"` // available, matched
	CreatedAt time.Time      `json:"created_at"`
}

// TradeProposal represents an identified match recorded in PostgreSQL
type TradeProposal struct {
	ID        uint           `gorm:"primaryKey" json:"id"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
	DeletedAt gorm.DeletedAt `gorm:"index" json:"-"`

	Status string `gorm:"default:'pending'" json:"status"` // pending, accepted, rejected, completed
	
	// K=3 Chain representation: Node A -> Node B -> Node C -> Node A
	UserA      string `json:"user_a"`
	ItemA      string `json:"item_a"`
	VerifiedA  bool   `gorm:"default:false" json:"verified_a"`
	
	UserB      string `json:"user_b"`
	ItemB      string `json:"item_b"`
	VerifiedB  bool   `gorm:"default:false" json:"verified_b"`
	
	UserC      string `json:"user_c"`
	ItemC      string `json:"item_c"`
	VerifiedC  bool   `gorm:"default:false" json:"verified_c"`
}
