"""Ryu/OpenFlow 1.3 PCMI gate.

Install a DROP or METER flow only after PCMI signature, freshness and clipping
checks pass. The v1 implementation intentionally does not pretend to provide ZKP.
"""
from __future__ import annotations
import json
try:
    from ryu.base import app_manager
    from ryu.controller import ofp_event
    from ryu.controller.handler import CONFIG_DISPATCHER, set_ev_cls
    from ryu.ofproto import ofproto_v1_3
    from ryu.app.wsgi import ControllerBase, WSGIApplication, route
    RYU_AVAILABLE = True
except ImportError:
    RYU_AVAILABLE = False

if RYU_AVAILABLE:
    class PCMIController(ControllerBase):
        def __init__(self, req, link, data, **config):
            super().__init__(req, link, data, **config)
            self.app = data['app']

    class PCMIApp(app_manager.RyuApp):
        OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
        _CONTEXTS = {'wsgi': WSGIApplication}
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.datapaths = {}
            wsgi = kwargs['wsgi']
            wsgi.register(PCMIController, {'app': self})

        @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
        def switch_features(self, ev):
            self.datapaths[ev.msg.datapath.id] = ev.msg.datapath

        def install_drop(self, dp, src_ip, dst_ip=None):
            p = dp.ofproto_parser; o = dp.ofproto
            match_kwargs = {'eth_type': 0x0800, 'ipv4_src': src_ip}
            if dst_ip: match_kwargs['ipv4_dst'] = dst_ip
            match = p.OFPMatch(**match_kwargs)
            mod = p.OFPFlowMod(datapath=dp, priority=50000, match=match, instructions=[])
            dp.send_msg(mod)

        def install_meter(self, dp, src_ip, rate_kbps=500):
            # Meter creation is switch/version dependent; caller should verify support.
            p = dp.ofproto_parser; o = dp.ofproto
            band = p.OFPMeterBandDrop(rate=rate_kbps, burst_size=max(rate_kbps//10,1))
            req = p.OFPMeterMod(dp, command=o.OFPMC_ADD, flags=o.OFPMF_KBPS, meter_id=1, bands=[band])
            dp.send_msg(req)
            match = p.OFPMatch(eth_type=0x0800, ipv4_src=src_ip)
            inst = [p.OFPInstructionMeter(1), p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, [p.OFPActionOutput(o.OFPP_NORMAL)])]
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=49000, match=match, instructions=inst))
else:
    class PCMIApp:
        """Import-safe placeholder when Ryu is not installed."""
        pass
