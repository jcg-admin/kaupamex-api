#!/bin/bash
cd /home/user/kaupamex-api
until grep -q '^EXIT=' /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-555ac073.log; do sleep 20; done
echo "multidb-555ac073 $(grep EXIT= /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-555ac073.log)" >> /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/chain-e302630b.events
bash /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/full-batch.sh > /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/full-s5.log 2>&1
echo "full-s5 $(tail -2 /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/full-s5.log | tr '\n' ' ')" >> /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/chain-e302630b.events
bash /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/run-gate-multidb.sh e302630b /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/gate-e302630b/kaupamex-api > /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-e302630b.log 2>&1
echo "multidb-e302630b $(grep EXIT= /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-e302630b.log) $(tail -1 /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/gate-e302630b/kaupamex-api/test-results/multidb/pytest_isolation.log)" >> /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/chain-e302630b.events
echo CHAIN-DONE >> /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/chain-e302630b.events
