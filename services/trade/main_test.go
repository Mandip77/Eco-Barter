package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/glebarez/sqlite"
	"github.com/golang-jwt/jwt/v5"
	"gorm.io/datatypes"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// ─────────────────────────────────────────────────────────────
// Test Setup: in-memory SQLite (avoids needing PostgreSQL)
// ─────────────────────────────────────────────────────────────

func setupTestDB(t *testing.T) {
	t.Helper()
	var err error
	// glebarez/sqlite is a pure-Go SQLite driver (no CGO)
	DB, err = gorm.Open(sqlite.Open("file::memory:?cache=shared&_busy_timeout=5000"), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		t.Fatalf("Failed to open in-memory SQLite: %v", err)
	}
	// In-memory SQLite requires a single connection to stay coherent across transactions
	sqlDB, _ := DB.DB()
	sqlDB.SetMaxOpenConns(1)
	if err := DB.AutoMigrate(&Item{}, &TradeProposal{}); err != nil {
		t.Fatalf("AutoMigrate failed: %v", err)
	}
	// Wipe all data so each test starts clean (shared memory DB persists within process)
	DB.Exec("DELETE FROM trade_proposals")
	DB.Exec("DELETE FROM items")
}

// makeToken creates a valid JWT for a given username using the dev secret.
func makeToken(t *testing.T, username string) string {
	t.Helper()
	secret := "super_secret_dev_key_do_not_use_in_prod"
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"username": username,
		"exp":      time.Now().Add(time.Hour).Unix(),
	})
	signed, err := token.SignedString([]byte(secret))
	if err != nil {
		t.Fatalf("Failed to sign test JWT: %v", err)
	}
	return signed
}

// setupRouter creates a Gin engine wired up with the same routes as main().
func setupRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()

	r.GET("/api/v1/trade", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "trade-engine"})
	})

	r.GET("/api/v1/trade/proposals", AuthRequired(), func(c *gin.Context) {
		currentUser := c.GetString("username")
		var proposals []TradeProposal
		result := DB.Where("user_a = ? OR user_b = ? OR user_c = ?",
			currentUser, currentUser, currentUser).Find(&proposals)
		if result.Error != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": result.Error.Error()})
			return
		}
		c.JSON(http.StatusOK, proposals)
	})

	type VerifyRequest struct {
		TradeID uint `json:"trade_id" binding:"required"`
	}

	r.POST("/api/v1/trade/verify", AuthRequired(), func(c *gin.Context) {
		currentUser := c.GetString("username")
		var req VerifyRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		var proposal TradeProposal
		if err := DB.First(&proposal, req.TradeID).Error; err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Trade proposal not found"})
			return
		}
		if proposal.Status != "pending" && proposal.Status != "in_progress" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Trade proposal is already completed or cancelled"})
			return
		}
		if proposal.UserA == currentUser {
			proposal.VerifiedA = true
		} else if proposal.UserB == currentUser {
			proposal.VerifiedB = true
		} else if proposal.UserC == currentUser {
			proposal.VerifiedC = true
		} else {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Target user not part of this trade"})
			return
		}
		if proposal.VerifiedA && proposal.VerifiedB && proposal.VerifiedC {
			proposal.Status = "completed"
		} else {
			proposal.Status = "in_progress"
		}
		DB.Save(&proposal)
		c.JSON(http.StatusOK, gin.H{"message": "Verification recorded", "proposal": proposal})
	})

	type MessageRequest struct {
		TradeID uint   `json:"trade_id" binding:"required"`
		Text    string `json:"text" binding:"required"`
	}

	r.POST("/api/v1/trade/message", AuthRequired(), func(c *gin.Context) {
		currentUser := c.GetString("username")
		var req MessageRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		var proposal TradeProposal
		if err := DB.First(&proposal, req.TradeID).Error; err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Trade proposal not found"})
			return
		}
		if proposal.UserA != currentUser && proposal.UserB != currentUser && proposal.UserC != currentUser {
			c.JSON(http.StatusForbidden, gin.H{"error": "You are not part of this trade"})
			return
		}
		// In tests, skip actual Centrifugo publish — just return OK
		c.JSON(http.StatusOK, gin.H{"status": "published"})
	})

	return r
}

