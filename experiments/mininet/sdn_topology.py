"""Mininet topology for SDN DDoS defense demo."""

from mininet.topo import Topo


class SDNDefenseTopo(Topo):
    """
    h_server  10.0.0.254  protected web service
    h1, h2    normal users
    h_attacker 10.0.0.99  attack source (optional)
    """

    def build(self, n_clients: int = 2, with_attacker: bool = True):
        s1 = self.addSwitch('s1')
        server = self.addHost('h_server', ip='10.0.0.254')
        self.addLink(server, s1)
        for i in range(1, n_clients + 1):
            h = self.addHost(f'h{i}', ip=f'10.0.0.{i}')
            self.addLink(h, s1)
        if with_attacker:
            atk = self.addHost('h_attacker', ip='10.0.0.99')
            self.addLink(atk, s1)


topos = {
    'sdn_defense': (lambda: SDNDefenseTopo()),
    'fl_topo': (lambda: SDNDefenseTopo(with_attacker=False)),
}
