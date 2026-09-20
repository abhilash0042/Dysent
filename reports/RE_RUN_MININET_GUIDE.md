# 🔄 How to Re-Run Mininet Simulation (Demo Guide)

Use this guide to demonstrate the project's authenticity to faculty.

## 1. Preparation

Open your **WSL Terminal** and navigate to the project folder:

```bash
cd /mnt/c/Users/HP/Desktop/Major\ Project/Main\ File-Code/
```

## 2. Cleanup (Crucial)

Always clean up previous virtual networks before starting a new one:

```bash
sudo mn -c
```

## 3. Start the Simulation

Launch the authentic network environment:

```bash
sudo python3 ddosdfl/experiments/mininet/run_simulation.py
```

_Wait until you see the `mininet>` prompt._

## 4. Verify Nodes are Running (Terminal 2)

Open a **new** WSL terminal tab and check the logs to prove processes are active:

**Check Client 1:**

```bash
tail -f h1.log
```

_You should see training progress._

**Check Server:**

```bash
tail -f server.log
```

_You should see updates receiving._

## 5. The "Authenticity" Proof (Wireshark)

1.  Run Wireshark as root:
    ```bash
    sudo wireshark
    ```
2.  Select Interface: **`s1-eth1`**
3.  Filter Box: Type `tcp.port == 5000` and hit Enter.
4.  **Show Faculty**: The green/black TCP packets. Click one to show the "Data" payload contains Python pickle data (Model Weights).

## 6. Shutdown

In the Mininet terminal:

```bash
exit
```

Then run cleanup again:

```bash
sudo mn -c
```
