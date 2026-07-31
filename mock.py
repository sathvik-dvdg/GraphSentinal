import sys
with open("/usr/bin/ovs-ofctl", "w") as f:
    f.write('''#!/bin/bash
FLOW_FILE="/tmp/ovs_mock_flows.txt"
touch $FLOW_FILE

if [ "$1" = "dump-flows" ]; then
    echo " nw_src=10.0.0.2,nw_dst=10.0.0.1,n_packets=5,n_bytes=300,tp_src=123,tp_dst=80,duration=10.0s tcp"
    cat $FLOW_FILE
elif [ "$1" = "add-flow" ]; then
    shift 2
    echo " $1" >> $FLOW_FILE
elif [ "$1" = "del-flows" ]; then
    > $FLOW_FILE
else
    echo "mocked action"
fi
''')
import os
os.chmod("/usr/bin/ovs-ofctl", 0o755)
