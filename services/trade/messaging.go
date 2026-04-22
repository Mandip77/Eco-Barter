package main

import (
	"log"
	"os"

	"github.com/nats-io/nats.go"
)

var NatsConn *nats.Conn
var JetStream nats.JetStreamContext

func initMessaging() {
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = nats.DefaultURL
	}

	var err error
	NatsConn, err = nats.Connect(natsURL)
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	JetStream, err = NatsConn.JetStream()
	if err != nil {
		log.Fatalf("Failed to initialize JetStream: %v", err)
	}

	// Ensure stream exists to avoid crash if Catalog Service hasn't started yet
	streamName := "ECOBARTER"
	subjectPattern := "item.preference.*"
	_, err = JetStream.StreamInfo(streamName)
	if err != nil {
		log.Printf("Stream %s not found, attempting to create...", streamName)
		_, err = JetStream.AddStream(&nats.StreamConfig{
			Name:     streamName,
			Subjects: []string{subjectPattern},
		})
		if err != nil {
			log.Printf("Warning: Failed to create stream: %v (it might be created by another service simultaneously)", err)
		} else {
			log.Printf("Stream %s created successfully", streamName)
		}
	}

	log.Println("Connected to NATS JetStream successfully")

	// Start Consumer
	go consumeProductEvents()
}

func consumeProductEvents() {
	streamName := "ECOBARTER"
	subject := "item.preference.updated"

	// Wait for the Catalog Service to have created the Stream, or we could ensure it here.
	// We'll create a durable consumer push subscription
	_, err := JetStream.Subscribe(subject, func(m *nats.Msg) {
		log.Printf("[NATS] Received message on %s", m.Subject)
		
		// Pass Event to Worker Pool
		EventChan <- m.Data
		
		// Acknowledge receipt
		m.Ack()
	}, nats.Durable("TRADE_ENGINE_WORKER"), nats.ManualAck())

	if err != nil {
		log.Fatalf("Failed to subscribe to %s: %v", subject, err)
	}
	
	log.Printf("Listening for NATS events tightly bound to stream: %s, subject: %s", streamName, subject)
}

func closeMessaging() {
	if NatsConn != nil {
		NatsConn.Close()
	}
}
