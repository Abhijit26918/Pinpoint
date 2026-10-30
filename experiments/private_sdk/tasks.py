"""24 tasks against the invented `halyard` SDK. Fixed before any model was run. Each task:
id, stem (function name), desc (plain words, no API names), starter, ref (reference solution),
visible (one test), hidden (more tests). Tests run after the solution code in the same namespace."""

T = []


def task(stem, desc, starter, ref, visible, hidden):
    T.append(dict(id=len(T), stem=stem, desc=desc, starter=starter, ref=ref, visible=visible, hidden=hidden))


PRE = "import halyard\n"

task("drain", "Process every ready job on the queue one at a time, marking each as finished. Return how many jobs were processed.",
     "def drain(client, queue):\n    pass",
     "def drain(client, queue):\n    n = 0\n    while True:\n        jobs = client.lease(queue)\n        if not jobs:\n            return n\n        client.ack(jobs[0])\n        n += 1",
     "c = halyard.Client()\nfor i in range(3): c.enqueue('q', i)\nassert drain(c, 'q') == 3",
     "c = halyard.Client()\nc.enqueue('q', 1)\nassert drain(c, 'q') == 1 and c.stats('q')['done'] == 1\nc.enqueue('q', 2); c.enqueue('q', 3)\nassert drain(c, 'q') == 2")

task("enqueue_many", "Put each payload from the list onto the queue as its own job and return the list of the new jobs' ids in order.",
     "def enqueue_many(client, queue, payloads):\n    pass",
     "def enqueue_many(client, queue, payloads):\n    return [client.enqueue(queue, p).id for p in payloads]",
     "c = halyard.Client()\nids = enqueue_many(c, 'q', ['a', 'b'])\nassert len(ids) == 2 and ids[0] != ids[1]",
     "c = halyard.Client()\nids = enqueue_many(c, 'q', list(range(5)))\nassert ids == sorted(ids) and len(set(ids)) == 5\nassert c.stats('q')['ready'] == 5\nassert enqueue_many(c, 'q', []) == []")

task("urgent_first", "Add the given routine payloads to the queue, then add one payload marked as the most urgent. Then take one job from the queue for processing and return its payload.",
     "def urgent_first(client, queue, routine_payloads, urgent_payload):\n    pass",
     "def urgent_first(client, queue, routine_payloads, urgent_payload):\n    for p in routine_payloads:\n        client.enqueue(queue, p)\n    client.enqueue(queue, urgent_payload, priority=halyard.Priority.URGENT)\n    return client.lease(queue)[0].payload",
     "c = halyard.Client()\nassert urgent_first(c, 'q', ['a', 'b'], 'U') == 'U'",
     "c = halyard.Client()\nassert urgent_first(c, 'q', list('xyz'), 'boss') == 'boss'\nassert c.stats('q')['leased'] == 1 and c.stats('q')['ready'] == 3")

task("enqueue_once", "Add a job to the queue under a de-duplication key so that submitting the same key twice does not create a second job. Return the job id.",
     "def enqueue_once(client, queue, key, payload):\n    pass",
     "def enqueue_once(client, queue, key, payload):\n    return client.enqueue(queue, payload, dedupe_key=key).id",
     "c = halyard.Client()\na = enqueue_once(c, 'q', 'k1', 'x')\nb = enqueue_once(c, 'q', 'k1', 'y')\nassert isinstance(a, int) and a == b",
     "c = halyard.Client()\na = enqueue_once(c, 'q', 'k1', 'x')\nb = enqueue_once(c, 'q', 'k2', 'x')\nassert a != b\nassert c.stats('q')['ready'] == 2\nenqueue_once(c, 'q', 'k1', 'z')\nassert c.stats('q')['ready'] == 2")