// ─────────────────────────────────────────────────────────────
// AuthRequired middleware
// ─────────────────────────────────────────────────────────────

func TestAuthRequired_MissingHeader(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/trade/proposals", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", w.Code)
	}
}

func TestAuthRequired_BadToken(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/trade/proposals", nil)
	req.Header.Set("Authorization", "Bearer not.a.valid.token")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", w.Code)
	}
}

func TestAuthRequired_ValidToken(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	token := makeToken(t, "alice")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/trade/proposals", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 with valid token, got %d", w.Code)
	}
}

// ─────────────────────────────────────────────────────────────
// GET /api/v1/trade — health check
// ─────────────────────────────────────────────────────────────

func TestHealthCheck(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/trade", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)
	if body["status"] != "ok" {
		t.Errorf("expected status=ok, got %v", body["status"])
	}
}

// ─────────────────────────────────────────────────────────────
// GET /api/v1/trade/proposals
// ─────────────────────────────────────────────────────────────

func TestGetProposals_Empty(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	token := makeToken(t, "alice")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/trade/proposals", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}

	var proposals []TradeProposal
	json.Unmarshal(w.Body.Bytes(), &proposals)
	if len(proposals) != 0 {
		t.Errorf("expected 0 proposals, got %d", len(proposals))
	}
}

func TestGetProposals_OnlyReturnsUsersProposals(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()

	// alice is UserA in one proposal; bob has no proposals
	DB.Create(&TradeProposal{
		Status: "pending",
		UserA:  "alice", ItemA: "📷 Camera",
		UserB: "carol", ItemB: "📚 Books",
		UserC: "dave", ItemC: "🎸 Guitar",
	})

	aliceToken := makeToken(t, "alice")
	req := httptest.NewRequest(http.MethodGet, "/api/v1/trade/proposals", nil)
	req.Header.Set("Authorization", "Bearer "+aliceToken)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	var proposals []TradeProposal
	json.Unmarshal(w.Body.Bytes(), &proposals)
	if len(proposals) != 1 {
		t.Errorf("alice should see 1 proposal, got %d", len(proposals))
	}

	// bob should see 0
	bobToken := makeToken(t, "bob")
	req2 := httptest.NewRequest(http.MethodGet, "/api/v1/trade/proposals", nil)
	req2.Header.Set("Authorization", "Bearer "+bobToken)
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)

	var proposals2 []TradeProposal
	json.Unmarshal(w2.Body.Bytes(), &proposals2)
	if len(proposals2) != 0 {
		t.Errorf("bob should see 0 proposals, got %d", len(proposals2))
	}
}

// ─────────────────────────────────────────────────────────────
// POST /api/v1/trade/verify
// ─────────────────────────────────────────────────────────────

func seedProposal(t *testing.T) uint {
	t.Helper()
	p := TradeProposal{
		Status: "pending",
		UserA:  "alice", ItemA: "Camera",
		UserB: "bob", ItemB: "Books",
		UserC: "carol", ItemC: "Guitar",
	}
	DB.Create(&p)
	return p.ID
}

func TestVerify_UserA_SetsVerifiedA(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	id := seedProposal(t)

	body, _ := json.Marshal(map[string]interface{}{"trade_id": id})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/verify", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+makeToken(t, "alice"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d — body: %s", w.Code, w.Body.String())
	}

	var result map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &result)
	proposal := result["proposal"].(map[string]interface{})
	if proposal["verified_a"] != true {
		t.Error("verified_a should be true after alice verifies")
	}
	if proposal["status"] != "in_progress" {
		t.Errorf("status should be in_progress, got %v", proposal["status"])
	}
}

