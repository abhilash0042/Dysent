package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// FLAuditContract provides functions for FL audit logging
type FLAuditContract struct {
	contractapi.Contract
}

// AuditRecord represents a single audit log entry
type AuditRecord struct {
	RecordID    string `json:"recordID"`
	Timestamp   string `json:"timestamp"`
	EventType   string `json:"eventType"`
	NodeID      string `json:"nodeID"`
	DataHash    string `json:"dataHash"`
	RoundNumber int    `json:"roundNumber"`
	Metadata    string `json:"metadata"`
}

// InitLedger initializes the chaincode
func (c *FLAuditContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
	record := AuditRecord{
		RecordID:    "genesis",
		Timestamp:   time.Now().Format(time.RFC3339),
		EventType:   "INIT",
		NodeID:      "system",
		DataHash:    "0x0",
		RoundNumber: 0,
		Metadata:    "FL-DDoS Audit Ledger Initialized",
	}

	recordJSON, err := json.Marshal(record)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(record.RecordID, recordJSON)
}

// RecordNodeRegistration logs when a node joins the FL network
func (c *FLAuditContract) RecordNodeRegistration(ctx contractapi.TransactionContextInterface,
	nodeID string, metadata string) error {

	record := AuditRecord{
		RecordID:    ctx.GetStub().GetTxID(),
		Timestamp:   time.Now().Format(time.RFC3339),
		EventType:   "NODE_REGISTRATION",
		NodeID:      nodeID,
		DataHash:    "",
		RoundNumber: 0,
		Metadata:    metadata,
	}

	recordJSON, err := json.Marshal(record)
	if err != nil {
		return err
	}

	err = ctx.GetStub().PutState(record.RecordID, recordJSON)
	if err != nil {
		return err
	}

	// Also index by node ID for efficient queries
	compositeKey, err := ctx.GetStub().CreateCompositeKey("node", []string{nodeID, record.RecordID})
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(compositeKey, []byte{0x00})
}

// RecordModelUpdate logs a model weight update from a client
func (c *FLAuditContract) RecordModelUpdate(ctx contractapi.TransactionContextInterface,
	nodeID string, weightHash string, roundNumber int, metadata string) error {

	record := AuditRecord{
		RecordID:    ctx.GetStub().GetTxID(),
		Timestamp:   time.Now().Format(time.RFC3339),
		EventType:   "MODEL_UPDATE",
		NodeID:      nodeID,
		DataHash:    weightHash,
		RoundNumber: roundNumber,
		Metadata:    metadata,
	}

	recordJSON, err := json.Marshal(record)
	if err != nil {
		return err
	}

	err = ctx.GetStub().PutState(record.RecordID, recordJSON)
	if err != nil {
		return err
	}

	// Index by round for querying all updates in a round
	compositeKey, err := ctx.GetStub().CreateCompositeKey("round", []string{fmt.Sprintf("%d", roundNumber), record.RecordID})
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(compositeKey, []byte{0x00})
}

// RecordAggregation logs when the server performs model aggregation
func (c *FLAuditContract) RecordAggregation(ctx contractapi.TransactionContextInterface,
	roundNumber int, globalModelHash string, participatingNodes string) error {

	record := AuditRecord{
		RecordID:    ctx.GetStub().GetTxID(),
		Timestamp:   time.Now().Format(time.RFC3339),
		EventType:   "AGGREGATION",
		NodeID:      "server",
		DataHash:    globalModelHash,
		RoundNumber: roundNumber,
		Metadata:    fmt.Sprintf("Nodes: %s", participatingNodes),
	}

	recordJSON, err := json.Marshal(record)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(record.RecordID, recordJSON)
}

// RecordSecurityAlert logs security events (Byzantine detection, etc.)
func (c *FLAuditContract) RecordSecurityAlert(ctx contractapi.TransactionContextInterface,
	nodeID string, alertType string, roundNumber int, details string) error {

	record := AuditRecord{
		RecordID:    ctx.GetStub().GetTxID(),
		Timestamp:   time.Now().Format(time.RFC3339),
		EventType:   "SECURITY_ALERT",
		NodeID:      nodeID,
		DataHash:    alertType,
		RoundNumber: roundNumber,
		Metadata:    details,
	}

	recordJSON, err := json.Marshal(record)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(record.RecordID, recordJSON)
}

// QueryAuditRecord retrieves a specific audit record by ID
func (c *FLAuditContract) QueryAuditRecord(ctx contractapi.TransactionContextInterface,
	recordID string) (*AuditRecord, error) {

	recordJSON, err := ctx.GetStub().GetState(recordID)
	if err != nil {
		return nil, fmt.Errorf("failed to read record %s: %v", recordID, err)
	}
	if recordJSON == nil {
		return nil, fmt.Errorf("record %s does not exist", recordID)
	}

	var record AuditRecord
	err = json.Unmarshal(recordJSON, &record)
	if err != nil {
		return nil, err
	}

	return &record, nil
}

// QueryRecordsByNode retrieves all audit records for a specific node
func (c *FLAuditContract) QueryRecordsByNode(ctx contractapi.TransactionContextInterface,
	nodeID string) ([]*AuditRecord, error) {

	resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey("node", []string{nodeID})
	if err != nil {
		return nil, err
	}
	defer resultsIterator.Close()

	var records []*AuditRecord
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}

		_, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
		if err != nil {
			return nil, err
		}

		recordID := compositeKeyParts[1]
		record, err := c.QueryAuditRecord(ctx, recordID)
		if err != nil {
			return nil, err
		}

		records = append(records, record)
	}

	return records, nil
}

// QueryRecordsByRound retrieves all audit records for a specific FL round
func (c *FLAuditContract) QueryRecordsByRound(ctx contractapi.TransactionContextInterface,
	roundNumber int) ([]*AuditRecord, error) {

	resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey("round", []string{fmt.Sprintf("%d", roundNumber)})
	if err != nil {
		return nil, err
	}
	defer resultsIterator.Close()

	var records []*AuditRecord
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}

		_, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
		if err != nil {
			return nil, err
		}

		recordID := compositeKeyParts[1]
		record, err := c.QueryAuditRecord(ctx, recordID)
		if err != nil {
			return nil, err
		}

		records = append(records, record)
	}

	return records, nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(&FLAuditContract{})
	if err != nil {
		fmt.Printf("Error creating FL Audit chaincode: %v\n", err)
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting FL Audit chaincode: %v\n", err)
	}
}
