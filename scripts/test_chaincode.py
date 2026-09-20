"""
Test FL Audit Chaincode on Hyperledger Fabric
Verifies chaincode deployment and functionality
"""

import subprocess
import json

def run_docker_command(cmd):
    """Execute docker command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1

def test_chaincode():
    """Test FL audit chaincode functions"""
    
    print("="*70)
    print("TESTING FL AUDIT CHAINCODE")
    print("="*70)
    print()
    
    CHANNEL = "flchannel"
    CHAINCODE = "fl-audit"
    
    #Test 1: Log a model update
    print("Test 1: Logging model update...")
    print("-"*70)
    
    args = '{\\"Args\\":[\\"LogModelUpdate\\",\\"test_node_1\\",\\"1\\",\\"0.85\\",\\"0.15\\",\\"{\\\\\\"test\\\\\\":\\\\\\"data\\\\\\"}"

]}'
    
    cmd = f'docker exec cli peer chaincode invoke -o orderer.fl-ddos.com:7050 -C {CHANNEL} -n {CHAINCODE} -c \'{args}\''
    
    stdout, stderr, code = run_docker_command(cmd)
    
    if code == 0:
        print("✅ Model update logged successfully")
        print(f"Response: {stdout[:200]}")
    else:
        print(f"❌ Failed to log update")
        print(f"Error: {stderr[:200]}")
    
    print()
    
    # Test 2: Query all records
    print("Test 2: Querying all records...")
    print("-"*70)
    
    args = '{\\"Args\\":[\\"QueryAllRecords\\"]}'
    cmd = f'docker exec cli peer chaincode query -C {CHANNEL} -n {CHAINCODE} -c \'{args}\''
    
    stdout, stderr, code = run_docker_command(cmd)
    
    if code == 0:
        try:
            records = json.loads(stdout)
            print(f"✅ Found {len(records)} records")
            
            if records:
                print("First record:")
                print(json.dumps(records[0], indent=2))
        except json.JSONDecodeError:
            print("✅ Query successful")
            print(f"Response: {stdout[:300]}")
    else:
        print(f"❌ Query failed")
        print(f"Error: {stderr[:200]}")
    
    print()
    
    # Test 3: Query by node
    print("Test 3: Querying by node...")
    print("-"*70)
    
    args = '{\\"Args\\":[\\"QueryByNode\\",\\"test_node_1\\"]}'
    cmd = f'docker exec cli peer chaincode query -C {CHANNEL} -n {CHAINCODE} -c \'{args}\''
    
    stdout, stderr, code = run_docker_command(cmd)
    
    if code == 0:
        print("✅ Node query successful")
        try:
            records = json.loads(stdout)
            print(f"Found {len(records)} records for test_node_1")
        except:
            print(f"Response: {stdout[:300]}")
    else:
        print(f"❌ Node query failed")
        print(f"Error: {stderr[:200]}")
    
    print()
    
    # Test 4: Query by round
    print("Test 4: Querying by round...")
    print("-"*70)
    
    args = '{\\"Args\\":[\\"QueryByRound\\",\\"1\\"]}'
    cmd = f'docker exec cli peer chaincode query -C {CHANNEL} -n {CHAINCODE} -c \'{args}\''
    
    stdout, stderr, code = run_docker_command(cmd)
    
    if code == 0:
        print("✅ Round query successful")
        try:
            records = json.loads(stdout)
            print(f"Found {len(records)} records for round 1")
        except:
            print(f"Response: {stdout[:300]}")
    else:
        print(f"❌ Round query failed")
        print(f"Error: {stderr[:200]}")
    
    print()
    print("="*70)
    print("Chaincode Testing Complete")
    print("="*70)

if __name__ == "__main__":
    test_chaincode()
