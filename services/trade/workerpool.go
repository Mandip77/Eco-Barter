package main

import (
	"log"
)

var EventChan = make(chan []byte, 1000)

// StartWorkerPool initializes N workers listening across the Event channel
func StartWorkerPool(numWorkers int) {
	for i := 1; i <= numWorkers; i++ {
		go worker(i)
	}
	log.Printf("Started Worker Pool with %d goroutines", numWorkers)
}

func worker(id int) {
	log.Printf("Worker %d listening...", id)
	for data := range EventChan {
		log.Printf("[Worker %d] Processing matching task", id)
		EvaluateMatch(data)
	}
}