task("delayed_visibility", "Add a job that should only become available after `delay` seconds have passed. Return a pair: how many jobs can be looked at right away, and how many can be looked at after the clock has moved forward by `delay` seconds. (Looking at jobs must not take them.)",
     "def delayed_visibility(client, queue, payload, delay):\n    pass",
     "def delayed_visibility(client, queue, payload, delay):\n    client.enqueue(queue, payload, delay=delay)\n    before = len(client.peek(queue))\n    client.advance_clock(delay)\n    return before, len(client.peek(queue))",
     "c = halyard.Client()\nassert delayed_visibility(c, 'q', 'p', 10) == (0, 1)",
     "c = halyard.Client()\nassert delayed_visibility(c, 'q', 'p', 60) == (0, 1)\nassert c.stats('q')['leased'] == 0\nc2 = halyard.Client()\nc2.enqueue('q', 'now')\nassert delayed_visibility(c2, 'q', 'later', 5) == (1, 2)")

task("take_batch", "Take up to n jobs from the queue in one go for processing and return their payloads in the order received.",
     "def take_batch(client, queue, n):\n    pass",
     "def take_batch(client, queue, n):\n    return [j.payload for j in client.lease(queue, max_jobs=n)]",
     "c = halyard.Client()\nfor i in range(5): c.enqueue('q', i)\nassert take_batch(c, 'q', 3) == [0, 1, 2]",
     "c = halyard.Client()\nfor i in range(2): c.enqueue('q', i)\nassert take_batch(c, 'q', 5) == [0, 1]\nassert take_batch(c, 'q', 5) == []\nassert c.stats('q')['leased'] == 2")

task("process_with_retry", "Take one job from the queue and run `handler` on its payload. If the handler succeeds, mark the job finished and store the handler's return value as its result. If it raises an exception, give the job back so that it becomes available again only after 5 seconds. Return True if the job succeeded, False if it failed, and None if there was no job.",
     "def process_with_retry(client, queue, handler):\n    pass",
     "def process_with_retry(client, queue, handler):\n    jobs = client.lease(queue)\n    if not jobs:\n        return None\n    job = jobs[0]\n    try:\n        result = handler(job.payload)\n    except Exception as e:\n        client.nack(job, requeue_after=5, reason=str(e))\n        return False\n    client.ack(job, result=result)\n    return True",
     "c = halyard.Client()\nc.enqueue('q', 2)\nassert process_with_retry(c, 'q', lambda p: p * 2) is True\nassert c.stats('q')['done'] == 1",
     "c = halyard.Client()\nc.enqueue('q', 1)\ndef boom(p): raise ValueError('x')\nassert process_with_retry(c, 'q', boom) is False\nassert c.peek('q') == []\nc.advance_clock(5)\nassert len(c.peek('q')) == 1\nassert process_with_retry(c, 'q', lambda p: 1) is True\nassert process_with_retry(c, 'q', lambda p: 1) is None")

task("dead_letter_count", "Keep taking jobs from the queue and giving every one of them back as failed (with the reason 'boom', available again immediately) until nothing is available any more. Return how many jobs ended up permanently failed.",
     "def dead_letter_count(client, queue):\n    pass",
     "def dead_letter_count(client, queue):\n    while True:\n        jobs = client.lease(queue)\n        if not jobs:\n            break\n        client.nack(jobs[0], reason='boom')\n    return client.stats(queue)['dead']",
     "c = halyard.Client()\nc.enqueue('q', 1); c.enqueue('q', 2)\nassert dead_letter_count(c, 'q') == 2",
     "c = halyard.Client(max_attempts=5)\nc.enqueue('q', 1)\nassert dead_letter_count(c, 'q') == 1\nassert c.peek('q') == []\nc2 = halyard.Client()\nc2.enqueue('q', 1)\ndead_letter_count(c2, 'q')\nassert c2.stats('q')['ready'] == 0")

