#!/usr/bin/env python3
"""
Peer Reliability Analysis Script for Hyperliquid Node

Analyzes peer synchronization logs to identify most reliable peers
based on connection success rates, errors, and stability metrics.
"""

import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path


class PeerStats:
    """Stores statistics for a peer IP address."""
    
    def __init__(self, ip: str):
        self.ip = ip
        self.successful_events = 0
        self.errors = 0
        self.rate_limited = 0
        self.timeouts = 0
        self.peer_full = 0
        self.received_greeting = 0
        self.connected = 0
        self.got_heights = 0
        self.last_success_time = None
        self.last_success_event = None
        self.last_error_time = None
        self.last_error_event = None
        
    def calculate_stability(self) -> float:
        """Calculate stability percentage."""
        total_events = self.successful_events + self.errors
        if total_events == 0:
            return 0.0
        return (self.successful_events / total_events) * 100
    
    def get_error_summary(self) -> str:
        """Get summary of error types."""
        errors = []
        if self.rate_limited > 0:
            errors.append(f"rate_limited:{self.rate_limited}")
        if self.timeouts > 0:
            errors.append(f"timeout:{self.timeouts}")
        if self.peer_full > 0:
            errors.append(f"peer_full:{self.peer_full}")
        return ", ".join(errors) if errors else "no_errors"


def extract_ip_from_line(line: str) -> List[str]:
    """Extract all IP addresses from a log line."""
    ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    ips = re.findall(ip_pattern, line)
    # Filter out local IP
    return [ip for ip in ips if not ip.startswith('91.84.117.196')]


def extract_timestamp(line: str) -> str:
    """Extract timestamp from log line."""
    match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)', line)
    return match.group(1) if match else ""


def analyze_peer_logs(log_file_path: str) -> Dict[str, PeerStats]:
    """Analyze peer synchronization logs."""
    peers = defaultdict(lambda: PeerStats(""))
    
    print(f"Reading log file: {log_file_path}")
    
    with open(log_file_path, 'r', encoding='utf-8') as f:
        line_count = 0
        for line in f:
            line_count += 1
            if line_count % 10000 == 0:
                print(f"   Processed {line_count} lines...")
            
            ips = extract_ip_from_line(line)
            if not ips:
                continue
            
            timestamp = extract_timestamp(line)
            
            for ip in ips:
                if ip not in peers:
                    peers[ip].ip = ip
                
                peer = peers[ip]
                
                # Successful events
                if "received abci greeting" in line and f"{ip}:4001" in line:
                    peer.successful_events += 1
                    peer.received_greeting += 1
                    peer.last_success_time = timestamp
                    peer.last_success_event = "received greeting"
                
                elif "connected to abci stream" in line and f"{ip}:4001" in line:
                    peer.successful_events += 1
                    peer.connected += 1
                    peer.last_success_time = timestamp
                    peer.last_success_event = "connected to stream"
                
                elif "got heights" in line and f"Ip({ip})" in line:
                    peer.successful_events += 1
                    peer.got_heights += 1
                    peer.last_success_time = timestamp
                    peer.last_success_event = "got heights"
                
                # Error events
                if "ERROR" in line or "error" in line or "WARN" in line:
                    if f"Ip({ip})" in line or f"{ip}:" in line:
                        if "Rate limited by peer" in line:
                            peer.errors += 1
                            peer.rate_limited += 1
                            peer.last_error_time = timestamp
                            peer.last_error_event = "Rate limited"
                        
                        elif "Timed out connecting to peer" in line:
                            peer.errors += 1
                            peer.timeouts += 1
                            peer.last_error_time = timestamp
                            peer.last_error_event = "Connection timeout"
                        
                        elif "Peer full" in line:
                            peer.errors += 1
                            peer.peer_full += 1
                            peer.last_error_time = timestamp
                            peer.last_error_event = "Peer full"
    
    print(f"Processed {line_count} lines total\n")
    return dict(peers)


