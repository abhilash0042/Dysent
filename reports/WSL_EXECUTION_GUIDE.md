# 🚀 Complete WSL Execution Guide for Mininet Simulation

Follow these steps **IN ORDER** to successfully run and demonstrate the project.

---

## Step 1: Open WSL Terminal

1. Press **Windows + R**
2. Type `wsl` and hit Enter
3. You should see a Linux prompt: `tarun@TarunsHP:~$`

---

## Step 2: Navigate to Project Directory

```bash
cd /mnt/c/Users/HP/Desktop/Major\ Project/Main\ File-Code/
```

---

## Step 3: Clean Up (IMPORTANT)

Remove any broken virtual environments from previous attempts:

```bash
rm -rf mininet_venv
sudo mn -c
```

---

## Step 4: Setup Environment (One-Time)

Install all required dependencies:

```bash
bash ddosdfl/setup_wsl_env.sh
```

**Wait for:** `✅ SETUP COMPLETE!`

_(This creates a `mininet_venv` folder with all necessary Python packages)_

---

## Step 5: Verify Installation (Optional but Recommended)

```bash
./mininet_venv/bin/python3 -c 'import numpy, yaml, tensorflow; print("All modules OK!")'
```

**Expected Output:** `All modules OK!`

---

## Step 6: Start the Simulation

```bash
sudo python3 ddosdfl/experiments/mininet/run_simulation.py
```

**Expected Output:**

```
*** Creating Network
*** Adding hosts: h1 h2 h3 h_server
*** Starting Network
*** Using Dedicated Mininet Venv: .../mininet_venv/bin/python
*** Starting FL Server on h_server (10.0.0.254)...
*** Starting FL Clients...
*** Authentic Network Traffic Generation in Progress...
*** Press Ctrl+D/exit to stop simulation
*** Starting CLI:
mininet>
```

✅ **You should see the `mininet>` prompt. DO NOT CLOSE THIS TERMINAL.**

---

## Step 7: Verify Training Logs (New Terminal)

1. **Open a NEW WSL terminal** (don't close the Mininet one)
2. Navigate to the project:
   ```bash
   cd /mnt/c/Users/HP/Desktop/Major\ Project/Main\ File-Code/
   ```
3. **Watch Client 1 Training:**
   ```bash
   tail -f h1.log
   ```

**Expected Output:**

```
Generating local dataset...
Connecting to server at 10.0.0.254:5000...
✅ Connected!
Received Initialization from Server
Starting Training Round...
Epoch 1/1 ... accuracy: 0.XXXX
Sending Model Update...
Round 1 Complete. Updating Global Weights.
```

Press **Ctrl+C** to stop watching.

4. **Watch Server:**
   ```bash
   tail -f server.log
   ```

**Expected Output:**

```
🚀 Server listening on 0.0.0.0:5000
➕ Client connected: ('10.0.0.1', XXXXX)
Registered Node: h1
--- Round 1: Waiting for update from h1 ---
Received update from h1: Accuracy=0.XXXX
```

---

## Step 8: Capture Network Traffic (Wireshark)

**THIS IS THE PROOF OF AUTHENTICITY!**

1. **In another terminal:**

   ```bash
   sudo wireshark
   ```

2. **In Wireshark GUI:**
   - Select interface: **`s1-eth1`** (the virtual switch cable)
   - Click the blue shark fin to start capture

3. **Apply Filter:**
   - Type in the filter box: `tcp.port == 5000`
   - Press Enter

4. **What You'll See:**
   - Green/Black TCP packets
   - Source: `10.0.0.1` (h1), `10.0.0.2` (h2), etc.
   - Destination: `10.0.0.254` (server)
   - Click a packet → "Data" tab shows Python pickle bytes (Model Weights!)

5. **Show Faculty:**
   - "These are the FL model updates being transferred over TCP"
   - "This is real network traffic, not simulated"

---

## Step 9: Shutdown

1. Go back to the **Mininet terminal**
2. Type: `exit`
3. Clean up: `sudo mn -c`

---

## 🎯 Quick Command Reference

**Start:** `sudo python3 ddosdfl/experiments/mininet/run_simulation.py`  
**Logs:** `tail -f h1.log` or `tail -f server.log`  
**Traffic:** `sudo wireshark` → select `s1-eth1` → filter `tcp.port == 5000`  
**Stop:** `exit` → `sudo mn -c`

---

## ⚠️ Troubleshooting

**If you see errors:**

1. Run: `rm -rf mininet_venv`
2. Run: `bash ddosdfl/setup_wsl_env.sh`
3. Try again

**If logs show "No such file or directory":**

- The simulation is still using system Python (missing deps)
- Verify: `ls mininet_venv/bin/python` exists
- Re-run setup script

---

**You're all set! Good luck with the demonstration! 🎉**
