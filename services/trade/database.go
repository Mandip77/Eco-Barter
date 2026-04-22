package main

import (
	"log"
	"os"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

var DB *gorm.DB

func initDB() {
	dbURL := os.Getenv("DB_URL")
	if dbURL == "" {
		dbURL = "host=localhost user=ecouser password=ecopassword dbname=ecobarter_db port=5432 sslmode=disable"
	}

	var err error
	DB, err = gorm.Open(postgres.Open(dbURL), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to PostgreSQL: %v", err)
	}

	log.Println("Connected to PostgreSQL successfully")

	// Automigrate TradeProposal & Item table
	err = DB.AutoMigrate(&TradeProposal{}, &Item{})
	if err != nil {
		log.Fatalf("Failed to AutoMigrate models: %v", err)
	}
	log.Println("AutoMigrate completed successfully")
}