func TestVerify_AllThreeUsers_CompletesProposal(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	id := seedProposal(t)

	for _, username := range []string{"alice", "bob", "carol"} {
		body, _ := json.Marshal(map[string]interface{}{"trade_id": id})
		req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/verify", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+makeToken(t, username))
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("%s verify failed: %d — %s", username, w.Code, w.Body.String())
		}
	}

	var p TradeProposal
	DB.First(&p, id)
	if p.Status != "completed" {
		t.Errorf("expected status=completed after all 3 verify, got %s", p.Status)
	}
}

func TestVerify_NonParticipant_Returns400(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	id := seedProposal(t)

	body, _ := json.Marshal(map[string]interface{}{"trade_id": id})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/verify", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+makeToken(t, "eve")) // not in this trade
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for non-participant, got %d", w.Code)
	}
}

func TestVerify_AlreadyCompleted_Returns400(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()

	p := TradeProposal{
		Status:    "completed",
		UserA:     "alice", ItemA: "Camera",
		UserB:     "bob", ItemB: "Books",
		UserC:     "carol", ItemC: "Guitar",
		VerifiedA: true, VerifiedB: true, VerifiedC: true,
	}
	DB.Create(&p)

	body, _ := json.Marshal(map[string]interface{}{"trade_id": p.ID})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/verify", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+makeToken(t, "alice"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for already-completed trade, got %d", w.Code)
	}
}

func TestVerify_NonExistentTrade_Returns404(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()

	body, _ := json.Marshal(map[string]interface{}{"trade_id": 9999})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/verify", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+makeToken(t, "alice"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404 for nonexistent trade, got %d", w.Code)
	}
}

// ─────────────────────────────────────────────────────────────
// POST /api/v1/trade/message
// ─────────────────────────────────────────────────────────────

func TestMessage_ParticipantCanSend(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	id := seedProposal(t)

	body, _ := json.Marshal(map[string]interface{}{
		"trade_id": id,
		"text":     "Hey, let's meet at the park!",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/message", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+makeToken(t, "alice"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 for participant sending message, got %d — %s", w.Code, w.Body.String())
	}
}

