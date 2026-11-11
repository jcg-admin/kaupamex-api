#!/bin/bash
E=/tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/chain-3d7faad3.events
until grep -q CHAIN-DONE /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/chain-e302630b.events 2>/dev/null; do sleep 20; done
echo "prev-chain-done" >> $E
bash /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/run-gate-multidb.sh 3d7faad3 /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/gate-3d7faad3/kaupamex-api > /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-3d7faad3.log 2>&1
echo "multidb-3d7faad3 $(grep EXIT= /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-3d7faad3.log) $(tail -1 /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/gate-3d7faad3/kaupamex-api/test-results/multidb/pytest_isolation.log)" >> $E
bash /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/run-gate-multidb-nullified.sh 3d7faad3 /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/gate-3d7faad3-null/kaupamex-api > /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-3d7faad3-null.log 2>&1
echo "multidb-null $(grep EXIT= /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/multidb-3d7faad3-null.log) $(grep -E '^(FAILED|ERROR) |passed|failed' /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/gate-3d7faad3-null/kaupamex-api/test-results/multidb/pytest_isolation.log | tail -3 | tr '\n' ' ')" >> $E
cd /home/user/kaupamex-api && bash /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/full-batch.sh > /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/full-3d7faad3.log 2>&1
echo "full-3d7faad3 $(tail -2 /tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/full-3d7faad3.log | tr '\n' ' ')" >> $E
echo CHAIN-DONE >> $E
