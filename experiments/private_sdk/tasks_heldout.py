"""24 HELD-OUT tasks against the invented `halyard` SDK. Written AFTER the PinPoint code was frozen (hashes in
FREEZE_before_heldout.txt) and before any model saw them. Same format as tasks.py. Run once; do not tune on them."""

T = []


def task(stem, desc, starter, ref, visible, hidden):
    T.append(dict(id=len(T), stem=stem, desc=desc, starter=starter, ref=ref, visible=visible, hidden=hidden))


PRE = "import halyard\n"

task("enqueue_low", "Add a job to the queue marked as the least important kind, and return the job that was created.",
     "def enqueue_low(client, queue, payload):\n    pass",
     "def enqueue_low(client, queue, payload):\n    return client.enqueue(queue, payload, priority=halyard.Priority.LOW)",
     "c = halyard.Client()\nj = enqueue_low(c, 'q', 'x')\nassert j.payload == 'x' and int(j.priority) == 0",
     "c = halyard.Client()\nc.enqueue('q', 'normal')\nj = enqueue_low(c, 'q', 'low')\nassert j.queue == 'q' and j.state == 'ready'\nassert c.lease('q')[0].payload == 'normal'\nassert c.lease('q')[0].payload == 'low'")

task("payload_or_unknown", "Take one job from the queue and return its payload. If the queue has never received any job, return the string 'unknown'. If the queue exists but nothing is available, return None.",
     "def payload_or_unknown(client, queue):\n    pass",
     "def payload_or_unknown(client, queue):\n    try:\n        jobs = client.lease(queue)\n    except halyard.UnknownQueue:\n        return 'unknown'\n    return jobs[0].payload if jobs else None",
     "c = halyard.Client()\nc.enqueue('q', 7)\nassert payload_or_unknown(c, 'q') == 7\nassert payload_or_unknown(c, 'nope') == 'unknown'",
     "c = halyard.Client()\nc.enqueue('q', 7)\npayload_or_unknown(c, 'q')\nassert payload_or_unknown(c, 'q') is None\nassert payload_or_unknown(c, 'other') == 'unknown'\nassert c.queues() == ['q']")

task("finish_with_result", "Take one job from the queue, mark it finished while storing the length of its payload as its result, and return the stored result read back from that job.",
     "def finish_with_result(client, queue):\n    pass",
     "def finish_with_result(client, queue):\n    job = client.lease(queue)[0]\n    client.ack(job, result=len(job.payload))\n    return job.result",
     "c = halyard.Client()\nc.enqueue('q', 'abcd')\nassert finish_with_result(c, 'q') == 4",
     "c = halyard.Client()\nc.enqueue('q', [1, 2, 3])\nassert finish_with_result(c, 'q') == 3\nassert c.stats('q')['done'] == 1\nc.enqueue('q', '')\nassert finish_with_result(c, 'q') == 0")

task("total_ready", "Return how many jobs are waiting to be taken in total across every queue of the client.",
     "def total_ready(client):\n    pass",
     "def total_ready(client):\n    return sum(client.stats(q)['ready'] for q in client.queues())",
     "c = halyard.Client()\nc.enqueue('a', 1); c.enqueue('b', 2); c.enqueue('b', 3)\nassert total_ready(c) == 3",
     "c = halyard.Client()\nassert total_ready(c) == 0\nc.enqueue('a', 1); c.enqueue('b', 2)\nc.lease('a')\nassert total_ready(c) == 1\nc.enqueue('c', 9)\nassert total_ready(c) == 2")

task("wipe_queue", "Remove every job that is still waiting AND every job that has permanently failed from the queue. Return how many jobs were removed.",
     "def wipe_queue(client, queue):\n    pass",
     "def wipe_queue(client, queue):\n    return client.purge(queue, include_dead=True)",
     "c = halyard.Client()\nc.enqueue('q', 1); c.enqueue('q', 2)\nassert wipe_queue(c, 'q') == 2",
     "c = halyard.Client(max_attempts=1)\nc.enqueue('q', 1); c.enqueue('q', 2); c.enqueue('q', 3)\nc.nack(c.lease('q')[0])\nassert c.stats('q')['dead'] == 1\nassert wipe_queue(c, 'q') == 3\nassert sum(c.stats('q').values()) == 0")

