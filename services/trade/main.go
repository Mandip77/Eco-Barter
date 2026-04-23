package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

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

// RateLimiter implements a fixed 1-minute window per-IP limiter using only stdlib.
// Allows up to 60 requests per minute per IP; stale windows are cleaned every 5 minutes.
func RateLimiter() gin.HandlerFunc {
	type window struct {
		count int
		start time.Time
	}
	var mu sync.Mutex
	windows := make(map[string]*window)
	const maxPerMinute = 60

	go func() {
		for range time.Tick(5 * time.Minute) {
			mu.Lock()
			for ip, w := range windows {
				if time.Since(w.start) > 2*time.Minute {
					delete(windows, ip)
				}
			}
			mu.Unlock()
		}
	}()

	return func(c *gin.Context) {
		ip := c.ClientIP()
		mu.Lock()
		w, ok := windows[ip]
		if !ok || time.Since(w.start) > time.Minute {
			windows[ip] = &window{count: 1, start: time.Now()}
			mu.Unlock()
			c.Next()
			return
		}
		w.count++
		count := w.count
		mu.Unlock()

		if count > maxPerMinute {
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{"error": "rate limit exceeded"})
			return
		}
		c.Next()
	}
}

func main() {
	log.Println("Booting EcoBarter Trade Engine...")

	initDB()
	initMessaging()
	defer closeMessaging()
	StartWorkerPool(5)

	r := gin.Default()
	r.Use(RateLimiter())

	r.GET("/api/v1/trade", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": "trade-engine",
			"message": "Consuming events and tracking K-Way Trade matches via PostgreSQL.",
		})
	})

	r.GET("/api/v1/trade/proposals", AuthRequired(), func(c *gin.Context) {
		currentUser := c.GetString("username")
		var proposals []TradeProposal
		result := DB.Where(
			"user_a = ? OR user_b = ? OR user_c = ? OR user_d = ?",
			currentUser, currentUser, currentUser, currentUser,
		).Find(&proposals)
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

		matched := false
		if proposal.UserA == currentUser {
			proposal.VerifiedA = true
			matched = true
		} else if proposal.UserB == currentUser {
			proposal.VerifiedB = true
			matched = true
		} else if proposal.K >= 3 && proposal.UserC == currentUser {
			proposal.VerifiedC = true
			matched = true
		} else if proposal.K >= 4 && proposal.UserD == currentUser {
			proposal.VerifiedD = true
			matched = true
		}

		if !matched {
			c.JSON(http.StatusBadRequest, gin.H{"error": "User is not part of this trade"})
			return
		}

		switch proposal.K {
		case 2:
			if proposal.VerifiedA && proposal.VerifiedB {
				proposal.Status = "completed"
			} else {
				proposal.Status = "in_progress"
			}
		case 4:
			if proposal.VerifiedA && proposal.VerifiedB && proposal.VerifiedC && proposal.VerifiedD {
				proposal.Status = "completed"
			} else {
				proposal.Status = "in_progress"
			}
		default: // K=3
			if proposal.VerifiedA && proposal.VerifiedB && proposal.VerifiedC {
				proposal.Status = "completed"
			} else {
				proposal.Status = "in_progress"
			}
		}

		DB.Save(&proposal)
		PublishToCentrifugo("trade_hub:proposals", map[string]interface{}{
			"event":    "proposal_updated",
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

		isParticipant := proposal.UserA == currentUser || proposal.UserB == currentUser ||
			(proposal.K >= 3 && proposal.UserC == currentUser) ||
			(proposal.K >= 4 && proposal.UserD == currentUser)
		if !isParticipant {
			c.JSON(http.StatusForbidden, gin.H{"error": "You are not part of this trade"})
			return
		}

		channel := fmt.Sprintf("chat_%d", proposal.ID)
		PublishToCentrifugo(channel, map[string]interface{}{
			"from": currentUser,
			"text": req.Text,
		})
		c.JSON(http.StatusOK, gin.H{"status": "published"})
	})

	go func() {
		if err := r.Run(":8000"); err != nil {
			log.Fatalf("Gin server failed: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down Trade Engine gracefully...")
}