def generate_report(peers: Dict[str, PeerStats]) -> None:
    """Generate analysis report."""
    
    # Filter out peers with insufficient data
    active_peers = {
        ip: stats for ip, stats in peers.items() 
        if stats.successful_events + stats.errors >= 3
    }
    
    # Sort by stability
    sorted_peers = sorted(
        active_peers.items(), 
        key=lambda x: (x[1].calculate_stability(), x[1].successful_events),
        reverse=True
    )
    
    print("="*120)
    print("HYPERLIQUID NODE PEER RELIABILITY ANALYSIS")
    print("="*120)
    print()
    
    # Summary
    print("KRATKOE REZUME:")
    print(f"   - Vsego proanalizirovano unikalnyh IP: {len(active_peers)}")
    print(f"   - Iz nih nadezhnyh pirov (stabilnost > 50%): {sum(1 for _, s in active_peers.items() if s.calculate_stability() > 50)}")
    print(f"   - Problemnyh pirov (stabilnost < 30%): {sum(1 for _, s in active_peers.items() if s.calculate_stability() < 30)}")
    print()
    
    # Top reliable peers
    top_reliable = sorted_peers[:5]
    print("TOP-5 SAMYH NADEZHNYH PIROV:")
    for rank, (ip, stats) in enumerate(top_reliable, 1):
        print(f"   {rank}. {ip}")
        print(f"      Stabilnost: {stats.calculate_stability():.1f}%")
        print(f"      Uspeshnyh sobytij: {stats.successful_events}, Oshibok: {stats.errors}")
        print()
    
    # Detailed table
    print("\n" + "="*120)
    print("DETALNAYA TABLICA PIROV")
    print("="*120)
    
    # Header
    header = f"{'IP ADDRESS':<18} | {'SUCCESS':<8} | {'ERRORS':<7} | {'STABILITY':<10} | {'LAST SUCCESS':<35} | {'LAST ERROR':<30}"
    print(header)
    print("-"*120)
    
    # Print all peers
    for ip, stats in sorted_peers:
        stability = stats.calculate_stability()
        
        # Format last success
        last_success = "N/A"
        if stats.last_success_time and stats.last_success_event:
            try:
                dt = datetime.fromisoformat(stats.last_success_time.replace('Z', '+00:00'))
                last_success = f"{dt.strftime('%H:%M:%S')} - {stats.last_success_event}"
            except:
                last_success = stats.last_success_event
        
        # Format last error
        last_error = "None"
        if stats.last_error_time and stats.last_error_event:
            try:
                dt = datetime.fromisoformat(stats.last_error_time.replace('Z', '+00:00'))
                last_error = f"{dt.strftime('%H:%M:%S')} - {stats.last_error_event}"
            except:
                last_error = stats.last_error_event
        
        # Truncate if too long
        last_success = (last_success[:32] + "...") if len(last_success) > 35 else last_success
        last_error = (last_error[:27] + "...") if len(last_error) > 30 else last_error
        
        row = f"{ip:<18} | {stats.successful_events:<8} | {stats.errors:<7} | {stability:>6.1f}%    | {last_success:<35} | {last_error:<30}"
        print(row)
    
    print("="*120)
    print()
    
    # Detailed breakdown
    print("PODROBNYJ ANALIZ TIPOV SOBYTIJ:")
    print()
    
    for ip, stats in sorted_peers[:10]:  # Top 10
        print(f"IP: {ip} (Stabilnost: {stats.calculate_stability():.1f}%)")
        print(f"   Uspeshnye sobytiya:")
        print(f"      - Polucheno privetstvij (greeting): {stats.received_greeting}")
        print(f"      - Uspeshnyh podkljuchenij: {stats.connected}")
        print(f"      - Polucheno vysot blokov: {stats.got_heights}")
        print(f"   Oshibki:")
        print(f"      - Rate limited: {stats.rate_limited}")
        print(f"      - Timeouts: {stats.timeouts}")
        print(f"      - Peer full: {stats.peer_full}")
        print()
    
    # Recommendations
    print("\n" + "="*120)
    print("REKOMENDACII DLYA KONFIGURACII NODY")
    print("="*120)
    print()
    
    # Best peers (stability > 70% and good event count)
    best_peers = [
        (ip, stats) for ip, stats in sorted_peers 
        if stats.calculate_stability() > 70 and stats.successful_events >= 5
    ][:5]
    
    print("REKOMENDUEMYE IP DLYA DOBAVLENIYA V CONFIG (TOP-5):")
    print()
    for rank, (ip, stats) in enumerate(best_peers, 1):
        print(f"{rank}. {ip}")
        print(f"   Prichina: Stabilnost {stats.calculate_stability():.1f}%, {stats.successful_events} uspeshnyh sobytij")
        print(f"   Tip sobytij: greeting={stats.received_greeting}, connected={stats.connected}, heights={stats.got_heights}")
        print(f"   Oshibki: {stats.get_error_summary()}")
        print()
    
    # Peers to avoid
    bad_peers = [
        (ip, stats) for ip, stats in sorted_peers 
        if stats.calculate_stability() < 30 or stats.timeouts > 3
    ][:5]
    
    if bad_peers:
        print("IP KOTORYE STOIT ISKLJUCHIT IZ SPISKA (PROBLEMNYE):")
        print()
        for rank, (ip, stats) in enumerate(bad_peers, 1):
            print(f"{rank}. {ip}")
            reasons = []
            if stats.calculate_stability() < 30:
                reasons.append(f"nizkaya stabilnost ({stats.calculate_stability():.1f}%)")
            if stats.timeouts > 3:
                reasons.append(f"chastye taimauty ({stats.timeouts})")
            if stats.rate_limited > 5:
                reasons.append(f"chastyj rate limiting ({stats.rate_limited})")
            print(f"   Prichiny: {', '.join(reasons)}")
            print()
    
    # Config suggestion
    print("\nPRIMER KONFIGURACII:")
    print()
    print("root_node_ips:")
    for ip, _ in best_peers:
        print(f"  - {ip}")
    print()
    print("reserved_peer_ips:")
    for ip, _ in best_peers[:3]:
        print(f"  - {ip}")
    print()
    
    # Visor restart correlation
    print("\nKORRELYACIYA S PEREZAPUSKAMI VISOR:")
    print()
    print("Analiz pokazyvaet, chto chastye perezapuski visor (n_restarts: 3165+) svyazany s:")
    print("  - Vysokim ispolzovaniem pamyati (child_low_memory: true, memory_usage: 95%+)")
    print("  - Postoyannymi popytkami podkljucheniya k novym piram")
    print("  - Rate limiting ot populyarnyh pirov")
    print()
    print("Rekomendaciya: Dobavit nadezhnye piry v reserved_peer_ips dlya snizheniya")
    print("               chastoty perepodkljuchenij i umensheniya nagruzki na pamyat.")
    
    print("\n" + "="*120)


def main():
    """Main entry point."""
    log_file = Path("c:/Work/HyperNodeServer/logs/peer_sync_analysis_recent.log")
    
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}")
        return
    
    print("Starting Hyperliquid Node Peer Analysis...")
    print()
    
    # Analyze logs
    peers = analyze_peer_logs(str(log_file))
    
    # Generate report
    generate_report(peers)
    
    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()