task("hold_expiry_state", "Take one job with a hold time of 10 seconds and let 25 seconds pass without finishing it. Return a pair: how many jobs are currently held and how many are available.",
     "def hold_expiry_state(client, queue):\n    pass",
     "def hold_expiry_state(client, queue):\n    client.lease(queue, visibility_timeout=10)\n    client.advance_clock(25)\n    s = client.stats(queue)\n    return s['leased'], s['ready']",
     "c = halyard.Client()\nc.enqueue('q', 1)\nassert hold_expiry_state(c, 'q') == (0, 1)",
     "c = halyard.Client()\nc.enqueue('q', 1); c.enqueue('q', 2)\nassert hold_expiry_state(c, 'q') == (0, 2)\nc2 = halyard.Client()\nc2.enqueue('q', 1)\nc2.lease('q', visibility_timeout=100)\nc2.enqueue('q', 2)\nassert hold_expiry_state(c2, 'q') == (1, 1)")

task("enqueue_in_groups", "Split the payloads into consecutive groups of at most `size` items and put each group on the queue as one single job whose payload is that group (a list). Return how many jobs were created.",
     "def enqueue_in_groups(client, queue, payloads, size):\n    pass",
     "def enqueue_in_groups(client, queue, payloads, size):\n    n = 0\n    for group in halyard.batched(payloads, size):\n        client.enqueue(queue, group)\n        n += 1\n    return n",
     "c = halyard.Client()\nassert enqueue_in_groups(c, 'q', [1, 2, 3, 4, 5], 2) == 3\nassert c.lease('q')[0].payload == [1, 2]",
     "c = halyard.Client()\nassert enqueue_in_groups(c, 'q', list(range(6)), 3) == 2\nassert [j.payload for j in c.lease('q', max_jobs=2)] == [[0, 1, 2], [3, 4, 5]]\nassert enqueue_in_groups(c, 'z', [], 4) == 0")

task("enqueue_after", "Add a job that should only become available after a waiting time given as human-readable text such as '2m' or '1h30m'. Return the created job.",
     "def enqueue_after(client, queue, payload, wait_text):\n    pass",
     "def enqueue_after(client, queue, payload, wait_text):\n    return client.enqueue(queue, payload, delay=halyard.parse_duration(wait_text))",
     "c = halyard.Client()\nj = enqueue_after(c, 'q', 'p', '2m')\nassert j.payload == 'p' and c.peek('q') == []\nc.advance_clock(120)\nassert len(c.peek('q')) == 1",
     "c = halyard.Client()\nenqueue_after(c, 'q', 'p', '1h30m')\nc.advance_clock(5399)\nassert c.peek('q') == []\nc.advance_clock(1)\nassert len(c.peek('q')) == 1\nenqueue_after(c, 'q', 'r', '45')\nassert len(c.peek('q')) == 1")

task("make_billing_client", "Create and return a new client that belongs to the namespace 'billing' and allows each job at most 2 attempts.",
     "def make_billing_client():\n    pass",
     "def make_billing_client():\n    return halyard.Client('billing', max_attempts=2)",
     "c = make_billing_client()\nassert c.namespace == 'billing' and c.max_attempts == 2",
     "c = make_billing_client()\nc.enqueue('q', 1)\nc.nack(c.lease('q')[0])\nc.nack(c.lease('q')[0])\nassert c.stats('q')['dead'] == 1\nassert make_billing_client() is not c")

