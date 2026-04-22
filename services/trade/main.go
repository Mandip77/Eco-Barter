package main

import (
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"strings"
	"fmt"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func AuthRequired() gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Authorization header missing"})
			return
		}
		parts := strings.Split(authHeader, " ")
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Invalid Authorization header format"})
			return
		}

		tokenString := parts[1]
		secret := os.Getenv("JWT_SECRET")
		if secret == "" {
			secret = "super_secret_dev_key_do_not_use_in_prod"
		}

		token, err := jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
			if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method")
			}
			return []byte(secret), nil
		})

		if err != nil || !token.Valid {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Invalid token"})
			return
		}

		claims, ok := token.Claims.(jwt.MapClaims)
		if !ok {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Invalid token claims"})
			return
		}

		username, ok := claims["username"].(string)
		if !ok {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Username not found in token"})
			return
		}

		c.Set("username", username)
		c.Next()
	}
}

func main() {
	log.Println("Booting EcoBarter Trade Engine...")

	// 1. Initialize Postgres
	initDB()

	// 2. Initialize NATS JetStream Consumer (async loop starts inside)
	initMessaging()
	defer closeMessaging()

	// 3. Initialize Worker Pool
	StartWorkerPool(5)

	// 4. Initialize HTTP Server via Gin
	r := gin.Default()

	// Endpoints (For Traefik probing and manual debug check)
	r.GET("/api/v1/trade", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": "trade-engine",
			"message": "Consuming events and tracking K-Way Trade matches via PostgreSQL.",
		})
	})
	
	// Expose our recent matches for authorized participants
	r.GET("/api/v1/trade/proposals", AuthRequired(), func(c *gin.Context) {
		currentUser := c.GetString("username")
		var proposals []TradeProposal
		result := DB.Where("user_a = ? OR user_b = ? OR user_c = ?", currentUser, currentUser, currentUser).Find(&proposals)
		if result.Error != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": result.Error.Error()})
			return
		}
		c.JSON(http.StatusOK, proposals)
	})

	type VerifyRequest struct {
		TradeID      uint   `json:"trade_id" binding:"required"`
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

		// Check if fully complete
		if proposal.VerifiedA && proposal.VerifiedB && proposal.VerifiedC {
			proposal.Status = "completed"
		} else {
			proposal.Status = "in_progress"
		}

		DB.Save(&proposal)
		
		PublishToCentrifugo("trade_hub:proposals", map[string]interface{}{
			"event": "proposal_updated",
			"proposal": proposal,
		})
		
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

		channel := fmt.Sprintf("chat_%d", proposal.ID)
		msgData := map[string]interface{}{
			"from": currentUser,
			"text": req.Text,
		}

		PublishToCentrifugo(channel, msgData)
		c.JSON(http.StatusOK, gin.H{"status": "published"})
	})

	// Run Server
	go func() {
		if err := r.Run(":80"); err != nil {
			log.Fatalf("Gin server failed: %v", err)
		}
	}()

	// Graceful Shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down Trade Engine gracefully...")
}
