#!/usr/bin/env python3
"""
█ __  __    _    __  _____  ____  
|  \/  |  / \   \ \/ / _ \|  _ \ 
| |\/| | / _ \   \  / | | | | | |
| |  | |/ ___ \  /  \ |_| | |_| |
|_|  |_/_/   \_\/_/\_\___/|____/ 
ADVANCED CANARY TOKEN CLI v2.0
Catch hackers, scammers, and data thieves in real-time
"""

import argparse
import json
import sqlite3
import datetime
import hashlib
import uuid
import requests
import socket
import sys
import os
import time
import threading
import queue
import base64
import random
import string
from colorama import init, Fore, Back, Style
import pyfiglet
from termcolor import colored
import whois
import dns.resolver
from fake_useragent import UserAgent
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

init(autoreset=True)

# ==================== CONFIGURATION ====================
DB_NAME = "canary_tokens.db"
WEBHOOK_URLS = []  # Add your Discord/Slack webhooks
SMTP_CONFIG = {
    'server': 'smtp.gmail.com',
    'port': 587,
    'username': 'your-email@gmail.com',
    'password': 'your-app-password'
}

# Cloudflare Worker URL (Part 2 mein deploy karenge)
CLOUDFLARE_WORKER = "https://canary-token.your-worker.workers.dev"

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Tokens table
    c.execute('''CREATE TABLE IF NOT EXISTS tokens
                 (id TEXT PRIMARY KEY,
                  name TEXT,
                  token_type TEXT,
                  target_email TEXT,
                  webhook TEXT,
                  created_at TIMESTAMP,
                  memo TEXT,
                  active BOOLEAN,
                  cf_worker_url TEXT,
                  hit_count INTEGER DEFAULT 0,
                  last_hit TIMESTAMP)''')
    
    # Alerts table with more details
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  token_id TEXT,
                  triggered_at TIMESTAMP,
                  ip_address TEXT,
                  port INTEGER,
                  user_agent TEXT,
                  headers TEXT,
                  location TEXT,
                  referer TEXT,
                  method TEXT,
                  raw_data TEXT,
                  browser_fingerprint TEXT,
                  screen_resolution TEXT,
                  timezone TEXT,
                  language TEXT,
                  cookies TEXT,
                  dom_storage TEXT,
                  canvas_fingerprint TEXT,
                  webgl_fingerprint TEXT,
                  FOREIGN KEY(token_id) REFERENCES tokens(id))''')
    
    # Threat intel table
    c.execute('''CREATE TABLE IF NOT EXISTS threat_intel
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ip_address TEXT UNIQUE,
                  country TEXT,
                  asn TEXT,
                  isp TEXT,
                  threat_score INTEGER,
                  is_vpn BOOLEAN,
                  is_tor BOOLEAN,
                  is_proxy BOOLEAN,
                  last_seen TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

# ==================== UTILITY FUNCTIONS ====================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    os.system('clear' if os.name == 'posix' else 'cls')
    banner = pyfiglet.figlet_format("CANARY ELITE", font="slant")
    print(f"{Colors.CYAN}{banner}{Colors.ENDC}")
    print(f"{Colors.GREEN}╔══════════════════════════════════════════════════════════╗")
    print(f"║     Advanced Canary Token System - CATCH SCAMMERS          ║")
    print(f"║     Version 2.0 | Cloudflare Integration | Real-time       ║")
    print(f"╚══════════════════════════════════════════════════════════════╝{Colors.ENDC}")
    print()

def generate_token_id():
    """Generate unique token ID"""
    return str(uuid.uuid4()).replace('-', '')

def get_public_ip():
    """Get your public IP"""
    try:
        return requests.get('https://api.ipify.org', timeout=5).text
    except:
        return "Unknown"

def get_ip_info(ip):
    """Get detailed IP information"""
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                'country': data.get('country', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'isp': data.get('isp', 'Unknown'),
                'org': data.get('org', 'Unknown'),
                'as': data.get('as', 'Unknown'),
                'lat': data.get('lat', 0),
                'lon': data.get('lon', 0),
                'timezone': data.get('timezone', 'Unknown')
            }
    except:
        pass
    return {'country': 'Unknown', 'city': 'Unknown'}