task("final_state_after_failures", "Using a client that allows only two attempts per job: add one job, and take it and give it back as failed (available again immediately) until nothing more can be taken. Return the final state of that job as text.",
     "def final_state_after_failures(payload):\n    pass",
     "def final_state_after_failures(payload):\n    c = halyard.Client(max_attempts=2)\n    job = c.enqueue('q', payload)\n    while True:\n        jobs = c.lease('q')\n        if not jobs:\n            break\n        c.nack(jobs[0])\n    return job.state",
     "assert final_state_after_failures('x') == 'dead'",
     "assert final_state_after_failures(None) == 'dead'\nassert isinstance(final_state_after_failures(1), str)")

task("rejected_payloads", "On a client where each queue may hold at most 2 waiting jobs, try to add every payload to the queue one by one. Return the list of payloads the queue refused, in order.",
     "def rejected_payloads(client, queue, payloads):\n    pass",
     "def rejected_payloads(client, queue, payloads):\n    client.max_ready = 2\n    rejected = []\n    for p in payloads:\n        try:\n            client.enqueue(queue, p)\n        except halyard.QuotaExceeded:\n            rejected.append(p)\n    return rejected",
     "c = halyard.Client()\nassert rejected_payloads(c, 'q', ['a', 'b', 'c', 'd']) == ['c', 'd']",
     "c = halyard.Client()\nassert rejected_payloads(c, 'q', ['a']) == []\nassert c.stats('q')['ready'] == 1\nc2 = halyard.Client()\nassert rejected_payloads(c2, 'q', list(range(5))) == [2, 3, 4]\nassert c2.stats('q')['ready'] == 2")

task("top_three", "Look at the payloads of the three jobs that would be taken next (without taking them), in the order they would be taken, and return them as a list.",
     "def top_three(client, queue):\n    pass",
     "def top_three(client, queue):\n    return [j.payload for j in client.peek(queue, limit=3)]",
     "c = halyard.Client()\nfor p in 'abcd': c.enqueue('q', p)\nassert top_three(c, 'q') == ['a', 'b', 'c']",
     "c = halyard.Client()\nc.enqueue('q', 'n1'); c.enqueue('q', 'u', priority=halyard.Priority.URGENT); c.enqueue('q', 'n2'); c.enqueue('q', 'l', priority=halyard.Priority.LOW)\nassert top_three(c, 'q') == ['u', 'n1', 'n2']\nassert c.stats('q')['leased'] == 0\nc2 = halyard.Client()\nc2.enqueue('q', 1)\nassert top_three(c2, 'q') == [1]")

task("job_total", "Return the total number of jobs the queue has seen, counting jobs in every state (waiting, held, finished and permanently failed).",
     "def job_total(client, queue):\n    pass",
     "def job_total(client, queue):\n    return sum(client.stats(queue).values())",
     "c = halyard.Client()\nfor i in range(4): c.enqueue('q', i)\nassert job_total(c, 'q') == 4",
     "c = halyard.Client(max_attempts=1)\nfor i in range(5): c.enqueue('q', i)\nc.ack(c.lease('q')[0])\nc.nack(c.lease('q')[0])\nc.lease('q')\nassert job_total(c, 'q') == 5\nassert job_total(halyard.Client(), 'z') if False else True")

task("doubled_results", "Keep taking one job at a time, marking each finished with twice its (numeric) payload stored as its result, until nothing is available. Return the stored results in the order the jobs were processed.",
     "def doubled_results(client, queue):\n    pass",
     "def doubled_results(client, queue):\n    out = []\n    while True:\n        jobs = client.lease(queue)\n        if not jobs:\n            return out\n        job = jobs[0]\n        client.ack(job, result=job.payload * 2)\n        out.append(job.result)",
     "c = halyard.Client()\nfor i in (1, 2, 3): c.enqueue('q', i)\nassert doubled_results(c, 'q') == [2, 4, 6]",
     "c = halyard.Client()\nc.enqueue('q', 5); c.enqueue('q', 50, priority=halyard.Priority.URGENT); c.enqueue('q', 1)\nassert doubled_results(c, 'q') == [100, 10, 2]\nassert c.stats('q')['done'] == 3\nassert doubled_results(c, 'q') == []")

