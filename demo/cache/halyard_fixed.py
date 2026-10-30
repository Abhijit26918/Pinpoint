import halyard


def drain(client: halyard.Client, queue):
    n = 0
    while True:
        jobs = client.lease(queue, max_jobs=1)
        if not jobs:
            return n
        job = jobs[0]
        client.ack(job)
        n += 1


def enqueue_urgent(client: halyard.Client, queue, payload):
    return client.enqueue(queue, payload, priority=9)
