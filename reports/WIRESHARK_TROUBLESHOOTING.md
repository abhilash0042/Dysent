# Wireshark Traffic Capture Troubleshooting

## Issue: No TCP Port 5000 Traffic Visible

### Quick Diagnosis Commands

**1. Verify FL Communication is Happening:**

```bash
# In Mininet terminal after simulation starts
tail -f h1.log
```

Look for: "Sending Model Update..." (confirms communication)

**2. Verify Port 5000 is Active:**

```bash
# In Mininet CLI (mininet> prompt)
h_server netstat -tuln | grep 5000
```

Should show: `0.0.0.0:5000` LISTEN

**3. Use tcpdump Instead of Wireshark:**

```bash
# In Mininet CLI
h1 tcpdump -i h1-eth0 -n port 5000 &
```

Then check if you see packets.

### Alternative Wireshark Approach

**Option A: Capture on Server Interface**
Instead of `s1-eth1`, try `s1-eth4` (the server's interface):

1. In Wireshark, select interface: **s1-eth4**
2. Filter: `tcp.port == 5000`

**Option B: Capture Without Filter (Recommended)**

1. Start capture on `s1-eth1` with **NO filter**
2. Let simulation run completely
3. Stop capture
4. **THEN** apply filter `tcp.port == 5000` to the captured data

**Option C: Capture All Switch Traffic**

1. Select interface: **any** (captures all interfaces)
2. Filter: `tcp.port == 5000`

### Expected Packet Details

When you finally see the packets:

- **Source**: 10.0.0.1, 10.0.0.2, 10.0.0.3
- **Destination**: 10.0.0.254
- **Protocol**: TCP
- **Length**: Large (thousands of bytes - the model weights)
- **Info**: [PSH, ACK], [ACK]

### If Still No Traffic

The traffic might be using loopback optimization. Verify with:

```bash
# In project directory
grep -n "PORT = " ddosdfl/experiments/mininet/mininet_server.py
grep -n "PORT = " ddosdfl/experiments/mininet/mininet_client.py
```

Both should show `PORT = 5000`.
