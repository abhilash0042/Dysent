package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// FLAuditContract provides functions for managing FL audit records
type FLAuditContract struct {
	contractapi.Contract
}

// FLRecord represents a federated learning operation record
type FLRecord struct {
	TxID      string  `json:"tx_id"`
	NodeID    string  `json:"node_id"`
	RoundNum  int     `json:"round_num"`
	Accuracy  float64 `json:"accuracy"`
	Loss      float64 `json:"loss"`
	Timestamp string  `json:"timestamp"`
	Metadata  string  `json:"metadata"`
}

// LogModelUpdate logs a model update from an FL node
func (c *FLAuditContract) LogModelUpdate(ctx contractapi.TransactionContextInterface, nodeID string, roundNum int, accuracy float64, loss float64, metadata string) error {
	txID := ctx.GetStub().GetTxID()
	timestamp := time.Now().Format(time.RFC3339)

	record := FLRecord{
		TxID:      txID,
		NodeID:    nodeID,
		RoundNum:  roundNum,
		Accuracy:  accuracy,
		Loss:      loss,
		Timestamp: timestamp,
		Metadata:  metadata,
	}

	recordJSON, err := json.Marshal(record)
	if err != nil {
		return err
	}

	// Store record with composite key: node_round_txid
	key := fmt.Sprintf("FL_%s_R%d_%s", nodeID, roundNum, txID)
	return ctx.GetStub().PutState(key, recordJSON)
}

// QueryByNode retrieves all records for a specific FL node
func (c *FLAuditContract) QueryByNode(ctx contractapi.TransactionContextInterface, nodeID string) ([]*FLRecord, error) {
	queryString := fmt.Sprintf(`{"selector":{"node_id":"%s"}}`, nodeID)
	return c.queryRecords(ctx, queryString)
}

// QueryByRound retrieves all records for a specific FL round
func (c *FLAuditContract) QueryByRound(ctx contractapi.TransactionContextInterface, roundNum int) ([]*FLRecord, error) {
	queryString := fmt.Sprintf(`{"selector":{"round_num":%d}}`, roundNum)
	return c.queryRecords(ctx, queryString)
}

// QueryAllRecords retrieves all FL audit records
func (c *FLAuditContract) QueryAllRecords(ctx contractapi.TransactionContextInterface) ([]*FLRecord, error) {
	queryString := `{"selector":{"tx_id":{"$gt":""}}}`
	return c.queryRecords(ctx, queryString)
}

// queryRecords is a helper function to execute queries
func (c *FLAuditContract) queryRecords(ctx contractapi.TransactionContextInterface, queryString string) ([]*FLRecord, error) {
	resultsIterator, err := ctx.GetStub().GetQueryResult(queryString)
	if err != nil {
		return nil, err
	}
	defer resultsIterator.Close()

	var records []*FLRecord
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}

		var record FLRecord
		err = json.Unmarshal(queryResponse.Value, &record)
		if err != nil {
			return nil, err
		}
		records = append(records, &record)
	}

	return records, nil
}

// GetRecord retrieves a specific record by transaction ID
func (c *FLAuditContract) GetRecord(ctx contractapi.TransactionContextInterface, txID string) (*FLRecord, error) {
	// Search for record with this txID
	queryString := fmt.Sprintf(`{"selector":{"tx_id":"%s"}}`, txID)
	records, err := c.queryRecords(ctx, queryString)
	if err != nil {
		return nil, err
	}

	if len(records) == 0 {
		return nil, fmt.Errorf("record not found: %s", txID)
	}

	return records[0], nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(&FLAuditContract{})
	if err != nil {
		fmt.Printf("Error creating FL audit chaincode: %v\n", err)
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting FL audit chaincode: %v\n", err)
	}
}
