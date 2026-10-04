# Traffic inside the running Mininet topology's host namespaces. Every flow below
# is real packets through s1; nothing is written to the flow table by hand.
h() { n=$1; shift; mnexec -a "$(pgrep -f "mininet:h$n\$" | head -1)" "$@"; }
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
log "listeners: h3 http :80, h4 tcp :22, h1 tcp :80"
h 3 bash -c 'cd /tmp && nohup python3 -m http.server 80 >/dev/null 2>&1 &'
h 4 bash -c 'nohup sh -c "while true; do nc -l -p 22 -q 0 </dev/null >/dev/null 2>&1; done" >/dev/null 2>&1 &'
h 1 bash -c 'cd /tmp && nohup python3 -m http.server 80 >/dev/null 2>&1 &'
sleep 2
log "benign: pings and HTTP fetches between ordinary hosts (about 60 s)"
for i in $(seq 1 12); do
  h 8 ping -c1 -W1 10.0.0.3 >/dev/null 2>&1; h 6 ping -c1 -W1 10.0.0.4 >/dev/null 2>&1
  h 8 curl -s -m 2 -o /dev/null http://10.0.0.3/ ; h 7 curl -s -m 2 -o /dev/null http://10.0.0.3/
  h 9 curl -s -m 2 -o /dev/null http://10.0.0.1/ ; h 10 curl -s -m 2 -o /dev/null http://10.0.0.1/
  sleep 5
done
log "port scan: h2 (10.0.0.2) nmap -sT of 10.0.0.1, 200 ports"
h 2 nmap -sT -Pn -n --max-retries 0 -T4 -p 1-200 10.0.0.1 >/dev/null 2>&1
sleep 25
log "brute force shape: h5 (10.0.0.5) 60 TCP connections to 10.0.0.4:22"
for i in $(seq 1 60); do h 5 bash -c 'timeout 1 bash -c "</dev/tcp/10.0.0.4/22" >/dev/null 2>&1'; done
sleep 25
log "flood: h2 and h5 hping3 SYN to 10.0.0.3:80, a new source port per packet, 500 packets each (many conversations)"
h 5 hping3 -S -p 80 -i u20000 -c 500 -q 10.0.0.3 >/dev/null 2>&1 &
h 2 hping3 -S -p 80 -i u20000 -c 500 -q 10.0.0.3 >/dev/null 2>&1; wait
log "benign again (about 70 s) so the last windows close"
for i in $(seq 1 14); do
  h 8 curl -s -m 2 -o /dev/null http://10.0.0.3/ ; h 9 curl -s -m 2 -o /dev/null http://10.0.0.1/
  h 6 ping -c1 -W1 10.0.0.4 >/dev/null 2>&1
  sleep 5
done
log "done"
