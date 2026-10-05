ML/retrain_logs/live_loop/ -- raw material of the live-loop runs of 2026-10-05

dump_flows_run1.txt, dump_flows_run2.txt
    A SECOND READING of the flow table: a loop running `ovs-ofctl dump-flows s1`
    every 5 s beside the enforcement daemon. They are NOT the bytes the backend's
    parser was given. The two readers saw the same table up to 5 s apart, so these
    are close to the parser's input and not identical to it. They are evidence of
    what was on the switch, not of what was parsed.

daemon_responses_run3.txt
    The daemon's own answers, written by backend/scripts/enforcement_daemon.py
    itself (DAEMON_DUMP_LOG) as it returned each one. This IS the parser's input,
    byte for byte. Parsed again with flow_parser._parse_output it gives, per
    window, exactly the flow counts the backend logged (ML/live_loop_run3.json).

traffic.sh            the traffic of runs 1 and 2 (flood as one conversation)
traffic_manyflow.sh   the traffic of run 3 (flood as many conversations); the
                      only difference from traffic.sh is the flood
backend_logging.json  the --log-config runs 1 and 2 needed. Not needed since
                      backend/app/logging_setup.py; run 3 was started without it.

Nothing in these files was written or edited by hand. Summaries:
ML/retrain_logs/live_loop_run.txt, live_loop_run3.txt, ML/live_loop_run.json,
ML/live_loop_run3.json.