def check_threat_intel(ip):
    """Check if IP is known threat"""
    threat_score = 0
    details = {}
    
    try:
        # Check if VPN/Proxy
        response = requests.get(f'https://vpnapi.io/api/{ip}?key=YOUR_API_KEY', timeout=2)
        if response.status_code == 200:
            data = response.json()
            details['is_vpn'] = data.get('security', {}).get('vpn', False)
            details['is_proxy'] = data.get('security', {}).get('proxy', False)
            details['is_tor'] = data.get('security', {}).get('tor', False)
            if any([details.get('is_vpn'), details.get('is_proxy'), details.get('is_tor')]):
                threat_score += 50
    except:
        pass
    
    # Check against known malicious IPs (you can add your own list)
    malicious_ips = []  # Load from file/database
    
    if ip in malicious_ips:
        threat_score += 100
    
    return threat_score, details

# ==================== TOKEN CREATION ====================
def create_token(args):
    """Create a new canary token"""
    print(f"\n{Colors.CYAN}[*] Creating new canary token...{Colors.ENDC}")
    
    token_id = generate_token_id()
    
    # Generate Cloudflare URL if requested
    cf_url = None
    if args.cloudflare:
        cf_url = f"{CLOUDFLARE_WORKER}?token={token_id}&target={args.target}"
    
    # Generate token URL based on type
    if args.type == "url":
        token_url = f"http://your-server.com/t/{token_id}"
    elif args.type == "image":
        token_url = f"http://your-server.com/i/{token_id}.png"
    elif args.type == "document":
        token_url = f"http://your-server.com/d/{token_id}.pdf"
    elif args.type == "email":
        token_url = f"http://your-server.com/e/{token_id}"
    elif args.type == "dns":
        token_url = f"{token_id}.canary.yourdomain.com"
    elif args.type == "cloudflare":
        token_url = cf_url
    else:
        token_url = f"http://your-server.com/{token_id}"
    
    # Save to database
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO tokens 
                 (id, name, token_type, target_email, webhook, created_at, memo, active, cf_worker_url)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (token_id, args.name, args.type, args.email, args.webhook, 
               datetime.datetime.now(), args.memo, True, cf_url))
    conn.commit()
    conn.close()
    
    # Generate QR code for the token
    try:
        import qrcode
        img = qrcode.make(token_url)
        img.save(f"token_{token_id}.png")
        qr_file = f"token_{token_id}.png"
    except:
        qr_file = None
    
    # Display token info
    print(f"\n{Colors.GREEN}✓ TOKEN CREATED SUCCESSFULLY!{Colors.ENDC}")
    print(f"\n{Colors.CYAN}════════════════════════ TOKEN DETAILS ════════════════════════{Colors.ENDC}")
    print(f"ID:       {Colors.WARNING}{token_id}{Colors.ENDC}")
    print(f"Name:     {args.name}")
    print(f"Type:     {args.type}")
    print(f"Created:  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{Colors.GREEN}URL:{Colors.ENDC} {token_url}")
    
    if cf_url:
        print(f"{Colors.GREEN}Cloudflare:{Colors.ENDC} {cf_url}")
    
    if qr_file:
        print(f"{Colors.GREEN}QR Code:{Colors.ENDC} saved as {qr_file}")
    
    print(f"\n{Colors.YELLOW}[!] Share this URL. When someone clicks, you'll be alerted!{Colors.ENDC}")
    
    return token_id

