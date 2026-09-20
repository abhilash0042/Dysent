"""
Mininet Topology for FL-DDoS Authenticity Validation
"""

from mininet.topo import Topo

class FLTopology(Topo):
    def build(self, n=2):
        # Add Central Switch
        switch = self.addSwitch('s1')
        
        # Add Server Host (Fixed IP)
        server = self.addHost('h_server', ip='10.0.0.254')
        self.addLink(server, switch)
        
        # Add Client Hosts
        for i in range(1, n + 1):
            host = self.addHost(f'h{i}', ip=f'10.0.0.{i}')
            self.addLink(host, switch)

topos = {'fl_topo': (lambda: FLTopology())}