task("failure_reason", "Using a client that allows only a single attempt per job: add one job, take it, and give it back as failed with the reason 'bad input'. Return the reason that is now recorded on that job.",
     "def failure_reason(payload):\n    pass",
     "def failure_reason(payload):\n    c = halyard.Client(max_attempts=1)\n    job = c.enqueue('q', payload)\n    c.nack(c.lease('q')[0], reason='bad input')\n    return job.result",
     "assert failure_reason(1) == 'bad input'",
     "assert failure_reason('x') == 'bad input'\nassert failure_reason(None) == 'bad input'")

task("same_key_two_queues", "Add one job with the de-duplication key 'k' to queue 'a' and another job with the same key 'k' to queue 'b'. Return the total number of waiting jobs across both queues afterwards.",
     "def same_key_two_queues(client):\n    pass",
     "def same_key_two_queues(client):\n    client.enqueue('a', 1, dedupe_key='k')\n    client.enqueue('b', 2, dedupe_key='k')\n    return client.stats('a')['ready'] + client.stats('b')['ready']",
     "c = halyard.Client()\nassert same_key_two_queues(c) == 2",
     "c = halyard.Client()\nassert same_key_two_queues(c) == 2\nassert c.queues() == ['a', 'b']\nc.enqueue('a', 3, dedupe_key='k')\nassert c.stats('a')['ready'] == 1")

task("double_extension", "Take one job with a hold time of 10 seconds, then extend its hold by 10 seconds twice. Let 25 seconds pass and return the job's state as text.",
     "def double_extension(client, queue):\n    pass",
     "def double_extension(client, queue):\n    job = client.lease(queue, visibility_timeout=10)[0]\n    job.extend_lease(10)\n    job.extend_lease(10)\n    client.advance_clock(25)\n    return job.state",
     "c = halyard.Client()\nc.enqueue('q', 1)\nassert double_extension(c, 'q') == 'leased'",
     "c = halyard.Client()\nc.enqueue('q', 1); c.enqueue('q', 2)\nassert double_extension(c, 'q') == 'leased'\nassert c.stats('q')['ready'] == 1\nc.advance_clock(10)\nassert c.stats('q')['leased'] == 0")

task("drain_by_level", "Add the given (payload, level) pairs to the queue, where level is the NAME of an importance level as text ('LOW', 'NORMAL' or 'URGENT'). Then take every job one at a time and return the payloads in the order they were taken.",
     "def drain_by_level(client, queue, items):\n    pass",
     "def drain_by_level(client, queue, items):\n    for payload, level in items:\n        client.enqueue(queue, payload, priority=halyard.Priority[level])\n    out = []\n    while True:\n        jobs = client.lease(queue)\n        if not jobs:\n            return out\n        out.append(jobs[0].payload)",
     "c = halyard.Client()\nassert drain_by_level(c, 'q', [('a', 'LOW'), ('b', 'URGENT'), ('c', 'NORMAL')]) == ['b', 'c', 'a']",
     "c = halyard.Client()\nassert drain_by_level(c, 'q', [('a', 'NORMAL'), ('b', 'NORMAL'), ('c', 'URGENT'), ('d', 'URGENT')]) == ['c', 'd', 'a', 'b']\nassert drain_by_level(c, 'q', []) == []")

task("group_sizes", "Cut the items into consecutive groups of at most `size` items and return the list of the group lengths.",
     "def group_sizes(items, size):\n    pass",
     "def group_sizes(items, size):\n    return [len(b) for b in halyard.batched(items, size)]",
     "assert group_sizes(list(range(7)), 3) == [3, 3, 1]",
     "assert group_sizes([], 3) == []\nassert group_sizes('abcd', 2) == [2, 2]\nassert group_sizes(range(5), 10) == [5]")