task("lease_recovery", "Take one job from the queue with a hold time of 10 seconds, then let 11 seconds pass without finishing it. Return the number of jobs that are available again.",
     "def lease_recovery(client, queue):\n    pass",
     "def lease_recovery(client, queue):\n    client.lease(queue, visibility_timeout=10)\n    client.advance_clock(11)\n    return client.stats(queue)['ready']",
     "c = halyard.Client()\nc.enqueue('q', 1)\nassert lease_recovery(c, 'q') == 1",
     "c = halyard.Client()\nc.enqueue('q', 1); c.enqueue('q', 2)\nassert lease_recovery(c, 'q') == 2\nassert c.stats('q')['leased'] == 0")

task("extend_hold", "Take one job from the queue with a hold time of 10 seconds, then extend that hold by 20 seconds, then let 15 seconds pass. Return the number of jobs still being held.",
     "def extend_hold(client, queue):\n    pass",
     "def extend_hold(client, queue):\n    job = client.lease(queue, visibility_timeout=10)[0]\n    job.extend_lease(20)\n    client.advance_clock(15)\n    return client.stats(queue)['leased']",
     "c = halyard.Client()\nc.enqueue('q', 1)\nassert extend_hold(c, 'q') == 1",
     "c = halyard.Client()\nc.enqueue('q', 1)\nextend_hold(c, 'q')\nc.advance_clock(20)\nassert c.stats('q') == {'ready': 1, 'leased': 0, 'done': 0, 'dead': 0}")

task("clear_queue", "Delete all jobs that are waiting in the queue. Also delete the permanently failed ones if `failed_too` is true. Return how many jobs were deleted.",
     "def clear_queue(client, queue, failed_too=False):\n    pass",
     "def clear_queue(client, queue, failed_too=False):\n    return client.purge(queue, include_dead=failed_too)",
     "c = halyard.Client()\nfor i in range(4): c.enqueue('q', i)\nassert clear_queue(c, 'q') == 4",
     "c = halyard.Client(max_attempts=1)\nc.enqueue('q', 1); c.enqueue('q', 2)\nj = c.lease('q')[0]; c.nack(j)\nassert clear_queue(c, 'q') == 1\nassert c.stats('q')['dead'] == 1\nassert clear_queue(c, 'q', True) == 1")

task("all_queue_names", "Return the names of all queues that have received jobs so far, in alphabetical order.",
     "def all_queue_names(client):\n    pass",
     "def all_queue_names(client):\n    return client.queues()",
     "c = halyard.Client()\nc.enqueue('b', 1); c.enqueue('a', 1)\nassert all_queue_names(c) == ['a', 'b']",
     "c = halyard.Client()\nassert all_queue_names(c) == []\nc.enqueue('z', 1); c.enqueue('m', 1); c.enqueue('z', 2)\nassert all_queue_names(c) == ['m', 'z']")

task("preview", "Look at the payloads of the next k jobs that would be taken from the queue, in that order, without taking them.",
     "def preview(client, queue, k):\n    pass",
     "def preview(client, queue, k):\n    return [j.payload for j in client.peek(queue, limit=k)]",
     "c = halyard.Client()\nfor i in range(4): c.enqueue('q', i)\nassert preview(c, 'q', 2) == [0, 1]",
     "c = halyard.Client()\nfor i in range(3): c.enqueue('q', i)\nassert preview(c, 'q', 10) == [0, 1, 2]\nassert c.stats('q')['ready'] == 3\nc.enqueue('q', 'hot', priority=halyard.Priority.URGENT)\nassert preview(c, 'q', 1) == ['hot']")

task("fill_until_full", "Add the payloads to the queue one by one until the queue refuses because it is full. Return how many were accepted.",
     "def fill_until_full(client, queue, payloads):\n    pass",
     "def fill_until_full(client, queue, payloads):\n    n = 0\n    for p in payloads:\n        try:\n            client.enqueue(queue, p)\n        except halyard.QuotaExceeded:\n            break\n        n += 1\n    return n",
     "c = halyard.Client()\nc.max_ready = 3\nassert fill_until_full(c, 'q', list(range(10))) == 3",
     "c = halyard.Client()\nc.max_ready = 2\nassert fill_until_full(c, 'q', [1]) == 1\nassert fill_until_full(c, 'q', [1, 2, 3]) == 1\nassert c.stats('q')['ready'] == 2")