# ==================== TOKEN MONITORING ====================
def monitor_tokens(interval=5):
    """Real-time token monitoring"""
    print(f"\n{Colors.CYAN}[*] Starting real-time token monitor...{Colors.ENDC}")
    print(f"{Colors.YELLOW}[!] Press Ctrl+C to stop{Colors.ENDC}\n")
    
    last_alert_id = 0
    
    try:
        while True:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            
            # Get new alerts
            c.execute('''SELECT a.*, t.name FROM alerts a 
                         JOIN tokens t ON a.token_id = t.id 
                         WHERE a.id > ? ORDER BY a.id DESC''', (last_alert_id,))
            new_alerts = c.fetchall()
            
            for alert in new_alerts:
                last_alert_id = max(last_alert_id, alert[0])
                
                # Display alert
                print(f"\n{Colors.FAIL}╔═════════════════════ ALERT! ═════════════════════╗{Colors.ENDC}")
                print(f"Token:     {Colors.WARNING}{alert[11]}{Colors.ENDC}")
                print(f"Time:      {alert[2]}")
                print(f"IP:        {Colors.GREEN}{alert[3]}{Colors.ENDC}")
                print(f"Location:  {alert[7]}")
                print(f"UserAgent: {alert[4][:80]}...")
                print(f"Referer:   {alert[8]}")
                print(f"{Colors.FAIL}╚══════════════════════════════════════════════════╝{Colors.ENDC}")
                
                # Play sound alert
                print('\a')  # Bell sound
                
                # Send webhook
                if args.webhook:
                    send_webhook_alert(alert)
            
            conn.close()
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[*] Monitor stopped{Colors.ENDC}")

def send_webhook_alert(alert):
    """Send alert to webhook"""
    webhook_url = args.webhook
    if not webhook_url:
        return
    
    data = {
        "content": f"🚨 **CANARY TOKEN TRIGGERED!** 🚨\n"
                   f"**Token:** {alert[11]}\n"
                   f"**IP:** {alert[3]}\n"
                   f"**Location:** {alert[7]}\n"
                   f"**Time:** {alert[2]}\n"
                   f"**User-Agent:** {alert[4][:100]}"
    }
    
    try:
        requests.post(webhook_url, json=data)
    except:
        pass

# ==================== TOKEN MANAGEMENT ====================
def list_tokens():
    """List all tokens"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''SELECT t.id, t.name, t.token_type, t.created_at, 
                 COUNT(a.id) as hits, MAX(a.triggered_at) as last_hit
                 FROM tokens t
                 LEFT JOIN alerts a ON t.id = a.token_id
                 WHERE t.active = 1
                 GROUP BY t.id
                 ORDER BY t.created_at DESC''')
    
    tokens = c.fetchall()
    conn.close()
    
    if not tokens:
        print(f"{Colors.YELLOW}[!] No active tokens found{Colors.ENDC}")
        return
    
    print(f"\n{Colors.CYAN}════════════════════ ACTIVE TOKENS ════════════════════{Colors.ENDC}")
    print(f"{'ID':<36} {'NAME':<20} {'TYPE':<10} {'HITS':<6} {'LAST HIT'}")
    print("-" * 80)
    
    for token in tokens:
        token_id = token[0][:8] + "..."
        name = token[1][:18] + ".." if len(token[1]) > 18 else token[1]
        last_hit = token[5][:16] if token[5] else "Never"
        print(f"{token_id:<36} {name:<20} {token[2]:<10} {token[4]:<6} {last_hit}")
    
    print()

def show_alerts(token_id=None, limit=20):
    """Show alerts"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if token_id:
        c.execute('''SELECT a.*, t.name FROM alerts a 
                     JOIN tokens t ON a.token_id = t.id 
                     WHERE a.token_id = ?
                     ORDER BY a.triggered_at DESC LIMIT ?''', (token_id, limit))
    else:
        c.execute('''SELECT a.*, t.name FROM alerts a 
                     JOIN tokens t ON a.token_id = t.id 
                     ORDER BY a.triggered_at DESC LIMIT ?''', (limit,))
    
    alerts = c.fetchall()
    conn.close()
    
    if not alerts:
        print(f"{Colors.YELLOW}[!] No alerts found{Colors.ENDC}")
        return
    
    print(f"\n{Colors.CYAN}════════════════════ RECENT ALERTS ════════════════════{Colors.ENDC}")
    
    for alert in alerts:
        print(f"\n[{alert[2]}] {Colors.WARNING}{alert[11]}{Colors.ENDC}")
        print(f"  IP: {Colors.GREEN}{alert[3]}{Colors.ENDC}")
        print(f"  Location: {alert[7]}")
        print(f"  User-Agent: {alert[4][:80]}...")

