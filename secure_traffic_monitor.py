from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.recoco import Timer
from pox.lib.addresses import IPAddr

log = core.getLogger()

# CONFIGURATION: Allow h1 (10.0.0.1) to talk to h2 (10.0.0.2)
ALLOWED_PAIR = (IPAddr("10.0.0.1"), IPAddr("10.0.0.2"))

class SecureController(object):
    def __init__(self):
        core.openflow.addListeners(self)
        # Periodic stats timer (Requirement: periodic monitoring)
        Timer(10, self._request_stats, recurring=True)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet or not packet.parsed: 
            return

        ip_pkt = packet.find('ipv4')
        
        # 1. Handling non-IP traffic (like ARP)
        if ip_pkt is None:
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            event.connection.send(msg)
            return

        src_ip = ip_pkt.srcip
        dst_ip = ip_pkt.dstip

        # 2. Check the White List (Requirement: Match + Action Logic)
        if (src_ip == ALLOWED_PAIR[0] and dst_ip == ALLOWED_PAIR[1]) or \
           (src_ip == ALLOWED_PAIR[1] and dst_ip == ALLOWED_PAIR[0]):
            
            log.info("ALLOWED: %s <-> %s", src_ip, dst_ip)
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet)
            msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            msg.idle_timeout = 10 
            event.connection.send(msg)
        else:
            # 3. EXPLICIT BLOCK (Requirement: Allowed vs Blocked scenario)
            log.warning("BLOCKED: %s <-> %s", src_ip, dst_ip)
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet)
            msg.idle_timeout = 10
            # NO ACTIONS = DROP
            event.connection.send(msg)

    def _request_stats(self):
        """ Requirement: Retrieve flow statistics """
        for connection in core.openflow.connections.values():
            connection.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))

    def _handle_FlowStatsReceived(self, event):
        """ Requirement: Display byte/packet counts """
        log.info("--- Periodic Traffic Report ---")
        for flow in event.stats:
            # We filter out some internal junk to keep the report clean
            if flow.match.dl_type == 0x0800: # Only show IPv4 stats
                log.info("Flow: %s | Pkts: %d | Bytes: %d", 
                         flow.match, flow.packet_count, flow.byte_count)

def launch():
    core.registerNew(SecureController)