task("safe_stats", "Return the job counts per state for the queue, or an empty dict if nothing was ever added to that queue.",
     "def safe_stats(client, queue):\n    pass",
     "def safe_stats(client, queue):\n    try:\n        return client.stats(queue)\n    except halyard.UnknownQueue:\n        return {}",
     "c = halyard.Client()\nassert safe_stats(c, 'nope') == {}",
     "c = halyard.Client()\nc.enqueue('q', 1)\nassert safe_stats(c, 'q') == {'ready': 1, 'leased': 0, 'done': 0, 'dead': 0}\nassert safe_stats(c, 'other') == {}")

task("to_seconds", "Convert a human-readable duration such as '2h5m' or '90s' into a number of seconds.",
     "def to_seconds(text):\n    pass",
     "def to_seconds(text):\n    return halyard.parse_duration(text)",
     "assert to_seconds('2h5m') == 7500",
     "assert to_seconds('90s') == 90\nassert to_seconds('1d') == 86400\nassert to_seconds('45') == 45")

task("count_batches", "Add the payloads to the queue grouped into chunks of at most `size` payloads, and return how many chunks there were.",
     "def count_batches(client, queue, payloads, size):\n    pass",
     "def count_batches(client, queue, payloads, size):\n    n = 0\n    for chunk in halyard.batched(payloads, size):\n        for p in chunk:\n            client.enqueue(queue, p)\n        n += 1\n    return n",
     "c = halyard.Client()\nassert count_batches(c, 'q', list(range(5)), 2) == 3",
     "c = halyard.Client()\nassert count_batches(c, 'q', list(range(4)), 2) == 2\nassert c.stats('q')['ready'] == 4\nassert count_batches(c, 'q', [], 3) == 0")

task("map_queue", "Process every available job on the queue by applying `fn` to its payload, marking the job finished with fn's result stored on it. Return the list of results in processing order.",
     "def map_queue(client, queue, fn):\n    pass",
     "def map_queue(client, queue, fn):\n    out = []\n    while True:\n        jobs = client.lease(queue)\n        if not jobs:\n            return out\n        r = fn(jobs[0].payload)\n        client.ack(jobs[0], result=r)\n        out.append(r)",
     "c = halyard.Client()\nfor i in range(3): c.enqueue('q', i)\nassert map_queue(c, 'q', lambda p: p * 2) == [0, 2, 4]",
     "c = halyard.Client()\nc.enqueue('q', 3)\nassert map_queue(c, 'q', str) == ['3']\nassert c.stats('q')['done'] == 1\nassert map_queue(c, 'q', str) == []")

task("priority_order", "Add three jobs to the queue with payloads 'l' (lowest priority), 'n' (normal priority) and 'u' (most urgent), in that order. Then take all three at once and return their payloads in the order they were handed out.",
     "def priority_order(client, queue):\n    pass",
     "def priority_order(client, queue):\n    client.enqueue(queue, 'l', priority=halyard.Priority.LOW)\n    client.enqueue(queue, 'n')\n    client.enqueue(queue, 'u', priority=halyard.Priority.URGENT)\n    return [j.payload for j in client.lease(queue, max_jobs=3)]",
     "c = halyard.Client()\nassert priority_order(c, 'q') == ['u', 'n', 'l']",
     "c = halyard.Client()\nassert priority_order(c, 'a') == ['u', 'n', 'l']\nassert priority_order(c, 'b') == ['u', 'n', 'l']\nassert c.stats('a')['leased'] == 3")