task("queues_with_work", "Return the sorted names of those queues of the client that currently have at least one waiting job.",
     "def queues_with_work(client):\n    pass",
     "def queues_with_work(client):\n    return [q for q in client.queues() if client.stats(q)['ready'] > 0]",
     "c = halyard.Client()\nc.enqueue('b', 1); c.enqueue('a', 1)\nassert queues_with_work(c) == ['a', 'b']",
     "c = halyard.Client()\nc.enqueue('b', 1); c.enqueue('a', 1); c.enqueue('c', 1)\nc.lease('a')\nassert queues_with_work(c) == ['b', 'c']\nassert queues_with_work(halyard.Client()) == []")

task("peek_or_empty", "Return the payloads of the waiting jobs of the queue without taking them. If the queue has never received a job, return an empty list.",
     "def peek_or_empty(client, queue):\n    pass",
     "def peek_or_empty(client, queue):\n    try:\n        return [j.payload for j in client.peek(queue)]\n    except halyard.UnknownQueue:\n        return []",
     "c = halyard.Client()\nc.enqueue('q', 'a')\nassert peek_or_empty(c, 'q') == ['a']\nassert peek_or_empty(c, 'zz') == []",
     "c = halyard.Client()\nc.enqueue('q', 'a'); c.enqueue('q', 'b')\nassert peek_or_empty(c, 'q') == ['a', 'b']\nassert c.stats('q')['leased'] == 0\nc.lease('q', max_jobs=2)\nassert peek_or_empty(c, 'q') == []")

task("clear_and_report", "Remove all waiting jobs from the queue and return the job counts per state of that queue afterwards.",
     "def clear_and_report(client, queue):\n    pass",
     "def clear_and_report(client, queue):\n    client.purge(queue)\n    return client.stats(queue)",
     "c = halyard.Client()\nc.enqueue('q', 1); c.enqueue('q', 2)\nassert clear_and_report(c, 'q') == {'ready': 0, 'leased': 0, 'done': 0, 'dead': 0}",
     "c = halyard.Client()\nc.enqueue('q', 1); c.enqueue('q', 2); c.enqueue('q', 3)\nc.ack(c.lease('q')[0])\nc.lease('q')\nassert clear_and_report(c, 'q') == {'ready': 0, 'leased': 1, 'done': 1, 'dead': 0}")

task("attempts_after_two_failures", "Add one job to the queue, then take it and give it back as failed (available again immediately) two times in a row, and return how many attempts the job has recorded.",
     "def attempts_after_two_failures(client, queue):\n    pass",
     "def attempts_after_two_failures(client, queue):\n    job = client.enqueue(queue, 'p')\n    for _ in range(2):\n        client.nack(client.lease(queue)[0])\n    return job.attempts",
     "c = halyard.Client()\nassert attempts_after_two_failures(c, 'q') == 2",
     "c = halyard.Client(max_attempts=5)\nassert attempts_after_two_failures(c, 'q') == 2\nassert c.stats('q')['ready'] == 1\nassert attempts_after_two_failures(c, 'r') == 2")

task("skip_ahead", "Move the client's clock forward by a time given as human-readable text such as '1h' or '2m30s', and return the clock's reading afterwards.",
     "def skip_ahead(client, text):\n    pass",
     "def skip_ahead(client, text):\n    client.advance_clock(halyard.parse_duration(text))\n    return client.now",
     "c = halyard.Client()\nassert skip_ahead(c, '1h') == 3600.0",
     "c = halyard.Client()\nassert skip_ahead(c, '2m30s') == 150.0\nassert skip_ahead(c, '30') == 180.0\nassert c.now == 180.0")

# Same typing convention as tasks.py (fixed before any model was run).
for _t in T:
    for _k in ("starter", "ref"):
        _t[_k] = "import halyard\n\n" + _t[_k].replace("(client,", "(client: halyard.Client,").replace("(client)", "(client: halyard.Client)")