def delete_token(token_id):
    """Delete a token"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # First delete associated alerts
    c.execute("DELETE FROM alerts WHERE token_id = ?", (token_id,))
    # Then delete token
    c.execute("DELETE FROM tokens WHERE id = ?", (token_id,))
    
    conn.commit()
    affected = c.rowcount
    conn.close()
    
    if affected:
        print(f"{Colors.GREEN}✓ Token {token_id} deleted successfully{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}✗ Token not found{Colors.ENDC}")

def deactivate_token(token_id):
    """Deactivate a token"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE tokens SET active = 0 WHERE id = ?", (token_id,))
    conn.commit()
    affected = c.rowcount
    conn.close()
    
    if affected:
        print(f"{Colors.GREEN}✓ Token {token_id} deactivated{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}✗ Token not found{Colors.ENDC}")

# ==================== STATISTICS ====================
def show_stats():
    """Show statistics"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Total tokens
    c.execute("SELECT COUNT(*) FROM tokens")
    total_tokens = c.fetchone()[0]
    
    # Active tokens
    c.execute("SELECT COUNT(*) FROM tokens WHERE active = 1")
    active_tokens = c.fetchone()[0]
    
    # Total alerts
    c.execute("SELECT COUNT(*) FROM alerts")
    total_alerts = c.fetchone()[0]
    
    # Alerts today
    c.execute("SELECT COUNT(*) FROM alerts WHERE date(triggered_at) = date('now')")
    alerts_today = c.fetchone()[0]
    
    # Top hit tokens
    c.execute('''SELECT t.name, COUNT(a.id) as hits 
                 FROM tokens t
                 LEFT JOIN alerts a ON t.id = a.token_id
                 GROUP BY t.id
                 ORDER BY hits DESC
                 LIMIT 5''')
    top_tokens = c.fetchall()
    
    # Top IPs
    c.execute('''SELECT ip_address, COUNT(*) as hits 
                 FROM alerts 
                 GROUP BY ip_address 
                 ORDER BY hits DESC 
                 LIMIT 5''')
    top_ips = c.fetchall()
    
    conn.close()
    
    print(f"\n{Colors.CYAN}════════════════════ STATISTICS ════════════════════{Colors.ENDC}")
    print(f"Total Tokens:  {Colors.WARNING}{total_tokens}{Colors.ENDC}")
    print(f"Active Tokens: {Colors.GREEN}{active_tokens}{Colors.ENDC}")
    print(f"Total Alerts:  {Colors.FAIL}{total_alerts}{Colors.ENDC}")
    print(f"Alerts Today:  {alerts_today}")
    
    if top_tokens:
        print(f"\n{Colors.CYAN}Top Tokens:{Colors.ENDC}")
        for token in top_tokens:
            print(f"  {token[0]}: {token[1]} hits")
    
    if top_ips:
        print(f"\n{Colors.CYAN}Top IPs:{Colors.ENDC}")
        for ip in top_ips:
            print(f"  {ip[0]}: {ip[1]} hits")

# ==================== EXPORT FUNCTIONS ====================
def export_alerts(format='json'):
    """Export alerts to file"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''SELECT a.*, t.name FROM alerts a 
                 JOIN tokens t ON a.token_id = t.id 
                 ORDER BY a.triggered_at DESC''')
    alerts = c.fetchall()
    conn.close()
    
    if format == 'json':
        filename = f"alerts_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(alerts, f, default=str, indent=2)
        print(f"{Colors.GREEN}✓ Exported to {filename}{Colors.ENDC}")
    
    elif format == 'csv':
        filename = f"alerts_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w') as f:
            f.write("ID,Token,Time,IP,Location,UserAgent\n")
            for alert in alerts:
                f.write(f"{alert[0]},{alert[11]},{alert[2]},{alert[3]},{alert[7]},{alert[4]}\n")
        print(f"{Colors.GREEN}✓ Exported to {filename}{Colors.ENDC}")

# ==================== CLOUDFLARE INTEGRATION ====================
def setup_cloudflare_worker():
    """Generate Cloudflare Worker code"""
    worker_code = """
// Cloudflare Worker for Canary Tokens
// Deploy this to workers.cloudflare.com

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const token = url.searchParams.get('token')
  const target = url.searchParams.get('target')
  
  // Log the visit
  const visitData = {
    token: token,
    ip: request.headers.get('CF-Connecting-IP'),
    country: request.cf?.country,
    city: request.cf?.city,
    time: new Date().toISOString(),
    userAgent: request.headers.get('User-Agent'),
    referer: request.headers.get('Referer')
  }
  
  // Send to your server
  await fetch('http://your-server.com/api/cloudflare_alert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(visitData)
  })
  
  // Redirect to target if provided
  if (target) {
    return Response.redirect(target, 302)
  }
  
  // Default response
  return new Response('Visit logged', {
    headers: { 'Content-Type': 'text/html' },
    status: 200
  })
}
"""
    
    print(f"\n{Colors.CYAN}════════════════ CLOUDFLARE WORKER CODE ════════════════{Colors.ENDC}")
    print(worker_code)
    print(f"\n{Colors.GREEN}1. Go to https://workers.cloudflare.com")
    print("2. Create new worker")
    print("3. Paste this code")
    print("4. Deploy")
    print(f"5. Update CLOUDFLARE_WORKER variable with your worker URL{Colors.ENDC}")

# ==================== MAIN CLI ====================
def main():
    parser = argparse.ArgumentParser(description='Advanced Canary Token System')
    parser.add_argument('--version', action='version', version='Canary Elite v2.0')
    
    # Token creation
    parser.add_argument('-c', '--create', action='store_true', help='Create new token')
    parser.add_argument('-n', '--name', default='Test Token', help='Token name')
    parser.add_argument('-t', '--type', choices=['url', 'image', 'document', 'email', 'dns', 'cloudflare'], 
                       default='url', help='Token type')
    parser.add_argument('-e', '--email', help='Target email for notifications')
    parser.add_argument('-w', '--webhook', help='Webhook URL for notifications')
    parser.add_argument('-m', '--memo', help='Memo/notes')
    parser.add_argument('--cloudflare', action='store_true', help='Use Cloudflare worker')
    parser.add_argument('--target', help='Redirect target URL')
    
    # Monitoring
    parser.add_argument('-M', '--monitor', action='store_true', help='Monitor tokens in real-time')
    parser.add_argument('-i', '--interval', type=int, default=5, help='Monitor interval (seconds)')
    
    # Token management
    parser.add_argument('-l', '--list', action='store_true', help='List all tokens')
    parser.add_argument('-a', '--alerts', help='Show alerts for token')
    parser.add_argument('--alerts-all', action='store_true', help='Show all recent alerts')
    parser.add_argument('-d', '--delete', help='Delete token')
    parser.add_argument('--deactivate', help='Deactivate token')
    
    # Stats and export
    parser.add_argument('-s', '--stats', action='store_true', help='Show statistics')
    parser.add_argument('--export', choices=['json', 'csv'], help='Export alerts')
    
    # Cloudflare
    parser.add_argument('--cf-worker', action='store_true', help='Generate Cloudflare worker code')
    
    # Other
    parser.add_argument('--info', help='Get IP information')
    
    global args
    args = parser.parse_args()
    
    print_banner()
    
    if len(sys.argv) == 1:
        parser.print_help()
        print(f"\n{Colors.CYAN}Examples:{Colors.ENDC}")
        print("  python canary_cli.py -c -n 'HR Database' -t url -e alert@example.com")
        print("  python canary_cli.py -M")
        print("  python canary_cli.py -l")
        print("  python canary_cli.py --alerts-all")
        print("  python canary_cli.py --cf-worker")
        print("  python canary_cli.py -s")
        return
    
    # Handle commands
    if args.create:
        create_token(args)
    
    elif args.monitor:
        monitor_tokens(args.interval)
    
    elif args.list:
        list_tokens()
    
    elif args.alerts:
        show_alerts(args.alerts)
    
    elif args.alerts_all:
        show_alerts()
    
    elif args.delete:
        delete_token(args.delete)
    
    elif args.deactivate:
        deactivate_token(args.deactivate)
    
    elif args.stats:
        show_stats()
    
    elif args.export:
        export_alerts(args.export)
    
    elif args.cf_worker:
        setup_cloudflare_worker()
    
    elif args.info:
        info = get_ip_info(args.info)
        print(f"\n{Colors.CYAN}IP Information for {args.info}:{Colors.ENDC}")
        for key, value in info.items():
            print(f"  {key}: {value}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
