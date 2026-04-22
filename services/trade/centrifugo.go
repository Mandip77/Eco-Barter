package main

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"os"
)

type CentrifugoPublishRequest struct {
	Method string      `json:"method"`
	Params interface{} `json:"params"`
}

type PublishParams struct {
	Channel string      `json:"channel"`
	Data    interface{} `json:"data"`
}

func PublishToCentrifugo(channel string, data interface{}) {
	centrifugoAPI := os.Getenv("CENTRIFUGO_API")
	if centrifugoAPI == "" {
		centrifugoAPI = "http://centrifugo:8000/api"
	}

	apiKey := os.Getenv("CENTRIFUGO_API_KEY")
	if apiKey == "" {
		log.Printf("[Centrifugo] WARNING: CENTRIFUGO_API_KEY is not set — skipping publish to %s", channel)
		return
	}

	reqBody := CentrifugoPublishRequest{
		Method: "publish",
		Params: PublishParams{Channel: channel, Data: data},
	}

	jsonValue, _ := json.Marshal(reqBody)
	req, err := http.NewRequest("POST", centrifugoAPI, bytes.NewBuffer(jsonValue))
	if err != nil {
		log.Printf("[Centrifugo] Failed to build request: %v", err)
		return
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "apikey "+apiKey)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("[Centrifugo] Failed to send publish request: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("[Centrifugo] Publish rejected: status %v on channel %s", resp.StatusCode, channel)
	} else {
		log.Printf("[Centrifugo] Published to %s", channel)
	}
}