func TestMessage_NonParticipantBlocked(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	id := seedProposal(t)

	body, _ := json.Marshal(map[string]interface{}{
		"trade_id": id,
		"text":     "I shouldn't be here",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/message", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+makeToken(t, "intruder"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusForbidden {
		t.Errorf("expected 403 for non-participant, got %d", w.Code)
	}
}

func TestMessage_MissingText_Returns400(t *testing.T) {
	setupTestDB(t)
	r := setupRouter()
	id := seedProposal(t)

	body, _ := json.Marshal(map[string]interface{}{"trade_id": id}) // no text
	req := httptest.NewRequest(http.MethodPost, "/api/v1/trade/message", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+makeToken(t, "alice"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for missing text, got %d", w.Code)
	}
}

// ─────────────────────────────────────────────────────────────
// EvaluateMatch (K=3 Circular Matching)
// ─────────────────────────────────────────────────────────────

func wantsJSON(category string) datatypes.JSON {
	b, _ := json.Marshal(map[string]string{"category": category})
	return datatypes.JSON(b)
}

func TestEvaluateMatch_NoMatch(t *testing.T) {
	setupTestDB(t)

	// Only one item — no loop possible
	DB.Create(&Item{
		ID: "item-1", OwnerID: "alice",
		Category: "Electronics", Title: "📷 Camera",
		Wants: wantsJSON("Books"), Status: "available",
	})

	event, _ := json.Marshal(map[string]interface{}{
		"_id":      "item-1",
		"owner_id": "alice",
		"title":    "Camera",
		"emoji":    "📷",
		"category": "Electronics",
		"wants":    map[string]interface{}{"category": "Books"},
		"tags":     []string{},
	})

	EvaluateMatch(event) // should not panic or produce a match

	var count int64
	DB.Model(&TradeProposal{}).Count(&count)
	if count != 0 {
		t.Errorf("expected 0 proposals with no loop, got %d", count)
	}
}

func TestEvaluateMatch_K3LoopCreatesProposal(t *testing.T) {
	setupTestDB(t)

	// Pre-seed B and C so they form a loop with A
	DB.Create(&Item{
		ID: "item-b", OwnerID: "bob",
		Category: "Books", Title: "📚 Encyclopedia",
		Wants: wantsJSON("Guitar"), Status: "available",
	})
	DB.Create(&Item{
		ID: "item-c", OwnerID: "carol",
		Category: "Guitar", Title: "🎸 Fender",
		Wants: wantsJSON("Electronics"), Status: "available",
	})

	// A wants Books → B has Books and wants Guitar → C has Guitar and wants Electronics → loop!
	event, _ := json.Marshal(map[string]interface{}{
		"_id":      "item-a",
		"owner_id": "alice",
		"title":    "Camera",
		"emoji":    "📷",
		"category": "Electronics",
		"wants":    map[string]interface{}{"category": "Books"},
		"tags":     []string{},
	})

	EvaluateMatch(event)

	var proposal TradeProposal
	DB.First(&proposal)
	if proposal.ID == 0 {
		t.Fatal("expected a TradeProposal to be created for K=3 loop")
	}
	if proposal.Status != "pending" {
		t.Errorf("expected status=pending, got %s", proposal.Status)
	}
	// All three items should now be marked matched
	var items []Item
	DB.Where("status = ?", "matched").Find(&items)
	if len(items) != 3 {
		t.Errorf("expected 3 items matched, got %d", len(items))
	}
}

func TestEvaluateMatch_SameOwnerNotMatched(t *testing.T) {
	setupTestDB(t)

	// B and C both belong to bob — should NOT form a valid loop
	DB.Create(&Item{
		ID: "item-b", OwnerID: "bob",
		Category: "Books", Title: "📚 Encyclopedia",
		Wants: wantsJSON("Guitar"), Status: "available",
	})
	DB.Create(&Item{
		ID: "item-c", OwnerID: "bob", // same owner as B
		Category: "Guitar", Title: "🎸 Fender",
		Wants: wantsJSON("Electronics"), Status: "available",
	})

	event, _ := json.Marshal(map[string]interface{}{
		"_id":      "item-a",
		"owner_id": "alice",
		"title":    "Camera",
		"emoji":    "📷",
		"category": "Electronics",
		"wants":    map[string]interface{}{"category": "Books"},
		"tags":     []string{},
	})

	EvaluateMatch(event)

	var count int64
	DB.Model(&TradeProposal{}).Count(&count)
	if count != 0 {
		t.Errorf("same-owner loop should be rejected, got %d proposals", count)
	}
}

// ─────────────────────────────────────────────────────────────
// Environment / config
// ─────────────────────────────────────────────────────────────

func TestJWTSecretFallback(t *testing.T) {
	os.Unsetenv("JWT_SECRET")
	setupTestDB(t)
	r := setupRouter()

	// Signing with the hardcoded fallback secret should still work
	token := makeToken(t, "testuser")
	req := httptest.NewRequest(http.MethodGet, "/api/v1/trade/proposals", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 with fallback JWT secret, got %d", w.Code)
	}
}

// ─────────────────────────────────────────────────────────────
// WorkerPool
// ─────────────────────────────────────────────────────────────

func TestWorkerPool_ProcessesEvents(t *testing.T) {
	setupTestDB(t)

	// Re-create the channel fresh for this test
	EventChan = make(chan []byte, 10)
	StartWorkerPool(2)

	event, _ := json.Marshal(map[string]interface{}{
		"_id":      fmt.Sprintf("item-%d", time.Now().UnixNano()),
		"owner_id": "pooluser",
		"title":    "Laptop",
		"emoji":    "💻",
		"category": "Electronics",
		"wants":    map[string]interface{}{"category": "Furniture"},
		"tags":     []string{},
	})

	EventChan <- event

	// Give the worker a moment to process
	time.Sleep(200 * time.Millisecond)

	var count int64
	DB.Model(&Item{}).Where("owner_id = ?", "pooluser").Count(&count)
	if count != 1 {
		t.Errorf("expected worker to save 1 item, got %d", count)
	}
}