task("attempts_after_retry", "Add one job to the queue. Take it, give it back as failed so it is available again immediately, take it again, and return the number of attempts recorded on the job.",
     "def attempts_after_retry(client, queue):\n    pass",
     "def attempts_after_retry(client, queue):\n    client.enqueue(queue, 'x')\n    job = client.lease(queue)[0]\n    client.nack(job)\n    job = client.lease(queue)[0]\n    return job.attempts",
     "c = halyard.Client()\nassert attempts_after_retry(c, 'q') == 2",
     "c = halyard.Client()\nassert attempts_after_retry(c, 'q') == 2\nassert c.stats('q')['leased'] == 1\nassert attempts_after_retry(c, 'r') == 2")

task("one_shot_client", "Create a new client that belongs to the namespace `name` and allows each job only a single attempt before it counts as permanently failed. Enqueue one job on queue 'q', take it, give it back as failed, and return a pair: the client's namespace and the number of permanently failed jobs.",
     "def one_shot_client(name):\n    pass",
     "def one_shot_client(name):\n    c = halyard.Client(name, max_attempts=1)\n    c.enqueue('q', 1)\n    c.nack(c.lease('q')[0])\n    return c.namespace, c.stats('q')['dead']",
     "assert one_shot_client('billing') == ('billing', 1)",
     "assert one_shot_client('x') == ('x', 1)\nassert one_shot_client('') == ('', 1)")

task("requeue_with_delay", "Add one job, take it, and give it back as failed so that it only becomes available again after 60 seconds. Return a pair: how many jobs can be looked at right after giving it back, and how many after the clock has moved forward 60 seconds.",
     "def requeue_with_delay(client, queue):\n    pass",
     "def requeue_with_delay(client, queue):\n    client.enqueue(queue, 'x')\n    client.nack(client.lease(queue)[0], requeue_after=60)\n    a = len(client.peek(queue))\n    client.advance_clock(60)\n    return a, len(client.peek(queue))",
     "c = halyard.Client()\nassert requeue_with_delay(c, 'q') == (0, 1)",
     "c = halyard.Client()\nassert requeue_with_delay(c, 'q') == (0, 1)\nc2 = halyard.Client()\nc2.enqueue('q', 'other')\nassert requeue_with_delay(c2, 'q') == (1, 2)")

task("resubmit_after_done", "Add a job under de-duplication key 'k', take it and mark it finished, then add another job with the same key. Return True if the second submission produced a different job than the first.",
     "def resubmit_after_done(client, queue):\n    pass",
     "def resubmit_after_done(client, queue):\n    a = client.enqueue(queue, 1, dedupe_key='k')\n    client.ack(client.lease(queue)[0])\n    b = client.enqueue(queue, 2, dedupe_key='k')\n    return a.id != b.id",
     "c = halyard.Client()\nassert resubmit_after_done(c, 'q') is True",
     "c = halyard.Client()\nassert resubmit_after_done(c, 'q') is True\nassert c.stats('q')['ready'] == 1 and c.stats('q')['done'] == 1")

task("lease_if_any", "Take one job from the queue if one is available and return its payload, otherwise return None.",
     "def lease_if_any(client, queue):\n    pass",
     "def lease_if_any(client, queue):\n    jobs = client.lease(queue)\n    return jobs[0].payload if jobs else None",
     "c = halyard.Client()\nc.enqueue('q', 'p')\nassert lease_if_any(c, 'q') == 'p'",
     "c = halyard.Client()\nc.enqueue('q', 'p')\nlease_if_any(c, 'q')\nassert lease_if_any(c, 'q') is None\nassert c.stats('q')['leased'] == 1")


# Starters and references are typed like real library code; the type annotation is what lets a static
# resolver know that `client` is a halyard.Client (applied before any model was run).
for _t in T:
    for _k in ("starter", "ref"):
        _t[_k] = "import halyard\n\n" + _t[_k].replace("(client,", "(client: halyard.Client,").replace("(client)", "(client: halyard.Client)")
